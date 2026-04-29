from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, time as time_of_day, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / "plexenv" / "bin" / "python"

PIPELINE_ADVISORY_LOCK_ID = 884722901

LOG_TAIL_MAX = 5000

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _python_executable() -> str:
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    return sys.executable


def _tail(s: str | None, max_len: int = LOG_TAIL_MAX) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[-max_len:]


def build_pipeline_stages() -> list[tuple[str, list[str]]]:
    """Ordered stages matching run_daily_pipeline.sh (single source for app runs)."""
    py = _python_executable()
    root = str(REPO_ROOT)
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = str(REPO_ROOT / f"shap_labels_{today}.csv")
    return [
        ("tautulli_incremental", [py, f"{root}/fetch_tautulli_data.py", "--mode", "incremental"]),
        ("library_embeddings", [py, f"{root}/fetch_tautulli_data.py", "--mode", "embeddings"]),
        ("watch_embeddings", [py, f"{root}/fetch_tautulli_data.py", "--mode", "watch_embeddings"]),
        ("user_embeddings", [py, f"{root}/build_user_embeddings.py"]),
        ("training_data", [py, f"{root}/build_training_data.py"]),
        ("train_model", [py, f"{root}/train_model.py"]),
        ("score_model", [py, f"{root}/score_model.py", "--all-users"]),
        (
            "batch_label",
            [
                py,
                f"{root}/batch_label_embeddings.py",
                "--label",
                "--save_label",
                "--refresh_existing",
                "--export_csv",
                csv_path,
                "--limit",
                "100",
            ],
        ),
    ]


def get_pipeline_schedule_slot(now_utc: datetime | None = None) -> dict[str, Any]:
    frequency = get_setting_value("pipeline.frequency", default="daily")
    weekly_day = get_setting_value("pipeline.weekly_day", default="sunday")
    run_time = get_setting_value("pipeline.run_time", default="03:00")
    tz_name = get_setting_value("pipeline.timezone", default="America/Chicago")

    tz = ZoneInfo(tz_name)
    now_local = (now_utc or datetime.now(tz)).astimezone(tz)
    hour_str, minute_str = str(run_time).split(":")
    scheduled_time = time_of_day(hour=int(hour_str), minute=int(minute_str))

    if frequency == "daily":
        slot_date = now_local.date()
        slot_dt = datetime.combine(slot_date, scheduled_time, tzinfo=tz)
        if slot_dt > now_local:
            slot_dt -= timedelta(days=1)
        schedule_key = (
            f"daily:{slot_dt.date().isoformat()}:{run_time}:{tz_name}"
        )
        return {"slot_dt": slot_dt, "schedule_key": schedule_key, "timezone": tz_name}

    target_weekday = WEEKDAY_INDEX[str(weekly_day).lower()]
    days_back = (now_local.weekday() - target_weekday) % 7
    slot_date = now_local.date() - timedelta(days=days_back)
    slot_dt = datetime.combine(slot_date, scheduled_time, tzinfo=tz)
    if slot_dt > now_local:
        slot_dt -= timedelta(days=7)
    schedule_key = f"weekly:{slot_dt.date().isoformat()}:{run_time}:{tz_name}"
    return {"slot_dt": slot_dt, "schedule_key": schedule_key, "timezone": tz_name}


