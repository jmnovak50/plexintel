from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.account_oidc import AccountOIDC, AccountOIDCError


def _b64uint(value: int) -> str:
    return (
        base64.urlsafe_b64encode(value.to_bytes((value.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()
    )


def _key(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    return private, {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _b64uint(numbers.n),
        "e": _b64uint(numbers.e),
    }


def _id_token(private, settings, *, kid: str = "account-key", **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": str(settings.account_oidc_issuer),
        "aud": settings.account_oidc_client_id,
        "sub": "authentik-user-uuid",
        "nonce": "expected-nonce",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


def _oidc_client(settings, keys, *, token: str | None = None):
    issuer = str(settings.account_oidc_issuer)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": issuer + "authorize/",
                    "token_endpoint": issuer + "token/",
                    "jwks_uri": issuer + "jwks/",
                    "token_endpoint_auth_methods_supported": ["client_secret_basic"],
                },
            )
        if request.url.path.endswith("jwks/"):
            return httpx.Response(200, json={"keys": keys})
        if request.url.path.endswith("token/"):
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"id_token": token})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_authorization_request_and_exchange_use_pkce_s256_and_confidential_client(settings):
    private, public = _key("account-key")
    signed = _id_token(private, settings)
    client = _oidc_client(settings, [public], token=signed)
    oidc = AccountOIDC(settings, client)
    verifier = "pkce-verifier-with-sufficient-random-looking-content"

    url = await oidc.authorization_url("random-state", "random-nonce", verifier)
    query = parse_qs(urlsplit(url).query)
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert query["response_type"] == ["code"]
    assert query["state"] == ["random-state"]
    assert query["nonce"] == ["random-nonce"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [expected_challenge]
    assert query["scope"] == ["openid profile email"]
    assert await oidc.exchange_code("authorization-code", verifier) == signed
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://auth.example.com/application/o/wrong/"},
        {"aud": "wrong-account-client"},
        {"aud": ["mealie-mcp-account-client", "another-client"]},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"nonce": "wrong-nonce"},
    ],
)
async def test_id_token_rejects_wrong_issuer_audience_expiry_and_nonce(settings, overrides):
    private, public = _key("account-key")
    client = _oidc_client(settings, [public])
    oidc = AccountOIDC(settings, client)
    assert await oidc.verify_id_token(_id_token(private, settings, **overrides), "expected-nonce") is None
    await client.aclose()


@pytest.mark.asyncio
async def test_id_token_rejects_invalid_signature(settings):
    _, trusted_public = _key("account-key")
    attacker, _ = _key("account-key")
    client = _oidc_client(settings, [trusted_public])
    oidc = AccountOIDC(settings, client)
    assert await oidc.verify_id_token(_id_token(attacker, settings), "expected-nonce") is None
    await client.aclose()


@pytest.mark.asyncio
async def test_id_token_accepts_single_exact_audience_in_array_form(settings):
    private, public = _key("account-key")
    client = _oidc_client(settings, [public])
    oidc = AccountOIDC(settings, client)
    claims = await oidc.verify_id_token(
        _id_token(private, settings, aud=[settings.account_oidc_client_id]),
        "expected-nonce",
    )
    assert claims is not None and claims["sub"] == "authentik-user-uuid"
    await client.aclose()


@pytest.mark.asyncio
async def test_discovery_rejects_cross_origin_authorization_token_and_jwks_endpoints(settings):
    issuer = str(settings.account_oidc_issuer)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "issuer": issuer,
                "authorization_endpoint": "https://attacker.example/authorize",
                "token_endpoint": issuer + "token/",
                "jwks_uri": issuer + "jwks/",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    oidc = AccountOIDC(settings, client)
    with pytest.raises(AccountOIDCError, match="authorization_endpoint"):
        await oidc.authorization_url("state", "nonce", "verifier")
    await client.aclose()
