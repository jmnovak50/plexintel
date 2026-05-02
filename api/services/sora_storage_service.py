from __future__ import annotations

import os
import re
from pathlib import Path


DEFAULT_SORA_STORAGE_ROOT = Path("/home/jmnovak/.sora")
SAFE_USER_ID_MAX_LENGTH = 80
SAFE_USER_ID_FALLBACK = "unknown_user"
SAFE_MP4_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.mp4$")
SAFE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class SoraStorageError(RuntimeError):
    pass


def get_sora_storage_root() -> Path:
    return Path(os.getenv("SORA_STORAGE_ROOT") or DEFAULT_SORA_STORAGE_ROOT).expanduser().resolve()


def sanitize_openwebui_user_id(user_id: str | None) -> str:
    value = (user_id or SAFE_USER_ID_FALLBACK).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    if not value:
        value = SAFE_USER_ID_FALLBACK
    return value[:SAFE_USER_ID_MAX_LENGTH].strip("_") or SAFE_USER_ID_FALLBACK


def validate_safe_user_id(safe_user_id: str) -> str:
    normalized = sanitize_openwebui_user_id(safe_user_id)
    if normalized != safe_user_id:
        raise SoraStorageError("safe_user_id is invalid.")
    return normalized


def validate_video_id_for_filename(video_id: str) -> str:
    if not SAFE_VIDEO_ID_RE.fullmatch(video_id or ""):
        raise SoraStorageError("video_id is invalid for local storage.")
    return video_id


def validate_mp4_filename(filename: str) -> str:
    if not SAFE_MP4_FILENAME_RE.fullmatch(filename or ""):
        raise SoraStorageError("filename is invalid.")
    return filename


def ensure_path_under_root(path: Path, root: Path | None = None) -> Path:
    resolved_root = (root or get_sora_storage_root()).resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SoraStorageError("Resolved path escapes Sora storage root.") from exc
    return resolved_path


def get_user_directory(openwebui_user_id: str | None, *, create: bool = True) -> tuple[str, Path]:
    root = get_sora_storage_root()
    safe_user_id = sanitize_openwebui_user_id(openwebui_user_id)
    user_dir = ensure_path_under_root(root / safe_user_id, root)
    if create:
        user_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            user_dir.chmod(0o700)
        except PermissionError:
            pass
    return safe_user_id, user_dir


def save_video_content(
    *,
    video_id: str,
    content: bytes,
    openwebui_user_id: str | None,
) -> tuple[str, Path]:
    safe_video_id = validate_video_id_for_filename(video_id)
    safe_user_id, user_dir = get_user_directory(openwebui_user_id, create=True)
    file_path = ensure_path_under_root(user_dir / f"{safe_video_id}.mp4")
    file_path.write_bytes(content)
    try:
        file_path.chmod(0o600)
    except PermissionError:
        pass
    return safe_user_id, file_path


def get_local_video_path(*, safe_user_id: str, filename: str) -> Path:
    root = get_sora_storage_root()
    validated_user_id = validate_safe_user_id(safe_user_id)
    validated_filename = validate_mp4_filename(filename)
    return ensure_path_under_root(root / validated_user_id / validated_filename, root)


def build_stream_url(*, safe_user_id: str, filename: str) -> str:
    validate_safe_user_id(safe_user_id)
    validate_mp4_filename(filename)
    return f"/api/agent/video/local/{safe_user_id}/{filename}"
