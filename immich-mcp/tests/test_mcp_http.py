import asyncio
import base64
import json
import logging

import httpx
import pytest
import respx
from mcp.server.auth.provider import AccessToken
from test_private_tools import mcp_user, private_server

from app.main import create_app


@pytest.mark.asyncio
async def test_mcp_publishes_resource_metadata_and_requires_bearer(settings):
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://mcp.example.com") as client:
        metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
        unauthorized = await client.get("/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == "https://mcp.example.com/mcp"
    assert metadata.json()["scopes_supported"] == ["immich.read"]
    assert unauthorized.status_code == 401
    assert "resource_metadata=" in unauthorized.headers["www-authenticate"]
    await app.state.oidc_verifier.aclose()
    await app.state.immich.aclose()


async def authenticated_app(settings, monkeypatch):
    _, provider, client, verifier = await private_server(settings)
    await verifier.aclose()
    app = create_app(
        settings.model_copy(update={"allowed_hosts": "mcp.example.com"}),
        immich_client=client,
        credential_provider=provider,
    )

    async def verify(token):
        if token not in {"user-a", "user-b", "unconnected", "no-scope"}:
            return None
        return AccessToken(
            token="validated",
            client_id="fixture",
            subject=token,
            scopes=[] if token == "no-scope" else ["immich.read"],
            claims={"identity_namespace": "authentik", "iss": "https://auth.example.com"},
        )

    monkeypatch.setattr(app.state.oidc_verifier, "verify_token", verify)
    return app


async def tool_call(http, token, name, arguments):
    return await http.post(
        "/mcp",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


@pytest.mark.parametrize("status", [400, 422, 401, 403, 429, 500, 503])
@pytest.mark.asyncio
@respx.mock
async def test_raw_http_search_error_has_no_invalid_argument_or_private_data(
    settings, monkeypatch, caplog, status
):
    caplog.set_level(logging.INFO)
    settings.http_max_retries = 2
    route = respx.post("https://photo.example.com/api/search/smart").mock(
        return_value=httpx.Response(status, text="private-body-canary")
    )
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):
        result = await tool_call(
            http,
            "user-a",
            "search_assets",
            {"query": "private-term-canary", "media_type": "IMAGE", "limit": 30},
        )
    assert result.status_code == 200
    wire = result.json()
    assert "error" not in wire and wire["result"]["isError"]
    assert "structuredContent" not in wire["result"]
    text = wire["result"]["content"][0]["text"]
    assert f"HTTP {status}" in text and "operation=search/smart" in text and "correlation_id=" in text
    assert "Do not automatically retry" in text and route.call_count == 1
    assert all(
        value not in result.text + caplog.text
        for value in [
            "private-body-canary",
            "private-term-canary",
            "api-key-a",
            "INVALID_ARGUMENT",
            "Traceback",
        ]
    )


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@pytest.mark.asyncio
@respx.mock
async def test_raw_http_location_account_boundaries_through_continuation_and_images(
    settings, monkeypatch, mode
):
    settings.immich_search_api_mode = mode
    revoked = set()
    seen = []

    async def upstream(request):
        await asyncio.sleep(0)
        key = request.headers["x-api-key"]
        assert "x-immich-share-key" not in request.headers and "authorization" not in request.headers
        seen.append((request.url.path, key))
        if key in revoked:
            return httpx.Response(401, text="private-body-canary")
        if request.url.path.endswith("/suggestions"):
            return httpx.Response(200, json=[None, "Hawaiʻi" if key == "api-key-a" else "Québec"])
        if request.url.path.endswith("/metadata"):
            body = json.loads(request.content)
            state = body["filter"]["state"]["eq"] if mode == "structured" else body["state"]
            assert state == ("Hawaiʻi" if key == "api-key-a" else "Québec")
            assert not any(k in body for k in ["user", "owner", "userIds", "api_key", "url"])
            second = body.get("cursor") == "002" if mode == "structured" else body.get("page") == 2
            return httpx.Response(
                200,
                json={
                    "assets": {
                        "items": [
                            {"id": key[-1] + str(second), "type": "IMAGE", "exifInfo": {"state": state}}
                        ],
                        "nextPage": "2" if mode == "legacy" and not second else None,
                        "nextCursor": "002" if mode == "structured" and not second else None,
                    }
                },
            )
        if key == "api-key-b":
            return httpx.Response(403, text="private-body-canary")
        return httpx.Response(200, content=b"synthetic-png", headers={"content-type": "image/png"})

    respx.route(host="photo.example.com").mock(side_effect=upstream)
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):

        async def first(token):
            suggestion = (
                await tool_call(http, token, "get_location_suggestions", {"field": "state"})
            ).json()["result"]
            state = suggestion["structuredContent"]["values"][0]
            page = (
                await tool_call(
                    http,
                    token,
                    "search_location_assets",
                    {"state": state, "user": "user-a", "api_key": "ignored-canary", "limit": 1},
                )
            ).json()["result"]
            return page["structuredContent"]

        a, b = await asyncio.gather(first("user-a"), first("user-b"))
        assert a["assets"][0]["state"] == "Hawaiʻi" and b["assets"][0]["state"] == "Québec"
        before = len(seen)
        cross = await tool_call(http, "user-b", "search_location_assets", {"continuation": a["continuation"]})
        assert cross.json()["result"]["isError"] and len(seen) == before
        for token, page in [("user-a", a), ("user-b", b)]:
            last = (
                await tool_call(http, token, "search_location_assets", {"continuation": page["continuation"]})
            ).json()["result"]["structuredContent"]
            assert last["complete"] and last["returnedSoFar"] == 2
        image = (await tool_call(http, "user-a", "get_asset_thumbnail", {"asset_id": "aFalse"})).json()[
            "result"
        ]
        assert base64.b64decode(image["content"][0]["data"]) == b"synthetic-png"
        assert "structuredContent" not in image
        denied = (await tool_call(http, "user-b", "get_asset_thumbnail", {"asset_id": "aFalse"})).json()[
            "result"
        ]
        assert denied["isError"] and "HTTP 403" in denied["content"][0]["text"]
        outstanding = (
            await tool_call(http, "user-a", "search_location_assets", {"state": "Hawaiʻi"})
        ).json()["result"]["structuredContent"]
        revoked.add("api-key-a")
        failed_page = (
            await tool_call(
                http, "user-a", "search_location_assets", {"continuation": outstanding["continuation"]}
            )
        ).json()["result"]
        assert failed_page["isError"] and "Reconnect Immich" in failed_page["content"][0]["text"]
        assert "Enumeration incomplete" in failed_page["content"][0]["text"]
        for name, args in [
            ("get_location_suggestions", {"field": "state"}),
            ("get_asset_thumbnail", {"asset_id": "aFalse"}),
        ]:
            assert (await tool_call(http, "user-a", name, args)).json()["result"]["isError"]
        await app.state.credentials.delete_for(mcp_user("user-a"))
        before = len(seen)
        for token in ["user-a", "unconnected"]:
            for name, args in [
                ("get_location_suggestions", {"field": "country"}),
                ("search_location_assets", {"state": "Hawaii"}),
                ("get_asset_thumbnail", {"asset_id": "aFalse"}),
            ]:
                assert (await tool_call(http, token, name, args)).json()["result"]["isError"]
        assert (
            await tool_call(http, "no-scope", "get_location_suggestions", {"field": "state"})
        ).status_code == 403
        assert (
            await tool_call(http, "invalid", "search_location_assets", {"state": "Hawaii"})
        ).status_code == 401
        assert len(seen) == before
