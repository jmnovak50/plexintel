from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from api.services import digest_service


class DigestServiceTests(unittest.TestCase):
    def test_sanitize_rich_html_strips_unsafe_tags_and_urls(self):
        raw_html = """
            <p>Hello <strong>there</strong></p>
            <script>alert('x')</script>
            <a href="javascript:alert(1)">bad</a>
            <a href="https://example.com">good</a>
            <img src="data:image/png;base64,AAAA" alt="bad" />
            <img src="https://cdn.example.com/poster.png" alt="good" />
        """

        sanitized = digest_service.sanitize_rich_html(raw_html)

        self.assertIn("<strong>there</strong>", sanitized)
        self.assertNotIn("<script>", sanitized)
        self.assertNotIn("javascript:alert", sanitized)
        self.assertIn('href="https://example.com"', sanitized)
        self.assertNotIn("data:image", sanitized)
        self.assertIn('src="https://cdn.example.com/poster.png"', sanitized)

    def test_html_to_plain_text_preserves_lists(self):
        rendered = digest_service.html_to_plain_text("<p>Intro</p><ul><li>One</li><li>Two</li></ul>")
        self.assertIn("Intro", rendered)
        self.assertIn("- One", rendered)
        self.assertIn("- Two", rendered)

    def test_schedule_slot_uses_latest_daily_slot(self):
        now = datetime(2026, 4, 15, 8, 30, tzinfo=ZoneInfo("America/Chicago"))
        with patch.object(
            digest_service,
            "_get_digest_settings",
            return_value={
                "enabled": True,
                "frequency": "daily",
                "weekly_day": "monday",
                "send_time": "09:00",
                "timezone": "America/Chicago",
                "top_movies": 25,
                "top_shows": 10,
                "base_url": "http://localhost:8489",
            },
        ):
            slot = digest_service._get_schedule_slot(now)

        self.assertEqual(slot["schedule_key"], "daily:2026-04-14:09:00:America/Chicago")

    def test_run_scheduled_digest_returns_disabled_when_feature_off(self):
        with patch.object(
            digest_service,
            "_get_digest_settings",
            return_value={
                "enabled": False,
                "frequency": "weekly",
                "weekly_day": "monday",
                "send_time": "09:00",
                "timezone": "America/Chicago",
                "top_movies": 25,
                "top_shows": 10,
                "base_url": "http://localhost:8489",
            },
        ):
            result = digest_service.run_scheduled_digest(force=False, triggered_by="test")

        self.assertEqual(result, {"status": "disabled"})


if __name__ == "__main__":
    unittest.main()
