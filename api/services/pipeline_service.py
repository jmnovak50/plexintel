from __future__ import annotations

import os
import signal
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
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
PIPELINE_LOG_PATH_ENV = "PIPELINE_LOG_PATH"
DEFAULT_PIPELINE_LOG_PATH = REPO_ROOT / "logs" / "pipeline.log"
PIPELINE_CANCEL_POLL_SECONDS_ENV = "PIPELINE_CANCEL_POLL_SECONDS"
PIPELINE_CANCEL_GRACE_SECONDS_ENV = "PIPELINE_CANCEL_GRACE_SECONDS"
DEFAULT_CANCEL_POLL_SECONDS = 2.0
DEFAULT_CANCEL_GRACE_SECONDS = 10.0
PIPELINE_CANCEL_RECONCILE_GRACE_SECONDS_ENV = "PIPELINE_CANCEL_RECONCILE_GRACE_SECONDS"
TERMINAL_RUN_STATUSES = {"success", "failed", "cancelled"}
SCHEDULE_TERMINAL_STATUSES = {"success", "cancelled"}
ACTIVE_SCHEDULE_STATUSES = {"started", "cancel_requested"}
PIPELINE_PROCESS_MARKERS = (
    "fetch_tautulli_data.py",
    "build_user_embeddings.py",
    "build_training_data.py",
    "train_model.py",
    "score_model.py",
    "batch_label_embeddings.py",
)

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class StageProcessResult:
    returncode: int | None
    stdout: str
    stderr: str
    cancelled: bool = False


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


def _row_value(row: Any, key: str, index: int = 0) -> Any:
    if row is None:
        return None
    if hasattr(row, "get"):
        return row.get(key)
    return row[index]


def fetch_score_model_refresh_status(cur) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM public.pipeline_runs
            WHERE current_stage_key = %s
              AND status NOT IN ('success', 'failed', 'cancelled')
        ) AS is_refreshing
        """,
        ("score_model",),
    )
    row = cur.fetchone()
    return bool(_row_value(row, "is_refreshing"))


def is_score_model_refreshing() -> bool:
    conn = connect_db(cursor_factory=RealDictCursor)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        return fetch_score_model_refresh_status(cur)
    finally:
        cur.close()
        conn.close()


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def _read_spooled_output(handle) -> str:
    handle.seek(0)
    data = handle.read()
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")


def _process_exists(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_matches_pipeline_process(pid: int | None) -> bool | None:
    if pid is None or pid <= 0:
        return False
    proc_dir = Path("/proc")
    if not proc_dir.is_dir():
        return None
    try:
        raw_cmdline = (proc_dir / str(pid) / "cmdline").read_bytes()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    cmdline = raw_cmdline.decode("utf-8", errors="replace")
    return any(marker in cmdline for marker in PIPELINE_PROCESS_MARKERS)


def _is_older_than(value: Any, seconds: float) -> bool:
    if value is None:
        return True
    if not hasattr(value, "tzinfo"):
        return True
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    return (now - value).total_seconds() >= seconds


def get_pipeline_log_path() -> Path:
    raw_path = os.getenv(PIPELINE_LOG_PATH_ENV, "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return DEFAULT_PIPELINE_LOG_PATH


def _append_pipeline_log(text: str) -> None:
    try:
        log_path = get_pipeline_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(text)
    except Exception as exc:
        print(f"Failed to write pipeline log file: {exc}", file=sys.stderr)


def _log_run_event(run_id: int, message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    _append_pipeline_log(f"[{timestamp}] [run:{run_id}] {message}\n")


def _log_stage_output(
    *,
    run_id: int,
    stage_key: str,
    argv: list[str],
    stdout: str | None,
    stderr: str | None,
    exit_code: int | None,
) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "\n",
        f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] command: {shlex.join(argv)}\n",
        f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] exit_code: {exit_code}\n",
        f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] stdout:\n",
        stdout or "",
    ]
    if stdout and not stdout.endswith("\n"):
        lines.append("\n")
    lines.extend(
        [
            f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] stderr:\n",
            stderr or "",
        ]
    )
    if stderr and not stderr.endswith("\n"):
        lines.append("\n")
    lines.append(f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] end\n")
    _append_pipeline_log("".join(lines))


def _is_pipeline_cancel_requested(conn, run_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (status = 'cancel_requested' OR cancel_requested_at IS NOT NULL) AS cancel_requested
            FROM public.pipeline_runs
            WHERE run_id = %s
            """,
            (run_id,),
        )
        row = cur.fetchone()
    return bool(_row_value(row, "cancel_requested"))


