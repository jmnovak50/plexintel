from __future__ import annotations

import json

import httpx
import pytest
from conftest import FIXTURES, public_resolver
from mcp.server.auth.provider import AccessToken

from app.main import create_app
from app.security.destinations import DestinationPolicy


@pytest.mark.asyncio
async def test_control_plane_is_owner_scoped_and_never_returns_credentials(settings, database):
    schema = json.loads((FIXTURES / "openapi" / "schema_a.json").read_text())
    seen_tokens: list[str] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        seen_tokens.append(request.headers.get("authorization", ""))
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=schema)
        if request.url.path == "/api/users/self":
            owner = "a" if request.headers["authorization"].endswith("a-canary") else "b"
            return httpx.Response(200, json={"id": f"mealie-user-{owner}"})
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": "v3.26.0"})
        return httpx.Response(404)

    mealie_http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    app = create_app(
        settings,
        database=database,
        mealie_http_client=mealie_http,
        destination_policy=DestinationPolicy(settings, public_resolver),
    )

    async def verify(token: str):
        if token not in {"oidc-a", "oidc-b"}:
            return None
        return AccessToken(
            token="validated",
            client_id="test",
            subject=token[-1],
            scopes=["mealie.read"],
        )

    app.state.identity.verify_token = verify
    headers_a = {"authorization": "Bearer oidc-a"}
    headers_b = {"authorization": "Bearer oidc-b"}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as client,
    ):
        created = await client.post(
            "/api/v1/mealie-connections",
            headers=headers_a,
            json={
                "name": "Home",
                "base_url": "https://mealie-a.example",
                "api_token": "mealie-a-canary",
            },
        )
        assert created.status_code == 201, created.text
        connection_id = created.json()["connection"]["id"]
        assert "mealie-a-canary" not in created.text
        assert "encrypted_api_token" not in created.text and "api_token" not in created.text
        assert created.json()["connection"]["status"] == "active"

        own = await client.get(f"/api/v1/mealie-connections/{connection_id}", headers=headers_a)
        other = await client.get(f"/api/v1/mealie-connections/{connection_id}", headers=headers_b)
        assert own.status_code == 200 and other.status_code == 404
        assert "mealie-a-canary" not in own.text

        replaced = await client.put(
            f"/api/v1/mealie-connections/{connection_id}/credential",
            headers=headers_a,
            json={"api_token": "replacement-a-canary"},
        )
        assert replaced.status_code == 200, replaced.text
        assert "replacement-a-canary" not in replaced.text
        other_list = await client.get("/api/v1/mealie-connections", headers=headers_b)
        assert other_list.status_code == 200 and other_list.json() == []

    assert "Bearer mealie-a-canary" in seen_tokens
    assert "Bearer replacement-a-canary" in seen_tokens
    await mealie_http.aclose()
