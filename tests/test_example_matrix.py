"""Hit every documented example path against the live history database."""

import unittest
from pathlib import Path

import db
from web import create_app


DOC_PATHS = [
    "/",
    "/docs",
    "/api",
    "/api/openapi.json",
    "/api/v1/overview",
    "/api/v1/prompts",
    "/api/v1/periods",
    "/api/v1/periods?range=daily",
    "/api/v1/periods?range=weekly",
    "/api/v1/periods?range=monthly",
    "/api/v1/snapshots/daily",
    "/api/v1/snapshots/weekly",
    "/api/v1/snapshots/monthly",
    "/api/v1/snapshots/weekly/2026-W35",
    "/api/v1/snapshots/monthly/2026-08",
    "/api/v1/repos?limit=1000",
    "/api/v1/repos?min_stars=5000&sort=peak_stars",
    "/api/v1/repos?fields=card&limit=1000",
    "/api/v1/repos?language=TypeScript&min_stars=1000&limit=1000",
    "/api/v1/repos?language=Python&min_stars=1000&limit=1000",
    "/api/v1/repos?sort=appearances",
    "/api/v1/repos?sort=first_seen",
    "/api/v1/repos?sort=last_seen",
    "/api/v1/repos?sort=name",
    "/api/v1/repos?range=weekly&period=2026-W35",
    "/api/v1/search?q=video+generation&limit=50",
    "/api/v1/search?q=video+generation&limit=100",
    "/api/v1/search?q=agent+harness&limit=1000",
    "/api/v1/repos/harry0703/MoneyPrinterTurbo",
    "/api/v1/repos/public-apis/public-apis",
]


class DocumentedExampleMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        live_db = Path(__file__).resolve().parents[1] / "trending_history.db"
        if not live_db.exists():
            raise unittest.SkipTest("live history database is not present")
        db.configure(live_db)
        db.init_db()
        cls.client = create_app().test_client()

    def test_every_documented_example_succeeds(self):
        failures = []
        for path in DOC_PATHS:
            response = self.client.get(path)
            if response.status_code != 200:
                failures.append(f"{response.status_code} {path}")
                continue
            if path.startswith("/api") and path != "/api/openapi.json":
                payload = response.get_json()
                if not payload or payload.get("ok") is not True:
                    failures.append(f"not ok {path}")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
