import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import db
from web import create_app


def _repo(name: str, description: str, language: str = "Python", stars: str = "1000") -> dict:
    return {
        "name": name,
        "description": description,
        "language": language,
        "total_stars": stars,
        "forks": "10",
        "stars_today": "50 stars today",
        "url": f"https://github.com/{name}",
    }


class _SeededDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()
        db.save_snapshot(
            "daily",
            [
                _repo("facebook/create-react-app", "Set up a modern web app", "JavaScript", "100000"),
                _repo("x/real-time-chat", "Realtime chat server", "Go", "5000"),
                _repo("someone/reverse-engineering-anything", "Point an agent at any binary", stars="900"),
            ],
            datetime(2026, 8, 3, 9, 0),
        )
        db.save_snapshot(
            "weekly",
            [
                _repo("Wan-Video/Wan2.2", "Open video generative models", stars="8000"),
                _repo("z/VideoCrafter", "开源视频生成模型", stars="3000"),
            ],
            datetime(2026, 8, 15, 9, 0),
        )
        db.save_snapshot(
            "daily",
            [_repo("someone/reverse-engineering-anything", "Point an agent at any binary", stars="1500")],
            datetime(2026, 8, 20, 9, 0),
        )

    def tearDown(self):
        self.tmp.cleanup()


class GlobalSearchTests(_SeededDb):
    def _names(self, query: str, **kwargs) -> list[str]:
        return [item["name"] for item in db.search_repos(query, **kwargs)["items"]]

    def test_acronym_finds_repo_ranked_first(self):
        names = self._names("REA")
        self.assertEqual(names[0], "someone/reverse-engineering-anything")
        # Substring noise ("create", "realtime") ranks below the acronym hit.
        self.assertNotIn("Wan-Video/Wan2.2", names)

    def test_words_match_across_separators(self):
        self.assertEqual(self._names("reverse engineering"), ["someone/reverse-engineering-anything"])
        self.assertEqual(self._names("reverseengineering"), ["someone/reverse-engineering-anything"])
        self.assertEqual(self._names("video crafter")[0], "z/VideoCrafter")

    def test_exact_full_name_and_owner(self):
        self.assertEqual(self._names("Wan-Video/Wan2.2"), ["Wan-Video/Wan2.2"])
        self.assertEqual(self._names("facebook"), ["facebook/create-react-app"])

    def test_description_words_and_cjk(self):
        self.assertEqual(self._names("generative models"), ["Wan-Video/Wan2.2"])
        self.assertEqual(self._names("视频"), ["z/VideoCrafter"])

    def test_tokens_are_anded(self):
        self.assertEqual(self._names("video chat"), [])

    def test_range_filter_and_sorts(self):
        self.assertEqual(self._names("video", time_range="daily"), [])
        names = self._names("a", sort="name")
        self.assertEqual(names, sorted(names))
        with self.assertRaises(ValueError):
            db.search_repos("x", sort="bogus")

    def test_cache_sees_new_snapshots(self):
        self.assertEqual(self._names("pocketbase"), [])
        db.save_snapshot(
            "monthly",
            [_repo("pocketbase/pocketbase", "Realtime backend in one file", "Go")],
            datetime(2026, 8, 31, 9, 0),
        )
        self.assertEqual(self._names("pocketbase"), ["pocketbase/pocketbase"])

    def test_suggestions_for_typos(self):
        suggestions = [item["name"] for item in db.suggest_repos("revers-enginering-anythin")]
        self.assertIn("someone/reverse-engineering-anything", suggestions)

    def test_last_seen_is_chronological_across_ranges(self):
        # "2026-W33" sorts after "2026-08-20" as a string but is older.
        history = db.get_repo_history("someone/reverse-engineering-anything")
        self.assertEqual(history["last_seen"], "2026-08-20")
        self.assertEqual(history["first_seen"], "2026-08-03")
        item = db.list_unique_repos(sort="last_seen")["items"][0]
        self.assertEqual(item["name"], "someone/reverse-engineering-anything")
        self.assertEqual(item["last_seen"], "2026-08-20")
        self.assertEqual(item["peak_stars"], 1500)


class SearchPageTests(_SeededDb):
    def setUp(self):
        super().setUp()
        self.client = create_app().test_client()

    def test_search_page_ranks_acronym(self):
        response = self.client.get("/search?q=REA")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("reverse-engineering-anything", body)
        self.assertLess(body.index("reverse-engineering-anything"), body.index("create-react-app"))
        self.assertIn('href="/repo/someone/reverse-engineering-anything?lang=en"', body)

    def test_search_page_empty_state_offers_github(self):
        body = self.client.get("/search?q=revers-enginering-anythin").get_data(as_text=True)
        self.assertIn("Did you mean", body)
        self.assertIn("github.com/search", body)

    def test_search_landing_and_language_browse(self):
        landing = self.client.get("/search?lang=zh").get_data(as_text=True)
        self.assertIn("全库搜索", landing)
        browse = self.client.get("/search?language=Go").get_data(as_text=True)
        self.assertIn('href="/repo/x/real-time-chat?lang=zh"', browse)
        self.assertNotIn("Wan2.2", browse)

    def test_repo_page_shows_history_and_chart(self):
        response = self.client.get("/repo/someone/reverse-engineering-anything")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Board appearances", body)
        self.assertIn("2026-08-20", body)
        self.assertIn('class="chart"', body)
        self.assertIn('href="/?range=daily&amp;period=2026-08-20&amp;lang=en"', body)

    def test_repo_page_not_found(self):
        response = self.client.get("/repo/nobody/nothing")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not in the trending history", response.get_data(as_text=True))

    def test_header_search_on_every_page(self):
        for path in ("/", "/docs", "/search"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn('id="global-q"', body, path)

    def test_api_search_defaults_to_relevance(self):
        payload = self.client.get("/api/v1/search?q=REA").get_json()
        self.assertEqual(payload["sort"], "relevance")
        self.assertEqual(payload["data"][0]["name"], "someone/reverse-engineering-anything")
        self.assertEqual(self.client.get("/api/v1/search?q=REA&sort=bogus").status_code, 400)
        named = self.client.get("/api/v1/search?q=a&sort=name").get_json()
        names = [item["name"] for item in named["data"]]
        self.assertEqual(names, sorted(names))


if __name__ == "__main__":
    unittest.main()
