from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from conftest import FIXTURES, public_resolver
from mcp.server.auth.provider import AccessToken
from pydantic import SecretStr

from app.db.models import ConnectionStatus, MealieConnection
from app.main import create_app
from app.mealie.resolver import OperationResolver
from app.security.destinations import DestinationPolicy
from app.security.secrets import LocalEncryptedSecretProvider


def tool_call(client: httpx.AsyncClient, token: str, name: str, arguments: dict):
    return client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


@pytest.mark.asyncio
async def test_representative_read_tools_through_mcp_and_concurrent_identity_isolation(settings, database):
    calls: list[tuple[str, str, str]] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0)
        authorization = request.headers["authorization"]
        owner = "a" if authorization == "Bearer mealie-token-a-canary" else "b"
        expected_host = f"mealie-{owner}.example"
        assert request.url.host == expected_host
        calls.append((owner, request.url.path, str(request.url.query)))
        path = request.url.path
        if path == "/api/recipes":
            return httpx.Response(200, json={"items": [{"slug": f"soup-{owner}", "owner": owner}]})
        if path.startswith("/api/recipes/"):
            return httpx.Response(200, json={"slug": path.rsplit("/", 1)[-1], "owner": owner})
        if path == "/api/households/mealplans":
            return httpx.Response(200, json={"items": [{"date": "2026-09-17", "owner": owner}]})
        if path == "/api/households/shopping/lists":
            return httpx.Response(200, json={"items": [{"id": f"list-{owner}", "owner": owner}]})
        if path.startswith("/api/households/shopping/lists/"):
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1], "owner": owner, "listItems": []})
        return httpx.Response(404)

    upstream_http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(
        settings,
        database=database,
        mealie_http_client=upstream_http,
        destination_policy=DestinationPolicy(settings, public_resolver),
    )

    async def verify(token: str):
        if token not in {"oidc-user-a", "oidc-user-b"}:
            return None
        return AccessToken(
            token="validated",
            client_id="test-client",
            subject=token.removeprefix("oidc-user-"),
            scopes=["mealie.read"],
            claims={"email": f"{token}@example.com"},
        )

    app.state.identity.verify_token = verify
    document = json.loads((FIXTURES / "openapi" / "schema_a.json").read_text())
    capabilities = OperationResolver().build(document).model_dump(mode="json")
    secrets = LocalEncryptedSecretProvider(settings.credential_encryption_key)
    for subject in ["a", "b"]:
        access = await verify(f"oidc-user-{subject}")
        principal = app.state.identity.principal_from_access_token(access)
        await app.state.connections.add(
            MealieConnection(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                name="Default",
                base_url=f"https://mealie-{subject}.example",
                encrypted_api_token=secrets.encrypt(SecretStr(f"mealie-token-{subject}-canary")),
                is_default=True,
                capabilities=capabilities,
                status=ConnectionStatus.active,
            )
        )

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        unauthorized = await client.post("/mcp", json={})
        assert unauthorized.status_code == 401

        representative = [
            ("search_recipes", {"search": "soup"}, "items"),
            ("get_recipe", {"slug": "soup-a"}, "slug"),
            (
                "get_meal_plan",
                {"start_date": "2026-09-15", "end_date": "2026-09-21"},
                "items",
            ),
            ("get_shopping_lists", {}, "items"),
            ("get_shopping_list", {"shopping_list_id": "list-a"}, "id"),
        ]
        for name, arguments, expected_key in representative:
            response = await tool_call(client, "oidc-user-a", name, arguments)
            assert response.status_code == 200
            result = response.json()["result"]
            assert not result.get("isError", False), result
            assert expected_key in result["structuredContent"]

        a, b = await asyncio.gather(
            tool_call(client, "oidc-user-a", "search_recipes", {"search": "a"}),
            tool_call(client, "oidc-user-b", "search_recipes", {"search": "b"}),
        )
        assert a.json()["result"]["structuredContent"]["items"][0]["owner"] == "a"
        assert b.json()["result"]["structuredContent"]["items"][0]["owner"] == "b"
        wire = a.text + b.text
        assert "mealie-token-a-canary" not in wire and "mealie-token-b-canary" not in wire
    await upstream_http.aclose()
    assert any(owner == "a" for owner, _, _ in calls)
    assert any(owner == "b" for owner, _, _ in calls)
