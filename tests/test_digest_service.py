from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import smtplib

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

    def test_render_item_grid_includes_table_cells_and_posters(self):
        rendered = digest_service._render_item_grid(
            [
                {
                    "title": "Movie One",
                    "year": 2024,
                    "genres": "Drama",
                    "semantic_themes": "Character Focus",
                    "predicted_probability": 0.985,
                    "poster_src": "/api/posters/101",
                },
                {
                    "title": "Movie Two",
                    "year": 2023,
                    "genres": "Comedy",
                    "predicted_probability": 0.973,
                    "poster_src": "/api/posters/102",
                },
            ],
            "Top Movies",
        )

        self.assertIn("<table", rendered)
        self.assertIn("/api/posters/101", rendered)
        self.assertIn("Movie One", rendered)
        self.assertIn("Top Movies", rendered)

    def test_public_poster_urls_use_base_url_and_token(self):
        items = [
            {"rating_key": 101},
            {"rating_key": None},
        ]

        digest_service._decorate_items_with_public_posters(
            items,
            base_url="https://plexintel.example.com/",
            unsubscribe_token="abc123",
        )

        self.assertEqual(
            items[0]["poster_src"],
            "https://plexintel.example.com/api/digest/posters/101?token=abc123",
        )
        self.assertIsNone(items[1]["poster_src"])

    def test_describe_smtp_auth_error_mentions_google_guidance(self):
        error = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

        message = digest_service._describe_smtp_auth_error(error)

        self.assertIn("App Password", message)
        self.assertIn("normal Google account password", message)

    def test_describe_smtp_data_error_mentions_size_limit(self):
        error = smtplib.SMTPDataError(552, b"5.3.4 Your message exceeded Google's message size limits")

        message = digest_service._describe_smtp_data_error(error)

        self.assertIn("exceeded the provider size limit", message)
        self.assertIn("resized before sending", message)

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
