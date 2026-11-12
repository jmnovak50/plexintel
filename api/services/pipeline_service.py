from __future__ import annotations

import fcntl
import json
import os
import pwd
import re
import signal
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, time as time_of_day, timedelta
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.predictive.progress import EVENT, STAGES, STAGE_NAMES, EventReader, clean_metrics, event_details
from api.predictive.failures import VERIFICATION_ONLY_EXIT,classify_failure,failure_message

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / "plexenv" / "bin" / "python"
PIPELINE_SCRIPT = REPO_ROOT / "run_daily_pipeline.sh"

LOG_TAIL_MAX = 5000
PIPELINE_LOG_PATH_ENV = "PIPELINE_LOG_PATH"
DEFAULT_PIPELINE_LOG_PATH = REPO_ROOT / "logs" / "pipeline.log"
PIPELINE_LOCK_PATH_ENV = "PIPELINE_LOCK_PATH"
DEFAULT_PIPELINE_LOCK_PATH = REPO_ROOT / "logs" / "daily-pipeline.lock"
PIPELINE_CANCEL_POLL_SECONDS_ENV = "PIPELINE_CANCEL_POLL_SECONDS"
PIPELINE_CANCEL_GRACE_SECONDS_ENV = "PIPELINE_CANCEL_GRACE_SECONDS"
DEFAULT_CANCEL_POLL_SECONDS = 2.0
DEFAULT_CANCEL_GRACE_SECONDS = 10.0
PIPELINE_CANCEL_RECONCILE_GRACE_SECONDS_ENV = "PIPELINE_CANCEL_RECONCILE_GRACE_SECONDS"
TERMINAL_RUN_STATUSES = {"success", "failed", "cancelled", "verification_only"}
SCHEDULE_TERMINAL_STATUSES = {"success", "cancelled"}
ACTIVE_SCHEDULE_STATUSES = {"started", "cancel_requested"}
PIPELINE_PROCESS_MARKERS = (
    "predictive_pipeline.py",
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
    pid: int | None = None
    elapsed_seconds: float | None = None
    output_logged: bool = False


@dataclass
class PipelineFileLock:
    path: Path
    handle: Any
    source: str

    def release(self) -> None:
        if self.handle.closed:
            return
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


def _python_executable() -> str:
    if VENV_PYTHON.is_file():
        return str(VENV_PYTHON)
    return sys.executable


def build_pipeline_environment() -> dict[str, str]:
    env = dict(os.environ)
    try:
        user_entry = pwd.getpwuid(os.geteuid())
        env.setdefault("USER", user_entry.pw_name)
        env.setdefault("LOGNAME", user_entry.pw_name)
        env.setdefault("HOME", user_entry.pw_dir)
        env.setdefault("SHELL", user_entry.pw_shell or "/bin/bash")
    except Exception:
        pass
    venv_dir = VENV_PYTHON.parent.parent
    current_path = env.get("PATH", "")
    path_parts = [str(VENV_PYTHON.parent)]
    if current_path:
        path_parts.append(current_path)
    env["PATH"] = os.pathsep.join(path_parts)
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PWD"] = str(REPO_ROOT)
    python_path = env.get("PYTHONPATH", "")
    if str(REPO_ROOT) not in python_path.split(os.pathsep):
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(REPO_ROOT), python_path) if part
        )
    env.setdefault("PGHOST", "localhost")
    env.setdefault("PGPORT", "5432")
    return env


