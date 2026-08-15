"""SQLite snapshot storage for trending reports."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from period import format_period_label, parse_count, period_key


DB_PATH = Path(__file__).parent / "trending_history.db"


def configure(db_path: Path | str) -> None:
    """Override the default database path (used by tests and env config)."""
    global DB_PATH
    DB_PATH = Path(db_path)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create snapshot tables if they do not exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                time_range TEXT NOT NULL,
                period_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                UNIQUE(time_range, period_key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshot_repos (
                id INTEGER PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                language TEXT,
                total_stars INTEGER,
                forks INTEGER,
                stars_period INTEGER,
                stars_period_label TEXT,
                url TEXT,
                is_new INTEGER DEFAULT 0,
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_range_period "
            "ON snapshots(time_range, period_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_snapshot "
            "ON snapshot_repos(snapshot_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_name_lookup "
            "ON snapshot_repos(name)"
        )
        for leftover in (
            "repos",
            "developers",
            "repos_daily",
            "repos_weekly",
            "repos_monthly",
            "developers_daily",
            "developers_weekly",
            "developers_monthly",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {leftover}")


def _is_new(conn: sqlite3.Connection, time_range: str, name: str, current_key: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM snapshot_repos r
        JOIN snapshots s ON s.id = r.snapshot_id
        WHERE s.time_range = ? AND r.name = ? AND s.period_key < ?
        LIMIT 1
        """,
        (time_range, name, current_key),
    ).fetchone()
    return row is None


def save_snapshot(
    time_range: str,
    repos: list[dict],
    when: datetime | None = None,
) -> dict:
    """Upsert a period snapshot and return the stored report.

    Empty repo lists are refused so a failed scrape cannot wipe a good snapshot.
    """
    if not repos:
        raise ValueError("refusing to save an empty snapshot")

    when = when or datetime.now()
    key = period_key(time_range, when)
    fetched_at = when.isoformat(timespec="seconds")

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM snapshots WHERE time_range = ? AND period_key = ?",
            (time_range, key),
        ).fetchone()

        if existing:
            snapshot_id = existing["id"]
            conn.execute("DELETE FROM snapshot_repos WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute(
                "UPDATE snapshots SET fetched_at = ? WHERE id = ?",
                (fetched_at, snapshot_id),
            )
        else:
            cursor = conn.execute(
                "INSERT INTO snapshots (time_range, period_key, fetched_at) VALUES (?, ?, ?)",
                (time_range, key, fetched_at),
            )
            snapshot_id = cursor.lastrowid

        stored = []
        for rank, repo in enumerate(repos, start=1):
            is_new = _is_new(conn, time_range, repo["name"], key)
            item = {
                "rank": rank,
                "name": repo["name"],
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "total_stars": parse_count(str(repo.get("total_stars") or "")),
                "forks": parse_count(str(repo.get("forks") or "")),
                "stars_period": parse_count(str(repo.get("stars_today") or "")),
                "stars_period_label": repo.get("stars_today") or "",
                "url": repo.get("url") or "",
                "is_new": is_new,
            }
            conn.execute(
                """
                INSERT INTO snapshot_repos (
                    snapshot_id, rank, name, description, language,
                    total_stars, forks, stars_period, stars_period_label, url, is_new
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    item["rank"],
                    item["name"],
                    item["description"],
                    item["language"],
                    item["total_stars"],
                    item["forks"],
                    item["stars_period"],
                    item["stars_period_label"],
                    item["url"],
                    1 if item["is_new"] else 0,
                ),
            )
            stored.append(item)

    return {
        "id": snapshot_id,
        "time_range": time_range,
        "period_key": key,
        "label": format_period_label(time_range, key),
        "fetched_at": fetched_at,
        "repos": stored,
        "new_count": sum(1 for item in stored if item["is_new"]),
    }


def list_periods(time_range: str) -> list[dict]:
    """List stored periods for a time range, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                s.period_key,
                s.fetched_at,
                COUNT(r.id) AS repo_count,
                COALESCE(SUM(r.is_new), 0) AS new_count
            FROM snapshots s
            LEFT JOIN snapshot_repos r ON r.snapshot_id = s.id
            WHERE s.time_range = ?
            GROUP BY s.id
            ORDER BY s.period_key DESC
            """,
            (time_range,),
        ).fetchall()

    return [
        {
            "period_key": row["period_key"],
            "label": format_period_label(time_range, row["period_key"]),
            "fetched_at": row["fetched_at"],
            "repo_count": row["repo_count"],
            "new_count": row["new_count"],
        }
        for row in rows
    ]


def get_report(time_range: str, period: str | None = None) -> dict | None:
    """Load one snapshot. Defaults to the newest period for the range."""
    with get_conn() as conn:
        if period:
            snapshot = conn.execute(
                "SELECT * FROM snapshots WHERE time_range = ? AND period_key = ?",
                (time_range, period),
            ).fetchone()
        else:
            snapshot = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE time_range = ?
                ORDER BY period_key DESC
                LIMIT 1
                """,
                (time_range,),
            ).fetchone()

        if not snapshot:
            return None

        rows = conn.execute(
            """
            SELECT * FROM snapshot_repos
            WHERE snapshot_id = ?
            ORDER BY rank
            """,
            (snapshot["id"],),
        ).fetchall()

    repos = [
        {
            "rank": row["rank"],
            "name": row["name"],
            "description": row["description"] or "",
            "language": row["language"] or "",
            "total_stars": row["total_stars"],
            "forks": row["forks"],
            "stars_period": row["stars_period"],
            "stars_period_label": row["stars_period_label"] or "",
            "url": row["url"] or "",
            "is_new": bool(row["is_new"]),
        }
        for row in rows
    ]
    return {
        "id": snapshot["id"],
        "time_range": snapshot["time_range"],
        "period_key": snapshot["period_key"],
        "label": format_period_label(snapshot["time_range"], snapshot["period_key"]),
        "fetched_at": snapshot["fetched_at"],
        "repos": repos,
        "new_count": sum(1 for repo in repos if repo["is_new"]),
    }
