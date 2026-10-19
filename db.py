"""SQLite snapshot storage for trending reports."""

import difflib
import re
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


OVERALL = ""  # scope of the main board; language boards use GitHub's slug


def init_db() -> None:
    """Create tables and migrate older databases in place."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                time_range TEXT NOT NULL,
                period_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'scrape',
                scope TEXT NOT NULL DEFAULT '',
                UNIQUE(time_range, period_key, scope)
            )
        """)
        _ensure_schema(conn)
    _migrate_snapshot_scope()
    with get_conn() as conn:
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
                best_rank INTEGER,
                seen_count INTEGER NOT NULL DEFAULT 1,
                in_latest INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
            )
        """)
        _ensure_repo_columns(conn)
        # Every scrape, verbatim. Snapshots are derived from these.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY,
                time_range TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT '',
                period_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_run_repos (
                run_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                language TEXT,
                total_stars INTEGER,
                forks INTEGER,
                stars_period INTEGER,
                stars_period_label TEXT,
                FOREIGN KEY(run_id) REFERENCES scrape_runs(id)
            )
        """)
        # Daily star counts from the GitHub API, independent of trending.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repo_stars (
                name TEXT NOT NULL,
                observed_on TEXT NOT NULL,
                stars INTEGER NOT NULL,
                forks INTEGER,
                PRIMARY KEY(name, observed_on)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repo_refresh (
                name TEXT PRIMARY KEY,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        conn.execute("DROP INDEX IF EXISTS idx_snapshots_range_period")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_range_scope_period "
            "ON snapshots(time_range, scope, period_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_snapshot "
            "ON snapshot_repos(snapshot_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_repos_name_lookup "
            "ON snapshot_repos(name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scrape_run_repos_run "
            "ON scrape_run_repos(run_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scrape_runs_board "
            "ON scrape_runs(time_range, scope, period_key)"
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


def _ensure_repo_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshot_repos)")}
    for name, ddl in (
        ("best_rank", "best_rank INTEGER"),
        ("seen_count", "seen_count INTEGER NOT NULL DEFAULT 1"),
        ("in_latest", "in_latest INTEGER NOT NULL DEFAULT 1"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE snapshot_repos ADD COLUMN {ddl}")
    conn.execute("UPDATE snapshot_repos SET best_rank = rank WHERE best_rank IS NULL")


def _migrate_snapshot_scope() -> None:
    """Rebuild snapshots with a scope column; SQLite cannot alter a UNIQUE constraint."""
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)")}
        if "scope" in columns:
            return
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("""
                CREATE TABLE snapshots_new (
                    id INTEGER PRIMARY KEY,
                    time_range TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'scrape',
                    scope TEXT NOT NULL DEFAULT '',
                    UNIQUE(time_range, period_key, scope)
                )
            """)
            conn.execute("""
                INSERT INTO snapshots_new (id, time_range, period_key, fetched_at, source, scope)
                SELECT id, time_range, period_key, fetched_at, source, '' FROM snapshots
            """)
            conn.execute("DROP TABLE snapshots")
            conn.execute("ALTER TABLE snapshots_new RENAME TO snapshots")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def _is_new(
    conn: sqlite3.Connection,
    time_range: str,
    scope: str,
    name: str,
    current_key: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM snapshot_repos r
        JOIN snapshots s ON s.id = r.snapshot_id
        WHERE s.time_range = ? AND s.scope = ? AND r.name = ? AND s.period_key < ?
        LIMIT 1
        """,
        (time_range, scope, name, current_key),
    ).fetchone()
    return row is None


def _scraped_item(repo: dict) -> dict:
    return {
        "name": repo["name"],
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "total_stars": parse_count(str(repo.get("total_stars") or "")),
        "forks": parse_count(str(repo.get("forks") or "")),
        "stars_period": parse_count(str(repo.get("stars_today") or "")),
        "stars_period_label": repo.get("stars_today") or "",
        "url": repo.get("url") or "",
    }


def save_snapshot(
    time_range: str,
    repos: list[dict],
    when: datetime | None = None,
    scope: str = OVERALL,
) -> dict:
    """Log a scrape and merge it into its period's snapshot.

    Repeated scrapes in one week or month accumulate: repos on the latest
    scrape come first in its order, then repos that were on the board
    earlier in the period but have since dropped off (``in_latest`` False).
    Empty repo lists are refused so a failed scrape cannot wipe a good snapshot.
    """
    if not repos:
        raise ValueError("refusing to save an empty snapshot")

    when = when or datetime.now()
    key = period_key(time_range, when)
    fetched_at = when.isoformat(timespec="seconds")
    scraped = [_scraped_item(repo) for repo in repos]

    with get_conn() as conn:
        run_id = conn.execute(
            """
            INSERT INTO scrape_runs (time_range, scope, period_key, fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (time_range, scope, key, fetched_at),
        ).lastrowid
        conn.executemany(
            """
            INSERT INTO scrape_run_repos (
                run_id, rank, name, description, language,
                total_stars, forks, stars_period, stars_period_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id, rank, item["name"], item["description"], item["language"],
                    item["total_stars"], item["forks"], item["stars_period"],
                    item["stars_period_label"],
                )
                for rank, item in enumerate(scraped, start=1)
            ],
        )

        existing = conn.execute(
            """
            SELECT id FROM snapshots
            WHERE time_range = ? AND period_key = ? AND scope = ?
            """,
            (time_range, key, scope),
        ).fetchone()

        previous: dict[str, sqlite3.Row] = {}
        if existing:
            snapshot_id = existing["id"]
            for row in conn.execute(
                "SELECT * FROM snapshot_repos WHERE snapshot_id = ? ORDER BY rank",
                (snapshot_id,),
            ):
                previous.setdefault(row["name"], row)
            conn.execute("DELETE FROM snapshot_repos WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute(
                "UPDATE snapshots SET fetched_at = ?, source = 'scrape' WHERE id = ?",
                (fetched_at, snapshot_id),
            )
        else:
            snapshot_id = conn.execute(
                """
                INSERT INTO snapshots (time_range, period_key, fetched_at, source, scope)
                VALUES (?, ?, ?, 'scrape', ?)
                """,
                (time_range, key, fetched_at, scope),
            ).lastrowid

        merged = []
        latest_names = set()
        for rank, item in enumerate(scraped, start=1):
            if item["name"] in latest_names:
                continue
            latest_names.add(item["name"])
            prev = previous.get(item["name"])
            merged.append({
                **item,
                "best_rank": min(rank, prev["best_rank"] or prev["rank"]) if prev else rank,
                "seen_count": (prev["seen_count"] or 1) + 1 if prev else 1,
                "in_latest": True,
                "first_in_period": prev is None,
            })
        for name, prev in previous.items():
            if name in latest_names:
                continue
            merged.append({
                "name": name,
                "description": prev["description"] or "",
                "language": prev["language"] or "",
                "total_stars": prev["total_stars"],
                "forks": prev["forks"],
                "stars_period": prev["stars_period"],
                "stars_period_label": prev["stars_period_label"] or "",
                "url": prev["url"] or "",
                "best_rank": prev["best_rank"] or prev["rank"],
                "seen_count": prev["seen_count"] or 1,
                "in_latest": False,
                "first_in_period": False,
            })

        stored = []
        for rank, item in enumerate(merged, start=1):
            item = {
                "rank": rank,
                **item,
                "is_new": _is_new(conn, time_range, scope, item["name"], key),
            }
            conn.execute(
                """
                INSERT INTO snapshot_repos (
                    snapshot_id, rank, name, description, language,
                    total_stars, forks, stars_period, stars_period_label, url, is_new,
                    best_rank, seen_count, in_latest
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    item["best_rank"],
                    item["seen_count"],
                    1 if item["in_latest"] else 0,
                ),
            )
            stored.append(item)

    return {
        "id": snapshot_id,
        "time_range": time_range,
        "scope": scope,
        "period_key": key,
        "label": format_period_label(time_range, key),
        "fetched_at": fetched_at,
        "repos": stored,
        "new_count": sum(1 for item in stored if item["is_new"]),
    }


def list_scopes(time_range: str | None = None) -> list[dict]:
    """Language boards that have at least one stored snapshot."""
    params: list = []
    range_sql = ""
    if time_range:
        range_sql = "AND time_range = ?"
        params.append(time_range)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT scope, COUNT(*) AS snapshots, MAX(period_key) AS last_period
            FROM snapshots
            WHERE scope != '' {range_sql}
            GROUP BY scope
            ORDER BY scope
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def list_periods(time_range: str, scope: str = OVERALL) -> list[dict]:
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
            WHERE s.time_range = ? AND s.scope = ?
            GROUP BY s.id
            ORDER BY s.period_key DESC
            """,
            (time_range, scope),
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


def get_report(
    time_range: str,
    period: str | None = None,
    scope: str = OVERALL,
) -> dict | None:
    """Load one snapshot. Defaults to the newest period for the range."""
    with get_conn() as conn:
        if period:
            snapshot = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE time_range = ? AND period_key = ? AND scope = ?
                """,
                (time_range, period, scope),
            ).fetchone()
        else:
            snapshot = conn.execute(
                """
                SELECT * FROM snapshots
                WHERE time_range = ? AND scope = ?
                ORDER BY period_key DESC
                LIMIT 1
                """,
                (time_range, scope),
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
        scrape_count = conn.execute(
            """
            SELECT COUNT(*) FROM scrape_runs
            WHERE time_range = ? AND scope = ? AND period_key = ?
            """,
            (snapshot["time_range"], snapshot["scope"], snapshot["period_key"]),
        ).fetchone()[0]

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
            best_rank=row["best_rank"] or row["rank"],
            seen_count=row["seen_count"] or 1,
            in_latest=bool(row["in_latest"]),
        )
        for row in rows
    ]
    return {
        "id": snapshot["id"],
        "time_range": snapshot["time_range"],
        "scope": snapshot["scope"],
        "period_key": snapshot["period_key"],
        "label": format_period_label(snapshot["time_range"], snapshot["period_key"]),
        "fetched_at": snapshot["fetched_at"],
        "source": snapshot["source"] if "source" in snapshot.keys() else "scrape",
        "scrape_count": scrape_count,
        "repos": repos,
        "new_count": sum(1 for repo in repos if repo["is_new"]),
        "dropped_count": sum(1 for repo in repos if not repo["in_latest"]),
    }


