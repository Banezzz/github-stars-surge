import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import db


def _repo(name: str, stars: str = "100", period_stars: str = "10") -> dict:
    return {
        "name": name,
        "description": f"{name} description",
        "language": "Python",
        "total_stars": stars,
        "forks": "5",
        "stars_today": f"{period_stars} stars this week",
        "url": f"https://github.com/{name}",
    }


class SnapshotDbTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_read_weekly_snapshot(self):
        when = datetime(2026, 8, 15, 9, 0)
        saved = db.save_snapshot("weekly", [_repo("owner/one"), _repo("owner/two")], when)

        self.assertEqual(saved["period_key"], "2026-W33")
        self.assertEqual(saved["new_count"], 2)

        report = db.get_report("weekly", "2026-W33")
        self.assertIsNotNone(report)
        self.assertEqual(len(report["repos"]), 2)
        self.assertEqual(report["repos"][0]["name"], "owner/one")
        self.assertEqual(report["repos"][0]["total_stars"], 100)
        self.assertTrue(report["repos"][0]["is_new"])

    def test_same_week_upsert_replaces_items(self):
        when = datetime(2026, 8, 15, 9, 0)
        db.save_snapshot("weekly", [_repo("owner/old")], when)
        db.save_snapshot("weekly", [_repo("owner/new")], when + datetime.resolution)

        periods = db.list_periods("weekly")
        self.assertEqual(len(periods), 1)
        report = db.get_report("weekly")
        self.assertEqual([repo["name"] for repo in report["repos"]], ["owner/new"])

    def test_new_flag_is_per_time_range_and_history(self):
        week1 = datetime(2026, 8, 10, 9, 0)
        week2 = datetime(2026, 8, 17, 9, 0)
        month = datetime(2026, 8, 20, 9, 0)

        db.save_snapshot("weekly", [_repo("owner/repeat")], week1)
        later = db.save_snapshot("weekly", [_repo("owner/repeat"), _repo("owner/fresh")], week2)
        monthly = db.save_snapshot("monthly", [_repo("owner/repeat")], month)

        later_by_name = {repo["name"]: repo["is_new"] for repo in later["repos"]}
        self.assertFalse(later_by_name["owner/repeat"])
        self.assertTrue(later_by_name["owner/fresh"])
        self.assertTrue(monthly["repos"][0]["is_new"])

    def test_list_periods_newest_first(self):
        db.save_snapshot("monthly", [_repo("owner/july")], datetime(2026, 7, 15))
        db.save_snapshot("monthly", [_repo("owner/aug")], datetime(2026, 8, 15))

        keys = [item["period_key"] for item in db.list_periods("monthly")]
        self.assertEqual(keys, ["2026-08", "2026-07"])

    def test_empty_snapshot_is_refused(self):
        when = datetime(2026, 8, 15, 9, 0)
        db.save_snapshot("weekly", [_repo("owner/keep")], when)
        with self.assertRaises(ValueError):
            db.save_snapshot("weekly", [], when)
        report = db.get_report("weekly", "2026-W33")
        self.assertEqual([repo["name"] for repo in report["repos"]], ["owner/keep"])


if __name__ == "__main__":
    unittest.main()
