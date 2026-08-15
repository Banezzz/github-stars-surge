import unittest
from datetime import datetime

from period import format_period_label, parse_count, period_bounds, period_key


class PeriodKeyTests(unittest.TestCase):
    def test_daily_key(self):
        when = datetime(2026, 8, 15, 10, 0)
        self.assertEqual(period_key("daily", when), "2026-08-15")

    def test_weekly_key_uses_iso_week(self):
        when = datetime(2026, 8, 15, 10, 0)
        self.assertEqual(period_key("weekly", when), "2026-W33")

    def test_monthly_key(self):
        when = datetime(2026, 8, 15, 10, 0)
        self.assertEqual(period_key("monthly", when), "2026-08")

    def test_unknown_range_raises(self):
        with self.assertRaises(ValueError):
            period_key("yearly", datetime(2026, 8, 15))


class PeriodLabelTests(unittest.TestCase):
    def test_weekly_bounds(self):
        start, end = period_bounds("weekly", "2026-W33")
        self.assertEqual(start.date().isoformat(), "2026-08-10")
        self.assertEqual(end.date().isoformat(), "2026-08-17")

    def test_weekly_label(self):
        label = format_period_label("weekly", "2026-W33")
        self.assertIn("2026-W33", label)
        self.assertIn("Aug", label)

    def test_monthly_label(self):
        self.assertEqual(format_period_label("monthly", "2026-08"), "August 2026")


class ParseCountTests(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(parse_count("1,234"), 1234)

    def test_stars_this_week(self):
        self.assertEqual(parse_count("123 stars this week"), 123)

    def test_empty(self):
        self.assertIsNone(parse_count(""))
        self.assertIsNone(parse_count(None))


if __name__ == "__main__":
    unittest.main()
