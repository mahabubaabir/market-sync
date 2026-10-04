import unittest
from datetime import datetime, timezone

from config import get_market
from markets import market_status, nyse_early_close, nyse_holidays


class MarketCalendarTests(unittest.TestCase):
    def test_countdown_uses_absolute_time_across_dst(self):
        market = get_market("NEW_YORK")
        now = datetime(2026, 10, 30, 21, 0, tzinfo=timezone.utc)
        status = market_status(market, now)
        self.assertFalse(status["is_open"])
        self.assertEqual(
            status["next_at_utc"],
            datetime(2026, 11, 2, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(status["countdown"].total_seconds(), 64 * 3600)

    def test_nyse_2026_calendar_boundaries(self):
        holidays = nyse_holidays(2026)
        self.assertIn(datetime(2026, 7, 3).date(), holidays)
        self.assertIn(datetime(2026, 12, 25).date(), holidays)
        self.assertEqual(nyse_early_close(datetime(2026, 11, 27)), "13:00")
        self.assertEqual(nyse_early_close(datetime(2026, 12, 24)), "13:00")
        self.assertIsNone(nyse_early_close(datetime(2026, 7, 3)))

    def test_nyse_2028_new_year_exception(self):
        self.assertNotIn(datetime(2027, 12, 31).date(), nyse_holidays(2027))
        self.assertNotIn(datetime(2027, 12, 31).date(), nyse_holidays(2028))


if __name__ == "__main__":
    unittest.main()
