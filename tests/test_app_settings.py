from __future__ import annotations

import importlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from api.services import app_settings


class FakeCursor:
    def __init__(self, fetch_rows=None):
        self.fetch_rows = list(fetch_rows or [])
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))

    def fetchall(self):
        return list(self.fetch_rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self, fetch_rows=None):
        self.cursor_obj = FakeCursor(fetch_rows=fetch_rows)
        self.commit_count = 0

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def close(self):
        return None


class AppSettingsTests(unittest.TestCase):
    def test_load_settings_env_targets_repo_dotenv(self):
        with patch.object(app_settings, "load_dotenv") as mock_load_dotenv:
            app_settings.load_settings_env()

        mock_load_dotenv.assert_called_once_with(
            Path(app_settings.__file__).resolve().parents[2] / ".env",
            override=False,
        )

    def test_resolve_settings_precedence(self):
        with patch.dict(os.environ, {"OLLAMA_HOST": "http://env-host:11434"}, clear=True):
            with patch.object(
                app_settings,
                "_fetch_setting_rows",
                return_value={
                    "labeling.provider": {
                        "key": "labeling.provider",
                        "raw_value": "openai",
                        "source": "admin_ui",
                        "updated_at": None,
                        "updated_by": "admin",
                    },
                    "public_api.api_key": {
                        "key": "public_api.api_key",
                        "raw_value": None,
                        "source": "cleared",
                        "updated_at": None,
                        "updated_by": "admin",
                    },
                },
            ):
                resolved = app_settings.resolve_settings(
                    keys=["ollama.host", "labeling.provider", "public_api.api_key", "scoring.shap_max_items"],
                    overrides={"ollama.host": "http://override-host:11434"},
                )

        self.assertEqual(resolved["ollama.host"].value, "http://override-host:11434")
        self.assertEqual(resolved["ollama.host"].source, app_settings.OVERRIDE_SOURCE)
        self.assertEqual(resolved["labeling.provider"].value, "openai")
        self.assertEqual(resolved["labeling.provider"].source, "admin_ui")
        self.assertIsNone(resolved["public_api.api_key"].value)
        self.assertEqual(resolved["public_api.api_key"].source, "cleared")
        self.assertEqual(resolved["scoring.shap_max_items"].value, 100)
        self.assertEqual(resolved["scoring.shap_max_items"].source, app_settings.DEFAULT_SOURCE)

    def test_bootstrap_settings_from_env_inserts_only_missing_keys(self):
        conn = FakeConnection(fetch_rows=[{"key": "public_api.api_key"}])
        with patch.dict(
            os.environ,
            {
                "TAUTULLI_API_URL": "https://tautulli.example.com/api/v2",
                "PUBLIC_API_KEY": "11111111-1111-1111-1111-111111111111",
            },
            clear=True,
        ):
            app_settings.bootstrap_settings_from_env(conn)

        inserts = [entry for entry in conn.cursor_obj.executed if "INSERT INTO public.app_settings" in entry[0]]
        self.assertEqual(len(inserts), 1)
        self.assertEqual(
            inserts[0][1],
            ("tautulli.api_url", "https://tautulli.example.com/api/v2", app_settings.ENV_SOURCE),
        )
        self.assertEqual(conn.commit_count, 1)

    def test_get_settings_payload_masks_secret(self):
        definition = app_settings.get_setting_definition("public_api.api_key")
        with patch.object(
            app_settings,
            "resolve_settings",
            return_value={
                "public_api.api_key": app_settings.EffectiveSetting(
                    definition=definition,
                    value="11111111-1111-1111-1111-111111111111",
                    raw_value="11111111-1111-1111-1111-111111111111",
                    source="admin_ui",
                    updated_at=None,
                    updated_by="admin",
                    has_value=True,
                )
            },
        ):
            with patch.object(app_settings, "SETTING_DEFINITIONS", (definition,)):
                with patch.object(
                    app_settings,
                    "SECTION_DEFINITIONS",
                    ({"key": "public_api", "label": "Public API"},),
                ):
                    payload = app_settings.get_settings_payload()

        self.assertIsNone(payload[0]["fields"][0]["value"])
        self.assertTrue(payload[0]["fields"][0]["masked_value"].endswith("1111"))

    def test_save_settings_upserts_updates_and_clears(self):
        conn = FakeConnection()
        with patch.object(app_settings, "connect_db", return_value=conn):
            app_settings.save_settings(
                updates={"ollama.timeout_s": "45", "embeddings.enable_media": False},
                clear_keys=["public_api.api_key"],
                updated_by="admin",
            )

        inserts = [entry for entry in conn.cursor_obj.executed if "INSERT INTO public.app_settings" in entry[0]]
        clear_insert = next(entry for entry in inserts if entry[1][0] == "public_api.api_key")
        timeout_insert = next(entry for entry in inserts if entry[1][0] == "ollama.timeout_s")
        bool_insert = next(entry for entry in inserts if entry[1][0] == "embeddings.enable_media")

        self.assertEqual(clear_insert[1], ("public_api.api_key", app_settings.CLEARED_SOURCE, "admin"))
        self.assertEqual(timeout_insert[1], ("ollama.timeout_s", "45", app_settings.ADMIN_SOURCE, "admin"))
        self.assertEqual(bool_insert[1], ("embeddings.enable_media", "false", app_settings.ADMIN_SOURCE, "admin"))
        self.assertEqual(conn.commit_count, 1)

    def test_digest_setting_validation(self):
        self.assertEqual(
            app_settings.parse_value(app_settings.get_setting_definition("digest.send_time"), "09:45"),
            "09:45",
        )
        self.assertEqual(
            app_settings.parse_value(app_settings.get_setting_definition("digest.timezone"), "America/Chicago"),
            "America/Chicago",
        )
        self.assertEqual(
            app_settings.parse_value(app_settings.get_setting_definition("smtp.from_email"), "alerts@example.com"),
            "alerts@example.com",
        )

        with self.assertRaises(app_settings.SettingsValidationError):
            app_settings.parse_value(app_settings.get_setting_definition("digest.send_time"), "25:00")

        with self.assertRaises(app_settings.SettingsValidationError):
            app_settings.parse_value(app_settings.get_setting_definition("digest.timezone"), "Mars/Olympus")

        with self.assertRaises(app_settings.SettingsValidationError):
            app_settings.parse_value(app_settings.get_setting_definition("smtp.from_email"), "Example <alerts@example.com>")

    def test_consumer_defaults_and_overrides(self):
        settings_map = {
            "labeling.provider": "ollama",
            "labeling.openai_model": "gpt-4o-mini",
            "labeling.ollama_model": "gemma3:12b",
            "ollama.host": "http://ollama.internal:11434",
            "ollama.timeout_s": 55,
            "labeling.default_fetch_items": 22,
            "scoring.shap_max_items": 321,
            "scoring.shap_raw_min_dims": 7,
            "scoring.shap_raw_max_dims": 17,
            "scoring.shap_raw_cumabs_target": 0.82,
            "scoring.shap_agg_top_dims": 61,
            "scoring.shap_prune_days": 9,
            "scoring.watched_engagement_threshold": 0.73,
            "training.watch_embed_min_engagement": 0.64,
        }

        def fake_get_setting_value(key, default=None, overrides=None):
            return settings_map.get(key, default)

        with patch("api.services.app_settings.get_setting_value", side_effect=fake_get_setting_value):
            with patch("api.db.connection.get_database_url", return_value="postgresql://example/test"):
                gpt_utils = importlib.reload(importlib.import_module("gpt_utils"))
                score_model = importlib.reload(importlib.import_module("score_model"))
                fetch_tautulli_data = importlib.reload(importlib.import_module("fetch_tautulli_data"))

        self.assertEqual(gpt_utils.DEFAULT_FETCH_ITEMS, 22)
        self.assertEqual(gpt_utils.resolve_label_backend(), ("ollama", "gemma3:12b"))
        self.assertEqual(gpt_utils.resolve_label_backend("openai", "gpt-4.1-mini"), ("openai", "gpt-4.1-mini"))
        self.assertEqual(score_model.SHAP_MAX_ITEMS, 321)
        self.assertEqual(score_model.WATCHED_ENGAGEMENT_THRESHOLD, 0.73)
        self.assertEqual(fetch_tautulli_data.get_embed_batch_size(), 128)


if __name__ == "__main__":
    unittest.main()
