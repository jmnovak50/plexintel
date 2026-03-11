from __future__ import annotations

import unittest
from unittest.mock import patch

import requests
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import main
from api.routes import admin_routes
from api.services.app_settings import SettingsValidationError


def _admin_user():
    return {"username": "admin", "is_admin": True}


def _deny_admin():
    raise HTTPException(status_code=403, detail="Admin access required")


class AdminSettingsRouteTests(unittest.TestCase):
    def tearDown(self):
        main.app.dependency_overrides.clear()

    def test_admin_settings_requires_admin(self):
        with patch.object(main, "ensure_app_schema", return_value=None):
            main.app.dependency_overrides[admin_routes.require_admin] = _deny_admin
            with TestClient(main.app) as client:
                response = client.get("/api/admin/settings")

        self.assertEqual(response.status_code, 403)

    def test_admin_settings_get_and_put(self):
        captured: dict[str, object] = {}

        def fake_save_settings(*, updates, clear_keys, updated_by):
            captured["updates"] = updates
            captured["clear_keys"] = clear_keys
            captured["updated_by"] = updated_by

        with patch.object(main, "ensure_app_schema", return_value=None):
            with patch.object(
                admin_routes,
                "get_settings_payload",
                return_value=[{"key": "connectivity", "label": "Connectivity", "fields": []}],
            ):
                with patch.object(admin_routes, "save_settings", side_effect=fake_save_settings):
                    main.app.dependency_overrides[admin_routes.require_admin] = _admin_user
                    with TestClient(main.app) as client:
                        get_response = client.get("/api/admin/settings")
                        put_response = client.put(
                            "/api/admin/settings",
                            json={"updates": {"ollama.timeout_s": 45}, "clear_keys": ["public_api.api_key"]},
                        )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(
            captured,
            {
                "updates": {"ollama.timeout_s": 45},
                "clear_keys": ["public_api.api_key"],
                "updated_by": "admin",
            },
        )

    def test_admin_settings_put_rejects_validation_errors(self):
        with patch.object(main, "ensure_app_schema", return_value=None):
            with patch.object(admin_routes, "save_settings", side_effect=SettingsValidationError("bad value")):
                main.app.dependency_overrides[admin_routes.require_admin] = _admin_user
                with TestClient(main.app) as client:
                    response = client.put("/api/admin/settings", json={"updates": {"ollama.timeout_s": -1}})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "bad value")

    def test_admin_settings_test_endpoints(self):
        with patch.object(main, "ensure_app_schema", return_value=None):
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
                    main.app.dependency_overrides[admin_routes.require_admin] = _admin_user
                    with TestClient(main.app) as client:
                        tautulli_response = client.post("/api/admin/settings/test/tautulli", json={"updates": {}})
                        ollama_response = client.post("/api/admin/settings/test/ollama", json={"updates": {}})

        self.assertEqual(tautulli_response.status_code, 200)
        self.assertEqual(tautulli_response.json()["user_count"], 4)
        self.assertEqual(ollama_response.status_code, 200)
        self.assertEqual(ollama_response.json()["available_models"], ["gemma3:12b"])

    def test_admin_settings_test_endpoint_maps_upstream_failures(self):
        with patch.object(main, "ensure_app_schema", return_value=None):
            with patch.object(admin_routes, "test_ollama_settings", side_effect=requests.RequestException("boom")):
                main.app.dependency_overrides[admin_routes.require_admin] = _admin_user
                with TestClient(main.app) as client:
                    response = client.post("/api/admin/settings/test/ollama", json={"updates": {}})

        self.assertEqual(response.status_code, 502)
        self.assertIn("Ollama test failed", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
