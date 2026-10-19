import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree

import db
from web import create_app

ATOM = "{http://www.w3.org/2005/Atom}"


def _repo(name: str, description: str = "", language: str = "Python") -> dict:
    return {
        "name": name,
        "description": description,
        "language": language,
        "total_stars": "100",
        "forks": "1",
        "stars_today": "5 stars today",
        "url": f"https://github.com/{name}",
    }


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()
        db.save_snapshot("daily", [_repo("owner/old", "video thing")], datetime(2026, 8, 1, 9))
        db.save_snapshot(
            "daily",
            [_repo("owner/old", "video thing"), _repo("owner/fresh", "agent harness", "Rust")],
            datetime(2026, 8, 2, 9),
        )
        db.save_snapshot("daily", [_repo("owner/pyonly", "agent tools")], datetime(2026, 8, 2, 9), scope="python")
        self.client = create_app().test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def _entries(self, path: str) -> list[str]:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("application/atom+xml"))
        root = ElementTree.fromstring(response.get_data())
        return [entry.find(f"{ATOM}title").text for entry in root.findall(f"{ATOM}entry")]

    def test_feed_lists_each_new_repo_once(self):
        self.assertEqual(self._entries("/feed.xml"), ["owner/fresh (Rust)", "owner/old (Python)"])

    def test_feed_filters(self):
        self.assertEqual(self._entries("/feed.xml?q=agent"), ["owner/fresh (Rust)"])
        self.assertEqual(self._entries("/feed.xml?language=Python"), ["owner/old (Python)"])
        self.assertEqual(self._entries("/feed.xml?scope=python"), ["owner/pyonly (Python)"])
        self.assertEqual(self._entries("/feed.xml?range=weekly"), [])

    def test_pages_advertise_feeds(self):
        body = self.client.get("/?range=daily").get_data(as_text=True)
        self.assertIn('type="application/atom+xml"', body)
        self.assertIn('href="/feed.xml?range=daily"', body)
        search = self.client.get("/search?q=agent").get_data(as_text=True)
        self.assertIn("/feed.xml?q=agent", search)

    def test_report_page_language_boards(self):
        body = self.client.get("/?range=daily").get_data(as_text=True)
        self.assertIn('<option value="python"', body)
        python = self.client.get("/?range=daily&scope=python").get_data(as_text=True)
        self.assertIn("owner/pyonly", python)
        self.assertNotIn("owner/fresh", python)
        api = self.client.get("/api/v1/snapshots/daily?scope=python").get_json()
        self.assertEqual(api["data"]["repos"][0]["name"], "owner/pyonly")
        self.assertEqual(self.client.get("/api/v1/snapshots/daily?scope=zig").status_code, 404)

    def test_dropped_repos_are_labeled(self):
        db.save_snapshot("daily", [_repo("owner/fresh", "agent harness", "Rust")], datetime(2026, 8, 2, 21))
        body = self.client.get("/?range=daily&period=2026-08-02").get_data(as_text=True)
        self.assertIn("off board", body)
        self.assertIn("merged from 2 scrapes", body)


class DeployTests(unittest.TestCase):
    def test_wsgi_module_builds_app_from_env(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"DB_PATH": str(Path(tmp) / "w.db")}):
            import wsgi
            wsgi = importlib.reload(wsgi)
            self.assertEqual(wsgi.app.test_client().get("/").status_code, 200)
            self.assertTrue((Path(tmp) / "w.db").exists())

    def test_proxy_headers_trusted_only_when_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            db.configure(Path(tmp) / "p.db")
            db.init_db()
            headers = {"X-Forwarded-Proto": "https", "X-Forwarded-Host": "ghstar.example"}
            with mock.patch.dict(os.environ, {"TRUST_PROXY": "1", "PUBLIC_BASE_URL": ""}):
                feed = create_app().test_client().get("/feed.xml", headers=headers)
                self.assertIn(b"https://ghstar.example/feed.xml", feed.get_data())
            with mock.patch.dict(os.environ, {"TRUST_PROXY": "0", "PUBLIC_BASE_URL": ""}):
                feed = create_app().test_client().get("/feed.xml", headers=headers)
                self.assertNotIn(b"ghstar.example", feed.get_data())


if __name__ == "__main__":
    unittest.main()
