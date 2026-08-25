"""SQLite snapshot storage for trending reports."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from period import TIME_RANGES, format_period_label, parse_count, period_key

REPO_CARD_FIELDS = ("name", "description", "url")


def repo_card(item: dict | None = None, **extra) -> dict:
    """Identity fields an agent needs: name, description, and link."""
    source = item or {}
    payload = {
        "name": source.get("name") or extra.get("name") or "",
        "description": source.get("description") or extra.get("description") or "",
        "url": source.get("url") or extra.get("url") or "",
    }
    for key, value in extra.items():
        if key not in payload:
            payload[key] = value
    return payload


def as_repo_cards(items: list[dict]) -> list[dict]:
    """Keep only name, description, and url."""
    return [repo_card(item) for item in items]


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
                source TEXT NOT NULL DEFAULT 'scrape',
                UNIQUE(time_range, period_key)
            )
        """)
        _ensure_schema(conn)
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


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the first schema version."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)")}
    if "source" not in columns:
        conn.execute(
            "ALTER TABLE snapshots ADD COLUMN source TEXT NOT NULL DEFAULT 'scrape'"
        )


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
                "UPDATE snapshots SET fetched_at = ?, source = 'scrape' WHERE id = ?",
                (fetched_at, snapshot_id),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO snapshots (time_range, period_key, fetched_at, source)
                VALUES (?, ?, ?, 'scrape')
                """,
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
                COALESCE(s.source, 'scrape') AS source,
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
            "source": row["source"],
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
        repo_card(
            {
                "name": row["name"],
                "description": row["description"] or "",
                "url": row["url"] or "",
            },
            rank=row["rank"],
            language=row["language"] or "",
            total_stars=row["total_stars"],
            forks=row["forks"],
            stars_period=row["stars_period"],
            stars_period_label=row["stars_period_label"] or "",
            is_new=bool(row["is_new"]),
        )
        for row in rows
    ]
    return {
        "id": snapshot["id"],
        "time_range": snapshot["time_range"],
        "period_key": snapshot["period_key"],
        "label": format_period_label(snapshot["time_range"], snapshot["period_key"]),
        "fetched_at": snapshot["fetched_at"],
        "source": snapshot["source"] if "source" in snapshot.keys() else "scrape",
        "repos": repos,
        "new_count": sum(1 for repo in repos if repo["is_new"]),
    }


def recompute_is_new() -> dict[str, int]:
    """Mark NEW only on a repo's first appearance in that daily/weekly/monthly board."""
    updated = 0
    with get_conn() as conn:
        ranges = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT time_range FROM snapshots ORDER BY time_range"
            )
        ]
        for time_range in ranges:
            snapshots = conn.execute(
                """
                SELECT id, period_key
                FROM snapshots
                WHERE time_range = ?
                ORDER BY period_key
                """,
                (time_range,),
            ).fetchall()
            seen: set[str] = set()
            for snapshot in snapshots:
                rows = conn.execute(
                    """
                    SELECT id, name
                    FROM snapshot_repos
                    WHERE snapshot_id = ?
                    ORDER BY rank
                    """,
                    (snapshot["id"],),
                ).fetchall()
                for row in rows:
                    is_new = 0 if row["name"] in seen else 1
                    conn.execute(
                        "UPDATE snapshot_repos SET is_new = ? WHERE id = ?",
                        (is_new, row["id"]),
                    )
                    seen.add(row["name"])
                    updated += 1
    return {"repos": updated}


def set_snapshot_source(time_range: str, period_key: str, source: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE snapshots SET source = ? WHERE time_range = ? AND period_key = ?",
            (source, time_range, period_key),
        )


REPO_SORTS = {
    "peak_stars": "peak_stars DESC, appearances DESC, r.name ASC",
    "appearances": "appearances DESC, peak_stars DESC, r.name ASC",
    "first_seen": "first_seen ASC, r.name ASC",
    "last_seen": "last_seen DESC, r.name ASC",
    "name": "r.name ASC",
}


