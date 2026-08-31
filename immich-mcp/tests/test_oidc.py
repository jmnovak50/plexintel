import base64
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.oidc import OIDCJWTVerifier


def b64uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def key_material():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "test-key",
        "n": b64uint(numbers.n),
        "e": b64uint(numbers.e),
    }
    return private, jwk


def token(private, settings, scope="openid immich.read", **overrides):
    now = datetime.now(timezone.utc)
    claims = {
        "iss": str(settings.oidc_issuer),
        "aud": settings.oidc_audience,
        "sub": "authentik-user-id",
        "email": "user@example.com",
        "preferred_username": "user",
        "scope": scope,
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test-key"})


def mock_discovery(settings, jwk):
    issuer = str(settings.oidc_issuer)
    respx.get(issuer.rstrip("/") + "/.well-known/openid-configuration").mock(
        return_value=httpx.Response(200, json={"issuer": issuer, "jwks_uri": issuer + "jwks/"})
    )
    respx.get(issuer + "jwks/").mock(return_value=httpx.Response(200, json={"keys": [jwk]}))


@pytest.mark.asyncio
@respx.mock
async def test_oidc_jwt_validation(settings):
    private, jwk = key_material()
    mock_discovery(settings, jwk)
    verifier = OIDCJWTVerifier(settings)
    access = await verifier.verify_token(token(private, settings))
    assert access is not None
    assert access.subject == "authentik-user-id"
    assert access.claims["email"] == "user@example.com"  # type: ignore[index]
    assert "immich.read" in access.scopes
    assert access.token == "validated"
    await verifier.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_insufficient_scope(settings):
    private, jwk = key_material()
    mock_discovery(settings, jwk)
    verifier = OIDCJWTVerifier(settings)
    assert await verifier.verify_token(token(private, settings, scope="openid profile")) is None
    await verifier.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_wrong_audience_is_rejected(settings):
    private, jwk = key_material()
    mock_discovery(settings, jwk)
    verifier = OIDCJWTVerifier(settings)
    assert await verifier.verify_token(token(private, settings, aud="some-other-api")) is None
    await verifier.aclose()