def _launch_environment_summary(*, source: str, env: dict[str, str]) -> str:
    try:
        effective_user = pwd.getpwuid(os.geteuid()).pw_name
    except Exception:
        effective_user = env.get("USER", "<unknown>")
    presence = " ".join(
        f"{key}_present={'true' if env.get(key) else 'false'}"
        for key in ("DB_HOST", "DB_NAME", "DB_USER", "DATABASE_URL")
    )
    return (
        f"pipeline invocation source={source} launcher_pid={os.getpid()} "
        f"effective_uid={os.geteuid()} effective_user={effective_user} "
        f"working_directory={REPO_ROOT} script_path={PIPELINE_SCRIPT} "
        f"python={_python_executable()} PATH={env.get('PATH', '<absent>')} "
        f"VIRTUAL_ENV={env.get('VIRTUAL_ENV', '<absent>')} "
        f"PYTHONPATH={env.get('PYTHONPATH', '<absent>')} {presence}"
    )


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
            WHERE current_stage_key IN (%s, %s, %s, %s)
              AND status NOT IN ('success', 'failed', 'cancelled')
        ) AS is_refreshing
        """,
        ("score_model", "shap", "publication", "verification"),
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


def _read_output_tail(handle, max_len: int = LOG_TAIL_MAX) -> str:
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(max(0, size - (max_len * 4)), os.SEEK_SET)
    data = handle.read()
    if isinstance(data, str):
        return _tail(data, max_len)
    return _tail(data.decode("utf-8", errors="replace"), max_len)


def _live_output_tail(handle, env, max_len=LOG_TAIL_MAX):
    """Read without moving the offset shared with the writing child."""
    size = os.fstat(handle.fileno()).st_size
    text = os.pread(handle.fileno(), min(size, max_len * 4), max(0, size - max_len * 4)).decode('utf-8', errors='replace')
    for key, value in env.items():
        if value and re.search(r'(?:^|_)(?:TOKEN|API_KEY|APIKEY|SECRET|PASSWORD)(?:_|$)', key, re.I):
            text = text.replace(value, '[REDACTED]')
    text = re.sub(r'(?i)(apikey|api_key|x-plex-token|password|token)=([^&\s]+)', r'\1=[REDACTED]', text)
    text = re.sub(r'(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+', r'\1[REDACTED]', text)
    return _tail(text, max_len)


@contextmanager
def _retained_stage_output(run_id, stage_key, stream):
    directory = get_pipeline_log_path().parent
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w+b', dir=directory,
            prefix=f'pipeline-run-{run_id}-{stage_key}-', suffix=f'.{stream}.log', delete=False) as handle:
        yield handle  # Mode 0600; retained even if the backend or child is killed.


def _save_live_output(run_id, stage_key, stdout, stderr):
    with _pipeline_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''UPDATE public.pipeline_run_stages SET stdout_tail=%s,stderr_tail=%s
                WHERE run_id=%s AND stage_key=%s''', (stdout, stderr, run_id, stage_key))


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


def get_pipeline_lock_path() -> Path:
    raw_path = os.getenv(PIPELINE_LOCK_PATH_ENV, "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return DEFAULT_PIPELINE_LOCK_PATH


def _pipeline_execution_locked():
    """A controller can still be finalizing after its child exits."""
    try:
        with get_pipeline_lock_path().open('rb') as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False
    except FileNotFoundError:
        return False
    except OSError:
        return True  # Uncertain ownership must not turn a live run into a failure.


def _append_pipeline_log(text: str) -> None:
    try:
        log_path = get_pipeline_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(text)
    except Exception as exc:
        print(f"Failed to write pipeline log file: {exc}", file=sys.stderr)


def _log_launcher_event(message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    _append_pipeline_log(f"[{timestamp}] [pipeline-launcher] {message}\n")


def try_acquire_pipeline_lock(*, source: str) -> PipelineFileLock | None:
    lock_path = get_pipeline_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        _log_launcher_event(
            f"pipeline invocation source={source} launcher_pid={os.getpid()} "
            f"lock_path={lock_path} lock_acquired=false another_pipeline_detected=true"
        )
        return None
    except Exception:
        handle.close()
        raise

    _log_launcher_event(
        f"pipeline invocation source={source} launcher_pid={os.getpid()} "
        f"lock_path={lock_path} lock_acquired=true another_pipeline_detected=false"
    )
    return PipelineFileLock(path=lock_path, handle=handle, source=source)


@contextmanager
def _pipeline_connection(*, cursor_factory=RealDictCursor) -> Iterator[Any]:
    """Commit or roll back, then promptly release a pipeline-status connection."""
    conn = connect_db(cursor_factory=cursor_factory)
    try:
        yield conn
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _log_run_event(run_id: int, message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    _append_pipeline_log(f"[{timestamp}] [run:{run_id}] {message}\n")


def _append_file_to_log(log_file, source_file) -> None:
    source_file.seek(0)
    while True:
        chunk = source_file.read(1024 * 1024)
        if not chunk:
            return
        log_file.write(chunk)


def _log_stage_output_files(
    *,
    run_id: int,
    stage_key: str,
    argv: list[str],
    stdout_file,
    stderr_file,
    exit_code: int | None,
) -> None:
    """Stream complete disk-backed output to the log without buffering it in RAM."""
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        log_path = get_pipeline_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_file:
            header = (
                f"\n[{timestamp}] [run:{run_id}] [stage:{stage_key}] command: {shlex.join(argv)}\n"
                f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] exit_code: {exit_code}\n"
                f"[{timestamp}] [run:{run_id}] [stage:{stage_key}] stdout:\n"
            )
            log_file.write(header.encode("utf-8", errors="replace"))
            _append_file_to_log(log_file, stdout_file)
            log_file.write(
                f"\n[{timestamp}] [run:{run_id}] [stage:{stage_key}] stderr:\n".encode()
            )
            _append_file_to_log(log_file, stderr_file)
            log_file.write(
                f"\n[{timestamp}] [run:{run_id}] [stage:{stage_key}] end\n".encode()
            )
    except Exception as exc:
        print(f"Failed to stream stage output to pipeline log: {exc}", file=sys.stderr)


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


def _read_pipeline_cancel_requested(run_id: int) -> bool:
    with _pipeline_connection() as conn:
        return _is_pipeline_cancel_requested(conn, run_id)


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


def _update_run_heartbeat_short(
    *,
    run_id: int,
    stage_key: str | None,
    pid: int | None,
) -> None:
    with _pipeline_connection() as conn:
        _update_run_heartbeat(conn, run_id=run_id, stage_key=stage_key, pid=pid)


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


def _mark_run_cancelled_short(*, run_id: int, notes: str) -> None:
    with _pipeline_connection() as conn:
        _mark_run_cancelled(conn, run_id=run_id, notes=notes)


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


def _reconcile_cancel_requested_runs(conn, *, run_id: int | None = None, execution_lock_held: bool = False) -> int:
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
                status,
                delivery_type,
                last_heartbeat_at,
                current_pid,
                current_stage_key,
                cancel_requested_at,
                EXISTS(SELECT 1 FROM public.pipeline_run_stages s WHERE s.run_id=public.pipeline_runs.run_id) AS has_stages
            FROM public.pipeline_runs
            WHERE status IN ('cancel_requested','started')
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
        if row.get('status') == 'started':
            # A null PID after dispatch may hide a live, unregistered child.
            # Only a provably pre-dispatch row is eligible for null-PID cleanup.
            if pid is None and (row.get('current_stage_key') or row.get('has_stages')):continue
            # Heartbeat age alone never means failure: a live worker may be busy.
            if (str(row.get('delivery_type', '')).startswith('content_discovery_')
                    or not _is_older_than(row.get('last_heartbeat_at'), 30)
                    or (pid is not None and _process_exists(pid))
                    or (not execution_lock_held and _pipeline_execution_locked())):
                continue
            note = ('Worker process disappeared before completion (for example after a backend restart). '
                    'Completion time is unknown; this record was reconciled now. '
                    'Existing production checkpoints are retained for manual resume.')
            with conn.cursor() as cur:
                cur.execute('''UPDATE public.pipeline_runs SET status='failed',completed_at=now(),
                    current_pid=NULL,current_stage_key=NULL,notes=CONCAT_WS(E'\\n',NULLIF(notes,''),%s)
                    WHERE run_id=%s AND status='started' AND current_pid IS NOT DISTINCT FROM %s
                      AND last_heartbeat_at IS NOT DISTINCT FROM %s
                      AND (current_pid IS NOT NULL OR NOT EXISTS
                        (SELECT 1 FROM public.pipeline_run_stages s WHERE s.run_id=public.pipeline_runs.run_id))
                    RETURNING run_id''',
                    (note, rid, pid, row.get('last_heartbeat_at')))
                if cur.fetchone() is None:
                    continue  # The controller advanced after our observation.
                cur.execute('''UPDATE public.pipeline_run_stages SET
                    status=CASE WHEN status='started' THEN 'failed' ELSE 'skipped' END,
                    completed_at=now(),stderr_tail=CONCAT_WS(E'\\n',NULLIF(stderr_tail,''),%s)
                    WHERE run_id=%s AND status IN ('started','pending')''', (note, rid))
            reconciled_count += 1
            _log_run_event(rid, note)
            continue
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
                SELECT run_id, status, current_pid, delivery_type
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

            delivery = row.get('delivery_type', '') if hasattr(row, 'get') else (row[3] if len(row)>3 else '')
            if str(delivery).startswith('content_discovery_'):
                # This worker is not an ML subprocess. Marking it cancelled here
                # would falsely imply that its canonical writer had stopped.
                return {"status": "independent_workflow", "run_id": run_id}

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


class PipelineStageObserver:
    """Observe one existing worker; never launch, cancel or publish anything."""
    def __init__(self, run_id):
        self.run_id = run_id
        self.events = {}
        self.initialized = False
        self.current_key = 'embeddinggemma2_generation'

    def accept(self, event):
        if event.get('event') != EVENT or event.get('stage_key') not in STAGE_NAMES:return
        key = event['stage_key']
        if event.get('status') not in {'started','success','failed','cancelled','pending','skipped','not_recorded'}:return
        try:
            at = datetime.fromisoformat(event['at'])
            if at.tzinfo is None:return
            seconds = float(event['elapsed_seconds'])
            if not 0 <= seconds < 1e9:return
        except (KeyError, ValueError, TypeError):return
        event = dict(event, metrics=clean_metrics(event.get('metrics') or {}))
        # EventReader accepts only known stages/statuses; keep a bounded payload.
        payload = json.dumps(event, allow_nan=False)
        if len(payload) > LOG_TAIL_MAX:return
        status = event['status']
        with _pipeline_connection() as conn:
            with conn.cursor() as cur:
                if not self.initialized:
                    for stage, _ in STAGES:
                        cur.execute("""INSERT INTO public.pipeline_run_stages(run_id,stage_key,status)
                            VALUES(%s,%s,'pending')""", (self.run_id, stage))
                cur.execute("""UPDATE public.pipeline_run_stages SET status=%s,stdout_tail=%s,
                    started_at=CASE WHEN status='pending' THEN %s ELSE started_at END,
                    completed_at=CASE WHEN %s='started' THEN NULL ELSE COALESCE(completed_at,%s) END
                    WHERE run_id=%s AND stage_key=%s""",
                    (status, payload, at, status, at, self.run_id, key))
        self.initialized = True
        self.events[key] = event
        if status == 'started':self.current_key = key

    def finish(self, *, cancelled, returncode):
        from datetime import timezone
        if not self.initialized:return
        for key, _ in STAGES:
            old = self.events.get(key, {})
            if old.get('status') in ('success', 'failed', 'cancelled', 'skipped'):continue
            active = old.get('status') == 'started'
            status = ('cancelled' if cancelled else 'failed') if active and (cancelled or returncode) else (
                'skipped' if cancelled or returncode else 'not_recorded')
            self.accept(dict(event=EVENT, stage_key=key, status=status,
                at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=old.get('elapsed_seconds', 0.),
                metrics=old.get('metrics', {}), message='Worker cancelled' if cancelled else (
                    'Worker exited before stage completed' if active else 'Stage not reached or not recorded')))


def _run_stage_process(
    *,
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

    with _retained_stage_output(run_id, stage_key, 'stdout') as stdout_file:
        with _retained_stage_output(run_id, stage_key, 'stderr') as stderr_file:
            started_at = datetime.now().astimezone()
            started_monotonic = time.monotonic()
            proc = subprocess.Popen(
                argv,
                cwd=str(REPO_ROOT),
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
            cancelled = False
            observer = PipelineStageObserver(run_id) if stage_key in ('embeddinggemma2_generation','predictive_daily') else None
            reader = EventReader(stdout_file) if observer else None
            observation_failed = False
            last_output = None

            def retain_live_output():
                nonlocal last_output
                try:
                    output = (_live_output_tail(stdout_file, env), _live_output_tail(stderr_file, env))
                    if output != last_output:
                        _save_live_output(run_id, stage_key, *output)
                        last_output = output
                except Exception as exc:
                    # Log observation must not strand a child or disable cancellation.
                    _log_run_event(run_id, 'Live log observation unavailable: '+type(exc).__name__)

            def observe(*, drain=False):
                nonlocal observation_failed
                if not reader or observation_failed:return
                try:
                    while True:
                        events, more = reader.read()
                        for event in events:observer.accept(event)
                        if not drain or not more:break
                except Exception as exc:
                    # Monitoring must not strand a running child or bypass cancellation.
                    observation_failed = True
                    _log_run_event(run_id, 'Stage observation unavailable: '+type(exc).__name__)

            _update_run_heartbeat_short(run_id=run_id, stage_key=stage_key, pid=proc.pid)
            _log_run_event(
                run_id,
                f"child launched stage={stage_key} child_pid={proc.pid} "
                f"start_timestamp={started_at.isoformat(timespec='seconds')} "
                f"stdout_log={stdout_file.name} stderr_log={stderr_file.name}",
            )

            while proc.poll() is None:
                observe()
                retain_live_output()
                if _read_pipeline_cancel_requested(run_id):
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
                if proc.poll() is None:
                    _update_run_heartbeat_short(
                        run_id=run_id,
                        stage_key=observer.current_key if observer and not observation_failed else stage_key,
                        pid=proc.pid,
                    )

            if proc.poll() is None:
                proc.wait()

            observe(drain=True)
            retain_live_output()
            if observer and not observation_failed:
                try:observer.finish(cancelled=cancelled, returncode=0 if proc.returncode==VERIFICATION_ONLY_EXIT else proc.returncode)
                except Exception as exc:_log_run_event(run_id, 'Stage observation incomplete: '+type(exc).__name__)

            elapsed_seconds = time.monotonic() - started_monotonic
            completed_at = datetime.now().astimezone()
            _log_stage_output_files(
                run_id=run_id,
                stage_key=stage_key,
                argv=argv,
                stdout_file=stdout_file,
                stderr_file=stderr_file,
                exit_code=proc.returncode,
            )
            stdout = _live_output_tail(stdout_file, env)
            stderr = _live_output_tail(stderr_file, env)
            _log_run_event(
                run_id,
                f"child completed stage={stage_key} child_pid={proc.pid} "
                f"exit_code={proc.returncode} completion_timestamp="
                f"{completed_at.isoformat(timespec='seconds')} elapsed_seconds={elapsed_seconds:.3f}",
            )
            return StageProcessResult(
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                cancelled=cancelled,
                pid=proc.pid,
                elapsed_seconds=elapsed_seconds,
                output_logged=True,
            )


def build_pipeline_stages() -> list[tuple[str, list[str]]]:
    """Ordered stages matching run_daily_pipeline.sh (single source for app runs)."""
    py = _python_executable()
    root = str(REPO_ROOT)
    # Daily operation retains the explicitly approved historical descriptions;
    # canonical identity and temporal supervision remain enforced by the worker.
    return [("predictive_daily", [py, f"{root}/scripts/predictive_pipeline.py", "daily", "--execute", "--allow-stored-history"])]


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


def _scheduled_retry_state(conn, schedule_key: str, *, now_utc: datetime | None = None) -> dict[str, Any] | None:
    """Count durable attempts across worker restarts; only exit 75 is retryable."""
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) OVER() AS failures,r.completed_at,
            (SELECT s.exit_code FROM public.pipeline_run_stages s WHERE s.run_id=r.run_id
                AND s.status='failed'
                ORDER BY CASE s.stage_key WHEN 'controller_dispatch' THEN 2
                    WHEN 'embeddinggemma2_generation' THEN 1 ELSE 0 END DESC,s.stage_id DESC LIMIT 1) AS exit_code
            FROM public.pipeline_runs r WHERE r.schedule_key=%s AND r.status='failed'
            ORDER BY r.run_id DESC LIMIT 1""",(schedule_key,))
        row=cur.fetchone()
    if row is None:return None
    if not isinstance(row,dict):row=dict(zip(('failures','completed_at','exit_code'),row))
    if row['exit_code']!=75:return dict(status='requires_operator',schedule_key=schedule_key)
    limit=int(get_setting_value('pipeline.max_attempts',default=3))
    if row['failures']>=limit:return dict(status='retry_exhausted',schedule_key=schedule_key)
    delay=int(get_setting_value('pipeline.retry_backoff_seconds',default=300))
    completed=row['completed_at']
    if completed is None:return dict(status='requires_operator',schedule_key=schedule_key)
    now=now_utc or datetime.now(ZoneInfo('UTC'))
    retry_at=completed+timedelta(seconds=delay)
    if now<retry_at:return dict(status='retry_backoff',schedule_key=schedule_key,retry_at=retry_at.isoformat())
    return None


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
        blocked=_scheduled_retry_state(conn,schedule_key)
        if blocked:return blocked
    finally:
        conn.close()

    return run_pipeline(
        delivery_type="scheduled",
        triggered_by=triggered_by or "app-scheduler",
        schedule_key=schedule_key,
        invocation_source="app-scheduler",
    )