def recompute_is_new() -> dict[str, int]:
    """Mark NEW only on a repo's first appearance on each board (range + scope)."""
    updated = 0
    with get_conn() as conn:
        boards = conn.execute(
            "SELECT DISTINCT time_range, scope FROM snapshots ORDER BY time_range, scope"
        ).fetchall()
        for board in boards:
            snapshots = conn.execute(
                """
                SELECT id, period_key
                FROM snapshots
                WHERE time_range = ? AND scope = ?
                ORDER BY period_key
                """,
                (board["time_range"], board["scope"]),
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


def set_snapshot_source(
    time_range: str,
    period_key: str,
    source: str,
    scope: str = OVERALL,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE snapshots SET source = ?
            WHERE time_range = ? AND period_key = ? AND scope = ?
            """,
            (source, time_range, period_key, scope),
        )


REPO_SORTS = {
    "peak_stars": "peak_stars DESC, appearances DESC, r.name ASC",
    "appearances": "appearances DESC, peak_stars DESC, r.name ASC",
    "first_seen": "first_seen_at ASC, r.name ASC",
    "last_seen": "last_seen_at DESC, r.name ASC",
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
                WHERE time_range = ? AND scope = ''
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
        "scopes": list_scopes(),
        "languages": [
            {"name": row["language"], "repo_count": row["repo_count"]}
            for row in languages
        ],
    }


def list_all_periods(time_range: str | None = None, scope: str = OVERALL) -> list[dict]:
    """List stored periods for one board scope, optionally one time range."""
    ranges = (time_range,) if time_range else TIME_RANGES
    items = []
    for current in ranges:
        for item in list_periods(current, scope):
            items.append({**item, "time_range": current, "scope": scope})
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
    limit: int = 1000,
    offset: int = 0,
    scope: str | None = None,
) -> dict:
    """Aggregate distinct repos across snapshots, with optional filters.

    ``scope=None`` covers the overall boards and every language board.
    """
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
    if scope is not None:
        where.append("s.scope = ?")
        params.append(scope)
    if language:
        where.append("r.language = ?")
        params.append(language)
    keyword_sql, keyword_params = _keyword_filter(keyword)
    if keyword_sql:
        where.append(keyword_sql)
        params.extend(keyword_params)

    having_source = ""
    having_filtered = ""
    having_params: list = []
    if min_stars is not None:
        having_source = "HAVING MAX(r.total_stars) >= ?"
        having_filtered = "HAVING MAX(total_stars) >= ?"
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
                {having_source}
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
                        ORDER BY fetched_at DESC, period_key DESC
                    ) AS rn,
                    ROW_NUMBER() OVER (
                        PARTITION BY name
                        ORDER BY fetched_at ASC, period_key ASC
                    ) AS rn_first
                FROM filtered
            ),
            agg AS (
                SELECT
                    name,
                    MAX(total_stars) AS peak_stars,
                    MAX(forks) AS peak_forks,
                    MAX(stars_period) AS peak_period_gain,
                    COUNT(*) AS appearances,
                    MIN(fetched_at) AS first_seen_at,
                    MAX(fetched_at) AS last_seen_at,
                    GROUP_CONCAT(DISTINCT time_range) AS time_ranges
                FROM filtered
                GROUP BY name
                {having_filtered}
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
                f.period_key AS first_seen,
                r.period_key AS last_seen,
                a.first_seen_at,
                a.last_seen_at,
                a.time_ranges
            FROM ranked r
            JOIN agg a ON a.name = r.name
            JOIN ranked f ON f.name = r.name AND f.rn_first = 1
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
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
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
                r.best_rank,
                r.in_latest,
                s.time_range,
                s.scope,
                s.period_key,
                s.fetched_at,
                COALESCE(s.source, 'scrape') AS source
            FROM snapshot_repos r
            JOIN snapshots s ON s.id = r.snapshot_id
            WHERE r.name = ? COLLATE NOCASE
            ORDER BY s.fetched_at DESC, s.period_key DESC, s.time_range ASC
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
            "scope": row["scope"],
            "period_key": row["period_key"],
            "label": format_period_label(row["time_range"], row["period_key"]),
            "fetched_at": row["fetched_at"],
            "source": row["source"],
            "rank": row["rank"],
            "best_rank": row["best_rank"] or row["rank"],
            "in_latest": bool(row["in_latest"]),
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

    # Rows are newest first by fetched_at; period keys of different ranges
    # ("2026-W40" vs "2026-10-08") do not sort chronologically as strings.
    latest = rows[0]
    earliest = rows[-1]
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
        first_seen=earliest["period_key"],
        last_seen=latest["period_key"],
        first_seen_at=earliest["fetched_at"],
        last_seen_at=latest["fetched_at"],
        time_ranges=ranges,
        scopes=sorted({row["scope"] for row in rows if row["scope"]}),
        history=appearances,
        star_history=get_star_series(latest["name"]),
    )


SEARCH_SORTS = ("relevance", *REPO_SORTS)
_SPLIT_WORDS = re.compile(r"[\W_]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _name_words(text: str) -> list[str]:
    """Split a repo slug into words: "ReverseEngineering-anything" -> reverse, engineering, anything."""
    return [word for word in _SPLIT_WORDS.split(_CAMEL.sub(" ", text).lower()) if word]


def _text_words(text: str) -> list[str]:
    return [word for word in _SPLIT_WORDS.split(text.lower()) if word]


def _compact(text: str) -> str:
    return "".join(_text_words(text))


def _token_score(token: str, repo_words, owner_words, repo_compact, desc_words, desc, language) -> int:
    """Best match for one query token. Short tokens only count on word starts."""
    if token in repo_words:
        return 30
    if any(word.startswith(token) for word in repo_words):
        return 20
    if len(token) >= 3 and token in repo_compact:
        return 12
    if token in owner_words:
        return 15
    if token == language:
        return 8
    if token in desc_words:
        return 10
    if len(token) >= 3 and any(word.startswith(token) for word in desc_words):
        return 6
    if (len(token) >= 4 or not token.isascii()) and token in desc:
        # Substring fallback; CJK descriptions have no spaces to split on.
        return 3
    return 0


def _search_features(item: dict) -> dict:
    """Pre-split the text fields that relevance scoring looks at."""
    owner, _, repo = item["name"].partition("/")
    repo_words = _name_words(repo)
    desc = (item.get("description") or "").lower()
    return {
        "name": item["name"].lower(),
        "repo_words": repo_words,
        "owner_words": _name_words(owner),
        "repo_compact": "".join(repo_words),
        "acronym": "".join(word[0] for word in repo_words) if len(repo_words) >= 2 else "",
        "desc": desc,
        "desc_words": set(_text_words(desc)),
        "language": (item.get("language") or "").lower(),
    }


def _relevance(f: dict, query: str, tokens: list[str]) -> int:
    """Score how well a repo matches; 0 means no match."""
    query_lower = query.lower()
    query_compact = "".join(tokens)
    repo_compact = f["repo_compact"]

    bonus = 0
    if f["name"] == query_lower:
        bonus += 200
    elif repo_compact and repo_compact == query_compact:
        bonus += 150
    elif f["acronym"] and f["acronym"] == query_compact:
        bonus += 100
    elif len(query_compact) >= 3 and repo_compact.startswith(query_compact):
        bonus += 60
    elif len(query_compact) >= 3 and query_compact in repo_compact:
        bonus += 40
    if len(tokens) > 1 and query_lower in f["desc"]:
        bonus += 20
    if f["language"] and f["language"] == query_lower:
        bonus += 20

    scores = [
        _token_score(
            token,
            f["repo_words"],
            f["owner_words"],
            repo_compact,
            f["desc_words"],
            f["desc"],
            f["language"],
        )
        for token in tokens
    ]
    if all(scores):
        return bonus + sum(scores)
    # A whole-name hit (exact, compact, acronym) still counts when tokens miss.
    return bonus if bonus >= 40 else 0


_SEARCH_CACHE: dict[tuple, list[tuple[dict, dict]]] = {}
_SEARCH_CACHE_SIZE = 16


def _data_version(conn: sqlite3.Connection) -> tuple:
    """Changes whenever a snapshot is written or replaced."""
    row = conn.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM snapshots),
            (SELECT MAX(fetched_at) FROM snapshots),
            (SELECT MAX(id) FROM snapshot_repos),
            (SELECT COUNT(*) FROM snapshot_repos)
        """
    ).fetchone()
    return tuple(row)


def _search_candidates(**filters) -> list[tuple[dict, dict]]:
    """Unique repos plus their search features, cached until the data changes."""
    with get_conn() as conn:
        version = _data_version(conn)
    key = (str(DB_PATH), version, tuple(sorted(filters.items())))
    cached = _SEARCH_CACHE.get(key)
    if cached is not None:
        return cached
    items = list_unique_repos(**filters, sort="peak_stars", limit=-1)["items"]
    candidates = [(item, _search_features(item)) for item in items]
    if len(_SEARCH_CACHE) >= _SEARCH_CACHE_SIZE:
        _SEARCH_CACHE.pop(next(iter(_SEARCH_CACHE)))
    _SEARCH_CACHE[key] = candidates
    return candidates


def search_repos(
    query: str,
    time_range: str | None = None,
    period: str | None = None,
    language: str | None = None,
    min_stars: int | None = None,
    sort: str = "relevance",
    limit: int = 1000,
    offset: int = 0,
    scope: str | None = None,
) -> dict:
    """Relevance-ranked search over every unique repo in the history.

    Matches name words, acronyms (``rea`` -> reverse-engineering-anything),
    owner, language, and description words. Tokens are AND-ed.
    """
    if sort not in SEARCH_SORTS:
        raise ValueError(f"unknown sort: {sort}")
    query = (query or "").strip()
    tokens = [_compact(part) for part in query.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return {"total": 0, "items": []}

    candidates = _search_candidates(
        time_range=time_range,
        period=period,
        language=language,
        min_stars=min_stars,
        scope=scope,
    )
    scored = []
    for item, features in candidates:
        score = _relevance(features, query, tokens)
        if score:
            scored.append((score, item))
    if sort == "relevance":
        # Stable sort keeps peak_stars order within the same score.
        scored.sort(key=lambda pair: pair[0], reverse=True)
    else:
        _sort_items(scored, sort)

    page = scored[offset: offset + limit] if limit >= 0 else scored[offset:]
    return {
        "total": len(scored),
        "items": [{**item, "relevance": score} for score, item in page],
    }


def _sort_items(scored: list[tuple[int, dict]], sort: str) -> None:
    """Apply a REPO_SORTS order to already-matched (score, item) pairs."""
    name = lambda pair: pair[1]["name"]
    if sort == "name":
        scored.sort(key=name)
    elif sort == "first_seen":
        scored.sort(key=name)
        scored.sort(key=lambda pair: pair[1]["first_seen_at"] or "")
    elif sort == "last_seen":
        scored.sort(key=name)
        scored.sort(key=lambda pair: pair[1]["last_seen_at"] or "", reverse=True)
    elif sort == "appearances":
        scored.sort(key=name)
        scored.sort(key=lambda pair: (pair[1]["appearances"], pair[1]["peak_stars"] or 0), reverse=True)
    # peak_stars: candidates already arrive in that order.


def suggest_repos(query: str, limit: int = 5) -> list[dict]:
    """Close spellings of repo names for a query that found nothing."""
    query_compact = _compact(query)
    if len(query_compact) < 3:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT name, MAX(total_stars) AS peak_stars
            FROM snapshot_repos
            GROUP BY name
            """
        ).fetchall()
    by_key: dict[str, dict] = {}
    for row in rows:
        repo = row["name"].partition("/")[2] or row["name"]
        key = _compact(repo)
        current = by_key.get(key)
        if current is None or (row["peak_stars"] or 0) > (current["peak_stars"] or 0):
            by_key[key] = {"name": row["name"], "peak_stars": row["peak_stars"]}
    matches = difflib.get_close_matches(query_compact, list(by_key), n=limit, cutoff=0.7)
    return [by_key[key] for key in matches]


def appearance_counts(names: list[str], time_range: str | None = None) -> dict[str, int]:
    """How many stored boards each repo has appeared on."""
    if not names:
        return {}
    placeholders = ",".join("?" for _ in names)
    params: list = list(names)
    range_sql = ""
    if time_range:
        range_sql = "AND s.time_range = ?"
        params.append(time_range)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT r.name, COUNT(*) AS n
            FROM snapshot_repos r
            JOIN snapshots s ON s.id = r.snapshot_id
            WHERE r.name IN ({placeholders}) {range_sql}
            GROUP BY r.name
            """,
            params,
        ).fetchall()
    return {row["name"]: row["n"] for row in rows}


def matches_query(item: dict, query: str) -> bool:
    """True when a repo dict would be returned by search_repos for this query."""
    tokens = [token for token in (_compact(part) for part in query.split()) if token]
    return bool(tokens) and _relevance(_search_features(item), query, tokens) > 0


def recent_new_repos(
    time_range: str,
    scope: str = OVERALL,
    snapshots: int = 14,
) -> list[dict]:
    """NEW repos from the newest snapshots of one board, newest first (for feeds).

    A repo counts once, on the scrape that first put it in that period.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                r.name, r.description, r.language, r.url, r.total_stars,
                r.stars_period, r.stars_period_label, r.best_rank,
                s.time_range, s.scope, s.period_key, s.fetched_at,
                (
                    SELECT MIN(sr.fetched_at)
                    FROM scrape_runs sr
                    JOIN scrape_run_repos srr ON srr.run_id = sr.id
                    WHERE sr.time_range = s.time_range AND sr.scope = s.scope
                      AND sr.period_key = s.period_key AND srr.name = r.name
                ) AS first_scraped_at
            FROM snapshot_repos r
            JOIN snapshots s ON s.id = r.snapshot_id
            WHERE s.id IN (
                SELECT id FROM snapshots
                WHERE time_range = ? AND scope = ?
                ORDER BY period_key DESC
                LIMIT ?
            )
            AND r.is_new = 1
            ORDER BY COALESCE(first_scraped_at, s.fetched_at) DESC, r.best_rank ASC
            """,
            (time_range, scope, snapshots),
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
            total_stars=row["total_stars"],
            stars_period=row["stars_period"],
            stars_period_label=row["stars_period_label"] or "",
            best_rank=row["best_rank"],
            time_range=row["time_range"],
            scope=row["scope"],
            period_key=row["period_key"],
            label=format_period_label(row["time_range"], row["period_key"]),
            seen_at=row["first_scraped_at"] or row["fetched_at"],
        ))
    return items