def _update_run_heartbeat(
    conn,
    *,
    run_id: int,
    stage_key: str | None,
    pid: int | None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.pipeline_runs
            SET last_heartbeat_at = now(),
                current_stage_key = %s,
                current_pid = %s
            WHERE run_id = %s
            """,
            (stage_key, pid, run_id),
        )
    conn.commit()


def _clear_run_current_stage(conn, run_id: int) -> None:
    _update_run_heartbeat(conn, run_id=run_id, stage_key=None, pid=None)


def _mark_run_cancelled(conn, *, run_id: int, notes: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.pipeline_run_stages
            SET status = 'cancelled',
                stderr_tail = COALESCE(NULLIF(stderr_tail, ''), %s),
                completed_at = COALESCE(completed_at, now())
            WHERE run_id = %s AND status = 'started'
            """,
            (_tail(notes), run_id),
        )
        cur.execute(
            """
            UPDATE public.pipeline_runs
            SET status = 'cancelled',
                notes = %s,
                completed_at = COALESCE(completed_at, now()),
                last_heartbeat_at = now(),
                current_stage_key = NULL,
                current_pid = NULL
            WHERE run_id = %s
            """,
            (_tail(notes, 2000), run_id),
        )
    conn.commit()


def _signal_pid_process_group(
    pid: int | None,
    sig: signal.Signals,
    *,
    require_pipeline_match: bool = False,
) -> bool:
    if pid is None or pid <= 0:
        return False
    if require_pipeline_match and _pid_matches_pipeline_process(pid) is False:
        return False
    try:
        os.killpg(pid, sig)
        return True
    except ProcessLookupError:
        try:
            os.kill(pid, sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False
    except PermissionError:
        return True
    except Exception:
        try:
            os.kill(pid, sig)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False


def _reconcile_cancel_requested_runs(conn, *, run_id: int | None = None) -> int:
    grace_seconds = _env_float(
        PIPELINE_CANCEL_RECONCILE_GRACE_SECONDS_ENV,
        DEFAULT_CANCEL_GRACE_SECONDS,
    )
    params: tuple[Any, ...] = ()
    run_filter = ""
    if run_id is not None:
        run_filter = "AND run_id = %s"
        params = (run_id,)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT
                run_id,
                current_pid,
                current_stage_key,
                cancel_requested_at
            FROM public.pipeline_runs
            WHERE status = 'cancel_requested'
            {run_filter}
            ORDER BY cancel_requested_at ASC NULLS FIRST
            """,
            params,
        )
        rows = list(cur.fetchall() or [])

    reconciled_count = 0
    for row in rows:
        rid = int(row["run_id"])
        pid = row.get("current_pid")
        stage_key = row.get("current_stage_key") or "active stage"
        cancel_requested_at = row.get("cancel_requested_at")

        if not pid:
            note = f"Pipeline run cancelled; no active process was registered for {stage_key}."
            _mark_run_cancelled(conn, run_id=rid, notes=note)
            _log_run_event(rid, note)
            reconciled_count += 1
            continue

        if not _process_exists(pid):
            note = f"Pipeline run cancelled; process {pid} for {stage_key} is no longer running."
            _mark_run_cancelled(conn, run_id=rid, notes=note)
            _log_run_event(rid, note)
            reconciled_count += 1
            continue

        if _pid_matches_pipeline_process(pid) is False:
            note = f"Pipeline run cancelled; process {pid} no longer matches a pipeline stage."
            _mark_run_cancelled(conn, run_id=rid, notes=note)
            _log_run_event(rid, note)
            reconciled_count += 1
            continue

        if _is_older_than(cancel_requested_at, grace_seconds):
            _signal_pid_process_group(pid, signal.SIGKILL, require_pipeline_match=True)
        else:
            _signal_pid_process_group(pid, signal.SIGTERM, require_pipeline_match=True)

    return reconciled_count


def reconcile_cancel_requested_runs(*, run_id: int | None = None) -> int:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        reconciled_count = _reconcile_cancel_requested_runs(conn, run_id=run_id)
        conn.commit()
        return reconciled_count
    finally:
        conn.close()


def request_pipeline_cancel(*, run_id: int, requested_by: str | None) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    current_pid: int | None = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, status, current_pid
                FROM public.pipeline_runs
                WHERE run_id = %s
                FOR UPDATE
                """,
                (run_id,),
            )
            row = cur.fetchone()
            if row is None:
                conn.commit()
                return {"status": "not_found", "run_id": run_id}

            current_status = str(_row_value(row, "status", 1))
            if current_status in TERMINAL_RUN_STATUSES:
                conn.commit()
                return {
                    "status": "already_terminal",
                    "run_id": run_id,
                    "run_status": current_status,
                }

            current_pid = _row_value(row, "current_pid", 2)
            cur.execute(
                """
                UPDATE public.pipeline_runs
                SET status = 'cancel_requested',
                    cancel_requested_at = COALESCE(cancel_requested_at, now()),
                    cancel_requested_by = COALESCE(cancel_requested_by, %s),
                    last_heartbeat_at = now()
                WHERE run_id = %s
                """,
                (requested_by, run_id),
        )
        conn.commit()
        _signal_pid_process_group(current_pid, signal.SIGTERM, require_pipeline_match=True)
        _reconcile_cancel_requested_runs(conn, run_id=run_id)
        conn.commit()
        _log_run_event(run_id, f"Pipeline cancellation requested by {requested_by or '-'}")
        return {"status": "cancel_requested", "run_id": run_id}
    finally:
        conn.close()


