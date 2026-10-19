import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import db
import stars
from web import create_app


def _repo(name: str, stars_count: str = "100") -> dict:
    return {
        "name": name,
        "description": "",
        "language": "Go",
        "total_stars": stars_count,
        "forks": "1",
        "stars_today": "5 stars today",
        "url": f"https://github.com/{name}",
    }


class _Response:
    def __init__(self, status: int, payload: dict | None = None, remaining: str = "50"):
        self.status_code = status
        self._payload = payload or {}
        self.headers = {"X-RateLimit-Remaining": remaining}

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []
        self.headers_seen: list[dict] = []

    def get(self, url, headers=None, timeout=None):
        name = url.split("/repos/", 1)[1]
        self.calls.append(name)
        self.headers_seen.append(headers or {})
        return self.responses[name]


class StarRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.configure(Path(self.tmp.name) / "test.db")
        db.init_db()
        db.save_snapshot("daily", [_repo("owner/a"), _repo("owner/gone")], datetime(2026, 8, 1, 9))
        db.save_snapshot("daily", [_repo("owner/a", "150")], datetime(2026, 8, 3, 9))
        db.save_snapshot("daily", [_repo("owner/old")], datetime(2026, 1, 1, 9))
        self.now = datetime(2026, 8, 20, 12)

    def tearDown(self):
        self.tmp.cleanup()

    def test_records_counts_and_skips_stale_and_checked_repos(self):
        session = _Session({
            "owner/a": _Response(200, {"stargazers_count": 400, "forks_count": 9}),
            "owner/gone": _Response(404),
        })
        result = stars.refresh_stars(token="t", session=session, now=self.now)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["missing"], 1)
        # owner/old has not trended within 90 days.
        self.assertEqual(sorted(session.calls), ["owner/a", "owner/gone"])
        self.assertEqual(session.headers_seen[0]["Authorization"], "Bearer t")
        self.assertEqual(db.get_star_series("owner/a"), [{"date": "2026-08-20", "stars": 400, "forks": 9}])
        # Same day again: nothing left to check.
        again = _Session({})
        self.assertEqual(stars.refresh_stars(session=again, now=self.now)["checked"], 0)
        self.assertEqual(again.calls, [])

    def test_stops_when_rate_limit_runs_out(self):
        session = _Session({
            "owner/a": _Response(403, remaining="0"),
            "owner/gone": _Response(403, remaining="0"),
        })
        result = stars.refresh_stars(session=session, now=self.now)
        self.assertTrue(result["rate_limited"])
        self.assertEqual(len(session.calls), 1)

    def test_api_counts_extend_the_chart_and_api(self):
        db.record_stars("owner/a", "2026-08-20", 400, 9)
        client = create_app().test_client()
        body = client.get("/repo/owner/a").get_data(as_text=True)
        self.assertIn("daily GitHub API counts", body)
        self.assertIn("2026-08-20", body)
        data = client.get("/api/v1/repos/owner/a").get_json()["data"]
        self.assertEqual(data["star_history"][-1]["stars"], 400)


if __name__ == "__main__":
    unittest.main()
