"""Daily star counts from the GitHub API, so history continues after a repo leaves trending."""

from datetime import datetime, timedelta

import requests

import db

API_BASE = "https://api.github.com"
# Unauthenticated calls get 60/hour; a token gets 5000/hour.
DEFAULT_LIMIT_ANON = 50
DEFAULT_LIMIT_TOKEN = 1000
RATE_LIMIT_RESERVE = 2


def refresh_stars(
    token: str | None = None,
    limit: int | None = None,
    days: int = 90,
    session: requests.Session | None = None,
    now: datetime | None = None,
    api_base: str = API_BASE,
) -> dict:
    """Record today's stars for repos seen on any board in the last ``days``.

    Each repo is checked at most once per day; the least recently checked go
    first so a small rate limit still cycles through everything over time.
    Stops early when GitHub's remaining quota runs low.
    """
    now = now or datetime.now()
    today = now.date().isoformat()
    limit = limit if limit is not None else (DEFAULT_LIMIT_TOKEN if token else DEFAULT_LIMIT_ANON)
    since = (now - timedelta(days=days)).isoformat(timespec="seconds")
    names = db.repos_to_refresh(since=since, limit=limit, checked_before=today)

    session = session or requests.Session()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-stars-surge",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    result = {"checked": 0, "updated": 0, "missing": 0, "errors": 0, "rate_limited": False}
    for name in names:
        try:
            response = session.get(f"{api_base}/repos/{name}", headers=headers, timeout=20)
        except requests.RequestException:
            result["errors"] += 1
            continue
        checked_at = datetime.now().isoformat(timespec="seconds")
        remaining = response.headers.get("X-RateLimit-Remaining")

        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                result["errors"] += 1
                continue
            db.record_stars(
                name,
                today,
                int(payload.get("stargazers_count") or 0),
                payload.get("forks_count"),
            )
            db.mark_refreshed(name, checked_at, "ok")
            result["updated"] += 1
        elif response.status_code in (404, 410, 451):
            # Deleted, made private, or blocked; retried after the window.
            db.mark_refreshed(name, checked_at, "missing")
            result["missing"] += 1
        elif response.status_code in (403, 429) and remaining == "0":
            result["rate_limited"] = True
            break
        else:
            result["errors"] += 1
        result["checked"] += 1

        if remaining is not None and remaining.isdigit() and int(remaining) <= RATE_LIMIT_RESERVE:
            result["rate_limited"] = True
            break
    return result
