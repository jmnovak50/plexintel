from __future__ import annotations

import re

_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
_SENSITIVE_KEYS = {"authorization", "api_token", "token", "credential", "encrypted_api_token"}


def redact_text(value: object) -> str:
    return _BEARER.sub("Bearer [REDACTED]", str(value))


def safe_fields(values: dict[str, object]) -> dict[str, object]:
    return {
        key: "[REDACTED]" if key.lower() in _SENSITIVE_KEYS else redact_text(value)
        for key, value in values.items()
    }
