from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from api.services.sora_storage_service import ensure_path_under_root, get_sora_storage_root


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RETENTION_HOURS = 24

logger = logging.getLogger(__name__)


def _retention_hours() -> float:
    raw_value = os.getenv("SORA_RETENTION_HOURS")
    if raw_value is None:
        return DEFAULT_RETENTION_HOURS
    try:
        hours = float(raw_value)
    except ValueError:
        logger.warning("Invalid SORA_RETENTION_HOURS=%r; using %s", raw_value, DEFAULT_RETENTION_HOURS)
        return DEFAULT_RETENTION_HOURS
    return max(hours, 0.0)


def cleanup_sora_files() -> int:
    root = get_sora_storage_root()
    if not root.exists():
        logger.info("Sora storage root does not exist: %s", root)
        return 0

    ensure_path_under_root(root, root)
    cutoff = time.time() - (_retention_hours() * 3600)
    deleted_count = 0

    for path in root.rglob("*"):
        try:
            ensure_path_under_root(path, root)
        except Exception:
            logger.warning("Skipping path outside Sora storage root: %s", path)
            continue

        if path.is_symlink() or not path.is_file():
            continue

        try:
            if path.stat().st_mtime <= cutoff:
                path.unlink()
                deleted_count += 1
                logger.info("Deleted old Sora file: %s", path)
        except OSError:
            logger.warning("Failed deleting Sora file: %s", path, exc_info=True)

    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            ensure_path_under_root(directory, root)
            directory.rmdir()
            logger.info("Removed empty Sora directory: %s", directory)
        except OSError:
            continue

    return deleted_count


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    deleted_count = cleanup_sora_files()
    logger.info("Sora cleanup complete. deleted_files=%s", deleted_count)


if __name__ == "__main__":
    main()
