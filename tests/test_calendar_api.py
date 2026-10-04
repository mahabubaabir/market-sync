import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

import calendar_api


class CalendarApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cache_dir = self.tmp.name
        self.news_cache = os.path.join(cache_dir, "news_events.json")
        self.legacy_cache = os.path.join(cache_dir, "calendar.json")
        self._patchers = [
            patch.object(calendar_api, "CACHE_DIR", cache_dir),
            patch.object(calendar_api, "CACHE_PATH", self.news_cache),
            patch.object(calendar_api, "LEGACY_NEWS_CACHE_PATH", self.legacy_cache),
        ]
        for p in self._patchers:
            p.start()
            self.addCleanup(p.stop)

    def _write_cache(self, path, payload):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        now_ts = datetime.now().timestamp()
        os.utime(path, (now_ts, now_ts))

    def test_fresh_legacy_cache_does_not_force_network(self):
        event = {
            "title": "CPI",
            "country": "USD",
            "currency": "USD",
            "date_utc": "2026-10-05T12:30:00+00:00",
            "impact": "High",
            "forecast": "",
            "previous": "",
            "actual": "",
        }
        self._write_cache(self.legacy_cache, [event])

        with patch.object(calendar_api, "HAS_REQUESTS", True),              patch.object(calendar_api.requests, "get") as get:
            events, from_cache, note = calendar_api.fetch_events(cache_ttl_min=15)

        self.assertEqual(events, [event])
        self.assertTrue(from_cache)
        self.assertIn("cache", note)
        get.assert_not_called()

    def test_unknown_impact_is_rejected(self):
        item = {
            "title": "Surprise",
            "country": "USD",
            "date": "2026-10-05T12:30:00Z",
            "impact": "Extreme",
        }
        self.assertIsNone(calendar_api._normalize(item))

    def test_malformed_feed_payload_falls_back_to_cache(self):
        event = {
            "title": "CPI",
            "country": "USD",
            "currency": "USD",
            "date_utc": "2026-10-05T12:30:00+00:00",
            "impact": "High",
            "forecast": "",
            "previous": "",
            "actual": "",
        }
        self._write_cache(self.news_cache, [event])

        response = unittest.mock.Mock()
        response.json.return_value = {"unexpected": "object"}
        response.raise_for_status.return_value = None

        with patch.object(calendar_api, "HAS_REQUESTS", True),              patch.object(calendar_api.requests, "get", return_value=response):
            events, from_cache, note = calendar_api.fetch_events(force_refresh=True)

        self.assertEqual(events, [event])
        self.assertTrue(from_cache)
        self.assertIn("ValueError", note)


if __name__ == "__main__":
    unittest.main()
