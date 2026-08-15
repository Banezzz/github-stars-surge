import unittest

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


if __name__ == "__main__":
    unittest.main()
