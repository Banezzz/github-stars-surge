import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import db
from web import create_app


def _repo(name: str, description: str, language: str = "Python") -> dict:
    return {
        "name": name,
        "description": description,
        "language": language,
        "total_stars": "1200",
        "forks": "30",
        "stars_today": "88 stars this week",
        "url": f"https://github.com/{name}",
    }


class PublicApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()
        db.save_snapshot(
            "weekly",
            [_repo("Wan-Video/Wan2.2", "Open video generative models")],
            datetime(2026, 8, 15, 9, 0),
        )
        db.save_snapshot(
            "monthly",
            [_repo("owner/month", "Monthly demo", "Go")],
            datetime(2026, 8, 15, 9, 0),
        )
        self.client = create_app().test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def _assert_card(self, item: dict, name: str, description: str):
        self.assertEqual(list(item.keys())[:3], ["name", "description", "url"])
        self.assertEqual(item["name"], name)
        self.assertEqual(item["description"], description)
        self.assertEqual(item["url"], f"https://github.com/{name}")

    def test_docs_page_and_header_link(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn('href="/docs"', home.get_data(as_text=True))

        docs = self.client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        body = docs.get_data(as_text=True)
        self.assertIn("name", body)
        self.assertIn("description", body)
        self.assertIn("Copy prompt", body)
        self.assertIn("/api/v1/search", body)

    def test_catalog_lists_repo_identity_fields(self):
        response = self.client.get("/api")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["repo_fields"],
            {
                "name": "owner/repo",
                "description": "GitHub about/blurb captured with the snapshot",
                "url": "Canonical GitHub link",
            },
        )
        self.assertIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_snapshot_includes_name_description_url(self):
        response = self.client.get("/api/v1/snapshots/weekly/2026-W33")
        self.assertEqual(response.status_code, 200)
        repo = response.get_json()["data"]["repos"][0]
        self._assert_card(repo, "Wan-Video/Wan2.2", "Open video generative models")

    def test_search_matches_description_not_just_name(self):
        response = self.client.get("/api/v1/search?q=generative+models")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self._assert_card(
            payload["data"][0],
            "Wan-Video/Wan2.2",
            "Open video generative models",
        )

    def test_repos_min_stars_query(self):
        response = self.client.get("/api/v1/repos?min_stars=5000&sort=peak_stars")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["total"], 0)

    def test_repos_card_projection(self):
        response = self.client.get("/api/v1/repos?fields=card")
        self.assertEqual(response.status_code, 200)
        item = response.get_json()["data"][0]
        self.assertEqual(set(item.keys()), {"name", "description", "url"})
        self.assertTrue(item["description"])

    def test_repo_detail_keeps_identity_fields(self):
        response = self.client.get("/api/v1/repos/Wan-Video/Wan2.2")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self._assert_card(data, "Wan-Video/Wan2.2", "Open video generative models")
        self.assertGreaterEqual(data["appearances"], 1)

    def test_unknown_range_is_rejected(self):
        response = self.client.get("/api/v1/snapshots/yearly")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_prompts_are_available(self):
        response = self.client.get("/api/v1/prompts")
        self.assertEqual(response.status_code, 200)
        prompts = response.get_json()["data"]
        self.assertGreaterEqual(len(prompts), 1)
        self.assertIn("description", prompts[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
