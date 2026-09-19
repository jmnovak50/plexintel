from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from conftest import FIXTURES
from mcp.server.auth.provider import AccessToken
from pydantic import SecretStr

from app.db.models import ConnectionStatus, MealieConnection
from app.main import create_app
from app.mealie.resolver import OperationResolver
from app.security.secrets import LocalEncryptedSecretProvider


async def call_tool(
    client: httpx.AsyncClient,
    token: str,
    name: str,
    arguments: dict | None = None,
) -> httpx.Response:
    return await client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )


def install_test_identity(app) -> None:
    async def verify(token: str):
        if token not in {"oidc-a", "oidc-b"}:
            return None
        return AccessToken(
            token="validated",
            client_id="test-client",
            subject=token[-1],
            scopes=["mealie.read"],
            claims={"email": f"{token[-1]}@example.com"},
        )

    app.state.identity.verify_token = verify


async def add_connection(app, settings, subject: str, token: str) -> MealieConnection:
    access = await app.state.identity.verify_token(f"oidc-{subject}")
    principal = app.state.identity.principal_from_access_token(access)
    document = json.loads((FIXTURES / "openapi" / "schema_a.json").read_text())
    capabilities = OperationResolver().build(document).model_dump(mode="json")
    secrets = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    connection = MealieConnection(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        name=f"Kitchen {subject.upper()}",
        base_url=f"https://mealie-{subject}.example",
        encrypted_api_token=secrets.encrypt(SecretStr(token)),
        is_default=True,
        mealie_user_id=f"mealie-user-{subject}",
        mealie_version="v3.4.5",
        capabilities=capabilities,
        status=ConnectionStatus.active,
        last_validated_at=datetime(2026, 9, 19, 12, 30, tzinfo=UTC),
    )
    return await app.state.connections.add(connection)


@pytest.mark.asyncio
async def test_disconnected_status_contract_instructions_and_private_tool_fallback(settings, database):
    app = create_app(settings, database=database)
    install_test_identity(app)

    status_tool = next(
        tool for tool in await app.state.mcp.list_tools() if tool.name == "get_mealie_connection_status"
    )
    assert status_tool.input_schema.get("properties") == {}
    assert status_tool.input_schema.get("required", []) == []
    assert "get_mealie_connection_status" in app.state.mcp.instructions
    assert "If connected=false, do not call other Mealie private tools" in app.state.mcp.instructions
    assert "Never ask for a Mealie API token in chat" in app.state.mcp.instructions

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        response = await call_tool(client, "oidc-a", "get_mealie_connection_status")
        assert response.status_code == 200
        result = response.json()["result"]
        assert not result.get("isError", False)
        assert result["structuredContent"] == {
            "connected": False,
            "actionRequired": "connect_mealie_account",
            "message": (
                "This user has not connected their Mealie account. "
                "Ask them to visit accountUrl before continuing."
            ),
            "accountUrl": "https://mcp.example.com/account",
        }

        attempted_override = await call_tool(
            client,
            "oidc-a",
            "get_mealie_connection_status",
            {"user_id": "b", "email": "b@example.com"},
        )
        assert attempted_override.json()["result"]["structuredContent"]["connected"] is False

        search = await call_tool(client, "oidc-a", "search_recipes", {"search": "soup"})
        search_result = search.json()["result"]
        assert search_result["isError"] is True
        assert search_result["content"][0]["text"].endswith(
            "Mealie is not connected for this user. Visit https://mcp.example.com/account "
            "to connect your Mealie account. Do not automatically retry this call."
        )


@pytest.mark.asyncio
async def test_connection_status_is_safe_owner_scoped_and_rechecked_after_connect(settings, database):
    app = create_app(settings, database=database)
    install_test_identity(app)
    token_a = "mealie-token-a-status-canary"
    token_b = "mealie-token-b-status-canary"
    connection_b = await add_connection(app, settings, "b", token_b)

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        status_a, status_b = await asyncio.gather(
            call_tool(client, "oidc-a", "get_mealie_connection_status"),
            call_tool(client, "oidc-b", "get_mealie_connection_status"),
        )
        assert status_a.json()["result"]["structuredContent"]["connected"] is False
        connected_b = status_b.json()["result"]["structuredContent"]
        assert connected_b == {
            "connected": True,
            "name": "Kitchen B",
            "server": "https://mealie-b.example",
            "status": "active",
            "version": "v3.4.5",
            "lastValidatedAt": "2026-09-19T12:30:00",
            "capabilities": sorted(
                OperationResolver()
                .build(json.loads((FIXTURES / "openapi" / "schema_a.json").read_text()))
                .names
            ),
            "accountUrl": "https://mcp.example.com/account",
        }
        wire_b = status_b.text
        assert token_b not in wire_b
        assert connection_b.encrypted_api_token not in wire_b
        assert "api_token" not in wire_b and "encrypted_api_token" not in wire_b
        assert "authorization" not in wire_b.casefold()
        assert "openapi" not in wire_b.casefold()

        connection_a = await add_connection(app, settings, "a", token_a)
        rechecked_a = await call_tool(client, "oidc-a", "get_mealie_connection_status")
        connected_a = rechecked_a.json()["result"]["structuredContent"]
        assert connected_a["connected"] is True
        assert connected_a["name"] == "Kitchen A"
        assert connected_a["server"] == "https://mealie-a.example"
        assert token_a not in rechecked_a.text
        assert connection_a.encrypted_api_token not in rechecked_a.text

        unchanged_b = await call_tool(client, "oidc-b", "get_mealie_connection_status")
        assert unchanged_b.json()["result"]["structuredContent"]["server"] == ("https://mealie-b.example")
