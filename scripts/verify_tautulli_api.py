#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.services.tautulli_api import (  # noqa: E402
    TautulliApiError,
    delete_tautulli_cache,
    resolve_tautulli_config,
    tautulli_request,
)


@dataclass(frozen=True)
class ApiCheck:
    name: str
    ok: bool
    detail: str


def _section_id(section: Any) -> int | None:
    if isinstance(section, dict):
        for key in ("section_id", "sectionId", "library_section_id", "id", "key"):
            value = section.get(key)
            if value not in (None, ""):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
    return None


def _extract_sections(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ("data", "libraries", "sections", "library_sections"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    if "section_id" in data or "id" in data:
        return [data]

    sections: list[dict[str, Any]] = []
    for key, value in data.items():
        try:
            section_id = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            section = dict(value)
            section.setdefault("section_id", section_id)
        else:
            section = {"section_id": section_id, "section_name": str(value)}
        sections.append(section)
    return sections


def _extract_media_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ("data", "media", "rows", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _check_users(data: Any) -> str:
    if isinstance(data, dict):
        users = data.get("users")
        if isinstance(users, list):
            return f"{len(users)} user(s)"
    if isinstance(data, list):
        return f"{len(data)} user(s)"
    raise TautulliApiError("get_users returned an unexpected data shape")


def _check_dict(name: str, data: Any) -> str:
    if not isinstance(data, dict):
        raise TautulliApiError(f"{name} returned an unexpected data shape")
    return "received data"


def run_checks(*, include_cache_clear: bool = False, timeout: float = 15) -> list[ApiCheck]:
    checks: list[ApiCheck] = []

    try:
        config = resolve_tautulli_config()
    except TautulliApiError as exc:
        return [ApiCheck("configuration", False, str(exc))]

    def run(name: str, func) -> Any:
        try:
            detail, value = func()
            checks.append(ApiCheck(name, True, detail))
            return value
        except Exception as exc:
            checks.append(ApiCheck(name, False, str(exc)))
            raise

    try:
        run(
            "get_server_info",
            lambda: (
                _check_dict(
                    "get_server_info",
                    tautulli_request("get_server_info", config=config, timeout=timeout),
                ),
                None,
            ),
        )
        run(
            "get_users",
            lambda: (
                _check_users(tautulli_request("get_users", config=config, timeout=timeout)),
                None,
            ),
        )

        sections = run(
            "get_library_names",
            lambda: _library_names_check(config=config, timeout=timeout),
        )

        media_row = run(
            "get_library_media_info",
            lambda: _library_media_check(sections, config=config, timeout=timeout),
        )

        rating_key = media_row.get("rating_key")
        run(
            "get_metadata",
            lambda: _metadata_check(rating_key, config=config, timeout=timeout),
        )

        if include_cache_clear:
            run(
                "delete_cache",
                lambda: (
                    "cache clear accepted",
                    delete_tautulli_cache(config=config, timeout=timeout),
                ),
            )
        else:
            checks.append(
                ApiCheck("delete_cache", True, "not requested; pass --include-cache-clear to mutate cache")
            )
    except Exception:
        return checks

    return checks


def _library_names_check(*, config, timeout: float) -> tuple[str, list[dict[str, Any]]]:
    data = tautulli_request("get_library_names", config=config, timeout=timeout)
    sections = [section for section in _extract_sections(data) if _section_id(section) is not None]
    if not sections:
        raise TautulliApiError("get_library_names returned no library sections")
    return f"{len(sections)} section(s)", sections


def _library_media_check(
    sections: list[dict[str, Any]],
    *,
    config,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    empty_sections: list[int] = []
    for section in sections:
        sid = _section_id(section)
        if sid is None:
            continue
        data = tautulli_request(
            "get_library_media_info",
            params={"section_id": sid, "start": 0, "length": 1},
            config=config,
            timeout=timeout,
        )
        rows = _extract_media_rows(data)
        if not rows:
            empty_sections.append(sid)
            continue
        rating_key = rows[0].get("rating_key")
        if rating_key in (None, ""):
            raise TautulliApiError(
                f"get_library_media_info section {sid} returned a row without rating_key"
            )
        return f"section {sid} returned rating_key {rating_key}", rows[0]

    raise TautulliApiError(
        "get_library_media_info returned no media rows"
        + (f" for section(s): {empty_sections}" if empty_sections else "")
    )


def _metadata_check(rating_key: Any, *, config, timeout: float) -> tuple[str, Any]:
    if rating_key in (None, ""):
        raise TautulliApiError("cannot call get_metadata without a rating_key")
    data = tautulli_request(
        "get_metadata",
        params={"rating_key": rating_key},
        config=config,
        timeout=timeout,
    )
    if not isinstance(data, dict):
        raise TautulliApiError("get_metadata returned an unexpected data shape")
    title = data.get("title") or "<untitled>"
    return f"metadata read for rating_key {rating_key}: {title}", data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live Tautulli API access.")
    parser.add_argument(
        "--include-cache-clear",
        action="store_true",
        help="Also call delete_cache after all read-only checks pass.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15,
        help="Per-request timeout in seconds.",
    )
    args = parser.parse_args(argv)

    checks = run_checks(
        include_cache_clear=args.include_cache_clear,
        timeout=args.timeout,
    )
    failed = False
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"{status} {check.name}: {check.detail}")
        failed = failed or not check.ok

    if failed:
        return 1
    print("Tautulli API verification complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
