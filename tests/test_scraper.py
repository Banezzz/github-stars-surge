import unittest
from unittest import mock

import requests

import scraper
from scraper import parse_trending_repos


SAMPLE_HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo">owner / repo</a></h2>
  <p>A description</p>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/owner/repo/stargazers">1,234</a>
  <a href="/owner/repo/forks">56</a>
  <span class="d-inline-block float-sm-right">88 stars this week</span>
</article>
<article class="Box-row">
  <h2><a href="/other/app">other / app</a></h2>
  <span>77 stars today</span>
</article>
</body></html>
"""


class ParseTrendingTests(unittest.TestCase):
    def test_parses_name_stats_and_period_stars(self):
        repos = parse_trending_repos(SAMPLE_HTML, "https://github.com")
        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0]["name"], "owner/repo")
        self.assertEqual(repos[0]["language"], "Python")
        self.assertEqual(repos[0]["total_stars"], "1,234")
        self.assertEqual(repos[0]["forks"], "56")
        self.assertEqual(repos[0]["stars_today"], "88 stars this week")
        self.assertEqual(repos[0]["url"], "https://github.com/owner/repo")

    def test_falls_back_to_star_text_in_spans(self):
        repos = parse_trending_repos(SAMPLE_HTML, "https://github.com")
        self.assertEqual(repos[1]["name"], "other/app")
        self.assertEqual(repos[1]["stars_today"], "77 stars today")



class _Response:
    def __init__(self, status: int, text: str = "", headers: dict | None = None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FetchTests(unittest.TestCase):
    def _fetch(self, responses, **kwargs):
        calls, sleeps = [], []

        def fake_get(url, **_):
            calls.append(url)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with mock.patch.object(scraper.requests, "get", fake_get):
            result = scraper.fetch_html("https://example.test/x", sleep=sleeps.append, **kwargs)
        return result, calls, sleeps

    def test_retries_5xx_and_network_errors_with_backoff(self):
        result, calls, sleeps = self._fetch([
            _Response(503),
            requests.ConnectionError("reset"),
            _Response(200, "ok"),
        ])
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_honours_retry_after(self):
        _, _, sleeps = self._fetch([_Response(429, headers={"Retry-After": "7"}), _Response(200, "ok")])
        self.assertEqual(sleeps, [7])

    def test_client_errors_are_not_retried(self):
        with self.assertRaises(scraper.ScrapeError):
            self._fetch([_Response(404)])

    def test_gives_up_after_attempts(self):
        with self.assertRaises(scraper.ScrapeError):
            self._fetch([_Response(502)] * 4)

    def test_zero_parsed_repos_is_an_error_not_an_empty_board(self):
        with mock.patch.object(scraper, "fetch_html", return_value="<html>new markup</html>"):
            with self.assertRaises(scraper.ScrapeError):
                scraper.fetch_trending_repos("https://github.com", "daily")
        empty = "<p>It looks like we don’t have any trending repositories for Zig.</p>"
        with mock.patch.object(scraper, "fetch_html", return_value=empty):
            self.assertEqual(scraper.fetch_trending_repos("https://github.com", "daily", "zig"), [])

    def test_language_urls(self):
        self.assertEqual(
            scraper.trending_url("https://github.com", "weekly", "c++"),
            "https://github.com/trending/c%2B%2B?since=weekly",
        )
        self.assertEqual(
            scraper.trending_url("https://github.com", "daily"),
            "https://github.com/trending?since=daily",
        )


if __name__ == "__main__":
    unittest.main()
