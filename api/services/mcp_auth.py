from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

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


def get_mcp_oauth_settings() -> MCPOAuthSettings:
    return MCPOAuthSettings(
        issuer_url=_normalize_issuer_url(get_setting_value("mcp.oauth.issuer_url")),
        audience=_normalize_optional(get_setting_value("mcp.oauth.audience")),
        email_claim=_normalize_optional(get_setting_value("mcp.oauth.email_claim")) or "email",
    )


def reset_jwks_cache() -> None:
    _jwks_clients.clear()


def authenticate_bearer_token(token: str, oauth_settings: MCPOAuthSettings | None = None) -> MCPAuthContext | None:
    normalized = (token or "").strip()
    if not normalized:
        return None

    settings = oauth_settings or get_mcp_oauth_settings()
    if not settings.issuer_url:
        return None

    claims = _decode_jwt(normalized, settings)
    if claims is None:
        return None

    email = extract_email_from_claims(claims, settings.email_claim)
    if not email:
        logger.info("MCP JWT authenticated but no email claim was found")
        return MCPAuthContext(auth_method="jwt", email=None)

    user = get_user_by_email(email)
    if user:
        return MCPAuthContext(
            auth_method="jwt",
            email=email,
            plex_username=user.get("username"),
            user_id=user.get("user_id"),
            is_admin=bool(user.get("is_admin")),
        )

    return MCPAuthContext(auth_method="jwt", email=email)


def extract_email_from_claims(claims: dict[str, Any], email_claim: str) -> str | None:
    for key in (email_claim, "email", "preferred_username"):
        value = claims.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if EMAIL_PATTERN.match(normalized):
                return normalized
    return None


def _decode_jwt(token: str, settings: MCPOAuthSettings) -> dict[str, Any] | None:
    try:
        signing_key = _get_signing_key(token, settings.issuer_url)
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            "options": {"verify_aud": bool(settings.audience), "verify_iss": False},
        }
        if settings.audience:
            decode_kwargs["audience"] = settings.audience
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
        token_issuer = claims.get("iss")
        if not _issuer_matches(token_issuer, settings.issuer_url):
            logger.info(
                "MCP JWT issuer mismatch: token=%s configured=%s",
                token_issuer,
                settings.issuer_url,
            )
            return None
        return claims
    except jwt.PyJWTError as exc:
        logger.info("MCP JWT validation failed: %s", exc)
        return None


def _issuer_matches(token_issuer: Any, configured_issuer: str | None) -> bool:
    if not configured_issuer or not isinstance(token_issuer, str):
        return False
    return token_issuer.rstrip("/") == configured_issuer.rstrip("/")


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
    normalized = _normalize_optional(value)
    if not normalized:
        return None
    return normalized.rstrip("/")


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
