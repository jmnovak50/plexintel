from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from jwt import PyJWK
from mcp.server.auth.provider import AccessToken

from app.auth.principal import Principal, principal_from_validated_identity
from app.config import Settings


class IdentityConfigurationError(RuntimeError):
    pass


class AuthentikIdentityProvider:
    """OIDC resource-server validation with provider-neutral principal output."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.issuer = str(settings.oidc_issuer).rstrip("/") + "/"
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5), follow_redirects=False
        )
        self._owns_client = client is None
        self._metadata: dict[str, Any] | None = None
        self._keys: dict[str, PyJWK] = {}
        self._cache_until = 0.0
        self._last_forced_refresh = 0.0
        self._lock = asyncio.Lock()

    @property
    def discovery_url(self) -> str:
        return self.issuer + ".well-known/openid-configuration"

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def warm(self) -> None:
        await self._refresh(force=False)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in self.settings.oidc_algorithms:
                return None
            await self._refresh(force=False)
            key = self._keys.get(kid)
            if (
                key is None
                and time.monotonic() - self._last_forced_refresh
                >= self.settings.oidc_unknown_kid_refresh_seconds
            ):
                await self._refresh(force=True)
                key = self._keys.get(kid)
            if key is None or key.algorithm_name != algorithm:
                return None
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=self.settings.oidc_audience,
                options={"require": ["iss", "sub", "aud", "exp"]},
                leeway=30,
            )
            scopes = _scopes(claims)
            if not set(self.settings.oidc_required_scopes).issubset(scopes):
                return None
            return AccessToken(
                token="validated",
                client_id=str(claims.get("client_id") or claims.get("azp") or "oidc-client"),
                subject=str(claims["sub"]),
                scopes=sorted(scopes),
                expires_at=int(claims["exp"]),
                resource=str(self.settings.mcp_public_url),
                claims={
                    "iss": self.issuer,
                    "email": claims.get("email"),
                    "identity_namespace": self.settings.identity_namespace,
                },
            )
        except (jwt.PyJWTError, httpx.HTTPError, IdentityConfigurationError, ValueError, TypeError):
            return None

    def principal_from_access_token(self, token: AccessToken) -> Principal:
        claims = token.claims or {}
        return principal_from_validated_identity(
            namespace=self.settings.identity_namespace,
            default_tenant_id=self.settings.default_tenant_id,
            subject=token.subject,
            email=claims.get("email") if isinstance(claims.get("email"), str) else None,
            scopes=frozenset(token.scopes),
            issuer=self.issuer,
        )

    async def _refresh(self, *, force: bool) -> None:
        now = time.monotonic()
        if not force and self._metadata is not None and now < self._cache_until:
            return
        async with self._lock:
            now = time.monotonic()
            if not force and self._metadata is not None and now < self._cache_until:
                return
            metadata_response = await self._bounded_get(self.discovery_url)
            metadata = metadata_response.json()
            if not isinstance(metadata, dict) or _canonical_issuer(metadata.get("issuer")) != self.issuer:
                raise IdentityConfigurationError("OIDC discovery issuer mismatch")
            jwks_uri = metadata.get("jwks_uri")
            if not isinstance(jwks_uri, str) or not _same_origin(self.issuer, jwks_uri):
                raise IdentityConfigurationError("OIDC JWKS URI must share issuer origin")
            jwks = (await self._bounded_get(jwks_uri)).json()
            if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
                raise IdentityConfigurationError("OIDC JWKS is malformed")
            keys: dict[str, PyJWK] = {}
            for raw in jwks["keys"]:
                if not isinstance(raw, dict) or raw.get("use", "sig") != "sig":
                    continue
                kid = raw.get("kid")
                if isinstance(kid, str) and raw.get("alg") in self.settings.oidc_algorithms:
                    keys[kid] = PyJWK.from_dict(raw)
            if not keys:
                raise IdentityConfigurationError("OIDC JWKS has no approved signing keys")
            self._metadata, self._keys = metadata, keys
            self._cache_until = now + self.settings.oidc_cache_seconds
            if force:
                self._last_forced_refresh = now

    async def _bounded_get(self, url: str) -> httpx.Response:
        response = await self._client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        if len(response.content) > 1_000_000:
            raise IdentityConfigurationError("OIDC response is too large")
        return response


def _canonical_issuer(value: object) -> str:
    return str(value or "").rstrip("/") + "/"


def _same_origin(left: str, right: str) -> bool:
    a, b = urlsplit(left), urlsplit(right)
    return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


def _scopes(claims: dict[str, Any]) -> set[str]:
    raw = claims.get("scope", claims.get("scopes", []))
    if isinstance(raw, str):
        return set(raw.split())
    if isinstance(raw, list):
        return {str(value) for value in raw}
    return set()
