from __future__ import annotations

import unittest
from unittest.mock import patch

import requests
from fastapi import HTTPException

from api.routes import admin_routes
from api.services.app_settings import SettingsValidationError


def _admin_user():
    return {"username": "admin", "is_admin": True}


class AdminSettingsRouteTests(unittest.TestCase):
    def test_require_admin_rejects_non_admin_users(self):
        with self.assertRaises(HTTPException) as raised:
            admin_routes.require_admin({"username": "viewer", "is_admin": False})

        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_settings_get_and_put(self):
        captured: dict[str, object] = {}

        def fake_save_settings(*, updates, clear_keys, updated_by):
            captured["updates"] = updates
            captured["clear_keys"] = clear_keys
            captured["updated_by"] = updated_by

        with patch.object(
            admin_routes,
            "get_settings_payload",
            return_value=[{"key": "connectivity", "label": "Connectivity", "fields": []}],
        ):
            with patch.object(admin_routes, "save_settings", side_effect=fake_save_settings):
                get_response = admin_routes.admin_get_settings(admin_user=_admin_user())
                put_response = admin_routes.admin_save_settings(
                    req=admin_routes.SettingsUpdateRequest(
                        updates={"ollama.timeout_s": 45},
                        clear_keys=["public_api.api_key"],
                    ),
                    admin_user=_admin_user(),
                )

        self.assertEqual(get_response["sections"][0]["key"], "connectivity")
        self.assertEqual(put_response["sections"][0]["label"], "Connectivity")
        self.assertEqual(
            captured,
            {
                "updates": {"ollama.timeout_s": 45},
                "clear_keys": ["public_api.api_key"],
                "updated_by": "admin",
            },
        )

    def test_admin_settings_put_rejects_validation_errors(self):
        with patch.object(admin_routes, "save_settings", side_effect=SettingsValidationError("bad value")):
            with self.assertRaises(HTTPException) as raised:
                admin_routes.admin_save_settings(
                    req=admin_routes.SettingsUpdateRequest(updates={"ollama.timeout_s": -1}),
                    admin_user=_admin_user(),
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "bad value")

    def test_admin_settings_test_endpoints(self):
        with patch.object(
            admin_routes,
            "test_tautulli_settings",
            return_value={"ok": True, "api_url": "https://t.example/api/v2", "user_count": 4},
        ):
            with patch.object(
                admin_routes,
                "test_ollama_settings",
                return_value={
                    "ok": True,
                    "host": "http://ollama.internal:11434",
                    "available_models": ["gemma3:12b"],
                    "missing_models": [],
                },
            ):
                tautulli_response = admin_routes.admin_test_tautulli(
                    req=admin_routes.SettingsTestRequest(updates={}),
                    admin_user=_admin_user(),
                )
                ollama_response = admin_routes.admin_test_ollama(
                    req=admin_routes.SettingsTestRequest(updates={}),
                    admin_user=_admin_user(),
                )

        self.assertEqual(tautulli_response["user_count"], 4)
        self.assertEqual(ollama_response["available_models"], ["gemma3:12b"])

    def test_admin_settings_test_endpoint_maps_upstream_failures(self):
        with patch.object(admin_routes, "test_ollama_settings", side_effect=requests.RequestException("boom")):
            with self.assertRaises(HTTPException) as raised:
                admin_routes.admin_test_ollama(
                    req=admin_routes.SettingsTestRequest(updates={}),
                    admin_user=_admin_user(),
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("Ollama test failed", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
