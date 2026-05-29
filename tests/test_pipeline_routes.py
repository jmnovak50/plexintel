from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api.routes import pipeline_admin_routes


def _admin_user():
    return {"user_id": 1, "username": "admin", "friendly_name": "Admin", "plex_email": None, "is_admin": True}


class PipelineAdminRoutesTests(unittest.TestCase):
    def test_list_runs(self):
        fake_runs = {
            "runs": [
                {
                    "run_id": 1,
                    "delivery_type": "manual",
                    "schedule_key": None,
                    "triggered_by": "admin",
                    "status": "success",
                    "notes": None,
                    "cancel_requested_at": None,
                    "cancel_requested_by": None,
                    "last_heartbeat_at": None,
                    "current_stage_key": None,
                    "current_pid": None,
                    "started_at": None,
                    "completed_at": None,
                    "stages": [],
                }
            ]
        }
        with patch.object(pipeline_admin_routes, "get_pipeline_runs", return_value=fake_runs):
            resp = pipeline_admin_routes.admin_list_pipeline_runs(limit=10, admin_user=_admin_user())

        self.assertEqual(resp["runs"][0]["run_id"], 1)
        self.assertEqual(resp["requested_by"], "admin")

    def test_get_run_not_found(self):
        with patch.object(pipeline_admin_routes, "get_pipeline_run", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                pipeline_admin_routes.admin_get_pipeline_run(run_id=999, admin_user=_admin_user())
            self.assertEqual(ctx.exception.status_code, 404)

    @patch.object(pipeline_admin_routes.threading, "Thread")
    def test_trigger_returns_accepted(self, mock_thread):
        mock_instance = mock_thread.return_value
        resp = pipeline_admin_routes.admin_trigger_pipeline(admin_user=_admin_user())
        self.assertEqual(resp["status"], "accepted")
        mock_thread.assert_called_once()
        mock_instance.start.assert_called_once()

    def test_cancel_run_returns_accepted(self):
        with patch.object(
            pipeline_admin_routes,
            "request_pipeline_cancel",
            return_value={"status": "cancel_requested", "run_id": 12},
        ):
            resp = pipeline_admin_routes.admin_cancel_pipeline_run(
                run_id=12,
                admin_user=_admin_user(),
            )

        self.assertEqual(resp["status"], "cancel_requested")
        self.assertEqual(resp["run_id"], 12)

    def test_cancel_run_not_found(self):
        with patch.object(
            pipeline_admin_routes,
            "request_pipeline_cancel",
            return_value={"status": "not_found", "run_id": 99},
        ):
            with self.assertRaises(HTTPException) as ctx:
                pipeline_admin_routes.admin_cancel_pipeline_run(
                    run_id=99,
                    admin_user=_admin_user(),
                )

        self.assertEqual(ctx.exception.status_code, 404)

    def test_cancel_terminal_run_conflicts(self):
        with patch.object(
            pipeline_admin_routes,
            "request_pipeline_cancel",
            return_value={"status": "already_terminal", "run_id": 7, "run_status": "success"},
        ):
            with self.assertRaises(HTTPException) as ctx:
                pipeline_admin_routes.admin_cancel_pipeline_run(
                    run_id=7,
                    admin_user=_admin_user(),
                )

        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
