from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.authentik import AuthentikIdentityProvider


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


def _token(private, settings, kid="key-a", **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": str(settings.oidc_issuer),
        "aud": settings.oidc_audience,
        "sub": "user-a",
        "scope": "openid mealie.read",
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": kid})


def _client(settings, jwks_values):
    issuer = str(settings.oidc_issuer)
    calls = {"jwks": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"issuer": issuer, "jwks_uri": issuer + "jwks/"})
        calls["jwks"] += 1
        index = min(calls["jwks"] - 1, len(jwks_values) - 1)
        return httpx.Response(200, json={"keys": jwks_values[index]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


async def _verified_principal(settings, subject: str):
    private, public = _key("identity-key")
    client, _ = _client(settings, [[public]])
    provider = AuthentikIdentityProvider(settings, client)
    try:
        access = await provider.verify_token(_token(private, settings, kid="identity-key", sub=subject))
        assert access is not None
        return provider.principal_from_access_token(access)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_valid_jwt_and_provider_neutral_principal(settings):
    private, public = _key("key-a")
    client, _ = _client(settings, [[public]])
    provider = AuthentikIdentityProvider(settings, client)
    access = await provider.verify_token(_token(private, settings))
    assert access is not None and access.token == "validated"
    principal = provider.principal_from_access_token(access)
    assert principal.subject == "user-a" and "mealie.read" in principal.scopes
    assert str(principal.user_id) not in {principal.subject, principal.email}
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://auth.example.com/application/o/wrong/"},
        {"aud": "other-client"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"scope": "openid"},
    ],
)
async def test_invalid_issuer_audience_expiry_and_scope_are_rejected(settings, overrides):
    private, public = _key("key-a")
    client, _ = _client(settings, [[public]])
    provider = AuthentikIdentityProvider(settings, client)
    assert await provider.verify_token(_token(private, settings, **overrides)) is None
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(settings):
    trusted, public = _key("key-a")
    attacker, _ = _key("key-a")
    client, _ = _client(settings, [[public]])
    provider = AuthentikIdentityProvider(settings, client)
    assert await provider.verify_token(_token(attacker, settings)) is None
    assert await provider.verify_token(_token(trusted, settings)) is not None
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_kid_refreshes_jwks_for_key_rotation(settings):
    old_private, old_public = _key("old")
    new_private, new_public = _key("new")
    client, calls = _client(settings, [[old_public], [old_public, new_public]])
    provider = AuthentikIdentityProvider(settings, client)
    assert await provider.verify_token(_token(old_private, settings, kid="old")) is not None
    assert await provider.verify_token(_token(new_private, settings, kid="new")) is not None
    assert calls["jwks"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_same_namespace_and_subject_reconcile_across_valid_issuers(settings):
    mcp_settings = settings.model_copy(
        update={"oidc_issuer": "https://auth.kabolly.com/application/o/mealie-mcp/"}
    )
    account_settings = settings.model_copy(
        update={
            "oidc_issuer": "https://auth.kabolly.com/application/o/mealie-mcp-account/",
            "oidc_audience": "mealie-mcp-account-client",
        }
    )

    mcp_principal = await _verified_principal(mcp_settings, "authentik-user-uuid")
    account_principal = await _verified_principal(account_settings, "authentik-user-uuid")

    expected_user_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{settings.identity_namespace}:user:authentik-user-uuid",
    )
    expected_tenant_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"{settings.identity_namespace}:tenant:{settings.default_tenant_id}",
    )
    assert mcp_principal.user_id == account_principal.user_id == expected_user_id
    assert mcp_principal.tenant_id == account_principal.tenant_id == expected_tenant_id
    assert mcp_principal.issuer == "https://auth.kabolly.com/application/o/mealie-mcp/"
    assert account_principal.issuer == "https://auth.kabolly.com/application/o/mealie-mcp-account/"


@pytest.mark.asyncio
async def test_different_subjects_have_different_internal_user_ids(settings):
    first = await _verified_principal(settings, "authentik-user-a")
    second = await _verified_principal(settings, "authentik-user-b")
    assert first.user_id != second.user_id


@pytest.mark.asyncio
async def test_different_identity_namespaces_have_different_internal_user_ids(settings):
    first = await _verified_principal(
        settings.model_copy(update={"identity_namespace": "authentik-primary"}),
        "authentik-user-uuid",
    )
    second = await _verified_principal(
        settings.model_copy(update={"identity_namespace": "future-saas"}),
        "authentik-user-uuid",
    )
    assert first.user_id != second.user_id
