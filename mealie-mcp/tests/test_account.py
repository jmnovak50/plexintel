from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from conftest import FIXTURES, public_resolver
from mcp.server.auth.provider import AccessToken
from sqlalchemy import select, update

from app.account.routes import SESSION_COOKIE, STATE_COOKIE
from app.auth.principal import principal_from_validated_identity
from app.db.models import AccountOAuthState, AccountSession, MealieConnection
from app.main import create_app
from app.security.destinations import DestinationPolicy


class FakeAccountOIDC:
    def __init__(self, settings) -> None:
        self.issuer = str(settings.account_oidc_issuer)
        self.client_id = settings.account_oidc_client_id
        self.authorization_calls: list[tuple[str, str, str]] = []
        self.warm_calls = 0
        self.reject_id_token = False

    async def warm(self) -> None:
        self.warm_calls += 1

    async def authorization_url(self, state: str, nonce: str, code_verifier: str) -> str:
        self.authorization_calls.append((state, nonce, code_verifier))
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        return "https://auth.example.com/authorize?" + urlencode(
            {
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )

    async def exchange_code(self, code: str, code_verifier: str) -> str:
        assert code_verifier
        return f"signed-id-token:{code}"

    async def verify_id_token(self, token: str, nonce: str):
        assert nonce
        if self.reject_id_token:
            return None
        subject = token.removeprefix("signed-id-token:code-")
        return {
            "iss": self.issuer,
            "sub": subject,
            "email": f"{subject}@example.com",
            "preferred_username": subject,
            "nonce": nonce,
        }


def _mealie_http():
    schema = json.loads((FIXTURES / "openapi" / "schema_a.json").read_text())
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("authorization", "")
        seen.append((request.url.host, request.url.path, authorization))
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=schema)
        if request.url.path == "/api/users/self":
            return httpx.Response(200, json={"id": "mealie-user"})
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": "v3.26.0"})
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


def _app(settings, database, oidc, mealie_http):
    return create_app(
        settings,
        database=database,
        account_oidc=oidc,
        mealie_http_client=mealie_http,
        destination_policy=DestinationPolicy(settings, public_resolver),
    )


async def _login(client: httpx.AsyncClient, subject: str = "user-a") -> tuple[str, str]:
    login = await client.get("/account/login")
    assert login.status_code == 303
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    callback = await client.get(
        "/account/callback",
        params={"state": state, "code": f"code-{subject}"},
    )
    assert callback.status_code == 303
    page = await client.get("/account")
    match = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
    assert page.status_code == 200 and match
    return state, match.group(1)


