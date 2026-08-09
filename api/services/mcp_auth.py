from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
import jwt
from jwt import PyJWKClient

from api.db.users import get_user_by_email
from api.services.app_settings import get_setting_value

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
JWKS_CACHE_TTL_SECONDS = 3600

_jwks_clients: dict[str, tuple[PyJWKClient, float]] = {}


@dataclass(frozen=True)
class MCPAuthContext:
    auth_method: str
    email: str | None = None
    plex_username: str | None = None
    user_id: int | None = None
    is_admin: bool = False


@dataclass(frozen=True)
class MCPOAuthSettings:
    issuer_url: str | None
    audience: str | None
    email_claim: str
    resource_url: str | None = None
    required_scopes: tuple[str, ...] = ("plexintel.read",)


class MCPTokenStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    WRONG_ISSUER = "wrong_issuer"
    WRONG_AUDIENCE = "wrong_audience"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    UNMAPPED_EMAIL = "unmapped_email"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass(frozen=True)
class MCPTokenValidation:
    status: MCPTokenStatus
    context: MCPAuthContext | None = None
    claims: dict[str, Any] | None = None


def get_mcp_oauth_settings() -> MCPOAuthSettings:
    resource_url = _normalize_resource_url(get_setting_value("mcp.oauth.resource_url"))
    return MCPOAuthSettings(
        issuer_url=_normalize_issuer_url(get_setting_value("mcp.oauth.issuer_url")),
        audience=_normalize_optional(get_setting_value("mcp.oauth.audience")),
        email_claim=_normalize_optional(get_setting_value("mcp.oauth.email_claim")) or "email",
        resource_url=resource_url,
        required_scopes=_split_scopes(get_setting_value("mcp.oauth.required_scopes", default="plexintel.read")),
    )


def reset_jwks_cache() -> None:
    _jwks_clients.clear()


def authenticate_bearer_token(token: str, oauth_settings: MCPOAuthSettings | None = None) -> MCPAuthContext | None:
    result = validate_bearer_token(token, oauth_settings)
    return result.context if result.status in (MCPTokenStatus.VALID, MCPTokenStatus.UNMAPPED_EMAIL) else None


def validate_bearer_token(token: str, oauth_settings: MCPOAuthSettings | None = None) -> MCPTokenValidation:
    normalized = (token or "").strip()
    if not normalized:
        return MCPTokenValidation(MCPTokenStatus.INVALID)

    settings = oauth_settings or get_mcp_oauth_settings()
    expected_audience = settings.audience or settings.resource_url
    if not settings.issuer_url or not expected_audience or not settings.required_scopes:
        return MCPTokenValidation(MCPTokenStatus.CONFIGURATION_ERROR)

    decoded = _decode_jwt_result(normalized, settings, expected_audience)
    if decoded.status is not MCPTokenStatus.VALID:
        return decoded
    claims = decoded.claims
    assert claims is not None

    if not set(settings.required_scopes).issubset(_extract_scopes(claims)):
        return MCPTokenValidation(MCPTokenStatus.INSUFFICIENT_SCOPE)

    email = extract_email_from_claims(claims, settings.email_claim)
    if not email:
        logger.info("MCP JWT authenticated but no email claim was found")
        return MCPTokenValidation(MCPTokenStatus.UNMAPPED_EMAIL, MCPAuthContext(auth_method="jwt", email=None))

    user = get_user_by_email(email)
    if user:
        return MCPTokenValidation(
            MCPTokenStatus.VALID,
            MCPAuthContext(
                auth_method="jwt",
                email=email,
                plex_username=user.get("username"),
                user_id=user.get("user_id"),
                is_admin=bool(user.get("is_admin")),
            ),
        )

    return MCPTokenValidation(
        MCPTokenStatus.UNMAPPED_EMAIL,
        MCPAuthContext(auth_method="jwt", email=email),
    )


def extract_email_from_claims(claims: dict[str, Any], email_claim: str) -> str | None:
    for key in (email_claim, "email", "preferred_username"):
        value = claims.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if EMAIL_PATTERN.match(normalized):
                return normalized
    return None


def _decode_jwt(token: str, settings: MCPOAuthSettings) -> dict[str, Any] | None:
    expected_audience = settings.audience or settings.resource_url
    if not expected_audience:
        return None
    result = _decode_jwt_result(token, settings, expected_audience)
    return result.claims if result.status is MCPTokenStatus.VALID else None


