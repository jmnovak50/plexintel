#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.services.tautulli_api import (  # noqa: E402
    TautulliApiError,
    delete_tautulli_cache,
    resolve_tautulli_config,
)


DEFAULT_LOCK_PATH = Path("/tmp/plexintel-tautulli-sync.lock")
DEFAULT_DEBOUNCE_SECONDS = 90
DEFAULT_LOG_PATH = REPO_ROOT / "logs" / "tautulli_recently_added_sync.log"


def _log_path() -> Path:
    configured = os.environ.get("PLEXINTEL_TAUTULLI_SYNC_LOG")
    return Path(configured) if configured else DEFAULT_LOG_PATH


def _log(message: str, *, error: bool = False) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line, file=sys.stderr if error else sys.stdout)
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return default


def _open_lock(lock_path: Path) -> TextIO | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def _python_executable() -> str:
    configured = os.environ.get("PLEXINTEL_PYTHON")
    if configured:
        return configured
    venv_python = REPO_ROOT / "plexenv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _resolve_event_config():
    return resolve_tautulli_config(
        api_url=os.environ.get("TAUTULLI_API_URL"),
        base_url=os.environ.get("TAUTULLI_URL"),
        api_key=os.environ.get("TAUTULLI_APIKEY") or os.environ.get("TAUTULLI_API_KEY"),
    )


def run_incremental_sync() -> int:
    cmd = [
        _python_executable(),
        str(REPO_ROOT / "fetch_tautulli_data.py"),
        "--mode",
        "incremental",
    ]
    _log(f"Running incremental sync command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clear Tautulli cache and run PlexIntel incremental sync after Recently Added."
    )
    parser.add_argument(
        "--debounce-seconds",
        type=float,
        default=_env_float("PLEXINTEL_DEBOUNCE_SECONDS", DEFAULT_DEBOUNCE_SECONDS),
        help="Seconds to wait before clearing cache and syncing.",
    )
    parser.add_argument(
        "--lock-path",
        type=Path,
        default=Path(os.environ.get("PLEXINTEL_TAUTULLI_SYNC_LOCK", DEFAULT_LOCK_PATH)),
        help="File lock path used to prevent overlapping runs.",
    )
    args = parser.parse_args(argv)

    _log(
        "Recently Added sync invoked "
        f"pid={os.getpid()} debounce={args.debounce_seconds:g}s lock={args.lock_path}"
    )

    lock_file = _open_lock(args.lock_path)
    if lock_file is None:
        _log("PlexIntel Tautulli sync already running; skipping this event.")
        return 0

    with lock_file:
        if args.debounce_seconds > 0:
            _log(f"Waiting {args.debounce_seconds:g}s for recently-added batch to settle.")
            time.sleep(args.debounce_seconds)

        try:
            config = _resolve_event_config()
            _log(f"Resolved Tautulli API URL: {config.api_url}")
            delete_tautulli_cache(config=config, timeout=30)
        except TautulliApiError as exc:
            _log(f"Failed to clear Tautulli cache: {exc}", error=True)
            return 1

        _log("Tautulli cache cleared. Running PlexIntel incremental sync.")
        return_code = run_incremental_sync()
        if return_code != 0:
            _log(
                f"PlexIntel incremental sync failed with exit code {return_code}.",
                error=True,
            )
            return return_code

        _log("PlexIntel incremental sync complete.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
