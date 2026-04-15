from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api.routes import digest_routes
from api.services.digest_service import DigestConfigError


def _admin_user():
    return {"user_id": 1, "username": "admin", "friendly_name": "Admin", "plex_email": "admin@example.com", "is_admin": True}


def _member_user():
    return {"user_id": 2, "username": "member", "friendly_name": "Member", "plex_email": "member@example.com", "is_admin": False}


class DigestRoutesTests(unittest.TestCase):
    def test_admin_digest_content_and_history_routes(self):
        with patch.object(
            digest_routes,
            "get_digest_content",
            return_value={"message_html": "<p>Hello</p>", "updated_at": None, "updated_by": "admin"},
        ):
            with patch.object(
                digest_routes,
                "save_digest_content",
                return_value={"message_html": "<p>Hello</p>", "updated_at": None, "updated_by": "admin"},
            ):
                with patch.object(
                    digest_routes,
                    "get_digest_history",
                    return_value={"runs": [{"run_id": 1}], "deliveries": [{"delivery_id": 1}]},
                ):
                    get_response = digest_routes.admin_get_digest_content(admin_user=_admin_user())
                    put_response = digest_routes.admin_save_digest_content(
                        digest_routes.DigestContentUpdateRequest(message_html="<p>Hello</p>"),
                        admin_user=_admin_user(),
                    )
                    history_response = digest_routes.admin_digest_history(admin_user=_admin_user())

        self.assertEqual(get_response["message_html"], "<p>Hello</p>")
        self.assertEqual(put_response["updated_by"], "admin")
        self.assertEqual(history_response["runs"][0]["run_id"], 1)

    def test_preview_and_test_send_routes_map_validation_errors(self):
        with patch.object(
            digest_routes,
            "generate_digest_preview",
            side_effect=DigestConfigError("bad preview"),
        ):
            with self.assertRaises(HTTPException) as preview_error:
                digest_routes.admin_preview_digest(
                    digest_routes.DigestPreviewRequest(sample_username="user"),
                    admin_user=_admin_user(),
                )

        with patch.object(
            digest_routes,
            "send_test_digest",
            side_effect=DigestConfigError("bad smtp"),
        ):
            with self.assertRaises(HTTPException) as send_error:
                digest_routes.admin_test_send_digest(
                    digest_routes.DigestTestSendRequest(target="self", sample_username="user"),
                    admin_user=_admin_user(),
                )

        self.assertEqual(preview_error.exception.status_code, 400)
        self.assertEqual(send_error.exception.status_code, 400)

    def test_member_preference_and_unsubscribe_routes(self):
        with patch.object(
            digest_routes,
            "get_user_email_preferences",
            return_value={"digest_enabled": True},
        ):
            prefs = digest_routes.my_email_preferences(user=_member_user())

        with patch.object(
            digest_routes,
            "update_user_email_preferences",
            return_value={"digest_enabled": False},
        ):
            updated = digest_routes.update_my_email_preferences(
                digest_routes.EmailPreferenceUpdateRequest(digest_enabled=False),
                user=_member_user(),
            )

        with patch.object(
            digest_routes,
            "get_unsubscribe_target",
            return_value={
                "username": "member",
                "friendly_name": "Member",
                "plex_email": "member@example.com",
                "digest_enabled": True,
            },
        ):
            unsubscribe_details = digest_routes.get_unsubscribe_details("token")

        with patch.object(
            digest_routes,
            "unsubscribe_by_token",
            return_value={
                "username": "member",
                "friendly_name": "Member",
                "plex_email": "member@example.com",
                "digest_enabled": False,
            },
        ):
            unsubscribed = digest_routes.unsubscribe_via_link("token")

        self.assertTrue(prefs["digest_enabled"])
        self.assertFalse(updated["digest_enabled"])
        self.assertEqual(unsubscribe_details["display_name"], "Member")
        self.assertFalse(unsubscribed["digest_enabled"])

    def test_public_digest_poster_route_requires_valid_token(self):
        with patch.object(digest_routes, "get_unsubscribe_target", return_value=None):
            with self.assertRaises(HTTPException) as error:
                digest_routes.get_public_digest_poster(101, token="bad-token")

        self.assertEqual(error.exception.status_code, 404)

    def test_public_digest_poster_route_returns_image_payload(self):
        with patch.object(
            digest_routes,
            "get_unsubscribe_target",
            return_value={"username": "member", "friendly_name": "Member", "plex_email": "member@example.com"},
        ):
            with patch.object(
                digest_routes,
                "fetch_poster_image_for_rating_key",
                return_value={"content": b"image-bytes", "content_type": "image/jpeg"},
            ):
                response = digest_routes.get_public_digest_poster(101, token="good-token")

        self.assertEqual(response.media_type, "image/jpeg")
        self.assertEqual(response.body, b"image-bytes")


if __name__ == "__main__":
    unittest.main()
