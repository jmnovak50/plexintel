from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import patch

from api.services import digest_scheduler


class DigestSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        digest_scheduler._scheduler_task = None

    async def asyncTearDown(self) -> None:
        await digest_scheduler.stop_digest_scheduler()

    def test_get_interval_seconds_defaults_to_60(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(digest_scheduler._get_interval_seconds(), 60)

    def test_get_interval_seconds_rejects_invalid_values(self):
        with patch.dict(os.environ, {"DIGEST_SCHEDULER_INTERVAL_SECONDS": "abc"}, clear=True):
            self.assertEqual(digest_scheduler._get_interval_seconds(), 60)
        with patch.dict(os.environ, {"DIGEST_SCHEDULER_INTERVAL_SECONDS": "0"}, clear=True):
            self.assertEqual(digest_scheduler._get_interval_seconds(), 60)

    async def test_scheduler_loop_invokes_run_scheduled_digest(self):
        calls: list[tuple[bool, str]] = []

        def fake_run_scheduled_digest(*, force: bool, triggered_by: str) -> dict[str, str]:
            calls.append((force, triggered_by))
            return {"status": "already_sent"}

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        async def fake_sleep(_seconds: int) -> None:
            raise asyncio.CancelledError()

        with patch.object(digest_scheduler, "run_scheduled_digest", side_effect=fake_run_scheduled_digest):
            with patch.object(digest_scheduler.asyncio, "to_thread", side_effect=fake_to_thread):
                with patch.object(digest_scheduler.asyncio, "sleep", side_effect=fake_sleep):
                    with self.assertRaises(asyncio.CancelledError):
                        await digest_scheduler._scheduler_loop(60)

        self.assertEqual(calls, [(False, "app-scheduler")])

    async def test_start_digest_scheduler_skips_when_disabled(self):
        with patch.object(digest_scheduler, "_env_flag", return_value=False):
            task = digest_scheduler.start_digest_scheduler()

        self.assertIsNone(task)


if __name__ == "__main__":
    unittest.main()