def record_stars(name: str, observed_on: str, stars: int, forks: int | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO repo_stars (name, observed_on, stars, forks)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name, observed_on) DO UPDATE SET
                stars = excluded.stars, forks = excluded.forks
            """,
            (name, observed_on, stars, forks),
        )


def mark_refreshed(name: str, checked_at: str, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO repo_refresh (name, checked_at, status) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                checked_at = excluded.checked_at, status = excluded.status
            """,
            (name, checked_at, status),
        )


def repos_to_refresh(since: str, limit: int, checked_before: str) -> list[str]:
    """Repos seen on a board since ``since``, least recently refreshed first.

    Repos already checked at or after ``checked_before`` are skipped, and
    repos GitHub reported missing are retried only after that window too.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT r.name, MAX(s.fetched_at) AS last_seen, f.checked_at
            FROM snapshot_repos r
            JOIN snapshots s ON s.id = r.snapshot_id
            LEFT JOIN repo_refresh f ON f.name = r.name
            WHERE s.fetched_at >= ?
            GROUP BY r.name
            HAVING f.checked_at IS NULL OR f.checked_at < ?
            ORDER BY f.checked_at IS NOT NULL, f.checked_at ASC, last_seen DESC
            LIMIT ?
            """,
            (since, checked_before, limit),
        ).fetchall()
    return [row["name"] for row in rows]


def get_star_series(name: str) -> list[dict]:
    """Daily GitHub API star counts for one repo, oldest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT observed_on, stars, forks FROM repo_stars
            WHERE name = ? COLLATE NOCASE
            ORDER BY observed_on
            """,
            (name,),
        ).fetchall()
    return [
        {"date": row["observed_on"], "stars": row["stars"], "forks": row["forks"]}
        for row in rows
    ]
