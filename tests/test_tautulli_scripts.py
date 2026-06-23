from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from api.services.tautulli_api import TautulliApiError, TautulliConfig
from scripts import tautulli_recently_added_sync, verify_tautulli_api


class TautulliVerifierTests(unittest.TestCase):
    def setUp(self):
        self.config = TautulliConfig(
            api_url="https://tautulli.example.com/api/v2",
            api_key="secret-key",
            base_url="https://tautulli.example.com",
        )

    def test_run_checks_verifies_read_only_endpoints_without_cache_clear(self):
        def fake_request(command, **kwargs):
            if command == "get_server_info":
                return {"pms_identifier": "server"}
            if command == "get_users":
                return {"users": [{"user_id": 1}]}
            if command == "get_library_names":
                return {"1": "Movies"}
            if command == "get_library_media_info":
                return {"data": [{"rating_key": 42, "title": "Arrival"}]}
            if command == "get_metadata":
                return {"rating_key": 42, "title": "Arrival"}
            raise AssertionError(f"unexpected command {command}")

        with patch.object(verify_tautulli_api, "resolve_tautulli_config", return_value=self.config):
            with patch.object(verify_tautulli_api, "tautulli_request", side_effect=fake_request):
                with patch.object(verify_tautulli_api, "delete_tautulli_cache") as mock_delete:
                    checks = verify_tautulli_api.run_checks()

        self.assertTrue(all(check.ok for check in checks))
        self.assertEqual([check.name for check in checks], [
            "get_server_info",
            "get_users",
            "get_library_names",
            "get_library_media_info",
            "get_metadata",
            "delete_cache",
        ])
        mock_delete.assert_not_called()
        self.assertIn("not requested", checks[-1].detail)

    def test_run_checks_can_include_explicit_cache_clear(self):
        def fake_request(command, **kwargs):
            responses = {
                "get_server_info": {"pms_identifier": "server"},
                "get_users": {"users": []},
                "get_library_names": [{"section_id": 1, "section_name": "Movies"}],
                "get_library_media_info": {"data": [{"rating_key": 42}]},
                "get_metadata": {"rating_key": 42, "title": "Arrival"},
            }
            return responses[command]

        with patch.object(verify_tautulli_api, "resolve_tautulli_config", return_value=self.config):
            with patch.object(verify_tautulli_api, "tautulli_request", side_effect=fake_request):
                with patch.object(verify_tautulli_api, "delete_tautulli_cache", return_value=None) as mock_delete:
                    checks = verify_tautulli_api.run_checks(include_cache_clear=True)

        self.assertTrue(all(check.ok for check in checks))
        mock_delete.assert_called_once()
        self.assertEqual(checks[-1].name, "delete_cache")
        self.assertIn("accepted", checks[-1].detail)

    def test_run_checks_stops_on_malformed_media_response(self):
        def fake_request(command, **kwargs):
            responses = {
                "get_server_info": {"pms_identifier": "server"},
                "get_users": {"users": []},
                "get_library_names": {"1": "Movies"},
                "get_library_media_info": {"data": []},
            }
            return responses[command]

        with patch.object(verify_tautulli_api, "resolve_tautulli_config", return_value=self.config):
            with patch.object(verify_tautulli_api, "tautulli_request", side_effect=fake_request):
                checks = verify_tautulli_api.run_checks()

        self.assertFalse(checks[-1].ok)
        self.assertEqual(checks[-1].name, "get_library_media_info")
        self.assertIn("no media rows", checks[-1].detail)


class TautulliRecentlyAddedSyncTests(unittest.TestCase):
    def setUp(self):
        self.config = TautulliConfig(
            api_url="https://tautulli.example.com/api/v2",
            api_key="secret-key",
            base_url="https://tautulli.example.com",
        )

    def test_open_lock_returns_none_when_lock_is_already_held(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / "sync.lock"
            first_lock = tautulli_recently_added_sync._open_lock(lock_path)
            try:
                self.assertIsNotNone(first_lock)
                second_lock = tautulli_recently_added_sync._open_lock(lock_path)
                self.assertIsNone(second_lock)
            finally:
                if first_lock is not None:
                    first_lock.close()

    def test_main_skips_when_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / "sync.lock"
            log_path = Path(tmp_dir) / "sync.log"
            first_lock = tautulli_recently_added_sync._open_lock(lock_path)
            try:
                self.assertIsNotNone(first_lock)
                with patch.dict("os.environ", {"PLEXINTEL_TAUTULLI_SYNC_LOG": str(log_path)}):
                    with patch.object(tautulli_recently_added_sync, "delete_tautulli_cache") as mock_delete:
                        result = tautulli_recently_added_sync.main([
                            "--debounce-seconds",
                            "0",
                            "--lock-path",
                            str(lock_path),
                        ])

                self.assertEqual(result, 0)
                mock_delete.assert_not_called()
                self.assertIn("already running", log_path.read_text(encoding="utf-8"))
            finally:
                if first_lock is not None:
                    first_lock.close()

    def test_main_clears_cache_then_runs_incremental_sync(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / "sync.lock"
            log_path = Path(tmp_dir) / "sync.log"
            log_text = ""
            with patch.dict("os.environ", {"PLEXINTEL_TAUTULLI_SYNC_LOG": str(log_path)}):
                with patch.object(
                    tautulli_recently_added_sync,
                    "_resolve_event_config",
                    return_value=self.config,
                ):
                    with patch.object(tautulli_recently_added_sync, "delete_tautulli_cache") as mock_delete:
                        with patch.object(
                            tautulli_recently_added_sync,
                            "run_incremental_sync",
                            return_value=0,
                        ) as mock_sync:
                            result = tautulli_recently_added_sync.main([
                                "--debounce-seconds",
                                "0",
                                "--lock-path",
                                str(lock_path),
                            ])
                            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        mock_delete.assert_called_once_with(config=self.config, timeout=30)
        mock_sync.assert_called_once()
        self.assertIn("Recently Added sync invoked", log_text)
        self.assertIn("Tautulli cache cleared", log_text)
        self.assertIn("PlexIntel incremental sync complete", log_text)

    def test_main_fails_without_running_sync_when_cache_clear_fails(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / "sync.lock"
            with patch.object(
                tautulli_recently_added_sync,
                "_resolve_event_config",
                return_value=self.config,
            ):
                with patch.object(
                    tautulli_recently_added_sync,
                    "delete_tautulli_cache",
                    side_effect=TautulliApiError("bad key"),
                ):
                    with patch.object(tautulli_recently_added_sync, "run_incremental_sync") as mock_sync:
                        result = tautulli_recently_added_sync.main([
                            "--debounce-seconds",
                            "0",
                            "--lock-path",
                            str(lock_path),
                        ])

        self.assertEqual(result, 1)
        mock_sync.assert_not_called()

    def test_run_incremental_sync_invokes_existing_ingestion_mode(self):
        completed = SimpleNamespace(returncode=7)

        with patch.object(
            tautulli_recently_added_sync.subprocess,
            "run",
            return_value=completed,
        ) as mock_run:
            result = tautulli_recently_added_sync.run_incremental_sync()

        self.assertEqual(result, 7)
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[-3:], [
            str(tautulli_recently_added_sync.REPO_ROOT / "fetch_tautulli_data.py"),
            "--mode",
            "incremental",
        ])
        self.assertEqual(mock_run.call_args.kwargs["cwd"], str(tautulli_recently_added_sync.REPO_ROOT))
        self.assertFalse(mock_run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
