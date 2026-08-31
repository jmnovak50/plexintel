import re
from urllib.parse import unquote, urlsplit

from app.config import Settings
from app.immich.client import InvalidShareLink

SHARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,512}$")


def validate_share_key(value: str) -> str:
    key = value.strip()
    if not SHARE_KEY_RE.fullmatch(key):
        raise InvalidShareLink("Share key has an invalid format")
    return key


def extract_share_key(value: str, settings: Settings) -> str:
    candidate = value.strip()
    if "://" not in candidate:
        return validate_share_key(candidate)
    parsed = urlsplit(candidate)
    if parsed.username or parsed.password:
        raise InvalidShareLink("Share URL credentials are not allowed")
    supplied_origin = _origin(parsed)
    if supplied_origin != settings.immich_origin:
        raise InvalidShareLink("Share URL host is not the configured Immich origin")
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    try:
        share_index = parts.index("share")
        key = parts[share_index + 1]
    except (ValueError, IndexError) as exc:
        raise InvalidShareLink("Share URL must contain /share/{key}") from exc
    if share_index + 2 != len(parts):
        raise InvalidShareLink("Share URL contains an unexpected path suffix")
    return validate_share_key(key)


def resolve_share_input(*, share_url: str | None, share_key: str | None, settings: Settings) -> str:
    if bool(share_url) == bool(share_key):
        raise InvalidShareLink("Provide exactly one of share_url or share_key")
    return extract_share_key(share_url or share_key or "", settings)


def _origin(parsed: object) -> str:
    scheme = getattr(parsed, "scheme", "").lower()
    hostname = getattr(parsed, "hostname", None)
    port = getattr(parsed, "port", None)
    default = (scheme == "https" and port in (None, 443)) or (scheme == "http" and port in (None, 80))
    authority = hostname if default else f"{hostname}:{port}"
    return f"{scheme}://{authority}"

