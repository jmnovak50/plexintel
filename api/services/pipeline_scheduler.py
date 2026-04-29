from __future__ import annotations

import asyncio
import contextlib
import os

from api.services.pipeline_service import run_scheduled_pipeline

DEFAULT_INTERVAL_SECONDS = 60
_scheduler_task: asyncio.Task | None = None


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_interval_seconds() -> int:
    raw_value = os.getenv("PIPELINE_SCHEDULER_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
    try:
        interval = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    return interval if interval > 0 else DEFAULT_INTERVAL_SECONDS


async def _scheduler_loop(interval_seconds: int) -> None:
    while True:
        try:
            await asyncio.to_thread(
                run_scheduled_pipeline,
                triggered_by="app-scheduler",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Pipeline scheduler error: {exc}")
        await asyncio.sleep(interval_seconds)


def start_pipeline_scheduler() -> asyncio.Task | None:
    global _scheduler_task

    if not _env_flag("PIPELINE_SCHEDULER_ENABLED", default=True):
        print("Pipeline scheduler disabled via environment.")
        return None

    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task

    interval_seconds = _get_interval_seconds()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(interval_seconds),
        name="pipeline-scheduler",
    )
    print(f"Pipeline scheduler started (interval={interval_seconds}s).")
    return _scheduler_task


async def stop_pipeline_scheduler() -> None:
    global _scheduler_task

    if _scheduler_task is None:
        return

    task = _scheduler_task
    _scheduler_task = None
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