@pytest.mark.asyncio
async def test_account_redirect_login_state_pkce_and_security_headers(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        account = await client.get("/account")
        assert account.status_code == 303 and account.headers["location"] == "/account/login"
        login = await client.get("/account/login")
        assert login.status_code == 303
        state, nonce, verifier = oidc.authorization_calls[-1]
        query = parse_qs(urlsplit(login.headers["location"]).query)
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        assert query["state"] == [state]
        assert query["nonce"] == [nonce]
        assert query["code_challenge"] == [expected]
        assert query["code_challenge_method"] == ["S256"]
        cookie = login.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert login.headers["cache-control"] == "no-store"
        async with database.sessions() as session:
            stored = await session.scalar(select(AccountOAuthState))
            assert stored is not None
            assert stored.state_hash != state and len(stored.state_hash) == 64
            assert stored.nonce == nonce and stored.code_verifier == verifier
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_callback_rejects_missing_mismatched_expired_and_reused_state(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        missing = await client.get("/account/callback")
        assert missing.status_code == 400

        await client.get("/account/login")
        mismatch = await client.get("/account/callback", params={"state": "wrong", "code": "code-user-a"})
        assert mismatch.status_code == 400

        login = await client.get("/account/login")
        expired_state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
        async with database.sessions.begin() as session:
            await session.execute(
                update(AccountOAuthState).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        expired = await client.get(
            "/account/callback",
            params={"state": expired_state, "code": "code-user-a"},
        )
        assert expired.status_code == 400

        login = await client.get("/account/login")
        state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
        first = await client.get("/account/callback", params={"state": state, "code": "code-user-a"})
        assert first.status_code == 303
        client.cookies.set(STATE_COOKIE, state, domain="mcp.example.com", path="/account/callback")
        reused = await client.get("/account/callback", params={"state": state, "code": "code-user-a"})
        assert reused.status_code == 400

        login = await client.get("/account/login")
        invalid_token_state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
        oidc.reject_id_token = True
        invalid_token = await client.get(
            "/account/callback",
            params={"state": invalid_token_state, "code": "code-user-a"},
        )
        assert invalid_token.status_code == 400
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_successful_callback_creates_opaque_server_session_and_expiry_is_enforced(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        _, _ = await _login(client, "authentik-user-uuid")
        raw_cookie = client.cookies.get(SESSION_COOKIE)
        assert raw_cookie
        assert all(
            canary not in raw_cookie
            for canary in (
                "authentik-user-uuid",
                "signed-id-token",
                "access_token",
                "api_token",
                "example.com",
            )
        )
        async with database.sessions() as session:
            stored = await session.scalar(select(AccountSession))
            assert stored is not None
            assert stored.token_hash != raw_cookie and len(stored.token_hash) == 64
            assert stored.subject == "authentik-user-uuid"
        async with database.sessions.begin() as session:
            await session.execute(
                update(AccountSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        expired = await client.get("/account")
        assert expired.status_code == 303 and expired.headers["location"] == "/account/login"
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_post_routes_require_csrf(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        await _login(client)
        for path, data in (
            ("/account/connect", {"base_url": "https://mealie.example", "api_token": "secret"}),
            ("/account/disconnect", {"connection_id": "00000000-0000-0000-0000-000000000000"}),
            ("/account/validate", {"connection_id": "00000000-0000-0000-0000-000000000000"}),
        ):
            response = await client.post(path, data={**data, "csrf_token": "wrong"})
            assert response.status_code == 403
            assert response.headers["cache-control"] == "no-store"
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_connect_uses_connection_service_without_disclosing_token(settings, database, capsys):
    mealie_http, seen = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    token = "mealie-browser-token-super-secret-canary"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        _, csrf = await _login(client)
        connected = await client.post(
            "/account/connect",
            data={
                "csrf_token": csrf,
                "name": "Home",
                "base_url": "https://mealie.example",
                "api_token": token,
            },
        )
        assert connected.status_code == 303
        page = await client.get("/account")
        assert page.status_code == 200
        assert "Mealie:</strong> Connected" in page.text
        assert "https://mealie.example" in page.text
        assert "recipe.search" in page.text and "shopping.get" in page.text
        assert token not in connected.text + page.text
        cookie = client.cookies.get(SESSION_COOKIE)
        assert cookie and token not in cookie
        assert page.headers["content-security-policy"].startswith("default-src 'none'")
        assert page.headers["referrer-policy"] == "no-referrer"
    captured = capsys.readouterr()
    assert token not in captured.out + captured.err
    assert any(auth == f"Bearer {token}" for _, _, auth in seen)
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_account_and_mcp_identity_reconcile_and_users_cannot_mutate_each_other(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as user_a,
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as user_b,
    ):
        _, csrf_a = await _login(user_a, "user-a")
        connected = await user_a.post(
            "/account/connect",
            data={
                "csrf_token": csrf_a,
                "name": "Home",
                "base_url": "https://mealie-a.example",
                "api_token": "token-a",
            },
        )
        assert connected.status_code == 303
        async with database.sessions() as session:
            connection = await session.scalar(select(MealieConnection))
            assert connection is not None
            connection_id = connection.id

        _, csrf_b = await _login(user_b, "user-b")
        for path in ("/account/validate", "/account/disconnect"):
            response = await user_b.post(
                path,
                data={"csrf_token": csrf_b, "connection_id": str(connection_id)},
            )
            assert response.status_code == 404
        async with database.sessions() as session:
            assert await session.get(MealieConnection, connection_id) is not None

        account_principal = principal_from_validated_identity(
            namespace=settings.identity_namespace,
            default_tenant_id=settings.default_tenant_id,
            subject="user-a",
            issuer=str(settings.account_oidc_issuer),
        )
        mcp_principal = app.state.identity.principal_from_access_token(
            AccessToken(
                token="validated",
                client_id="mcp-client",
                subject="user-a",
                scopes=["mealie.read"],
            )
        )
        assert account_principal.user_id == mcp_principal.user_id

        validated = await user_a.post(
            "/account/validate",
            data={"csrf_token": csrf_a, "connection_id": str(connection_id)},
        )
        assert validated.status_code == 303
        disconnected = await user_a.post(
            "/account/disconnect",
            data={"csrf_token": csrf_a, "connection_id": str(connection_id)},
        )
        assert disconnected.status_code == 303
        async with database.sessions() as session:
            assert await session.get(MealieConnection, connection_id) is None
    await mealie_http.aclose()


@pytest.mark.asyncio
async def test_ready_checks_account_oidc(settings, database):
    mealie_http, _ = _mealie_http()
    oidc = FakeAccountOIDC(settings)
    app = _app(settings, database, oidc, mealie_http)

    async def warm_identity() -> None:
        return None

    app.state.identity.warm = warm_identity
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        response = await client.get("/ready")
        assert response.status_code == 200
        assert oidc.warm_calls == 1
    await mealie_http.aclose()


def test_account_persistence_models_are_in_metadata():
    from app.db.base import Base

    state = Base.metadata.tables["account_oauth_states"]
    session = Base.metadata.tables["account_sessions"]
    assert {"state_hash", "nonce", "code_verifier", "expires_at"}.issubset(state.columns.keys())
    assert {
        "token_hash",
        "subject",
        "issuer",
        "email",
        "preferred_username",
        "expires_at",
    }.issubset(session.columns.keys())
    assert "access_token" not in session.columns and "id_token" not in session.columns
