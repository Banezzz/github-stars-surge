import unittest

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


if __name__ == "__main__":
    unittest.main()
