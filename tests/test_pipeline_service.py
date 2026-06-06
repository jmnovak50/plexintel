from __future__ import annotations

import signal
import tempfile
import unittest
from datetime import datetime, timedelta
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

    def fetchall(self):
        return self.conn.fetchall_results.pop(0)


class FakeConnection:
    def __init__(self, fetchone_results, fetchall_results=None):
        self.fetchone_results = list(fetchone_results)
        self.fetchall_results = list(fetchall_results or [])
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


class PipelineStageTests(unittest.TestCase):
    def test_build_pipeline_stages_uses_label_batch_setting_defaults(self):
        with patch.object(pipeline_service, "get_setting_value", side_effect=lambda _key, default=None: default):
            stages = pipeline_service.build_pipeline_stages()

        batch_label = dict(stages)["batch_label"]
        self.assertIn("batch_label_embeddings.py", batch_label[1])
        self.assertEqual(batch_label[batch_label.index("--selection_mode") + 1], "coverage")
        self.assertEqual(batch_label[batch_label.index("--limit") + 1], "25")
        self.assertEqual(batch_label[batch_label.index("--dim_type") + 1], "all")
        self.assertIn("--label", batch_label)
        self.assertIn("--save_label", batch_label)
        self.assertIn("--export_csv", batch_label)
        self.assertNotIn("--coverage_share", batch_label)
        self.assertNotIn("--refresh_existing", batch_label)

    def test_build_pipeline_stages_can_disable_labeling(self):
        values = {
            "pipeline.labeling_enabled": False,
        }

        with patch.object(
            pipeline_service,
            "get_setting_value",
            side_effect=lambda key, default=None: values.get(key, default),
        ):
            stages = pipeline_service.build_pipeline_stages()

        self.assertNotIn("batch_label", dict(stages))

    def test_build_pipeline_stages_can_refresh_existing_labels_from_settings(self):
        values = {
            "pipeline.labeling_enabled": True,
            "pipeline.label_selection_mode": "importance",
            "pipeline.label_batch_limit": 25,
            "pipeline.label_dim_type": "media",
            "pipeline.refresh_existing_labels": True,
        }

        with patch.object(
            pipeline_service,
            "get_setting_value",
            side_effect=lambda key, default=None: values.get(key, default),
        ):
            stages = pipeline_service.build_pipeline_stages()

        batch_label = dict(stages)["batch_label"]
        self.assertEqual(batch_label[batch_label.index("--selection_mode") + 1], "importance")
        self.assertEqual(batch_label[batch_label.index("--limit") + 1], "25")
        self.assertEqual(batch_label[batch_label.index("--dim_type") + 1], "media")
        self.assertNotIn("--coverage_share", batch_label)
        self.assertIn("--refresh_existing", batch_label)

    def test_build_pipeline_stages_passes_coverage_share_for_hybrid_only(self):
        values = {
            "pipeline.labeling_enabled": True,
            "pipeline.label_selection_mode": "hybrid",
            "pipeline.label_batch_limit": 40,
            "pipeline.label_dim_type": "user",
            "pipeline.label_coverage_share": 0.55,
        }

        with patch.object(
            pipeline_service,
            "get_setting_value",
            side_effect=lambda key, default=None: values.get(key, default),
        ):
            stages = pipeline_service.build_pipeline_stages()

        batch_label = dict(stages)["batch_label"]
        self.assertEqual(batch_label[batch_label.index("--selection_mode") + 1], "hybrid")
        self.assertEqual(batch_label[batch_label.index("--coverage_share") + 1], "0.55")
        self.assertEqual(batch_label[batch_label.index("--limit") + 1], "40")
        self.assertEqual(batch_label[batch_label.index("--dim_type") + 1], "user")

    def test_build_pipeline_stages_passes_review_mode_without_hybrid_share(self):
        values = {
            "pipeline.labeling_enabled": True,
            "pipeline.label_selection_mode": "review",
            "pipeline.label_batch_limit": 25,
            "pipeline.label_dim_type": "all",
            "pipeline.label_coverage_share": 0.55,
        }

        with patch.object(
            pipeline_service,
            "get_setting_value",
            side_effect=lambda key, default=None: values.get(key, default),
        ):
            stages = pipeline_service.build_pipeline_stages()

        batch_label = dict(stages)["batch_label"]
        self.assertEqual(batch_label[batch_label.index("--selection_mode") + 1], "review")
        self.assertEqual(batch_label[batch_label.index("--limit") + 1], "25")
        self.assertEqual(batch_label[batch_label.index("--dim_type") + 1], "all")
        self.assertNotIn("--coverage_share", batch_label)


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
                {"cancel_requested": False},
                {"stage_id": 456},
                {"status": "success"},
            ]
        )
        completed = pipeline_service.StageProcessResult(
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
                        with patch.object(pipeline_service, "_run_stage_process", return_value=completed):
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

    def test_run_pipeline_cancel_before_next_stage_prevents_next_subprocess(self):
        conn = FakeConnection(
            [
                {"acquired": True},
                {"run_id": 123},
                {"cancel_requested": False},
                {"stage_id": 456},
                {"cancel_requested": True},
                {"status": "cancelled"},
            ]
        )
        completed = pipeline_service.StageProcessResult(
            returncode=0,
            stdout="stage one done\n",
            stderr="",
        )

        with patch.object(pipeline_service, "connect_db", return_value=conn):
            with patch.object(
                pipeline_service,
                "build_pipeline_stages",
                return_value=[
                    ("stage_one", ["python", "one.py"]),
                    ("stage_two", ["python", "two.py"]),
                ],
            ):
                with patch.object(pipeline_service, "_run_stage_process", return_value=completed) as mock_run:
                    out = pipeline_service.run_pipeline(
                        delivery_type="manual",
                        triggered_by="admin",
                        schedule_key=None,
                    )

        self.assertEqual(out, {"status": "cancelled", "run_id": 123})
        mock_run.assert_called_once()
        executed_params = [params for _sql, params in conn.executed if params]
        self.assertTrue(
            any(
                isinstance(params, tuple)
                and params
                and "cancelled before stage stage_two" in str(params[0])
                for params in executed_params
            )
        )

    def test_run_stage_process_sends_term_then_kill_on_cancel(self):
        class FakeProc:
            pid = 987
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self):
                self.returncode = -9
                return self.returncode

            def terminate(self):
                self.returncode = -15

            def kill(self):
                self.returncode = -9

        conn = FakeConnection([{"cancel_requested": True}])
        fake_proc = FakeProc()
        signals: list[tuple[int, signal.Signals]] = []

        with patch.object(pipeline_service.subprocess, "Popen", return_value=fake_proc):
            with patch.object(
                pipeline_service.os,
                "killpg",
                side_effect=lambda pid, sig: signals.append((pid, sig)),
            ):
                result = pipeline_service._run_stage_process(
                    conn=conn,
                    run_id=123,
                    stage_key="stage_one",
                    argv=["python", "stage.py"],
                    env={},
                    poll_seconds=0,
                    grace_seconds=0,
                )

        self.assertTrue(result.cancelled)
        self.assertEqual(result.returncode, -9)
        self.assertEqual(
            signals,
            [(987, signal.SIGTERM), (987, signal.SIGKILL)],
        )

    def test_run_scheduled_pipeline_treats_cancelled_schedule_as_terminal(self):
        conn = FakeConnection([{"exists": 1}], fetchall_results=[[]])

        with patch.object(pipeline_service, "get_setting_value", return_value=True):
            with patch.object(
                pipeline_service,
                "get_pipeline_schedule_slot",
                return_value={"schedule_key": "daily:test"},
            ):
                with patch.object(pipeline_service, "connect_db", return_value=conn):
                    with patch.object(pipeline_service, "run_pipeline") as mock_run_pipeline:
                        out = pipeline_service.run_scheduled_pipeline(triggered_by="test")

        self.assertEqual(out, {"status": "already_ran", "schedule_key": "daily:test"})
        mock_run_pipeline.assert_not_called()
        executed_sql = " ".join(sql for sql, _params in conn.executed)
        self.assertIn("status IN", executed_sql)
        self.assertIn(("cancelled", "success"), [params[1] for _sql, params in conn.executed if params][0:1])

    def test_run_scheduled_pipeline_reconciles_cancel_requested_before_retry(self):
        conn = FakeConnection(
            [{"exists": 1}],
            fetchall_results=[
                [
                    {
                        "run_id": 321,
                        "current_pid": None,
                        "current_stage_key": "train_model",
                        "cancel_requested_at": datetime.now(ZoneInfo("UTC")) - timedelta(seconds=30),
                    }
                ]
            ],
        )

        with patch.object(pipeline_service, "get_setting_value", return_value=True):
            with patch.object(
                pipeline_service,
                "get_pipeline_schedule_slot",
                return_value={"schedule_key": "daily:test"},
            ):
                with patch.object(pipeline_service, "connect_db", return_value=conn):
                    with patch.object(pipeline_service, "run_pipeline") as mock_run_pipeline:
                        out = pipeline_service.run_scheduled_pipeline(triggered_by="test")

        self.assertEqual(out, {"status": "already_ran", "schedule_key": "daily:test"})
        mock_run_pipeline.assert_not_called()
        executed_sql = " ".join(sql for sql, _params in conn.executed)
        self.assertIn("status = 'cancelled'", executed_sql)

    def test_run_scheduled_pipeline_skips_active_cancel_requested_run(self):
        conn = FakeConnection(
            [None, {"exists": 1}],
            fetchall_results=[[]],
        )

        with patch.object(pipeline_service, "get_setting_value", return_value=True):
            with patch.object(
                pipeline_service,
                "get_pipeline_schedule_slot",
                return_value={"schedule_key": "daily:test"},
            ):
                with patch.object(pipeline_service, "connect_db", return_value=conn):
                    with patch.object(pipeline_service, "run_pipeline") as mock_run_pipeline:
                        out = pipeline_service.run_scheduled_pipeline(triggered_by="test")

        self.assertEqual(out, {"status": "already_running", "schedule_key": "daily:test"})
        mock_run_pipeline.assert_not_called()

    def test_request_cancel_reconciles_missing_pid(self):
        conn = FakeConnection(
            [
                {"run_id": 123, "status": "started", "current_pid": None},
            ],
            fetchall_results=[
                [
                    {
                        "run_id": 123,
                        "current_pid": None,
                        "current_stage_key": "train_model",
                        "cancel_requested_at": datetime.now(ZoneInfo("UTC")) - timedelta(seconds=30),
                    }
                ]
            ],
        )

        with patch.object(pipeline_service, "connect_db", return_value=conn):
            out = pipeline_service.request_pipeline_cancel(
                run_id=123,
                requested_by="admin",
            )

        self.assertEqual(out, {"status": "cancel_requested", "run_id": 123})
        executed_sql = " ".join(sql for sql, _params in conn.executed)
        self.assertIn("SET status = 'cancel_requested'", executed_sql)
        self.assertIn("SET status = 'cancelled'", executed_sql)


if __name__ == "__main__":
    unittest.main()
