from __future__ import annotations

import unittest
from datetime import datetime
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


if __name__ == "__main__":
    unittest.main()