def _finalize_controller_failure(run_id: int, exc: Exception) -> bool:
    """Best effort after dispatch/controller failure; never overrides completion."""
    failure=classify_failure(exc)
    note=json.dumps(dict(outcome='controller_failed',error=failure_message(exc),**failure))
    try:
        with _pipeline_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE public.pipeline_runs SET status='failed',notes=%s,
                    completed_at=now(),last_heartbeat_at=now(),current_pid=NULL,current_stage_key=NULL
                    WHERE run_id=%s AND status='started' RETURNING run_id""",(note,run_id))
                if cur.fetchone() is None:return False
                cur.execute("""INSERT INTO public.pipeline_run_stages
                    (run_id,stage_key,status,exit_code,completed_at,stderr_tail)
                    VALUES(%s,'controller_dispatch','failed',%s,now(),%s)""",
                    (run_id,75 if failure['retryable'] else 78,note))
                cur.execute("""UPDATE public.pipeline_run_stages SET status='failed',completed_at=now()
                    WHERE run_id=%s AND status='started'""",(run_id,))
        return True
    except Exception:
        # The abandoned null-PID row is reconciled only when old and unlocked.
        return False


def run_pipeline(
    *,
    delivery_type: str,
    triggered_by: str | None,
    schedule_key: str | None,
    invocation_source: str | None = None,
    acquired_lock: PipelineFileLock | None = None,
) -> dict[str, Any]:
    source = invocation_source or delivery_type
    pipeline_lock = acquired_lock or try_acquire_pipeline_lock(source=source)
    if pipeline_lock is None:
        return {"status": "locked"}

    run_id: int | None = None
    run_started_monotonic = time.monotonic()
    try:
        if schedule_key is not None and delivery_type == "scheduled":
            with _pipeline_connection() as conn:
                _reconcile_cancel_requested_runs(conn,execution_lock_held=True)
                if _has_terminal_scheduled_run_for_schedule_key(conn, schedule_key):
                    return {"status": "already_ran", "schedule_key": schedule_key}
                if _has_active_run_for_schedule_key(conn, schedule_key):
                    return {"status": "already_running", "schedule_key": schedule_key}
                blocked=_scheduled_retry_state(conn,schedule_key)
                if blocked:return blocked

        with _pipeline_connection() as conn:
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

        env = build_pipeline_environment()
        _log_run_event(
            run_id,
            f"Pipeline run started delivery_type={delivery_type} schedule_key={schedule_key or '-'} "
            f"triggered_by={triggered_by or '-'} lock_acquired=true lock_path={pipeline_lock.path}",
        )
        _log_run_event(run_id, _launch_environment_summary(source=source, env=env))

        stages = build_pipeline_stages()
        for stage_key, argv in stages:
            if _read_pipeline_cancel_requested(run_id):
                note = f"Pipeline run cancelled before stage {stage_key}"
                _mark_run_cancelled_short(run_id=run_id, notes=note)
                _log_run_event(run_id, note)
                break

            with _pipeline_connection() as conn:
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

            try:
                proc_result = _run_stage_process(
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
                with _pipeline_connection() as conn:
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
                _log_run_event(run_id, f"Pipeline run failed during stage {stage_key}: {err_msg}")
                break

            out_t = _tail(proc_result.stdout)
            err_t = _tail(proc_result.stderr)
            stage_status = (
                "cancelled"
                if proc_result.cancelled
                else "verification_only" if proc_result.returncode == VERIFICATION_ONLY_EXIT
                else "success" if proc_result.returncode == 0 else "failed"
            )
            if not proc_result.output_logged:
                _log_stage_output(
                    run_id=run_id,
                    stage_key=stage_key,
                    argv=argv,
                    stdout=proc_result.stdout,
                    stderr=proc_result.stderr,
                    exit_code=proc_result.returncode,
                )
            with _pipeline_connection() as conn:
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
                    cur.execute(
                        """
                        UPDATE public.pipeline_runs
                        SET last_heartbeat_at = now(),
                            current_stage_key = NULL,
                            current_pid = NULL
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )

            if proc_result.cancelled:
                note = f"Pipeline run cancelled during stage {stage_key}"
                _mark_run_cancelled_short(run_id=run_id, notes=note)
                _log_run_event(run_id, note)
                break

            if proc_result.returncode == VERIFICATION_ONLY_EXIT:
                note=json.dumps(dict(outcome='verification_only',fresh_workload_completed=False))
                with _pipeline_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE public.pipeline_runs SET status='verification_only',notes=%s,
                            completed_at=now(),last_heartbeat_at=now(),current_stage_key=NULL,current_pid=NULL
                            WHERE run_id=%s""",(note,run_id))
                break  # This schedule slot still needs a fresh daily workload.

            if proc_result.returncode != 0:
                note = f"Stage {stage_key} exited with code {proc_result.returncode}"
                note += ('; transient failure, automatic retry subject to limits/backoff'
                         if proc_result.returncode==75 else '; automatic retry blocked: operator review required')
                with _pipeline_connection() as conn:
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
                _log_run_event(run_id, f"Pipeline run failed: {note}")
                break
        else:
            with _pipeline_connection() as conn:
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
            _log_run_event(
                run_id,
                f"Pipeline run completed successfully elapsed_seconds="
                f"{time.monotonic() - run_started_monotonic:.3f}",
            )

        result: dict[str, Any] = {"status": "success", "run_id": run_id}
        with _pipeline_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM public.pipeline_runs WHERE run_id = %s",
                    (run_id,),
                )
                r = cur.fetchone()
                final_status = r["status"] if isinstance(r, dict) else r[0]
        if final_status == "failed":
            result = {"status": "failed", "run_id": run_id}
        elif final_status == "cancelled":
            result = {"status": "cancelled", "run_id": run_id}
        elif final_status == "success":
            result = {"status": "success", "run_id": run_id}
        elif final_status == 'verification_only':
            result = dict(status='verification_only',run_id=run_id,fresh_workload_completed=False)
        return result
    except Exception as exc:
        if run_id is not None:
            persisted=_finalize_controller_failure(run_id,exc)
            return dict(status='failed',run_id=run_id,failure_persisted=persisted,**classify_failure(exc))
        raise
    finally:
        pipeline_lock.release()


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

        from api.services.pipeline_visibility import enrich_runs
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            enrich_runs(cur, out_runs)

        return {"runs": out_runs}
    finally:
        conn.close()


def purge_pipeline_runs(*, keep: int) -> dict[str, int]:
    """Delete older terminal run history while preserving scheduler safety markers."""
    current_schedule_key = get_pipeline_schedule_slot()["schedule_key"]
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH ranked_terminal_runs AS (
                    SELECT
                        run_id,
                        schedule_key,
                        ROW_NUMBER() OVER (
                            ORDER BY started_at DESC, run_id DESC
                        ) AS retention_rank
                    FROM public.pipeline_runs
                    WHERE status IN %s
                ),
                purge_candidates AS (
                    SELECT run_id
                    FROM ranked_terminal_runs
                    WHERE retention_rank > %s
                      AND schedule_key IS DISTINCT FROM %s
                )
                DELETE FROM public.pipeline_runs
                WHERE run_id IN (SELECT run_id FROM purge_candidates)
                RETURNING run_id
                """,
                (
                    tuple(sorted(TERMINAL_RUN_STATUSES)),
                    keep,
                    current_schedule_key,
                ),
            )
            deleted_rows = list(cur.fetchall() or [])
        conn.commit()
        return {"keep": keep, "deleted_count": len(deleted_rows)}
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
        from api.services.pipeline_visibility import enrich_runs
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            enrich_runs(cur, [rdict])
        return rdict
    finally:
        conn.close()
