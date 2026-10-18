import contextlib
import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import db
import main
from main import DISCORD_DESCRIPTION_LIMIT, format_repos_embed


class EmbedTests(unittest.TestCase):
    def test_only_new_repos_are_included(self):
        embed = format_repos_embed({
            "time_range": "weekly",
            "period_key": "2026-W33",
            "repos": [
                {"name": "old/one", "description": "old", "url": "https://github.com/old/one", "is_new": False},
                {
                    "name": "new/two",
                    "description": "fresh",
                    "url": "https://github.com/new/two",
                    "language": "Python",
                    "total_stars": 10,
                    "forks": 1,
                    "stars_period_label": "5 stars this week",
                    "is_new": True,
                },
            ],
        })
        self.assertIsNotNone(embed)
        self.assertIn("new/two", embed["description"])
        self.assertNotIn("old/one", embed["description"])
        self.assertIn("2026-W33", embed["title"])

    def test_no_new_repos_returns_none(self):
        embed = format_repos_embed({
            "time_range": "daily",
            "period_key": "2026-08-15",
            "repos": [{"name": "old/one", "description": "", "url": "", "is_new": False}],
        })
        self.assertIsNone(embed)

    def test_long_description_is_truncated(self):
        repos = [
            {
                "name": f"owner/repo-{index}",
                "description": "x" * 200,
                "url": f"https://github.com/owner/repo-{index}",
                "is_new": True,
            }
            for index in range(25)
        ]
        embed = format_repos_embed({
            "time_range": "monthly",
            "period_key": "2026-08",
            "repos": repos,
        })
        self.assertLessEqual(len(embed["description"]), DISCORD_DESCRIPTION_LIMIT)



class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def _repos(self, *names):
        return [
            {"name": name, "description": "", "language": "Python", "total_stars": "10",
             "forks": "1", "stars_today": "5 stars today", "url": f"https://github.com/{name}"}
            for name in names
        ]

    def test_failures_are_collected_and_alerted(self):
        def fake_fetch(base, time_range, language=""):
            if language == "rust":
                raise main.ScrapeError("parsed 0 repos")
            return self._repos(f"owner/{time_range}-{language or 'all'}")

        sent = []
        with mock.patch.object(main, "fetch_trending_repos", fake_fetch), \
                mock.patch.object(main, "TRENDING_LANGUAGES", ["python", "rust"]), \
                mock.patch.object(main, "REQUEST_DELAY", 0), \
                mock.patch.object(main, "STAR_REFRESH", False), \
                mock.patch.object(main, "DISCORD_WEBHOOK", "https://discord.test/hook"), \
                mock.patch.object(main, "send_discord_message", lambda **kw: sent.append(kw)), \
                contextlib.redirect_stdout(io.StringIO()):
            failures = main.job()

        self.assertEqual([board for board, _ in failures], ["daily/rust", "weekly/rust", "monthly/rust"])
        self.assertIsNotNone(db.get_report("daily", scope="python"))
        # Main boards post NEW repos; language boards never do; one alert for the failures.
        embeds = [kw for kw in sent if "embeds" in kw]
        alerts = [kw for kw in sent if "content" in kw]
        self.assertEqual(len(embeds), 3)
        self.assertEqual(len(alerts), 1)
        self.assertIn("daily/rust", alerts[0]["content"])

    def test_repeat_scrape_does_not_reannounce(self):
        snapshot = db.save_snapshot("weekly", self._repos("owner/a"), datetime(2026, 8, 10, 9))
        self.assertIsNotNone(format_repos_embed(snapshot))
        again = db.save_snapshot("weekly", self._repos("owner/a"), datetime(2026, 8, 11, 9))
        self.assertIsNone(format_repos_embed(again))


if __name__ == "__main__":
    unittest.main()
