from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from api.services import pipeline_service


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.fetchone_results.pop(0)


class FakeConnection:
    def __init__(self, fetchone_results):
        self.fetchone_results = list(fetchone_results)
        self.executed = []
        self.commit_count = 0
        self.closed = False

    def cursor(self, *args, **kwargs):
        return FakeCursor(self)

    def commit(self):
        self.commit_count += 1

    def close(self):
        self.closed = True


class PipelineScheduleSlotTests(unittest.TestCase):
    def test_daily_slot_schedule_key_format(self):
        with patch.object(pipeline_service, "get_setting_value") as mock_gsv:
            def gsv(key, default=None):
                m = {
                    "pipeline.frequency": "daily",
                    "pipeline.weekly_day": "sunday",
                    "pipeline.run_time": "03:00",
                    "pipeline.timezone": "America/Chicago",
                }
                return m.get(key, default)

            mock_gsv.side_effect = gsv
            fixed = datetime(2026, 4, 28, 10, 30, 0, tzinfo=ZoneInfo("America/Chicago"))
            slot = pipeline_service.get_pipeline_schedule_slot(fixed)
            self.assertIn("daily:", slot["schedule_key"])
            self.assertIn("03:00", slot["schedule_key"])
            self.assertIn("America/Chicago", slot["schedule_key"])
            self.assertEqual(slot["timezone"], "America/Chicago")

    def test_run_scheduled_pipeline_disabled(self):
        with patch.object(pipeline_service, "get_setting_value", return_value=False):
            out = pipeline_service.run_scheduled_pipeline(triggered_by="test")
            self.assertEqual(out["status"], "disabled")


class PipelineRunTests(unittest.TestCase):
    def test_run_pipeline_reads_named_advisory_lock_result(self):
        conn = FakeConnection(
            [
                {"acquired": True},
                {"run_id": 123},
                {"status": "success"},
            ]
        )

        with patch.object(pipeline_service, "connect_db", return_value=conn):
            with patch.object(pipeline_service, "build_pipeline_stages", return_value=[]):
                out = pipeline_service.run_pipeline(
                    delivery_type="manual",
                    triggered_by="admin",
                    schedule_key=None,
                )

        self.assertEqual(out, {"status": "success", "run_id": 123})
        self.assertTrue(conn.closed)
        executed_sql = " ".join(sql for sql, _params in conn.executed)
        self.assertIn("pg_try_advisory_lock", executed_sql)
        self.assertIn("AS acquired", executed_sql)
        self.assertIn("pg_advisory_unlock", executed_sql)

    def test_run_pipeline_returns_locked_when_advisory_lock_denied(self):
        conn = FakeConnection([{"acquired": False}])

        with patch.object(pipeline_service, "connect_db", return_value=conn):
            out = pipeline_service.run_pipeline(
                delivery_type="manual",
                triggered_by="admin",
                schedule_key=None,
            )

        self.assertEqual(out, {"status": "locked"})
        self.assertTrue(conn.closed)
        executed_sql = " ".join(sql for sql, _params in conn.executed)
        self.assertIn("pg_try_advisory_lock", executed_sql)
        self.assertNotIn("pg_advisory_unlock", executed_sql)

    def test_run_pipeline_writes_complete_stage_log_to_file(self):
        conn = FakeConnection(
            [
                {"acquired": True},
                {"run_id": 123},
                {"stage_id": 456},
                {"status": "success"},
            ]
        )
        completed = subprocess.CompletedProcess(
            args=["python", "stage.py"],
            returncode=0,
            stdout="complete stdout\nincluding a second line\n",
            stderr="complete stderr\n",
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "logs" / "pipeline.log"
            with patch.dict("os.environ", {"PIPELINE_LOG_PATH": str(log_path)}):
                with patch.object(pipeline_service, "connect_db", return_value=conn):
                    with patch.object(
                        pipeline_service,
                        "build_pipeline_stages",
                        return_value=[("stage_one", ["python", "stage.py"])],
                    ):
                        with patch.object(pipeline_service.subprocess, "run", return_value=completed):
                            out = pipeline_service.run_pipeline(
                                delivery_type="manual",
                                triggered_by="admin",
                                schedule_key=None,
                            )

            self.assertEqual(out, {"status": "success", "run_id": 123})
            log_text = log_path.read_text(encoding="utf-8")

        self.assertIn("[run:123] Pipeline run started", log_text)
        self.assertIn("[stage:stage_one] command: python stage.py", log_text)
        self.assertIn("complete stdout\nincluding a second line\n", log_text)
        self.assertIn("complete stderr\n", log_text)
        self.assertIn("[run:123] Pipeline run completed successfully", log_text)


if __name__ == "__main__":
    unittest.main()
