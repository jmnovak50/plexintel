from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
import smtplib

from api.services import digest_service


class DigestServiceTests(unittest.TestCase):
    @staticmethod
    def _user(username: str, *, is_admin: bool = False) -> dict:
        return {
            "user_id": abs(hash(username)) % 10_000 + 1,
            "username": username,
            "friendly_name": username.title(),
            "plex_email": f"{username}@example.com",
            "is_admin": is_admin,
        }

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
        self.assertIn('style="display:block;max-width:100%;width:auto;height:auto;', sanitized)

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
        self.assertIn('width="84"', rendered)
        self.assertIn("max-width:25%", rendered)

    def test_preview_poster_urls_use_digest_token_route(self):
        items = [
            {"rating_key": 101},
            {"rating_key": None},
        ]

        digest_service._decorate_items_with_preview_posters(
            items,
            unsubscribe_token="abc123",
        )

        self.assertEqual(
            items[0]["poster_src"],
            "/api/digest/posters/101?token=abc123",
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

    def test_digest_movie_recommendations_apply_display_threshold(self):
        executed: dict[str, object] = {}

        class FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, sql, params):
                executed["sql"] = sql
                executed["params"] = params

            def fetchall(self):
                return []

        class FakeConn:
            def cursor(self, *_, **__):
                return FakeCursor()

        rows = digest_service.fetch_top_movie_recommendations(
            FakeConn(),
            "member",
            5,
            0.70,
        )

        self.assertEqual(rows, [])
        self.assertIn("recs.predicted_probability >= %s", executed["sql"])
        self.assertEqual(executed["params"], ("member", "member", 0.70, 5))

    def test_digest_show_recommendations_apply_display_threshold(self):
        executed: dict[str, object] = {}

        class FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def execute(self, sql, params):
                executed["sql"] = sql
                executed["params"] = params

            def fetchall(self):
                return []

        class FakeConn:
            def cursor(self, *_, **__):
                return FakeCursor()

        rows = digest_service.fetch_top_show_recommendations(
            FakeConn(),
            "member",
            5,
            0.70,
        )

        self.assertEqual(rows, [])
        self.assertIn("sr.rollup_score >= %s", executed["sql"])
        self.assertEqual(executed["params"], ("member", "member", 0.70, 5))

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

    def test_test_send_all_admins_renders_each_admins_own_digest(self):
        sample_user = self._user("sample-user")
        admin_one = self._user("admin-one", is_admin=True)
        admin_two = self._user("admin-two", is_admin=True)
        rendered_pairs: list[tuple[str, str]] = []

        class FakeConn:
            def close(self):
                return None

        def fake_fetch_digest_user(_conn, *, username=None, user_id=None):
            if username == "sample-user":
                return sample_user
            if username == "trigger-admin":
                return self._user("trigger-admin", is_admin=True)
            return None

        def fake_build_preview_payload(
            _conn,
            *,
            rendered_for_user,
            recipient_user,
            message_html,
            is_test,
            poster_mode,
        ):
            rendered_pairs.append((recipient_user["username"], rendered_for_user["username"]))
            return {
                "subject": "subject",
                "html": "<p>html</p>",
                "text": "text",
                "inline_images": [],
                "counts": {"movies": 1, "shows": 1},
                "message_html": message_html or "",
            }

        with patch.object(
            digest_service,
            "_get_digest_settings",
            return_value={"frequency": "weekly"},
        ):
            with patch.object(digest_service, "_get_smtp_settings", return_value={"from_name": "PlexIntel"}):
                with patch.object(digest_service, "connect_db", return_value=FakeConn()):
                    with patch.object(digest_service, "sync_users_from_tautulli", return_value=None):
                        with patch.object(digest_service, "_fetch_digest_user", side_effect=fake_fetch_digest_user):
                            with patch.object(digest_service, "_list_admin_users", return_value=[admin_one, admin_two]):
                                with patch.object(digest_service, "_build_subject", return_value="[TEST] PlexIntel Weekly Picks"):
                                    with patch.object(digest_service, "_record_run_start", return_value=7):
                                        with patch.object(digest_service, "_build_preview_payload", side_effect=fake_build_preview_payload):
                                            with patch.object(digest_service, "_send_email", return_value=None):
                                                with patch.object(digest_service, "_record_delivery", return_value=None):
                                                    with patch.object(digest_service, "_finalize_run", return_value=None):
                                                        result = digest_service.send_test_digest(
                                                            target="all_admins",
                                                            sample_username="sample-user",
                                                            triggered_by="trigger-admin",
                                                        )

        self.assertEqual(rendered_pairs, [("admin-one", "admin-one"), ("admin-two", "admin-two")])
        self.assertEqual(result["rendering_mode"], "per_admin_recipient")

    def test_scheduled_digest_renders_each_recipient_for_themselves(self):
        recipient_one = self._user("member-one")
        recipient_two = self._user("member-two")
        rendered_pairs: list[tuple[str, str]] = []

        class FakeConn:
            def close(self):
                return None

        def fake_build_preview_payload(
            _conn,
            *,
            rendered_for_user,
            recipient_user,
            message_html,
            is_test,
            poster_mode,
        ):
            rendered_pairs.append((recipient_user["username"], rendered_for_user["username"]))
            return {
                "subject": "subject",
                "html": "<p>html</p>",
                "text": "text",
                "inline_images": [],
                "counts": {"movies": 1, "shows": 1},
                "message_html": message_html or "",
            }

        with patch.object(
            digest_service,
            "_get_digest_settings",
            return_value={
                "enabled": True,
                "frequency": "weekly",
                "weekly_day": "monday",
                "send_time": "09:00",
                "timezone": "America/Chicago",
                "top_movies": 25,
                "top_shows": 10,
                "base_url": "http://localhost:8489",
            },
        ):
            with patch.object(digest_service, "_get_smtp_settings", return_value={"from_name": "PlexIntel"}):
                with patch.object(digest_service, "_get_schedule_slot", return_value={"schedule_key": "weekly:test", "due": True}):
                    with patch.object(digest_service, "connect_db", return_value=FakeConn()):
                        with patch.object(digest_service, "sync_users_from_tautulli", return_value=None):
                            with patch.object(digest_service, "_build_subject", return_value="PlexIntel Weekly Picks"):
                                with patch.object(digest_service, "_record_run_start", return_value=9):
                                    with patch.object(digest_service, "_list_digest_recipients", return_value=[recipient_one, recipient_two]):
                                        with patch.object(digest_service, "get_digest_content", return_value={"message_html": ""}):
                                            with patch.object(digest_service, "_build_preview_payload", side_effect=fake_build_preview_payload):
                                                with patch.object(digest_service, "_send_email", return_value=None):
                                                    with patch.object(digest_service, "_record_delivery", return_value=None):
                                                        with patch.object(digest_service, "_finalize_run", return_value=None):
                                                            result = digest_service.run_scheduled_digest(force=False, triggered_by="system")

        self.assertEqual(rendered_pairs, [("member-one", "member-one"), ("member-two", "member-two")])
        self.assertEqual(result["status"], "completed")


if __name__ == "__main__":
    unittest.main()