def _decode_jwt_result(token: str, settings: MCPOAuthSettings, expected_audience: str) -> MCPTokenValidation:
    try:
        signing_key = _get_signing_key(token, settings.issuer_url)
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            "options": {"verify_aud": True, "verify_iss": False},
            "audience": expected_audience,
        }
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
        token_issuer = claims.get("iss")
        if not _issuer_matches(token_issuer, settings.issuer_url):
            logger.info("MCP JWT issuer mismatch")
            return MCPTokenValidation(MCPTokenStatus.WRONG_ISSUER)
        return MCPTokenValidation(MCPTokenStatus.VALID, claims=claims)
    except jwt.ExpiredSignatureError:
        logger.info("MCP JWT validation failed: expired token")
        return MCPTokenValidation(MCPTokenStatus.EXPIRED)
    except jwt.ImmatureSignatureError:
        logger.info("MCP JWT validation failed: token not yet valid")
        return MCPTokenValidation(MCPTokenStatus.NOT_YET_VALID)
    except jwt.InvalidAudienceError:
        logger.info("MCP JWT validation failed: audience mismatch")
        return MCPTokenValidation(MCPTokenStatus.WRONG_AUDIENCE)
    except jwt.PyJWTError:
        logger.info("MCP JWT validation failed")
        return MCPTokenValidation(MCPTokenStatus.INVALID)
    except (httpx.HTTPError, ValueError):
        logger.warning("MCP JWT validation could not load issuer keys")
        return MCPTokenValidation(MCPTokenStatus.CONFIGURATION_ERROR)


def _issuer_matches(token_issuer: Any, configured_issuer: str | None) -> bool:
    if not configured_issuer or not isinstance(token_issuer, str):
        return False
    return token_issuer == configured_issuer


def resolve_context_from_email(email: str, auth_method: str) -> MCPAuthContext:
    normalized = (email or "").strip()
    if not normalized:
        return MCPAuthContext(auth_method=auth_method)

    user = get_user_by_email(normalized)
    if user:
        return MCPAuthContext(
            auth_method=auth_method,
            email=normalized,
            plex_username=user.get("username"),
            user_id=user.get("user_id"),
            is_admin=bool(user.get("is_admin")),
        )
    return MCPAuthContext(auth_method=auth_method, email=normalized)


def _get_signing_key(token: str, issuer_url: str):
    client = _get_jwks_client(issuer_url)
    return client.get_signing_key_from_jwt(token)


def _get_jwks_client(issuer_url: str) -> PyJWKClient:
    now = time.time()
    cached = _jwks_clients.get(issuer_url)
    if cached and now - cached[1] < JWKS_CACHE_TTL_SECONDS:
        return cached[0]

    jwks_uri = _fetch_jwks_uri(issuer_url)
    client = PyJWKClient(jwks_uri, cache_keys=True)
    _jwks_clients[issuer_url] = (client, now)
    return client


def _fetch_jwks_uri(issuer_url: str) -> str:
    discovery_url = urljoin(f"{issuer_url}/", ".well-known/openid-configuration")
    with httpx.Client(timeout=10.0) as client:
        response = client.get(discovery_url)
        response.raise_for_status()
        payload = response.json()
    jwks_uri = payload.get("jwks_uri")
    if not jwks_uri:
        raise ValueError(f"OIDC discovery for {issuer_url} did not return jwks_uri")
    return str(jwks_uri)


def _normalize_issuer_url(value: str | None) -> str | None:
    return _normalize_optional(value)


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_resource_url(value: str | None) -> str | None:
    normalized = _normalize_optional(value)
    if not normalized:
        return None
    parts = urlsplit(normalized)
    if not parts.scheme or not parts.netloc:
        return normalized
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))


def _split_scopes(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(part for part in re.split(r"[\s,]+", str(value).strip()) if part))


def _extract_scopes(claims: dict[str, Any]) -> set[str]:
    scopes: set[str] = set()
    for claim_name in ("scope", "scp"):
        value = claims.get(claim_name)
        if isinstance(value, str):
            scopes.update(part for part in value.split() if part)
        elif isinstance(value, (list, tuple)):
            scopes.update(str(part).strip() for part in value if str(part).strip())
    return scopes


def oauth_resource_metadata_url(resource_url: str | None) -> str | None:
    if not resource_url:
        return None
    parts = urlsplit(resource_url)
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, "/.well-known/oauth-protected-resource", "", ""))


def build_oauth_challenge(
    settings: MCPOAuthSettings,
    *,
    error: str = "invalid_token",
    description: str = "Authentication required",
) -> str:
    def safe(value: str) -> str:
        return re.sub(r"[^\x20-\x21\x23-\x5b\x5d-\x7e]", " ", value).replace("\\", " ").strip()

    metadata_url = oauth_resource_metadata_url(settings.resource_url) or ""
    scope = " ".join(settings.required_scopes)
    return (
        f'Bearer resource_metadata="{safe(metadata_url)}", scope="{safe(scope)}", '
        f'error="{safe(error)}", error_description="{safe(description)}"'
    )
