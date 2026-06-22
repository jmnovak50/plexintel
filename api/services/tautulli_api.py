from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

from api.services.app_settings import get_setting_value


class TautulliApiError(RuntimeError):
    """Raised when Tautulli cannot be reached or returns an invalid API response."""


class TautulliConfigError(TautulliApiError):
    """Raised when Tautulli connection settings are incomplete."""


@dataclass(frozen=True)
class TautulliConfig:
    api_url: str
    api_key: str
    base_url: str | None = None


def _clean_url(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.rstrip("/") if text else None


def normalize_tautulli_base_url(value: Any) -> str | None:
    url = _clean_url(value)
    if not url:
        return None
    if url.lower().endswith("/api/v2"):
        return url[:-7].rstrip("/")
    return url


def normalize_tautulli_api_url(*, api_url: Any = None, base_url: Any = None) -> str | None:
    api = _clean_url(api_url)
    if api:
        return api if api.lower().endswith("/api/v2") else f"{api}/api/v2"

    base = normalize_tautulli_base_url(base_url)
    if base:
        return f"{base}/api/v2"
    return None


def resolve_tautulli_config(
    *,
    api_url: Any = None,
    base_url: Any = None,
    api_key: Any = None,
    overrides: dict[str, Any] | None = None,
) -> TautulliConfig:
    configured_api_url = api_url
    configured_base_url = base_url
    configured_api_key = api_key

    if configured_api_url is None and configured_base_url is None:
        configured_api_url = get_setting_value("tautulli.api_url", overrides=overrides)
    if configured_base_url is None:
        configured_base_url = get_setting_value("tautulli.base_url", overrides=overrides)
    if configured_api_key is None:
        configured_api_key = get_setting_value("tautulli.api_key", overrides=overrides)

    normalized_api_url = normalize_tautulli_api_url(
        api_url=configured_api_url,
        base_url=configured_base_url,
    )
    normalized_base_url = normalize_tautulli_base_url(
        configured_base_url
        or configured_api_url
    )
    normalized_api_key = str(configured_api_key).strip() if configured_api_key else None

    if not normalized_api_url:
        raise TautulliConfigError("Tautulli API URL is not configured")
    if not normalized_api_key:
        raise TautulliConfigError("Tautulli API key is not configured")

    parsed = urlparse(normalized_api_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TautulliConfigError("Tautulli API URL must be an absolute HTTP(S) URL")

    return TautulliConfig(
        api_url=normalized_api_url,
        api_key=normalized_api_key,
        base_url=normalized_base_url,
    )


def tautulli_request(
    command: str,
    *,
    params: dict[str, Any] | None = None,
    config: TautulliConfig | None = None,
    timeout: float = 30,
    require_data: bool = True,
) -> Any:
    cfg = config or resolve_tautulli_config()
    request_params = dict(params or {})
    request_params["cmd"] = command
    request_params["apikey"] = cfg.api_key

    try:
        response = requests.get(cfg.api_url, params=request_params, timeout=timeout)
    except requests.Timeout as exc:
        raise TautulliApiError(f"Tautulli command '{command}' timed out") from exc
    except requests.RequestException as exc:
        raise TautulliApiError(
            f"Tautulli command '{command}' failed before a response was received"
        ) from exc

    if response.status_code in {401, 403}:
        raise TautulliApiError(
            f"Tautulli command '{command}' was rejected; check the API key"
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise TautulliApiError(
            f"Tautulli command '{command}' returned HTTP {response.status_code}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise TautulliApiError(
            f"Tautulli command '{command}' returned non-JSON content"
        ) from exc

    envelope = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(envelope, dict):
        raise TautulliApiError(
            f"Tautulli command '{command}' returned a malformed API envelope"
        )

    result = str(envelope.get("result") or "").lower()
    if result and result != "success":
        message = envelope.get("message") or "unknown Tautulli API error"
        raise TautulliApiError(f"Tautulli command '{command}' failed: {message}")

    if require_data and "data" not in envelope:
        raise TautulliApiError(
            f"Tautulli command '{command}' returned no response data"
        )

    return envelope.get("data")


def delete_tautulli_cache(
    *,
    config: TautulliConfig | None = None,
    timeout: float = 30,
) -> Any:
    return tautulli_request(
        "delete_cache",
        config=config,
        timeout=timeout,
        require_data=False,
    )
