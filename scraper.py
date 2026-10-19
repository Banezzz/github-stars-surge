"""Fetch and parse GitHub trending repository pages."""

import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 120
# GitHub's wording when a language genuinely has nothing trending.
EMPTY_PAGE_MARKERS = ("don’t have any trending repositories", "don't have any trending repositories")


class ScrapeError(RuntimeError):
    """The page could not be fetched, or it no longer parses."""


def _retry_delay(attempt: int, response: requests.Response | None, base_delay: float) -> float:
    """Exponential backoff, or the server's Retry-After when it sends one."""
    if response is not None:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(int(retry_after), MAX_RETRY_AFTER)
    return base_delay * (2 ** (attempt - 1))


def fetch_html(
    url: str,
    attempts: int = 4,
    timeout: int = 30,
    base_delay: float = 2.0,
    sleep=time.sleep,
) -> str:
    """GET a page, retrying network errors, 429 and 5xx with backoff (2s, 4s, 8s)."""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        response = None
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response.text
            last_error = ScrapeError(f"HTTP {response.status_code} from {url}")
        except requests.HTTPError as exc:
            # 404 and other client errors will not get better on retry.
            raise ScrapeError(f"{exc} ({url})") from exc
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            sleep(_retry_delay(attempt, response, base_delay))
    raise ScrapeError(f"giving up on {url} after {attempts} attempts: {last_error}")


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


def trending_url(github_base: str, time_range: str = "daily", language: str = "") -> str:
    path = f"/trending/{quote(language, safe='')}" if language else "/trending"
    return f"{github_base}{path}?since={time_range}"


def fetch_trending_repos(
    github_base: str,
    time_range: str = "daily",
    language: str = "",
) -> list[dict]:
    """Download and parse one trending board (overall, or one language slug).

    Raises ScrapeError when a page loads but yields no repos, which almost
    always means GitHub changed its markup, so it is not mistaken for "quiet day".
    """
    url = trending_url(github_base, time_range, language)
    html = fetch_html(url)
    repos = parse_trending_repos(html, github_base)
    if not repos:
        if any(marker in html for marker in EMPTY_PAGE_MARKERS):
            return []
        raise ScrapeError(f"parsed 0 repos from {url}; GitHub's markup may have changed")
    return repos
