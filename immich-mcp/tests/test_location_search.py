"""Synthetic library and protocol tests; never use a running server or stored credentials."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp import Client
from mcp.client._memory import InMemoryTransport
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from structlog.testing import capture_logs
from test_private_tools import mcp_user, private_server

from app.immich import client as client_module
from app.immich.client import (
    ImmichClient,
    ImmichError,
    ImmichValidationError,
    MalformedImmichResponse,
)
from app.immich.location import LocationSearch
from app.immich.models import PrivateImmichCredential
from app.mcp.tools import connection

IDENTITY = ("authentik", "user-a")
KEY = PrivateImmichCredential(kind="api_key", token="credential-canary")
BASE = "https://photo.example.com/api/"


def asset(identifier, media_type="IMAGE", state="Hawaii"):
    return {
        "id": identifier,
        "type": media_type,
        "fileCreatedAt": "2026-01-02T12:00:00Z",
        "exifInfo": {"state": state, "city": None, "country": "United States"},
    }


def response(items, next_value=None, mode="legacy"):
    return httpx.Response(
        200,
        json={
            "assets": {
                "items": items,
                "total": 999999,
                "nextPage": next_value if mode == "legacy" else None,
                "nextCursor": next_value if mode == "structured" else None,
            }
        },
    )


def test_imports_edited_checkout():
    assert (
        Path(client_module.__file__).resolve() == Path(__file__).resolve().parents[1] / "app/immich/client.py"
    )


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@pytest.mark.asyncio
@respx.mock
async def test_location_all_media_and_two_photo_sample_without_smart_or_bulk_images(
    settings, monkeypatch, mode
):
    settings.immich_search_api_mode = mode
    library = [
        asset("photo-1"),
        asset("video", "VIDEO"),
        asset("photo-2"),
        asset("photo-3"),
        asset("elsewhere", state="California"),
        asset("missing", state=None),
    ]

    def search(request):
        body = json.loads(request.content)
        filters = body["filter"] if mode == "structured" else body
        value = lambda name: filters.get(name, {}).get("eq") if mode == "structured" else filters.get(name)
        assert value("state") == "Hawaii"
        matches = [
            a
            for a in library
            if a["exifInfo"]["state"] == value("state")
            and (value("type") is None or a["type"] == value("type"))
        ]
        return response(matches[: body["size"]], "next-opaque" if mode == "structured" else "2", mode)

    metadata = respx.post(BASE + "search/metadata").mock(side_effect=search)
    smart = respx.post(BASE + "search/smart").mock(return_value=httpx.Response(503))
    thumbs = [
        respx.get(BASE + f"assets/photo-{i}/thumbnail").mock(
            return_value=httpx.Response(
                200, content=f"image-{i}".encode(), headers={"content-type": "image/png"}
            )
        )
        for i in [1, 2]
    ]
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        all_page = (await server.call_tool("search_location_assets", {"state": "Hawaii"})).structured_content
        assert {a["type"] for a in all_page["assets"]} == {"IMAGE", "VIDEO"}
        assert all_page["partial"] and not all_page["complete"] and "total" not in all_page
        sample = (
            await server.call_tool(
                "search_location_assets", {"state": "Hawaii", "media_type": "IMAGE", "limit": 2}
            )
        ).structured_content
        assert sample["returned"] == 2 and sample["partial"]
        assert [a["id"] for a in sample["assets"]] == ["photo-1", "photo-2"]
        assert all(a["state"] == "Hawaii" and a["fileCreatedAt"] for a in sample["assets"])
        assert sum(t.call_count for t in thumbs) == smart.call_count == 0
        for a in sample["assets"]:
            result = await server.call_tool("get_asset_thumbnail", {"asset_id": a["id"], "size": "thumbnail"})
            assert result.content[0].type == "image" and result.structured_content is None
        assert sum(t.call_count for t in thumbs) == 2
        assert metadata.call_count == 2 and smart.call_count == 0
        # Native payload success is tested here; real client visible attachments remain a manual check.
    finally:
        await client.aclose()
        await verifier.aclose()


@pytest.mark.parametrize(
    "mode,cursor", [("legacy", "2"), ("structured", "opaque:/+="), ("structured", "002")]
)
@pytest.mark.asyncio
@respx.mock
async def test_scope_dates_contract_and_deduplication_across_pages(settings, mode, cursor):
    settings.immich_search_api_mode = mode
    route = respx.post(BASE + "search/metadata").mock(
        side_effect=[
            response([asset("one"), asset("one")], cursor, mode),
            response([asset("one"), asset("two", "VIDEO")], None, mode),
        ]
    )
    async with ImmichClient(settings)._client as http:
        search = LocationSearch(ImmichClient(settings, http))
        first = await search.page(
            KEY,
            identity=IDENTITY,
            state="Hawaiʻi",
            city="Hilo",
            country="US",
            start_date="2026-01-01",
            end_date="2026-02-01",
            limit=2,
        )
        second = await search.page(KEY, identity=IDENTITY, continuation=first["continuation"])
    assert first["returned"] == second["returned"] == 1
    assert second["returnedSoFar"] == 2 and second["complete"] and not second["partial"]
    assert second["continuation"] is None and second["pagesRetrieved"] == 2
    bodies = [json.loads(c.request.content) for c in route.calls]
    if mode == "structured":
        expected = {
            "filter": {
                "state": {"eq": "Hawaiʻi"},
                "city": {"eq": "Hilo"},
                "country": {"eq": "US"},
                "takenAt": {"gte": "2026-01-01T00:00:00+00:00", "lte": "2026-02-01T00:00:00+00:00"},
            },
            "orderBy": {"field": "fileCreatedAt", "direction": "desc"},
            "withExif": True,
            "size": 2,
        }
        assert bodies == [expected, {**expected, "cursor": cursor}]
    else:
        expected = {
            "state": "Hawaiʻi",
            "city": "Hilo",
            "country": "US",
            "order": "desc",
            "page": 1,
            "takenAfter": "2026-01-01T00:00:00+00:00",
            "takenBefore": "2026-02-01T00:00:00+00:00",
            "withExif": True,
            "size": 2,
        }
        assert bodies == [expected, {**expected, "page": 2}]


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@pytest.mark.parametrize("items", [[], [asset("one")]])
@pytest.mark.asyncio
@respx.mock
async def test_terminal_and_zero_matches(settings, mode, items):
    settings.immich_search_api_mode = mode
    respx.post(BASE + "search/metadata").mock(return_value=response(items, None, mode))
    client = ImmichClient(settings)
    try:
        result = await LocationSearch(client).page(KEY, identity=IDENTITY, state="Hawaii")
        assert result["complete"] and result["returned"] == len(items) and not result["hasMore"]
        assert "Missing or incorrect" in result["metadataCaveat"]
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "mode,bad",
    [
        ("legacy", "opaque"),
        ("legacy", True),
        ("legacy", 0),
        ("legacy", ""),
        ("legacy", {}),
        ("legacy", "٢"),
        ("structured", 2),
        ("structured", ""),
        ("structured", []),
        ("structured", False),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_malformed_continuation_never_becomes_terminal(settings, mode, bad):
    settings.immich_search_api_mode = mode
    route = respx.post(BASE + "search/metadata").mock(return_value=response([asset("one")], bad, mode))
    client = ImmichClient(settings)
    try:
        with pytest.raises(MalformedImmichResponse, match="Enumeration incomplete"):
            await LocationSearch(client).page(KEY, identity=IDENTITY, state="Hawaii")
        assert route.call_count == 1
    finally:
        await client.aclose()


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@pytest.mark.parametrize("failure", ["repeat", "empty", "http", "wrong-contract", "missing-id", "oversize"])
@pytest.mark.asyncio
@respx.mock
async def test_failed_second_page_retains_incomplete_status_and_stops(settings, mode, failure):
    settings.immich_search_api_mode = mode
    cursor = "opaque" if mode == "structured" else "2"
    failed = {
        "repeat": response([asset("two")], cursor, mode),
        "empty": response([], "opaque-next" if mode == "structured" else "3", mode),
        "http": httpx.Response(503, content=b"private-body-canary"),
        "wrong-contract": response([asset("two")], "2", "legacy" if mode == "structured" else "structured"),
        "missing-id": response([{}], None, mode),
        "oversize": response([asset(str(i)) for i in range(3)], None, mode),
    }[failure]
    route = respx.post(BASE + "search/metadata").mock(
        side_effect=[response([asset("one")], cursor, mode), failed]
    )
    client = ImmichClient(settings)
    search = LocationSearch(client)
    try:
        first = await search.page(KEY, identity=IDENTITY, state="Hawaii", limit=2)
        assert first["partial"]
        with pytest.raises(ImmichError, match="Enumeration incomplete; previously returned 1") as exc:
            await search.page(KEY, identity=IDENTITY, continuation=first["continuation"])
        assert "private-body-canary" not in str(exc.value)
        with pytest.raises(ImmichValidationError):
            await search.page(KEY, identity=IDENTITY, continuation=first["continuation"])
        assert route.call_count == 2
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "setting,stop", [("location_search_max_pages", "page_limit"), ("location_search_max_items", "item_limit")]
)
@pytest.mark.asyncio
@respx.mock
async def test_safety_limit_reports_partial_without_automatic_traversal(settings, setting, stop):
    setattr(settings, setting, 1)
    route = respx.post(BASE + "search/metadata").mock(return_value=response([asset("one")], "2"))
    client = ImmichClient(settings)
    try:
        result = await LocationSearch(client).page(KEY, identity=IDENTITY, state="Hawaii")
        assert result["stopReason"] == stop and result["partial"] and result["hasMore"]
        assert not result["complete"] and result["continuation"] is None and route.call_count == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_handles_bound_to_identity_credential_scope_ttl_and_capacity(settings, monkeypatch):
    settings.location_search_session_limit = 1
    clock = [100.0]
    monkeypatch.setattr("app.immich.location.monotonic", lambda: clock[0])
    route = respx.post(BASE + "search/metadata").mock(return_value=response([asset("one")], "2"))
    client = ImmichClient(settings)
    search = LocationSearch(client)
    try:
        first = await search.page(KEY, identity=IDENTITY, state="Hawaii")
        for key, identity, extras in [
            (KEY, ("authentik", "other"), {}),
            (PrivateImmichCredential(kind="api_key", token="reconnected"), IDENTITY, {}),
            (KEY, IDENTITY, {"state": "California"}),
            (KEY, IDENTITY, {"limit": 3}),
        ]:
            with pytest.raises(ImmichValidationError):
                await search.page(key, identity=identity, continuation=first["continuation"], **extras)
        assert route.call_count == 1
        newer = await search.page(KEY, identity=IDENTITY, state="Hawaii")
        with pytest.raises(ImmichValidationError):
            await search.page(KEY, identity=IDENTITY, continuation=first["continuation"])
        clock[0] += settings.location_search_ttl_seconds + 1
        with pytest.raises(ImmichValidationError):
            await search.page(KEY, identity=IDENTITY, continuation=newer["continuation"])
        assert route.call_count == 2 and len(search._sessions) == 0
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"state": ""},
        {"state": "Hawaii", "limit": 0},
        {"state": "Hawaii", "start_date": "yesterday"},
        {"state": "Hawaii", "start_date": "2026-01-01T12:00:00"},
        {"state": "Hawaii", "start_date": "2026-03-01", "end_date": "2026-01-01"},
        {"state": "Hawaii", "media_type": "SECRET-CANARY"},
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_validation_is_deliberate_sanitized_tool_error_without_requests(settings, monkeypatch, args):
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        with pytest.raises(ToolError) as exc:
            await server.call_tool("search_location_assets", args)
        assert not isinstance(exc.value, UnexpectedToolError) and "CANARY" not in str(exc.value)
        assert len(respx.calls) == 0
    finally:
        await client.aclose()
        await verifier.aclose()


@pytest.mark.parametrize(
    "field,kwargs",
    [("state", {"country": "US"}), ("city", {"country": "US", "state": "Hawaiʻi"}), ("country", {})],
)
@pytest.mark.asyncio
@respx.mock
async def test_suggestions_unicode_nulls_bound_pages_and_distinct_credentials(
    settings, monkeypatch, field, kwargs
):
    def suggestions(request):
        assert dict(request.url.params) == {"type": field, **kwargs}
        return httpx.Response(
            200,
            json=[None, "", "Hawaiʻi", "Hawaiʻi", "Hawaii", "HI"]
            if request.headers["x-api-key"] == "api-key-a"
            else [None, "Québec"],
        )

    route = respx.get(BASE + "search/suggestions").mock(side_effect=suggestions)
    server, _, client, verifier = await private_server(settings)
    try:
        monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
        first = (
            await server.call_tool("get_location_suggestions", {"field": field, "limit": 1, **kwargs})
        ).structured_content
        assert first["values"] == ["Hawaii"] and first["hasMore"] and first["nextOffset"] == 1
        rest = (
            await server.call_tool("get_location_suggestions", {"field": field, "offset": 1, **kwargs})
        ).structured_content
        assert rest["values"] == ["Hawaiʻi", "HI"]
        monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-b"))
        other = (
            await server.call_tool("get_location_suggestions", {"field": field, **kwargs})
        ).structured_content
        assert other["values"] == ["Québec"]
        assert [c.request.headers["x-api-key"] for c in route.calls] == [
            "api-key-a",
            "api-key-a",
            "api-key-b",
        ]
    finally:
        await client.aclose()
        await verifier.aclose()


@pytest.mark.parametrize(
    "failure,category",
    [
        (400, "ImmichBadRequest"),
        (422, "ImmichValidationError"),
        (401, "InvalidImmichCredential"),
        (403, "ImmichForbidden"),
        (429, "ImmichRateLimited"),
        (500, "ImmichUnavailable"),
        (503, "ImmichUnavailable"),
        ("timeout", "ImmichTimeout"),
        ("network", "ImmichNetworkError"),
        ("json", "MalformedImmichResponse"),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_search_errors_cross_sdk_boundary_sanitized_with_no_post_retry(
    settings, monkeypatch, failure, category
):
    settings.http_max_retries = 2

    def fail(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("body-secret-canary", request=request)
        if failure == "network":
            raise httpx.ConnectError("body-secret-canary", request=request)
        return httpx.Response(failure if type(failure) is int else 200, content=b"body-secret-canary")

    route = respx.post(BASE + "search/smart").mock(side_effect=fail)
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        with capture_logs() as logs:
            async with Client(InMemoryTransport(server)) as session:
                result = await session.call_tool(
                    "search_assets", {"query": "search-term-canary", "media_type": "IMAGE", "limit": 30}
                )
                wire = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        assert wire["isError"] and "structuredContent" not in wire
        text = wire["content"][0]["text"]
        assert category in text and "operation=search/smart" in text and "correlation_id=" in text
        assert "Do not automatically retry" in text
        assert f"status={failure if type(failure) is int else 200 if failure == 'json' else None}" in text
        assert route.call_count == 1
        encoded = json.dumps([wire, logs])
        assert all(
            s not in encoded
            for s in ["body-secret-canary", "search-term-canary", "api-key-a", "INVALID_ARGUMENT"]
        )
        assert logs[0]["attempts"] == 1 and logs[0]["duration_ms"] >= 0
    finally:
        await client.aclose()
        await verifier.aclose()


@pytest.mark.parametrize("status,attempts", [(400, 1), (401, 1), (403, 1), (422, 1), (429, 3), (503, 3)])
@pytest.mark.asyncio
@respx.mock
async def test_suggestions_get_retry_policy_is_bounded_and_does_not_widen_scope(settings, status, attempts):
    settings.http_max_retries = 2
    route = respx.get(BASE + "search/suggestions").mock(
        return_value=httpx.Response(status, text="body-canary")
    )
    client = ImmichClient(settings)
    try:
        with pytest.raises(ImmichError):
            await client.location_suggestions(KEY, field="city", state="Hawaiʻi", country="US")
        assert route.call_count == attempts
        assert all(
            dict(c.request.url.params) == {"type": "city", "state": "Hawaiʻi", "country": "US"}
            for c in route.calls
        )
    finally:
        await client.aclose()
