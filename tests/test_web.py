import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import db
from web import create_app


class WebViewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()
        db.save_snapshot(
            "weekly",
            [{
                "name": "owner/demo",
                "description": "A demo repo",
                "language": "Python",
                "total_stars": "1200",
                "forks": "30",
                "stars_today": "88 stars this week",
                "url": "https://github.com/owner/demo",
            }],
            datetime(2026, 8, 15, 9, 0),
        )
        db.save_snapshot(
            "monthly",
            [{
                "name": "owner/month",
                "description": "Monthly demo",
                "language": "Go",
                "total_stars": "900",
                "forks": "10",
                "stars_today": "200 stars this month",
                "url": "https://github.com/owner/month",
            }],
            datetime(2026, 8, 15, 9, 0),
        )
        self.client = create_app().test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_weekly_history_page(self):
        response = self.client.get("/?range=weekly")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("owner/demo", body)
        self.assertIn("2026-W33", body)
        self.assertIn("stars this week", body)
        self.assertIn('id="q"', body)
        self.assertIn("filterCards", body)
        self.assertIn('href="/docs"', body)

    def test_monthly_history_page(self):
        response = self.client.get("/?range=monthly&period=2026-08")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("owner/month", body)
        self.assertIn("August 2026", body)
        self.assertIn("stars this month", body)

    def test_empty_daily_page(self):
        response = self.client.get("/?range=daily")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No daily snapshots yet", response.get_data(as_text=True))

    def test_discord_archive_is_labeled(self):
        db.save_snapshot(
            "daily",
            [{
                "name": "owner/old",
                "description": "from discord",
                "language": "Rust",
                "total_stars": "10",
                "forks": "1",
                "stars_today": "2 stars today",
                "url": "https://github.com/owner/old",
            }],
            datetime(2026, 3, 15, 9, 0),
        )
        db.set_snapshot_source("daily", "2026-03-15", "discord")
        response = self.client.get("/?range=daily&period=2026-03-15")
        body = response.get_data(as_text=True)
        self.assertIn("partial archive", body)
        self.assertIn("NEW", body)


if __name__ == "__main__":
    unittest.main()
