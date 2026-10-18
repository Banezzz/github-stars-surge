import sqlite3
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

    def test_same_week_scrapes_merge_instead_of_replacing(self):
        # A repo that trended on Monday but dropped off by Sunday stays on the weekly board.
        when = datetime(2026, 8, 10, 9, 0)
        db.save_snapshot("weekly", [_repo("owner/early"), _repo("owner/stays")], when)
        later = db.save_snapshot(
            "weekly",
            [_repo("owner/late"), _repo("owner/stays", stars="150")],
            datetime(2026, 8, 16, 9, 0),
        )

        self.assertEqual(len(db.list_periods("weekly")), 1)
        report = db.get_report("weekly")
        self.assertEqual(
            [repo["name"] for repo in report["repos"]],
            ["owner/late", "owner/stays", "owner/early"],
        )
        by_name = {repo["name"]: repo for repo in report["repos"]}
        self.assertTrue(by_name["owner/stays"]["in_latest"])
        self.assertEqual(by_name["owner/stays"]["total_stars"], 150)
        self.assertEqual(by_name["owner/stays"]["seen_count"], 2)
        self.assertEqual(by_name["owner/stays"]["best_rank"], 2)
        self.assertFalse(by_name["owner/early"]["in_latest"])
        self.assertEqual(by_name["owner/early"]["best_rank"], 1)
        self.assertEqual(report["scrape_count"], 2)
        self.assertEqual(report["dropped_count"], 1)
        # Only repos the period had not seen yet are fresh for notifications.
        fresh = {repo["name"] for repo in later["repos"] if repo["first_in_period"]}
        self.assertEqual(fresh, {"owner/late"})

    def test_every_scrape_is_logged_verbatim(self):
        db.save_snapshot("daily", [_repo("owner/a"), _repo("owner/b")], datetime(2026, 8, 15, 9))
        db.save_snapshot("daily", [_repo("owner/b")], datetime(2026, 8, 15, 21))
        with db.get_conn() as conn:
            runs = conn.execute("SELECT COUNT(*) FROM scrape_runs").fetchone()[0]
            rows = conn.execute("SELECT COUNT(*) FROM scrape_run_repos").fetchone()[0]
        self.assertEqual((runs, rows), (2, 3))

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

    def test_recompute_is_new_marks_first_seen_per_board(self):
        week1 = datetime(2026, 8, 10, 9, 0)
        week2 = datetime(2026, 8, 17, 9, 0)
        db.save_snapshot("weekly", [_repo("owner/repeat")], week1)
        db.save_snapshot("weekly", [_repo("owner/repeat"), _repo("owner/fresh")], week2)

        with db.get_conn() as conn:
            conn.execute("UPDATE snapshot_repos SET is_new = 1")

        db.recompute_is_new()
        later = {repo["name"]: repo["is_new"] for repo in db.get_report("weekly", "2026-W34")["repos"]}
        self.assertFalse(later["owner/repeat"])
        self.assertTrue(later["owner/fresh"])

    def test_unique_repos_min_stars_filters_peak(self):
        db.save_snapshot(
            "weekly",
            [_repo("owner/small", "100"), _repo("owner/big", "9000")],
            datetime(2026, 8, 15),
        )
        result = db.list_unique_repos(min_stars=5000, sort="peak_stars")
        names = [item["name"] for item in result["items"]]
        self.assertEqual(names, ["owner/big"])
        self.assertEqual(result["total"], 1)

    def test_unique_repos_search_uses_description(self):
        db.save_snapshot(
            "weekly",
            [_repo("cryptic/xyz", "88")],
            datetime(2026, 8, 15),
        )
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE snapshot_repos SET description = ? WHERE name = ?",
                ("Open video generative models", "cryptic/xyz"),
            )

        result = db.list_unique_repos(keyword="video generative")
        self.assertEqual(result["total"], 1)
        item = result["items"][0]
        self.assertEqual(list(item.keys())[:3], ["name", "description", "url"])
        self.assertEqual(item["name"], "cryptic/xyz")
        self.assertIn("video generative", item["description"])
        self.assertEqual(item["url"], "https://github.com/cryptic/xyz")

    def test_empty_snapshot_is_refused(self):
        when = datetime(2026, 8, 15, 9, 0)
        db.save_snapshot("weekly", [_repo("owner/keep")], when)
        with self.assertRaises(ValueError):
            db.save_snapshot("weekly", [], when)
        report = db.get_report("weekly", "2026-W33")
        self.assertEqual([repo["name"] for repo in report["repos"]], ["owner/keep"])



class LanguageBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_language_boards_are_separate_from_main_board(self):
        when = datetime(2026, 8, 15, 9, 0)
        db.save_snapshot("daily", [_repo("owner/main")], when)
        db.save_snapshot("daily", [_repo("owner/main"), _repo("owner/py")], when, scope="python")

        self.assertEqual([r["name"] for r in db.get_report("daily")["repos"]], ["owner/main"])
        python = db.get_report("daily", scope="python")
        self.assertEqual([r["name"] for r in python["repos"]], ["owner/main", "owner/py"])
        # NEW is per board: owner/main is new on the python board too.
        self.assertTrue(all(r["is_new"] for r in python["repos"]))
        self.assertEqual(db.list_scopes(), [{"scope": "python", "snapshots": 1, "last_period": "2026-08-15"}])
        self.assertEqual(db.overview()["ranges"]["daily"]["snapshots"], 1)
        # Aggregates cover every board unless narrowed.
        names = {item["name"] for item in db.list_unique_repos()["items"]}
        self.assertEqual(names, {"owner/main", "owner/py"})
        main_only = {item["name"] for item in db.list_unique_repos(scope="")["items"]}
        self.assertEqual(main_only, {"owner/main"})
        self.assertEqual(db.search_repos("py")["items"][0]["name"], "owner/py")

    def test_old_database_is_migrated_in_place(self):
        path = Path(self.tmp.name) / "old.db"
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY,
                time_range TEXT NOT NULL,
                period_key TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'scrape',
                UNIQUE(time_range, period_key)
            );
            CREATE TABLE snapshot_repos (
                id INTEGER PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT, language TEXT, total_stars INTEGER, forks INTEGER,
                stars_period INTEGER, stars_period_label TEXT, url TEXT,
                is_new INTEGER DEFAULT 0,
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
            );
            INSERT INTO snapshots VALUES (7, 'weekly', '2026-W33', '2026-08-15T09:00:00', 'discord');
            INSERT INTO snapshot_repos (snapshot_id, rank, name, total_stars, is_new)
                VALUES (7, 3, 'owner/old', 10, 1);
        """)
        conn.commit()
        conn.close()

        db.configure(path)
        db.init_db()
        db.init_db()  # idempotent
        report = db.get_report("weekly", "2026-W33")
        self.assertEqual(report["id"], 7)
        self.assertEqual(report["source"], "discord")
        self.assertEqual(report["scope"], "")
        self.assertEqual(report["repos"][0]["best_rank"], 3)
        self.assertTrue(report["repos"][0]["in_latest"])
        # The new unique key allows a language board for the same period.
        db.save_snapshot("weekly", [_repo("owner/py")], datetime(2026, 8, 15, 10), scope="python")
        self.assertIsNotNone(db.get_report("weekly", "2026-W33", "python"))
        with db.get_conn() as check:
            self.assertEqual(check.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