def _signal_process_group(proc: subprocess.Popen, sig: signal.Signals) -> None:
    if _signal_pid_process_group(proc.pid, sig):
        return
    if sig == signal.SIGTERM:
        proc.terminate()
    elif sig == signal.SIGKILL:
        proc.kill()


def _run_stage_process(
    *,
    conn,
    run_id: int,
    stage_key: str,
    argv: list[str],
    env: dict[str, str],
    poll_seconds: float | None = None,
    grace_seconds: float | None = None,
) -> StageProcessResult:
    poll_interval = (
        poll_seconds
        if poll_seconds is not None
        else _env_float(PIPELINE_CANCEL_POLL_SECONDS_ENV, DEFAULT_CANCEL_POLL_SECONDS)
    )
    cancel_grace = (
        grace_seconds
        if grace_seconds is not None
        else _env_float(PIPELINE_CANCEL_GRACE_SECONDS_ENV, DEFAULT_CANCEL_GRACE_SECONDS)
    )

    with tempfile.TemporaryFile(mode="w+b") as stdout_file:
        with tempfile.TemporaryFile(mode="w+b") as stderr_file:
            proc = subprocess.Popen(
                argv,
                cwd=str(REPO_ROOT),
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
                start_new_session=True,
            )
            cancelled = False
            _update_run_heartbeat(conn, run_id=run_id, stage_key=stage_key, pid=proc.pid)

            while proc.poll() is None:
                if _is_pipeline_cancel_requested(conn, run_id):
                    cancelled = True
                    _signal_process_group(proc, signal.SIGTERM)
                    deadline = time.monotonic() + cancel_grace
                    while proc.poll() is None and time.monotonic() < deadline:
                        time.sleep(min(0.2, max(deadline - time.monotonic(), 0)))
                    if proc.poll() is None:
                        _signal_process_group(proc, signal.SIGKILL)
                    proc.wait()
                    break

                if poll_interval > 0:
                    time.sleep(poll_interval)
                _update_run_heartbeat(conn, run_id=run_id, stage_key=stage_key, pid=proc.pid)

            if proc.poll() is None:
                proc.wait()

            stdout = _read_spooled_output(stdout_file)
            stderr = _read_spooled_output(stderr_file)
            return StageProcessResult(
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                cancelled=cancelled,
            )


