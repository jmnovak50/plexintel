"""Synthetic image regressions; no production credentials or photo fixtures."""

import asyncio
import base64
import json
from contextvars import ContextVar

import httpx
import pytest
import respx
from mcp import Client
from mcp.client._memory import InMemoryTransport
from mcp.server.mcpserver.exceptions import ToolError
from structlog.testing import capture_logs
from test_private_tools import mcp_user, private_server

from app.immich.client import ImmichClient, ImmichError, ImmichImageBusy, ImmichTimeout, ImmichUnavailable
from app.immich.models import PrivateImmichCredential
from app.mcp.tools import connection


def credential(name):
    return PrivateImmichCredential(kind="api_key", token=name)


@pytest.mark.asyncio
async def test_admission_bounds_images_but_other_users_and_metadata_progress(settings):
    settings = settings.model_copy(
        update={
            "image_max_concurrency": 3,
            "image_per_credential_concurrency": 2,
            "image_queue_timeout_seconds": 0.05,
        }
    )
    entered, release = asyncio.Event(), asyncio.Event()
    active = peak = 0
    seen = []

    async def handler(request):
        nonlocal active, peak
        if request.url.path.endswith("/albums"):
            return httpx.Response(200, json=[])
        active += 1
        peak = max(peak, active)
        seen.append(request.headers["x-api-key"])
        if active == 2:
            entered.set()
        try:
            if request.headers["x-api-key"] == "a":
                await release.wait()
            return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})
        finally:
            active -= 1

    async with httpx.AsyncClient(
        base_url="https://fixture/api/", transport=httpx.MockTransport(handler)
    ) as http:
        client = ImmichClient(settings, http)
        tasks = [asyncio.create_task(client.get_asset_thumbnail(credential("a"), str(i))) for i in range(2)]
        await asyncio.wait_for(entered.wait(), 1)
        try:
            excess = asyncio.create_task(client.get_asset_thumbnail(credential("a"), "excess"))
            assert await client.list_albums(credential("a")) == []
            assert (await client.get_asset_thumbnail(credential("b"), "b")).data == b"image"
            with pytest.raises(ImmichImageBusy):
                await excess
            assert seen == ["a", "a", "b"] and peak == 3
        finally:
            release.set()
            await asyncio.gather(*tasks)
        assert client._credential_image_slots == {}
        assert (await client.get_asset_thumbnail(credential("a"), "again")).data == b"image"


@pytest.mark.asyncio
async def test_global_limit_and_cancelled_waiter_release_credential_slot(settings):
    client = ImmichClient(settings.model_copy(update={"image_max_concurrency": 1}))
    started = asyncio.Event()

    async def wait_for_slot():
        started.set()
        async with client._image_admission(credential("b")):
            pytest.fail("global capacity exceeded")

    try:
        async with client._image_admission(credential("a")):
            waiter = asyncio.create_task(wait_for_slot())
            await started.wait()
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
        assert client._credential_image_slots == {}
        async with client._image_admission(credential("b")):
            pass
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [503, "timeout"])
async def test_retries_keep_existing_budget_and_sanitized_diagnostics(settings, failure):
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("private-url-and-body", request=request)
        return httpx.Response(failure, content=b"private upstream body")

    async with httpx.AsyncClient(
        base_url="https://fixture/api/", transport=httpx.MockTransport(handler)
    ) as http:
        client = ImmichClient(settings.model_copy(update={"http_max_retries": 2}), http)
        with (
            capture_logs() as logs,
            pytest.raises(ImmichTimeout if failure == "timeout" else ImmichUnavailable),
        ):
            await client.get_asset_thumbnail(credential("credential-canary"), "private-id", size="thumbnail")
        assert count == 3
        assert len(logs) == 1 and logs[0]["attempts"] == 3
        assert logs[0]["tool"] == "get_asset_thumbnail" and logs[0]["size"] == "thumbnail"
        assert logs[0]["status"] == (503 if failure == 503 else None)
        assert logs[0]["duration_ms"] >= 0
        assert "private" not in json.dumps(logs) and "credential-canary" not in json.dumps(logs)
        assert client._credential_image_slots == {}


class SlowImage(httpx.AsyncByteStream):
    closed = False

    async def __aiter__(self):
        yield b"first"
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_total_deadline_closes_stream_without_outer_retry(settings):
    stream = SlowImage()
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, stream=stream, headers={"content-type": "image/jpeg"})

    async with httpx.AsyncClient(
        base_url="https://fixture/api/", transport=httpx.MockTransport(handler)
    ) as http:
        client = ImmichClient(
            settings.model_copy(update={"image_total_timeout_seconds": 0.02, "http_max_retries": 2}), http
        )
        with pytest.raises(ImmichTimeout, match="total retrieval deadline"):
            await client.get_asset_thumbnail(credential("a"), "one")
        assert calls == 1 and stream.closed
        assert client._credential_image_slots == {}


