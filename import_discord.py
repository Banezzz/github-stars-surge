#!/usr/bin/env python3
"""Backfill snapshot history from a Discord channel export.

Reads messages.json produced by the Discord API (oldest first) and writes
period snapshots. Existing snapshots are left untouched so a live scrape is
not replaced by a partial Discord embed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import db
from period import parse_count, period_key as period_key_from_date

REPO_HEADER = re.compile(
    r"\*\*\[(?P<name>[^\]]+)\]\((?P<url>[^)]+)\)\*\*(?:\s+`(?P<badge>[^`]+)`)?",
)
TITLE_RE = re.compile(
    r"^(?:🔥\s*)?(?:New\s+)?Trending Repositories"
    r"(?:\s+\((?P<label>[^)]+)\))?\s*-\s*(?P<key>\S+)\s*$",
    re.IGNORECASE,
)
STATS_RE = re.compile(r"^`([^`]+)`$")
LABEL_TO_RANGE = {
    "today": "daily",
    "daily": "daily",
    "this week": "weekly",
    "weekly": "weekly",
    "this month": "monthly",
    "monthly": "monthly",
}


def parse_title(title: str) -> tuple[str, str] | None:
    """Return (time_range, period_key) or None if this embed is not a repo report."""
    if not title or "developer" in title.lower():
        return None
    match = TITLE_RE.match(title.strip())
    if not match:
        return None

    label = (match.group("label") or "").strip().lower()
    raw_key = match.group("key").strip()
    time_range = LABEL_TO_RANGE.get(label, "daily")

    if time_range == "weekly":
        if re.fullmatch(r"\d{4}-W\d{2}", raw_key):
            return time_range, raw_key
        when = datetime.strptime(raw_key, "%Y-%m-%d")
        return time_range, period_key_from_date("weekly", when)
    if time_range == "monthly":
        if re.fullmatch(r"\d{4}-\d{2}", raw_key):
            return time_range, raw_key
        when = datetime.strptime(raw_key, "%Y-%m-%d")
        return time_range, period_key_from_date("monthly", when)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_key):
        return "daily", raw_key
    return None


def parse_stats(line: str) -> dict:
    """Parse `Python | ⭐ 1,234 | 🍴 56 | 📈 123 stars today`."""
    inner = line.strip()
    if inner.startswith("`") and inner.endswith("`"):
        inner = inner[1:-1]
    parts = [part.strip() for part in inner.split("|")]
    out = {
        "language": "",
        "total_stars": None,
        "forks": None,
        "stars_period": None,
        "stars_period_label": "",
    }
    for part in parts:
        if part.startswith("⭐"):
            out["total_stars"] = parse_count(part)
        elif part.startswith("🍴"):
            out["forks"] = parse_count(part)
        elif part.startswith("📈"):
            out["stars_period"] = parse_count(part)
            out["stars_period_label"] = part[1:].strip()
        elif part and not out["language"]:
            out["language"] = part
    return out


def parse_repos(description: str) -> list[dict]:
    """Extract repo blocks from an embed description."""
    if not description:
        return []

    text = description.strip()
    text = re.sub(r"^\*\d+\s+new out of \d+ total\*\s*", "", text, flags=re.I)

    repos = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        header = REPO_HEADER.match(line.strip())
        if header:
            if current:
                repos.append(current)
            name = header.group("name").strip()
            url = header.group("url").strip()
            badge = (header.group("badge") or "").strip()
            current = {
                "name": name,
                "url": url,
                "description": "",
                "language": "",
                "total_stars": None,
                "forks": None,
                "stars_period": None,
                "stars_period_label": "",
                "is_new": badge.upper() != "X2",
            }
            continue
        if current is None:
            continue
        stripped = line.strip()
        if STATS_RE.match(stripped) or stripped.startswith("⭐") or "📈" in stripped:
            current.update(parse_stats(stripped))
        elif not current["description"]:
            current["description"] = stripped
        else:
            current["description"] += " " + stripped
    if current:
        repos.append(current)
    return [repo for repo in repos if "/" in repo["name"]]


def collect_periods(messages: list[dict]) -> dict[tuple[str, str], dict]:
    """Group parsed embeds into (time_range, period_key) buckets."""
    periods: dict[tuple[str, str], dict] = {}
    skipped_titles = defaultdict(int)

    for message in messages:
        fetched_at = message.get("timestamp") or ""
        for embed in message.get("embeds") or []:
            title = embed.get("title") or ""
            parsed = parse_title(title)
            if not parsed:
                skipped_titles[title or "(empty)"] += 1
                continue
            time_range, key = parsed
            repos = parse_repos(embed.get("description") or "")
            if not repos:
                continue
            bucket = periods.setdefault(
                (time_range, key),
                {"repos": {}, "order": [], "fetched_at": fetched_at, "sources": 0},
            )
            bucket["sources"] += 1
            if fetched_at > bucket["fetched_at"]:
                bucket["fetched_at"] = fetched_at
            for repo in repos:
                name = repo["name"]
                if name not in bucket["repos"]:
                    bucket["order"].append(name)
                    bucket["repos"][name] = repo
                else:
                    existing = bucket["repos"][name]
                    # Later message wins for stats; keep a NEW badge if any copy had it.
                    merged = {**existing, **{k: v for k, v in repo.items() if v not in ("", None)}}
                    merged["is_new"] = existing.get("is_new", True) or repo.get("is_new", True)
                    bucket["repos"][name] = merged

    return periods, dict(skipped_titles)


def existing_keys() -> set[tuple[str, str]]:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT time_range, period_key FROM snapshots").fetchall()
    return {(row["time_range"], row["period_key"]) for row in rows}


def insert_snapshot(time_range: str, key: str, fetched_at: str, repos: list[dict]) -> None:
    fetched_at = _normalize_ts(fetched_at)
    with db.get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO snapshots (time_range, period_key, fetched_at, source)
            VALUES (?, ?, ?, 'discord')
            """,
            (time_range, key, fetched_at),
        )
        snapshot_id = cursor.lastrowid
        for rank, repo in enumerate(repos, start=1):
            conn.execute(
                """
                INSERT INTO snapshot_repos (
                    snapshot_id, rank, name, description, language,
                    total_stars, forks, stars_period, stars_period_label, url, is_new
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    rank,
                    repo["name"],
                    repo.get("description") or "",
                    repo.get("language") or "",
                    repo.get("total_stars"),
                    repo.get("forks"),
                    repo.get("stars_period"),
                    repo.get("stars_period_label") or "",
                    repo.get("url") or "",
                    1 if repo.get("is_new", True) else 0,
                ),
            )


def _normalize_ts(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    except ValueError:
        return value[:19]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--messages",
        default=Path(__file__).parent / "import" / "messages.json",
        type=Path,
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.messages.exists():
        print(f"Missing export: {args.messages}", file=sys.stderr)
        return 1

    messages = json.loads(args.messages.read_text())
    periods, skipped = collect_periods(messages)
    already = existing_keys() if not args.dry_run else existing_keys()

    print(f"Parsed {len(messages)} messages into {len(periods)} period snapshots")
    if skipped:
        print("Skipped titles:")
        for title, count in sorted(skipped.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {count:3d}  {title}")

    inserted = 0
    skipped_existing = 0
    by_range = defaultdict(int)
    for (time_range, key), bucket in sorted(periods.items()):
        repos = [bucket["repos"][name] for name in bucket["order"]]
        by_range[time_range] += 1
        exists = (time_range, key) in already
        action = "skip-existing" if exists else "insert"
        print(
            f"  {action:14s} {time_range:8s} {key:10s}  "
            f"{len(repos):3d} repos  sources={bucket['sources']}  {bucket['fetched_at'][:19]}"
        )
        if exists:
            skipped_existing += 1
            continue
        if args.dry_run:
            continue
        insert_snapshot(time_range, key, bucket["fetched_at"], repos)
        inserted += 1

    print(
        f"Done. insert={inserted} skipped_existing={skipped_existing} "
        f"daily={by_range['daily']} weekly={by_range['weekly']} monthly={by_range['monthly']}"
    )
    return 0


if __name__ == "__main__":
    db.init_db()
    raise SystemExit(main())