def build_pipeline_stages() -> list[tuple[str, list[str]]]:
    """Ordered stages matching run_daily_pipeline.sh (single source for app runs)."""
    py = _python_executable()
    root = str(REPO_ROOT)
    today = datetime.now().strftime("%Y-%m-%d")
    csv_path = str(REPO_ROOT / f"shap_labels_{today}.csv")
    labeling_enabled = get_setting_value("pipeline.labeling_enabled", default=True)
    label_selection_mode = get_setting_value("pipeline.label_selection_mode", default="eligible")
    label_batch_limit = get_setting_value("pipeline.label_batch_limit", default=25)
    label_dim_type = get_setting_value("pipeline.label_dim_type", default="all")
    label_coverage_share = get_setting_value("pipeline.label_coverage_share", default=0.80)
    refresh_existing_labels = get_setting_value("pipeline.refresh_existing_labels", default=False)
    if str(label_selection_mode) not in {"eligible", "importance", "coverage", "hybrid"}:
        label_selection_mode = "eligible"

    stages = [
        ("tautulli_incremental", [py, f"{root}/fetch_tautulli_data.py", "--mode", "incremental"]),
        ("library_embeddings", [py, f"{root}/fetch_tautulli_data.py", "--mode", "embeddings"]),
        ("watch_embeddings", [py, f"{root}/fetch_tautulli_data.py", "--mode", "watch_embeddings"]),
        ("user_embeddings", [py, f"{root}/build_user_embeddings.py"]),
        ("training_data", [py, f"{root}/build_training_data.py"]),
        ("train_model", [py, f"{root}/train_model.py"]),
        ("score_model", [py, f"{root}/score_model.py", "--all-users"]),
    ]

    if labeling_enabled:
        batch_label_args = [
            py,
            f"{root}/batch_label_embeddings.py",
            "--selection_mode",
            str(label_selection_mode),
            "--limit",
            str(label_batch_limit),
            "--dim_type",
            str(label_dim_type),
            "--label",
            "--save_label",
            "--export_csv",
            csv_path,
        ]
        if str(label_selection_mode) == "hybrid":
            batch_label_args.extend(["--coverage_share", str(label_coverage_share)])
        if refresh_existing_labels:
            batch_label_args.append("--refresh_existing")
        stages.append(("batch_label", batch_label_args))

    return stages


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


