from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from api.services import pipeline_scheduler


class PipelineSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        pipeline_scheduler._scheduler_task = None

    async def asyncTearDown(self) -> None:
        await pipeline_scheduler.stop_pipeline_scheduler()

    def test_get_interval_seconds_defaults_to_60(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(pipeline_scheduler._get_interval_seconds(), 60)

    def test_get_interval_seconds_rejects_invalid_values(self):
        with patch.dict(os.environ, {"PIPELINE_SCHEDULER_INTERVAL_SECONDS": "abc"}, clear=True):
            self.assertEqual(pipeline_scheduler._get_interval_seconds(), 60)
        with patch.dict(os.environ, {"PIPELINE_SCHEDULER_INTERVAL_SECONDS": "0"}, clear=True):
            self.assertEqual(pipeline_scheduler._get_interval_seconds(), 60)

    async def test_scheduler_loop_invokes_run_scheduled_pipeline(self):
        calls: list[tuple[str | None]] = []

        def fake_run_scheduled_pipeline(*, triggered_by: str | None = None) -> dict[str, str]:
            calls.append((triggered_by,))
            return {"status": "disabled"}

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        async def fake_sleep(_seconds: int) -> None:
            raise asyncio.CancelledError()

        with patch.object(pipeline_scheduler, "run_scheduled_pipeline", side_effect=fake_run_scheduled_pipeline):
            with patch.object(pipeline_scheduler.asyncio, "to_thread", side_effect=fake_to_thread):
                with patch.object(pipeline_scheduler.asyncio, "sleep", side_effect=fake_sleep):
                    with self.assertRaises(asyncio.CancelledError):
                        await pipeline_scheduler._scheduler_loop(60)

        self.assertEqual(calls, [("app-scheduler",)])

    async def test_start_pipeline_scheduler_skips_when_disabled(self):
        with patch.object(pipeline_scheduler, "_env_flag", return_value=False):
            task = pipeline_scheduler.start_pipeline_scheduler()

        self.assertIsNone(task)


if __name__ == "__main__":
    unittest.main()
