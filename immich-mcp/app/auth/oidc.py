import asyncio
import hmac
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
import structlog
from jwt import PyJWK
from mcp.server.auth.provider import AccessToken

from app.config import Settings

log = structlog.get_logger(__name__)


class OIDCConfigurationError(RuntimeError):
    pass


class OIDCJWTVerifier:
    """Validate Authentik JWT access tokens using discovered OIDC metadata and JWKS."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        *,
        issuer: str | None = None,
        audience: str | None = None,
        required_scopes: list[str] | None = None,
    ) -> None:
        self.settings = settings
        self.issuer = issuer or str(settings.oidc_issuer)
        self.audience = audience or str(settings.oidc_audience)
        self.required_scopes = settings.required_scopes if required_scopes is None else required_scopes
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds, connect=settings.http_connect_timeout_seconds),
            verify=settings.tls_verify,
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._metadata: dict[str, Any] | None = None
        self._keys: dict[str, PyJWK] = {}
        self._cache_until = 0.0
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def discovery_url(self) -> str:
        if self.issuer.endswith("/.well-known/openid-configuration"):
            return self.issuer
        return self.issuer.rstrip("/") + "/.well-known/openid-configuration"

    async def warm(self) -> None:
        await self._refresh(force=False)

    async def metadata(self) -> dict[str, Any]:
        await self._refresh(force=False)
        return dict(self._metadata or {})

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = await self._decode(
                token, audience=self.audience, required=["exp", "sub", "iss", "aud"]
            )
            scopes = _scopes(claims)
            if not set(self.required_scopes).issubset(scopes):
                return None
            client_id = str(claims.get("client_id") or claims.get("azp") or self.settings.oidc_client_id)
            return AccessToken(
                token="validated",
                client_id=client_id,
                scopes=sorted(scopes),
                expires_at=int(claims["exp"]),
                resource=str(self.settings.mcp_public_url),
                subject=str(claims["sub"]),
                claims={
                    "iss": claims["iss"],
                    "identity_namespace": self.settings.identity_namespace,
                    "email": claims.get("email"),
                    "preferred_username": claims.get("preferred_username"),
                },
            )
        except (jwt.PyJWTError, OIDCConfigurationError, httpx.HTTPError, ValueError, TypeError):
            # Authentication failures are intentionally indistinguishable and never include the token.
            return None

    async def verify_id_token(
        self, token: str, *, audience: str, nonce: str
    ) -> dict[str, Any] | None:
        try:
            claims = await self._decode(
                token, audience=audience, required=["exp", "sub", "iss", "aud", "nonce"]
            )
            if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
                return None
            return claims
        except (jwt.PyJWTError, OIDCConfigurationError, httpx.HTTPError, ValueError, TypeError):
            return None

    async def _decode(self, token: str, *, audience: str, required: list[str]) -> dict[str, Any]:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        algorithm = header.get("alg")
        if not kid or not algorithm or str(algorithm).lower() == "none":
            raise OIDCConfigurationError("OIDC token header is invalid")
        await self._refresh(force=False)
        key = self._keys.get(str(kid))
        if key is None:
            await self._refresh(force=True)
            key = self._keys.get(str(kid))
        if key is None or key.algorithm_name != algorithm:
            raise OIDCConfigurationError("OIDC signing key is unavailable")
        return jwt.decode(
            token,
            key.key,
            algorithms=[str(algorithm)],
            audience=audience,
            issuer=self.issuer,
            options={"require": required},
            leeway=30,
        )

    async def _refresh(self, *, force: bool) -> None:
        if not force and self._metadata is not None and time.monotonic() < self._cache_until:
            return
        async with self._lock:
            if not force and self._metadata is not None and time.monotonic() < self._cache_until:
                return
            metadata_response = await self._client.get(self.discovery_url)
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            if not isinstance(metadata, dict) or metadata.get("issuer") != self.issuer:
                raise OIDCConfigurationError("OIDC discovery issuer does not match configured issuer")
            jwks_uri = metadata.get("jwks_uri")
            if not isinstance(jwks_uri, str) or not jwks_uri.startswith("https://") and not jwks_uri.startswith("http://"):
                raise OIDCConfigurationError("OIDC discovery does not contain a valid jwks_uri")
            # Prevent discovery from turning this service into an arbitrary proxy: JWKS must share the issuer origin.
            issuer_url = urlsplit(self.issuer)
            jwks_url = urlsplit(jwks_uri)
            if (jwks_url.scheme, jwks_url.hostname, jwks_url.port) != (
                issuer_url.scheme,
                issuer_url.hostname,
                issuer_url.port,
            ):
                raise OIDCConfigurationError("OIDC jwks_uri must use the issuer host")
            jwks_response = await self._client.get(jwks_uri)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
            if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
                raise OIDCConfigurationError("OIDC JWKS is malformed")
            keys: dict[str, PyJWK] = {}
            for value in jwks["keys"]:
                if isinstance(value, dict) and value.get("kid") and value.get("use", "sig") == "sig":
                    parsed = PyJWK.from_dict(value)
                    keys[str(value["kid"])] = parsed
            if not keys:
                raise OIDCConfigurationError("OIDC JWKS has no signing keys")
            self._metadata = metadata
            self._keys = keys
            self._cache_until = time.monotonic() + 300


def _scopes(claims: dict[str, Any]) -> set[str]:
    raw = claims.get("scope", claims.get("scopes", []))
    if isinstance(raw, str):
        return {scope for scope in raw.split() if scope}
    if isinstance(raw, list):
        return {str(scope) for scope in raw}
    return set()