@pytest.mark.asyncio
@respx.mock
async def test_protocol_images_errors_and_partial_success(settings, monkeypatch):
    route = respx.get("https://photo.example.com/api/assets/one/thumbnail").mock(
        return_value=httpx.Response(200, content=b"synthetic-jpeg", headers={"content-type": "image/jpeg"})
    )
    fail = respx.get("https://photo.example.com/api/assets/bad/thumbnail").mock(
        return_value=httpx.Response(503, content=b"upstream-body-canary")
    )
    original = respx.get("https://photo.example.com/api/assets/one/original").mock(
        return_value=httpx.Response(200, content=b"native-heic", headers={"content-type": "image/heic"})
    )
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        async with Client(InMemoryTransport(server)) as session:
            tools = await session.list_tools()
            thumb_tool = next(t for t in tools.tools if t.name == "get_asset_thumbnail")
            assert thumb_tool.output_schema is None
            assert thumb_tool.input_schema["properties"]["size"]["default"] == "preview"
            good = await session.call_tool("get_asset_thumbnail", {"asset_id": "one", "size": "thumbnail"})
            bad = await session.call_tool("get_asset_thumbnail", {"asset_id": "bad"})
            native = await session.call_tool("get_asset_image", {"asset_id": "one"})
            wire = good.model_dump(mode="json", by_alias=True, exclude_none=True)
            assert not good.is_error and len(wire["content"]) == 1
            assert wire["content"][0] == {
                "type": "image",
                "data": base64.b64encode(b"synthetic-jpeg").decode(),
                "mimeType": "image/jpeg",
            }
            assert "structuredContent" not in wire
            assert bad.is_error and "ImmichUnavailable" in bad.content[0].text
            assert "upstream-body-canary" not in bad.content[0].text
            assert "Do not automatically retry" in bad.content[0].text
            assert base64.b64decode(native.content[0].data) == b"native-heic"
            assert native.content[0].mime_type == "image/heic"
            assert route.call_count == fail.call_count == original.call_count == 1
            assert route.calls[0].request.url.params["size"] == "thumbnail"
    finally:
        await verifier.aclose()
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_concurrent_tool_identity_and_disconnected_access(settings, monkeypatch):
    identity = ContextVar("test_identity")
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user(identity.get()))

    async def handler(request):
        await asyncio.sleep(0)
        if request.headers["x-api-key"] == "api-key-b":
            return httpx.Response(403, content=b"private-body")
        return httpx.Response(200, content=b"a-image", headers={"content-type": "image/png"})

    route = respx.get("https://photo.example.com/api/assets/private/thumbnail").mock(side_effect=handler)
    server, _, client, verifier = await private_server(settings)

    async def call_as(subject):
        identity.set(subject)
        return await server.call_tool("get_asset_thumbnail", {"asset_id": "private", "subject": "user-a"})

    try:
        a, b = await asyncio.gather(call_as("user-a"), call_as("user-b"), return_exceptions=True)
        assert base64.b64decode(a.content[0].data) == b"a-image"
        assert isinstance(b, ToolError) and "Immich denied" in str(b)
        with pytest.raises(ToolError, match="mcp.example.com/account"):
            await call_as("unconnected")
        assert route.call_count == 2
        assert client._credential_image_slots == {}
    finally:
        await verifier.aclose()
        await client.aclose()


@pytest.mark.asyncio
async def test_redirect_never_forwards_credentials_even_with_injected_client(settings):
    seen = []

    async def handler(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://untrusted.example/image"})

    async with httpx.AsyncClient(
        base_url="https://fixture/api/", follow_redirects=True, transport=httpx.MockTransport(handler)
    ) as http:
        client = ImmichClient(settings, http)
        with pytest.raises(ImmichError, match="redirect was not followed"):
            await client.get_asset_thumbnail(credential("a"), "one", size="fullsize")
    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,category",
    [
        (401, "Reconnect Immich"),
        (403, "Immich denied"),
        (404, "ImmichNotFound"),
        (429, "ImmichRateLimited"),
        (500, "ImmichUnavailable"),
    ],
)
@respx.mock
async def test_expected_image_errors_are_deliberate_tool_errors(settings, monkeypatch, status, category):
    from mcp.server.mcpserver.exceptions import UnexpectedToolError

    route = respx.get("https://photo.example.com/api/assets/one/thumbnail").mock(
        return_value=httpx.Response(status, content=b"upstream-private-body")
    )
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        with pytest.raises(ToolError) as error:
            await server.call_tool("get_asset_thumbnail", {"asset_id": "one"})
        assert not isinstance(error.value, UnexpectedToolError)
        assert category in str(error.value) and "upstream-private-body" not in str(error.value)
        assert route.call_count == 1
    finally:
        await verifier.aclose()
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_http_auth_context_selects_private_image_credential(settings, monkeypatch):
    from mcp.server.auth.provider import AccessToken

    from app.main import create_app

    _, provider, client, verifier = await private_server(settings)
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
    seen = []

    async def image_response(request):
        seen.append(request.headers["x-api-key"])
        return httpx.Response(
            200, content=request.headers["x-api-key"].encode(), headers={"content-type": "image/png"}
        )

    respx.get("https://photo.example.com/api/assets/shared/thumbnail").mock(side_effect=image_response)
    try:
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
        ):

            async def call(token, name="get_asset_thumbnail", arguments=None):
                return await http.post(
                    "/mcp",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": name,
                            "arguments": arguments
                            if arguments is not None
                            else {"asset_id": "shared", "subject": "user-a", "size": "thumbnail"},
                        },
                    },
                )

            a, b = await asyncio.gather(call("user-a"), call("user-b"))
            assert a.status_code == b.status_code == 200
            assert base64.b64decode(a.json()["result"]["content"][0]["data"]) == b"api-key-a"
            assert base64.b64decode(b.json()["result"]["content"][0]["data"]) == b"api-key-b"
            assert sorted(seen) == ["api-key-a", "api-key-b"]
            status = await call("unconnected", "get_immich_connection_status", {})
            assert status.json()["result"]["structuredContent"]["connected"] is False
            denied = await call("unconnected")
            assert denied.json()["result"]["isError"]
            assert "mcp.example.com/account" in denied.json()["result"]["content"][0]["text"]
            assert (await call("invalid")).status_code == 401
            assert (await call("no-scope")).status_code == 403
            assert len(seen) == 2
    finally:
        await verifier.aclose()
        await app.state.account_oidc_verifier.aclose()
