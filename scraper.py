"""Fetch and parse GitHub trending repository pages."""

import time

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html",
}


def fetch_html(url: str, attempts: int = 3, timeout: int = 30) -> str:
    """GET a page with short retries for transient GitHub failures."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt)
    assert last_error is not None
    raise last_error


def parse_trending_repos(html: str, github_base: str) -> list[dict]:
    """Parse a GitHub trending HTML page into repo dicts."""
    soup = BeautifulSoup(html, "html.parser")
    repos = []

    for article in soup.select("article.Box-row"):
        h2 = article.select_one("h2 a")
        if not h2:
            continue

        name = h2.get("href", "").strip("/")
        if not name:
            continue

        desc_elem = article.select_one("p")
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        lang_elem = article.select_one("[itemprop='programmingLanguage']")
        language = lang_elem.get_text(strip=True) if lang_elem else ""

        star_link = article.select_one('a[href$="/stargazers"]')
        fork_link = article.select_one('a[href$="/forks"]')
        total_stars = star_link.get_text(strip=True) if star_link else ""
        forks = fork_link.get_text(strip=True) if fork_link else ""

        stars_period = ""
        period_elem = article.select_one("span.d-inline-block.float-sm-right")
        if period_elem:
            stars_period = period_elem.get_text(strip=True)
        else:
            for span in article.select("span"):
                text = span.get_text(" ", strip=True)
                if "star" in text.lower() and ("today" in text.lower() or "this" in text.lower()):
                    stars_period = text
                    break

        repos.append({
            "name": name,
            "description": description,
            "language": language,
            "total_stars": total_stars,
            "forks": forks,
            "stars_today": stars_period,
            "url": f"{github_base}/{name}",
        })

    return repos


def fetch_trending_repos(github_base: str, time_range: str = "daily") -> list[dict]:
    """Download and parse one trending time range."""
    url = f"{github_base}/trending?since={time_range}"
    return parse_trending_repos(fetch_html(url), github_base)