def _has_terminal_scheduled_run_for_schedule_key(conn, schedule_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM public.pipeline_runs
            WHERE schedule_key = %s AND status IN %s
            LIMIT 1
            """,
            (schedule_key, tuple(sorted(SCHEDULE_TERMINAL_STATUSES))),
        )
        return cur.fetchone() is not None


def _has_active_run_for_schedule_key(conn, schedule_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM public.pipeline_runs
            WHERE schedule_key = %s AND status IN %s
            LIMIT 1
            """,
            (schedule_key, tuple(sorted(ACTIVE_SCHEDULE_STATUSES))),
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
        _reconcile_cancel_requested_runs(conn)
        conn.commit()
        if _has_terminal_scheduled_run_for_schedule_key(conn, schedule_key):
            return {"status": "already_ran", "schedule_key": schedule_key}
        if _has_active_run_for_schedule_key(conn, schedule_key):
            return {"status": "already_running", "schedule_key": schedule_key}
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
            _reconcile_cancel_requested_runs(conn)
            conn.commit()
            if _has_terminal_scheduled_run_for_schedule_key(conn, schedule_key):
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_ADVISORY_LOCK_ID,))
                conn.commit()
                return {"status": "already_ran", "schedule_key": schedule_key}
            if _has_active_run_for_schedule_key(conn, schedule_key):
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (PIPELINE_ADVISORY_LOCK_ID,))
                conn.commit()
                return {"status": "already_running", "schedule_key": schedule_key}

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.pipeline_runs (
                    delivery_type, schedule_key, triggered_by, status, started_at, last_heartbeat_at
                )
                VALUES (%s, %s, %s, 'started', now(), now())
                RETURNING run_id
                """,
                (delivery_type, schedule_key, triggered_by),
            )
            rid = cur.fetchone()
            run_id = rid["run_id"] if isinstance(rid, dict) else rid[0]
        conn.commit()
        _log_run_event(
            run_id,
            f"Pipeline run started delivery_type={delivery_type} schedule_key={schedule_key or '-'} triggered_by={triggered_by or '-'}",
        )

        env = {**os.environ}
        env.setdefault("PGHOST", env.get("PGHOST", "localhost"))
        env.setdefault("PGPORT", env.get("PGPORT", "5432"))

        stages = build_pipeline_stages()
        for stage_key, argv in stages:
            if _is_pipeline_cancel_requested(conn, run_id):
                note = f"Pipeline run cancelled before stage {stage_key}"
                _mark_run_cancelled(conn, run_id=run_id, notes=note)
                _log_run_event(run_id, note)
                break

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
                proc_result = _run_stage_process(
                    conn=conn,
                    run_id=run_id,
                    stage_key=stage_key,
                    argv=argv,
                    env=env,
                )
            except Exception as exc:
                err_msg = str(exc)
                _log_stage_output(
                    run_id=run_id,
                    stage_key=stage_key,
                    argv=argv,
                    stdout="",
                    stderr=err_msg,
                    exit_code=None,
                )
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
                        SET status = 'failed',
                            notes = %s,
                            completed_at = now(),
                            last_heartbeat_at = now(),
                            current_stage_key = NULL,
                            current_pid = NULL
                        WHERE run_id = %s
                        """,
                        (_tail(err_msg, 2000), run_id),
                    )
                conn.commit()
                _log_run_event(run_id, f"Pipeline run failed during stage {stage_key}: {err_msg}")
                break

            out_t = _tail(proc_result.stdout)
            err_t = _tail(proc_result.stderr)
            stage_status = (
                "cancelled"
                if proc_result.cancelled
                else "success" if proc_result.returncode == 0 else "failed"
            )
            _log_stage_output(
                run_id=run_id,
                stage_key=stage_key,
                argv=argv,
                stdout=proc_result.stdout,
                stderr=proc_result.stderr,
                exit_code=proc_result.returncode,
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.pipeline_run_stages
                    SET status = %s, exit_code = %s,
                        stdout_tail = %s, stderr_tail = %s,
                        completed_at = now()
                    WHERE stage_id = %s
                    """,
                    (stage_status, proc_result.returncode, out_t, err_t, stage_id),
                )
            conn.commit()
            _clear_run_current_stage(conn, run_id)

            if proc_result.cancelled:
                note = f"Pipeline run cancelled during stage {stage_key}"
                _mark_run_cancelled(conn, run_id=run_id, notes=note)
                _log_run_event(run_id, note)
                break

            if proc_result.returncode != 0:
                note = f"Stage {stage_key} exited with code {proc_result.returncode}"
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE public.pipeline_runs
                        SET status = 'failed',
                            notes = %s,
                            completed_at = now(),
                            last_heartbeat_at = now(),
                            current_stage_key = NULL,
                            current_pid = NULL
                        WHERE run_id = %s
                        """,
                        (_tail(note, 2000), run_id),
                    )
                conn.commit()
                _log_run_event(run_id, f"Pipeline run failed: {note}")
                break
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.pipeline_runs
                    SET status = 'success',
                        completed_at = now(),
                        last_heartbeat_at = now(),
                        current_stage_key = NULL,
                        current_pid = NULL
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
            conn.commit()
            _log_run_event(run_id, "Pipeline run completed successfully")

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
        elif final_status == "cancelled":
            result = {"status": "cancelled", "run_id": run_id}
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
        _reconcile_cancel_requested_runs(conn)
        conn.commit()
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
                    cancel_requested_at,
                    cancel_requested_by,
                    last_heartbeat_at,
                    current_stage_key,
                    current_pid,
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
        _reconcile_cancel_requested_runs(conn, run_id=run_id)
        conn.commit()
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
                    cancel_requested_at,
                    cancel_requested_by,
                    last_heartbeat_at,
                    current_stage_key,
                    current_pid,
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
