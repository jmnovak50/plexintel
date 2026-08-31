import re
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx

from app.credentials.crypto import CredentialCipher
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient
from app.immich.models import AuthenticatedUser
from app.main import create_app


class FakeIDTokenVerifier:
    async def verify_id_token(self, token, *, audience, nonce):
        assert token == "signed-id-token"
        assert audience == "immich-mcp-account"
        return {
            "iss": "https://auth.example.com/application/o/immich-mcp/",
            "sub": "authentik-subject-a",
            "email": "same@example.com",
            "preferred_username": "user-a",
            "nonce": nonce,
        }


class FakeAccountOIDC:
    def __init__(self):
        self.verifier = FakeIDTokenVerifier()

    async def authorization_url(self, state, nonce, code_verifier):
        return f"https://auth.example.com/authorize?state={state}"

    async def exchange_code(self, code, code_verifier):
        assert code == "authorization-code"
        return {"id_token": "signed-id-token"}


async def account_test_app(settings):
    provider = SQLiteCredentialProvider(
        settings.credential_db_path,
        CredentialCipher(settings.credential_encryption_key.get_secret_value()),
        settings.account_session_secret.get_secret_value(),
    )
    await provider.initialize()
    immich = ImmichClient(settings)
    app = create_app(
        settings, immich_client=immich, credential_provider=provider,
        account_oidc=FakeAccountOIDC(),
    )
    return app, provider


async def sign_in(client):
    login = await client.get("/account/login")
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    callback = await client.get(
        "/account/callback", params={"state": state, "code": "authorization-code"}
    )
    assert callback.status_code == 303
    page = await client.get("/account")
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert csrf
    return csrf.group(1)


@pytest.mark.asyncio
async def test_account_requires_direct_oidc_and_valid_state(settings):
    app, _ = await account_test_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.example.com") as client:
        account = await client.get("/account")
        invalid = await client.get("/account/callback?state=wrong&code=authorization-code")
    assert account.status_code == 303 and account.headers["location"] == "/account/login"
    assert invalid.status_code == 400
    await app.state.oidc_verifier.aclose()
    await app.state.immich.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_connect_csrf_secret_redaction_identity_and_disconnect(settings):
    route = respx.get("https://photo.example.com/api/users/me").mock(
        return_value=httpx.Response(
            200, json={"id": "immich-user-a", "email": "immich@example.com", "name": "Immich A"}
        )
    )
    app, provider = await account_test_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.example.com") as client:
        csrf = await sign_in(client)
        rejected = await client.post(
            "/account/connect", data={"csrf_token": "wrong", "api_key": "never-log-this"}
        )
        assert rejected.status_code == 403
        connected = await client.post(
            "/account/connect", data={"csrf_token": csrf, "api_key": "private-user-api-key"}
        )
        assert connected.status_code == 303
        page = await client.get("/account")
        assert "Immich A" in page.text
        assert "private-user-api-key" not in page.text
        assert route.calls[0].request.headers["x-api-key"] == "private-user-api-key"
        identity = AuthenticatedUser(
            issuer=str(settings.oidc_issuer), sub="authentik-subject-a", email="same@example.com",
            scopes=["immich.read"],
        )
        stored = await provider.credential_for(identity)
        assert stored is not None and stored.token == "private-user-api-key"
        disconnected = await client.post(
            "/account/disconnect", data={"csrf_token": csrf}
        )
        assert disconnected.status_code == 303
        assert await provider.credential_for(identity) is None
    await app.state.oidc_verifier.aclose()
    await app.state.immich.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_invalid_api_key_is_rejected_and_not_echoed(settings):
    respx.get("https://photo.example.com/api/users/me").mock(return_value=httpx.Response(401))
    app, provider = await account_test_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.example.com") as client:
        csrf = await sign_in(client)
        response = await client.post(
            "/account/connect", data={"csrf_token": csrf, "api_key": "bad-secret-key"}
        )
        assert response.status_code == 400
        assert "bad-secret-key" not in response.text
        identity = AuthenticatedUser(
            issuer=str(settings.oidc_issuer), sub="authentik-subject-a", scopes=["immich.read"]
        )
        assert await provider.credential_for(identity) is None
    await app.state.oidc_verifier.aclose()
    await app.state.immich.aclose()
