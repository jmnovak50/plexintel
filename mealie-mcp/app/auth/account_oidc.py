from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from jwt import PyJWK

from app.config import Settings


class AccountOIDCError(RuntimeError):
    pass


class AccountOIDC:
    """Confidential Authorization Code + PKCE client for browser account linking."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.issuer = str(settings.account_oidc_issuer).rstrip("/") + "/"
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5),
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._metadata: dict[str, Any] | None = None
        self._keys: dict[str, PyJWK] = {}
        self._cache_until = 0.0
        self._lock = asyncio.Lock()

    @property
    def discovery_url(self) -> str:
        return self.issuer + ".well-known/openid-configuration"

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def warm(self) -> None:
        await self._refresh(force=False)

    async def authorization_url(self, state: str, nonce: str, code_verifier: str) -> str:
        metadata = await self._metadata_document()
        endpoint = self._endpoint(metadata, "authorization_endpoint")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return (
            endpoint
            + "?"
            + urlencode(
                {
                    "response_type": "code",
                    "client_id": self.settings.account_oidc_client_id,
                    "redirect_uri": str(self.settings.account_redirect_uri),
                    "scope": " ".join(self.settings.account_scopes),
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        metadata = await self._metadata_document()
        endpoint = self._endpoint(metadata, "token_endpoint")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": str(self.settings.account_redirect_uri),
            "client_id": self.settings.account_oidc_client_id,
            "code_verifier": code_verifier,
        }
        methods = metadata.get("token_endpoint_auth_methods_supported", ["client_secret_basic"])
        if not isinstance(methods, list):
            raise AccountOIDCError("OIDC token endpoint authentication metadata is malformed")
        try:
            if "client_secret_basic" in methods:
                response = await self._client.post(
                    endpoint,
                    data=data,
                    auth=(
                        self.settings.account_oidc_client_id,
                        self.settings.account_oidc_client_secret.get_secret_value(),
                    ),
                    headers={"Accept": "application/json"},
                )
            elif "client_secret_post" in methods:
                response = await self._client.post(
                    endpoint,
                    data={
                        **data,
                        "client_secret": self.settings.account_oidc_client_secret.get_secret_value(),
                    },
                    headers={"Accept": "application/json"},
                )
            else:
                raise AccountOIDCError("OIDC provider does not support confidential clients")
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise AccountOIDCError("OIDC token response is too large")
            token = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise AccountOIDCError("OIDC authorization code exchange failed") from exc
        id_token = token.get("id_token") if isinstance(token, dict) else None
        if not isinstance(id_token, str):
            raise AccountOIDCError("OIDC provider did not return an ID token")
        return id_token

    async def verify_id_token(self, token: str, nonce: str) -> dict[str, Any] | None:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            algorithm = header.get("alg")
            if not isinstance(kid, str) or algorithm not in self.settings.oidc_algorithms:
                return None
            await self._refresh(force=False)
            key = self._keys.get(kid)
            if key is None:
                await self._refresh(force=True)
                key = self._keys.get(kid)
            if key is None or key.algorithm_name != algorithm:
                return None
            claims = jwt.decode(
                token,
                key.key,
                algorithms=[algorithm],
                issuer=self.issuer,
                audience=self.settings.account_oidc_client_id,
                options={"require": ["iss", "sub", "aud", "exp", "nonce"]},
                leeway=30,
            )
            audience = claims.get("aud")
            if audience not in (
                self.settings.account_oidc_client_id,
                [self.settings.account_oidc_client_id],
            ):
                return None
            if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
                return None
            return claims
        except (jwt.PyJWTError, httpx.HTTPError, AccountOIDCError, ValueError, TypeError):
            return None

    async def _metadata_document(self) -> dict[str, Any]:
        await self._refresh(force=False)
        return dict(self._metadata or {})

    async def _refresh(self, *, force: bool) -> None:
        if not force and self._metadata is not None and time.monotonic() < self._cache_until:
            return
        async with self._lock:
            if not force and self._metadata is not None and time.monotonic() < self._cache_until:
                return
            try:
                metadata_response = await self._client.get(
                    self.discovery_url, headers={"Accept": "application/json"}
                )
                metadata_response.raise_for_status()
                if len(metadata_response.content) > 1_000_000:
                    raise AccountOIDCError("OIDC discovery response is too large")
                metadata = metadata_response.json()
                if not isinstance(metadata, dict) or _canonical_issuer(metadata.get("issuer")) != self.issuer:
                    raise AccountOIDCError("OIDC discovery issuer mismatch")
                for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                    self._endpoint(metadata, name)
                jwks_response = await self._client.get(
                    self._endpoint(metadata, "jwks_uri"), headers={"Accept": "application/json"}
                )
                jwks_response.raise_for_status()
                if len(jwks_response.content) > 1_000_000:
                    raise AccountOIDCError("OIDC JWKS response is too large")
                jwks = jwks_response.json()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise AccountOIDCError("OIDC discovery or JWKS retrieval failed") from exc
            if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
                raise AccountOIDCError("OIDC JWKS is malformed")
            keys: dict[str, PyJWK] = {}
            for raw in jwks["keys"]:
                if (
                    isinstance(raw, dict)
                    and raw.get("use", "sig") == "sig"
                    and raw.get("alg") in self.settings.oidc_algorithms
                    and isinstance(raw.get("kid"), str)
                ):
                    keys[raw["kid"]] = PyJWK.from_dict(raw)
            if not keys:
                raise AccountOIDCError("OIDC JWKS has no approved signing keys")
            self._metadata = metadata
            self._keys = keys
            self._cache_until = time.monotonic() + self.settings.oidc_cache_seconds

    def _endpoint(self, metadata: dict[str, Any], name: str) -> str:
        endpoint = metadata.get(name)
        if not isinstance(endpoint, str) or not _same_origin(self.issuer, endpoint):
            raise AccountOIDCError(f"OIDC {name} must share the configured issuer origin")
        return endpoint


def new_oauth_values() -> tuple[str, str, str]:
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)


def _canonical_issuer(value: object) -> str:
    return str(value or "").rstrip("/") + "/"


def _same_origin(left: str, right: str) -> bool:
    first, second = urlsplit(left), urlsplit(right)
    return (first.scheme, first.hostname, first.port) == (
        second.scheme,
        second.hostname,
        second.port,
    ) and second.scheme in {"http", "https"}