def _has_successful_run_for_schedule_key(conn, schedule_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM public.pipeline_runs
            WHERE schedule_key = %s AND status = 'success'
            LIMIT 1
            """,
            (schedule_key,),
        )
        return cur.fetchone() is not None


def run_scheduled_pipeline(*, triggered_by: str | None = None) -> dict[str, Any]:
    enabled = get_setting_value("pipeline.enabled", default=False)
    if not enabled:
        return {"status": "disabled"}

    slot = get_pipeline_schedule_slot()
    schedule_key = slot["schedule_key"]

    conn = connect_db()
    try:
        if _has_successful_run_for_schedule_key(conn, schedule_key):
            return {"status": "already_ran", "schedule_key": schedule_key}
    finally:
        conn.close()

    return run_pipeline(
        delivery_type="scheduled",
        triggered_by=triggered_by or "app-scheduler",
        schedule_key=schedule_key,
    )


def run_pipeline(
    *,
    delivery_type: str,
    triggered_by: str | None,
    schedule_key: str | None,
) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    lock_acquired = False
    run_id: int | None = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (PIPELINE_ADVISORY_LOCK_ID,),
            )
            row = cur.fetchone()
            lock_acquired = bool(row and row["acquired"])
        conn.commit()

        if not lock_acquired:
            return {"status": "locked"}

        if schedule_key is not None and delivery_type == "scheduled":
            if _has_successful_run_for_schedule_key(conn, schedule_key):
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_ADVISORY_LOCK_ID,))
                conn.commit()
                return {"status": "already_ran", "schedule_key": schedule_key}

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.pipeline_runs (
                    delivery_type, schedule_key, triggered_by, status, started_at
                )
                VALUES (%s, %s, %s, 'started', now())
                RETURNING run_id
                """,
                (delivery_type, schedule_key, triggered_by),
            )
            rid = cur.fetchone()
            run_id = rid["run_id"] if isinstance(rid, dict) else rid[0]
        conn.commit()

        env = {**os.environ}
        env.setdefault("PGHOST", env.get("PGHOST", "localhost"))
        env.setdefault("PGPORT", env.get("PGPORT", "5432"))

        stages = build_pipeline_stages()
        for stage_key, argv in stages:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.pipeline_run_stages (
                        run_id, stage_key, status, started_at
                    )
                    VALUES (%s, %s, 'started', now())
                    RETURNING stage_id
                    """,
                    (run_id, stage_key),
                )
                sid_row = cur.fetchone()
                stage_id = sid_row["stage_id"] if isinstance(sid_row, dict) else sid_row[0]
            conn.commit()

            try:
                proc = subprocess.run(
                    argv,
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=None,
                )
            except Exception as exc:
                err_msg = str(exc)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.pipeline_run_stages
                        SET status = 'failed', exit_code = NULL,
                            stdout_tail = %s, stderr_tail = %s,
                            completed_at = now()
                        WHERE stage_id = %s
                        """,
                        ("", _tail(err_msg), stage_id),
                    )
                    cur.execute(
                        """
                        UPDATE public.pipeline_runs
                        SET status = 'failed', notes = %s, completed_at = now()
                        WHERE run_id = %s
                        """,
                        (_tail(err_msg, 2000), run_id),
                    )
                conn.commit()
                break

            out_t = _tail(proc.stdout)
            err_t = _tail(proc.stderr)
            stage_status = "success" if proc.returncode == 0 else "failed"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.pipeline_run_stages
                    SET status = %s, exit_code = %s,
                        stdout_tail = %s, stderr_tail = %s,
                        completed_at = now()
                    WHERE stage_id = %s
                    """,
                    (stage_status, proc.returncode, out_t, err_t, stage_id),
                )
            conn.commit()

            if proc.returncode != 0:
                note = f"Stage {stage_key} exited with code {proc.returncode}"
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.pipeline_runs
                        SET status = 'failed', notes = %s, completed_at = now()
                        WHERE run_id = %s
                        """,
                        (_tail(note, 2000), run_id),
                    )
                conn.commit()
                break
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.pipeline_runs
                    SET status = 'success', completed_at = now()
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
            conn.commit()

        result: dict[str, Any] = {"status": "success", "run_id": run_id}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM public.pipeline_runs WHERE run_id = %s",
                (run_id,),
            )
            r = cur.fetchone()
            final_status = r["status"] if isinstance(r, dict) else r[0]
        conn.commit()
        if final_status == "failed":
            result = {"status": "failed", "run_id": run_id}
        elif final_status == "success":
            result = {"status": "success", "run_id": run_id}
        return result
    finally:
        if lock_acquired:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_unlock(%s)", (PIPELINE_ADVISORY_LOCK_ID,)
                    )
                conn.commit()
            except Exception:
                pass
        conn.close()


def get_pipeline_runs(*, limit: int = 50) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    run_id,
                    delivery_type,
                    schedule_key,
                    triggered_by,
                    status,
                    notes,
                    started_at,
                    completed_at
                FROM public.pipeline_runs
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            runs = list(cur.fetchall() or [])

            if not runs:
                return {"runs": []}

            run_ids = [r["run_id"] for r in runs]
            cur.execute(
                """
                SELECT
                    stage_id,
                    run_id,
                    stage_key,
                    status,
                    exit_code,
                    stdout_tail,
                    stderr_tail,
                    started_at,
                    completed_at
                FROM public.pipeline_run_stages
                WHERE run_id IN %s
                ORDER BY stage_id ASC
                """,
                (tuple(run_ids),),
            )
            stage_rows = list(cur.fetchall() or [])

        stages_by_run: dict[int, list[dict[str, Any]]] = {}
        for s in stage_rows:
            rid = s["run_id"]
            stages_by_run.setdefault(rid, []).append(dict(s))

        out_runs = []
        for r in runs:
            rd = dict(r)
            rd["stages"] = stages_by_run.get(rd["run_id"], [])
            out_runs.append(rd)

        return {"runs": out_runs}
    finally:
        conn.close()


def get_pipeline_run(run_id: int) -> dict[str, Any] | None:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    run_id,
                    delivery_type,
                    schedule_key,
                    triggered_by,
                    status,
                    notes,
                    started_at,
                    completed_at
                FROM public.pipeline_runs
                WHERE run_id = %s
                """,
                (run_id,),
            )
            run = cur.fetchone()
            if not run:
                return None
            cur.execute(
                """
                SELECT
                    stage_id,
                    run_id,
                    stage_key,
                    status,
                    exit_code,
                    stdout_tail,
                    stderr_tail,
                    started_at,
                    completed_at
                FROM public.pipeline_run_stages
                WHERE run_id = %s
                ORDER BY stage_id ASC
                """,
                (run_id,),
            )
            stages = list(cur.fetchall() or [])
        rdict = dict(run)
        rdict["stages"] = [dict(s) for s in stages]
        return rdict
    finally:
        conn.close()