def overview() -> dict:
    """High-level catalog stats for the public API."""
    with get_conn() as conn:
        unique_repos = conn.execute(
            "SELECT COUNT(DISTINCT name) FROM snapshot_repos"
        ).fetchone()[0]
        snapshot_rows = conn.execute(
            "SELECT COUNT(*) FROM snapshot_repos"
        ).fetchone()[0]
        ranges = {}
        for time_range in TIME_RANGES:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS snapshots,
                    MIN(period_key) AS first_period,
                    MAX(period_key) AS last_period
                FROM snapshots
                WHERE time_range = ?
                """,
                (time_range,),
            ).fetchone()
            ranges[time_range] = {
                "snapshots": row["snapshots"],
                "first_period": row["first_period"],
                "last_period": row["last_period"],
            }
        languages = conn.execute(
            """
            SELECT
                language,
                COUNT(DISTINCT name) AS repo_count
            FROM snapshot_repos
            WHERE language IS NOT NULL AND language != ''
            GROUP BY language
            ORDER BY repo_count DESC, language ASC
            """
        ).fetchall()

    return {
        "unique_repos": unique_repos,
        "snapshot_rows": snapshot_rows,
        "ranges": ranges,
        "languages": [
            {"name": row["language"], "repo_count": row["repo_count"]}
            for row in languages
        ],
    }


def list_all_periods(time_range: str | None = None) -> list[dict]:
    """List stored periods, optionally limited to one time range."""
    ranges = (time_range,) if time_range else TIME_RANGES
    items = []
    for current in ranges:
        for item in list_periods(current):
            items.append({**item, "time_range": current})
    return items


def _keyword_filter(keyword: str | None) -> tuple[str, list]:
    """AND-match whitespace tokens against name, description, and language."""
    if not keyword or not keyword.strip():
        return "", []
    clauses = []
    params: list = []
    for token in keyword.split():
        like = f"%{token}%"
        clauses.append(
            "(r.name LIKE ? OR IFNULL(r.description, '') LIKE ? "
            "OR IFNULL(r.language, '') LIKE ?)"
        )
        params.extend([like, like, like])
    return " AND ".join(clauses), params


def list_unique_repos(
    keyword: str | None = None,
    time_range: str | None = None,
    period: str | None = None,
    language: str | None = None,
    min_stars: int | None = None,
    sort: str = "peak_stars",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    """Aggregate distinct repos across snapshots, with optional filters."""
    if sort not in REPO_SORTS:
        raise ValueError(f"unknown sort: {sort}")

    where = ["1=1"]
    params: list = []
    if time_range:
        where.append("s.time_range = ?")
        params.append(time_range)
    if period:
        where.append("s.period_key = ?")
        params.append(period)
    if language:
        where.append("r.language = ?")
        params.append(language)
    keyword_sql, keyword_params = _keyword_filter(keyword)
    if keyword_sql:
        where.append(keyword_sql)
        params.extend(keyword_params)

    having = ""
    having_params: list = []
    if min_stars is not None:
        having = "HAVING MAX(r.total_stars) >= ?"
        having_params.append(min_stars)

    where_sql = " AND ".join(where)
    order_sql = REPO_SORTS[sort]

    with get_conn() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT r.name
                FROM snapshot_repos r
                JOIN snapshots s ON s.id = r.snapshot_id
                WHERE {where_sql}
                GROUP BY r.name
                {having}
            )
            """,
            (*params, *having_params),
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            WITH filtered AS (
                SELECT
                    r.name,
                    r.description,
                    r.language,
                    r.url,
                    r.total_stars,
                    r.forks,
                    r.stars_period,
                    s.time_range,
                    s.period_key,
                    s.fetched_at
                FROM snapshot_repos r
                JOIN snapshots s ON s.id = r.snapshot_id
                WHERE {where_sql}
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (
                        PARTITION BY name
                        ORDER BY period_key DESC, fetched_at DESC
                    ) AS rn
                FROM filtered
            ),
            agg AS (
                SELECT
                    name,
                    MAX(total_stars) AS peak_stars,
                    MAX(forks) AS peak_forks,
                    MAX(stars_period) AS peak_period_gain,
                    COUNT(*) AS appearances,
                    MIN(period_key) AS first_seen,
                    MAX(period_key) AS last_seen,
                    GROUP_CONCAT(DISTINCT time_range) AS time_ranges
                FROM filtered
                GROUP BY name
                {having}
            )
            SELECT
                r.name,
                r.description,
                r.language,
                r.url,
                a.peak_stars,
                a.peak_forks,
                a.peak_period_gain,
                a.appearances,
                a.first_seen,
                a.last_seen,
                a.time_ranges
            FROM ranked r
            JOIN agg a ON a.name = r.name
            WHERE r.rn = 1
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            (*params, *having_params, limit, offset),
        ).fetchall()

    items = []
    for row in rows:
        items.append(repo_card(
            {
                "name": row["name"],
                "description": row["description"] or "",
                "url": row["url"] or "",
            },
            language=row["language"] or "",
            peak_stars=row["peak_stars"],
            peak_forks=row["peak_forks"],
            peak_period_gain=row["peak_period_gain"],
            appearances=row["appearances"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            time_ranges=[
                part for part in (row["time_ranges"] or "").split(",") if part
            ],
        ))
    return {"total": total, "items": items}


def get_repo_history(name: str) -> dict | None:
    """Return one repo's latest summary plus every snapshot appearance."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                r.name,
                r.description,
                r.language,
                r.url,
                r.rank,
                r.total_stars,
                r.forks,
                r.stars_period,
                r.stars_period_label,
                r.is_new,
                s.time_range,
                s.period_key,
                s.fetched_at,
                COALESCE(s.source, 'scrape') AS source
            FROM snapshot_repos r
            JOIN snapshots s ON s.id = r.snapshot_id
            WHERE r.name = ? COLLATE NOCASE
            ORDER BY s.period_key DESC, s.time_range ASC
            """,
            (name,),
        ).fetchall()

    if not rows:
        return None

    appearances = []
    peak_stars = None
    peak_forks = None
    peak_period_gain = None
    ranges: list[str] = []
    for row in rows:
        appearances.append({
            "time_range": row["time_range"],
            "period_key": row["period_key"],
            "label": format_period_label(row["time_range"], row["period_key"]),
            "fetched_at": row["fetched_at"],
            "source": row["source"],
            "rank": row["rank"],
            "total_stars": row["total_stars"],
            "forks": row["forks"],
            "stars_period": row["stars_period"],
            "stars_period_label": row["stars_period_label"] or "",
            "is_new": bool(row["is_new"]),
        })
        if row["total_stars"] is not None:
            peak_stars = row["total_stars"] if peak_stars is None else max(
                peak_stars, row["total_stars"]
            )
        if row["forks"] is not None:
            peak_forks = row["forks"] if peak_forks is None else max(
                peak_forks, row["forks"]
            )
        if row["stars_period"] is not None:
            peak_period_gain = (
                row["stars_period"]
                if peak_period_gain is None
                else max(peak_period_gain, row["stars_period"])
            )
        if row["time_range"] not in ranges:
            ranges.append(row["time_range"])

    latest = rows[0]
    period_keys = [row["period_key"] for row in rows]
    return repo_card(
        {
            "name": latest["name"],
            "description": latest["description"] or "",
            "url": latest["url"] or "",
        },
        language=latest["language"] or "",
        peak_stars=peak_stars,
        peak_forks=peak_forks,
        peak_period_gain=peak_period_gain,
        appearances=len(appearances),
        first_seen=min(period_keys),
        last_seen=max(period_keys),
        time_ranges=ranges,
        history=appearances,
    )
