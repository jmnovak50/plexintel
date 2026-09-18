from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_BEARER = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "proxy_authorization",
        "api_key",
        "api_token",
        "token",
        "credential",
        "credentials",
        "encrypted_api_token",
        "client_secret",
        "access_token",
        "refresh_token",
        "id_token",
        "password",
        "cookie",
        "set_cookie",
    }
)
_SENSITIVE_SUFFIXES = ("_token", "_secret", "_credential", "_password", "_api_key")


def redact_text(value: object) -> str:
    return _BEARER.sub("Bearer [REDACTED]", str(value))


def _sensitive_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def redact_value(value: Any, *, key: object | None = None) -> Any:
    if key is not None and _sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {item_key: redact_value(item, key=item_key) for item_key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, BaseException):
        return redact_text(value)
    return value


def safe_fields(values: dict[str, object]) -> dict[str, object]:
    return redact_value(values)


def redact_processor(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return redact_value(event_dict)
