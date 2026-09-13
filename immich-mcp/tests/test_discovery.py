"""Synthetic discovery contracts, scope boundaries and bounded sampling; no live library."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ToolError
from structlog.testing import capture_logs
from test_location_search import BASE, response
from test_mcp_http import authenticated_app, tool_call
from test_private_tools import mcp_user, private_server

from app.immich import discovery as discovery_module
from app.mcp.tools import connection


def uid(n):
    return f"00000000-0000-4000-8000-{n:012d}"


P, Q, R, S, REF = [uid(i) for i in range(1, 6)]


def person(identifier=P, name="Élodie", hidden=False):
    return {
        "id": identifier,
        "name": name,
        "isHidden": hidden,
        "thumbnailPath": "/private/filesystem-canary",
        "birthDate": "2000-01-01",
    }


def photo(identifier, captured="2026-01-02T12:00:00Z", people=(P, Q), state="Hawaiʻi"):
    return {
        "id": identifier,
        "type": "IMAGE",
        "fileCreatedAt": captured,
        "createdAt": "2026-09-13T20:00:00Z",
        "localDateTime": "1999-01-01T00:00:00Z",
        "exifInfo": {"state": state, "city": "Test City", "country": "United States"},
        "people": [person(p, "" if p == R else "Fixture") for p in people],
    }


@pytest.fixture
async def service(settings, monkeypatch):
    server, provider, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    try:
        yield server, provider
    finally:
        await client.aclose()
        await verifier.aclose()


async def call(service, tool_name, **arguments):
    result = await service[0].call_tool(tool_name, arguments)
    assert not result.is_error
    return result.structured_content


def allow_people(*ids):
    return [
        respx.get(BASE + "people/" + p).mock(return_value=httpx.Response(200, json=person(p))) for p in ids
    ]


def test_discovery_import_is_checkout():
    assert (
        Path(discovery_module.__file__).resolve()
        == Path(__file__).resolve().parents[1] / "app/immich/discovery.py"
    )


@pytest.mark.parametrize(
    "name,match,records,resolution,expected",
    [
        ("ÉLODIE", "exact", [person()], "candidate", [P]),
        ("Élo", "fuzzy", [person(), person(Q, "Élodie")], "ambiguous", [P, Q]),
        ("Jason", "exact", [person(P, "Jason"), person(Q, "jason")], "ambiguous", [P, Q]),
        ("Absent", "fuzzy", [], "not_found", []),
        ("Elodie", "exact", [person()], "not_found", []),
    ],
)
@respx.mock
async def test_name_candidates_never_choose_arbitrarily(service, name, match, records, resolution, expected):
    route = respx.get(BASE + "search/person").mock(return_value=httpx.Response(200, json=records))
    result = await call(service, "find_people", name=name, match=match)
    assert result["resolution"] == resolution
    assert [p["id"] for p in result["people"]] == expected
    assert dict(route.calls[0].request.url.params) == {"name": name, "withHidden": "false"}
    assert route.calls[0].request.headers["x-api-key"] == "api-key-a"
    assert "filesystem-canary" not in json.dumps(result) and "birthDate" not in json.dumps(result)
    assert route.call_count == 1


@respx.mock
async def test_name_cap_local_pagination_and_hidden_opt_in(service):
    records = [person(uid(n + 10), "Same") for n in range(100)]
    route = respx.get(BASE + "search/person").mock(return_value=httpx.Response(200, json=records))
    result = await call(service, "find_people", name="Same", match="exact", limit=2)
    assert result["resolution"] == "incomplete" and result["upstreamTruncated"]
    assert result["nextOffset"] == 2 and not result["complete"]
    second = await call(service, "find_people", name="Same", match="exact", limit=2, offset=2)
    assert not {p["id"] for p in result["people"]} & {p["id"] for p in second["people"]}
    route.mock(return_value=httpx.Response(200, json=[person(hidden=True)]))
    assert (await call(service, "find_people", name="Élodie"))["people"] == []
    assert (await call(service, "find_people", name="Élodie", include_hidden=True))["people"][0]["isHidden"]
    with pytest.raises(ToolError, match="Text clues"):
        await call(service, "find_people", name="  ")
    assert route.call_count == 4


@respx.mock
async def test_unnamed_people_pages_and_safety_stop(service, settings):
    settings.location_search_max_pages = 2
    route = respx.get(BASE + "people").mock(
        side_effect=[
            httpx.Response(200, json={"people": [person()], "hasNextPage": True}),
            httpx.Response(200, json={"people": [person(Q, ""), person(R, "", True)], "hasNextPage": True}),
        ]
    )
    first = await call(service, "list_people", unnamed_only=True)
    assert first["people"] == [] and first["nextPage"] == 2
    second = await call(service, "list_people", unnamed_only=True, page=2)
    assert [p["id"] for p in second["people"]] == [Q]
    assert second["truncated"] and not second["enumerationEnd"] and second["stopReason"] == "page_limit"
    with pytest.raises(ToolError, match="traversal bound"):
        await call(service, "list_people", page=3)
    assert [c.request.url.params["page"] for c in route.calls] == ["1", "2"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"people": [], "hasNextPage": True},
        {"people": [None], "hasNextPage": False},
        {"people": [person() | {"name": None}], "hasNextPage": False},
    ],
)
@respx.mock
async def test_malformed_people_are_errors_not_empty_success(service, payload):
    route = respx.get(BASE + "people").mock(return_value=httpx.Response(200, json=payload))
    with pytest.raises(ToolError, match="MalformedImmichResponse.*operation=people"):
        await call(service, "list_people")
    assert route.call_count == 1


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@respx.mock
async def test_all_people_location_dates_ocr_and_preference_preserved(service, settings, mode):
    settings.immich_search_api_mode = mode
    people = allow_people(P, Q)
    matched = photo(uid(20), people=(P, Q, R))
    metadata = respx.post(BASE + "search/metadata").mock(return_value=response([matched], mode=mode))
    smart = respx.post(BASE + "search/smart").mock(return_value=httpx.Response(503))
    result = await call(
        service,
        "search_library",
        filters={
            "people_all": [P, Q, P],
            "state": "Hawaiʻi",
            "city": "Test City",
            "country": "United States",
            "ocr": "Louisiana",
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
            "media_type": "IMAGE",
        },
        visual_preference="sunsets",
    )
    body = json.loads(metadata.calls[0].request.content)
    if mode == "legacy":
        assert body["personIds"] == [P, Q] and body["state"] == "Hawaiʻi" and body["ocr"] == "Louisiana"
        assert body["takenAfter"] == "2026-01-01T00:00:00+00:00" and body["page"] == 1
        assert not {"filter", "cursor", "orderBy"} & body.keys()
    else:
        assert body["filter"] == {
            "personIds": {"all": [P, Q]},
            "state": {"eq": "Hawaiʻi"},
            "city": {"eq": "Test City"},
            "country": {"eq": "United States"},
            "type": {"eq": "IMAGE"},
            "ocr": {"matches": "Louisiana"},
            "takenAt": {"gte": "2026-01-01T00:00:00+00:00", "lte": "2026-02-01T00:00:00+00:00"},
        }
        assert not {"personIds", "page", "state", "ocr", "order", "takenAfter"} & body.keys()
    assert body["withPeople"] and body["withExif"] and smart.call_count == 0
    assert result["complete"] and result["assets"][0]["state"] == "Hawaiʻi"
    assert result["assets"][0]["detectedPeople"][-1]["name"] == ""
    assert "only us" in result["searchContext"]["detectionCaveat"]
    assert result["searchContext"]["visualPreference"] == "sunsets"
    assert all(p.call_count == 1 for p in people)
    # Empty mandatory results stay empty; the preference never invokes smart search.
    metadata.mock(return_value=response([], mode=mode))
    empty = await call(
        service,
        "search_library",
        filters={"people_all": [P, Q], "state": "Hawaiʻi"},
        visual_preference="sunsets",
    )
    assert empty["assets"] == [] and empty["complete"] and smart.call_count == 0


@pytest.mark.parametrize(
    "predicates",
    [
        {"people_any": [R, S]},
        {"people_none": [Q]},
        {"people_all": [P], "people_any": [R, S], "people_none": [Q]},
    ],
)
@respx.mock
async def test_any_none_operator_results_and_legacy_limitation(service, settings, predicates):
    allow_people(P, Q, R, S)
    library = [photo(uid(30), people=(P, R)), photo(uid(31), people=(P, Q, S)), photo(uid(32), people=())]

    def search(request):
        body = json.loads(request.content)
        ops = body["filter"]["personIds"]
        assert body["filter"]["state"] == {"eq": "Hawaiʻi"} and "or" not in body["filter"]
        assert ops == {key.removeprefix("people_"): value for key, value in predicates.items()}

        def matches(a):
            known = {p["id"] for p in a["people"]}
            return (
                set(ops.get("all", [])) <= known
                and (not ops.get("any") or bool(set(ops["any"]) & known))
                and not set(ops.get("none", [])) & known
            )

        return response([a for a in library if matches(a)], mode="structured")

    route = respx.post(BASE + "search/metadata").mock(side_effect=search)
    with pytest.raises(ToolError, match="ImmichUnsupportedFeature"):
        await call(service, "search_library", filters=predicates | {"state": "Hawaiʻi"})
    assert route.call_count == 0
    settings.immich_search_api_mode = "structured"
    result = await call(service, "search_library", filters=predicates | {"state": "Hawaiʻi"})
    expected = (
        [uid(30), uid(31)]
        if "people_none" not in predicates
        else [uid(30), uid(32)]
        if "people_all" not in predicates
        else [uid(30)]
    )
    assert [a["id"] for a in result["assets"]] == expected


@pytest.mark.parametrize(
    "filters",
    [
        {"people_all": [P], "people_none": [P]},
        {"people_any": [P], "people_none": [P]},
        {"people_all": []},
        {"people_all": ["account-id"]},
        {"state": "  "},
        {"start_date": "2026-02-01", "end_date": "2026-01-01"},
        {"start_date": "2026-01-01T12:00:00"},
        {"query": " "},
        {"ocr": ""},
        {"reference_asset_id": REF},
        {"window_minutes": 20},
        {"reference_asset_id": REF, "reference_mode": "similar", "query": "snow"},
    ],
)
@respx.mock
async def test_contradictions_fail_before_upstream(service, filters):
    with pytest.raises(ToolError, match="ImmichValidationError"):
        await call(service, "search_library", filters=filters)
    assert not respx.calls


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@respx.mock
async def test_required_semantic_query_preserves_filters_and_pet_uncertainty(service, settings, mode):
    settings.immich_search_api_mode = mode
    allow_people(P)
    smart = respx.post(BASE + "search/smart").mock(return_value=response([photo(uid(33))], mode=mode))
    metadata = respx.post(BASE + "search/metadata").mock(return_value=response([]))
    args = {"filters": {"query": "dog in snow", "people_all": [P], "state": "Hawaiʻi", "ocr": "sign"}}
    result = await call(service, "search_library", **args)
    assert result["partial"] and not result["complete"] and result["stopReason"] == "ranked_sample"
    assert "pet" in result["searchContext"]["detectionCaveat"]
    body = json.loads(smart.calls[0].request.content)
    assert body["query"] == "dog in snow" and "withPeople" not in body
    assert "orderBy" not in body and "cursor" not in body and "page" not in body
    assert (body["filter"]["state"]["eq"] if mode == "structured" else body["state"]) == "Hawaiʻi"
    smart.mock(return_value=httpx.Response(503, text="body-canary"))
    with pytest.raises(ToolError, match="HTTP 503.*operation=search/smart"):
        await call(service, "search_library", **args)
    assert smart.call_count == 2 and metadata.call_count == 0


@pytest.mark.parametrize("mode,first,second", [("legacy", "2", "3"), ("structured", "opaque+/%", "002")])
@respx.mock
async def test_continuation_scope_reauthorization_duplicates_and_partial_failure(
    service, settings, monkeypatch, mode, first, second
):
    settings.immich_search_api_mode = mode
    person_read = allow_people(P)[0]
    route = respx.post(BASE + "search/metadata").mock(
        side_effect=[
            response([photo(uid(40))], first, mode),
            response([photo(uid(40)), photo(uid(41))], second, mode),
            httpx.Response(500, text="body-canary"),
        ]
    )
    page = await call(service, "search_library", filters={"people_all": [P], "state": "Hawaiʻi"}, limit=2)
    handle = page["continuation"]
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-b"))
    with pytest.raises(ToolError, match="unavailable for this account"):
        await call(service, "search_library", continuation=handle)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    with pytest.raises(ToolError, match="only continuation"):
        await call(service, "search_library", continuation=handle, filters={"state": "Elsewhere"})
    with pytest.raises(ToolError, match="unavailable for this account"):
        await call(service, "search_location_assets", continuation=handle)
    page = await call(service, "search_library", continuation=handle)
    assert page["returned"] == 1 and page["returnedSoFar"] == 2 and page["partial"]
    with pytest.raises(ToolError, match="previously returned 2 unique assets"):
        await call(service, "search_library", continuation=page["continuation"])
    assert route.call_count == 3 and person_read.call_count == 3
    bodies = [json.loads(c.request.content) for c in route.calls]
    field = "cursor" if mode == "structured" else "page"
    assert bodies[1][field] == (first if mode == "structured" else int(first))
    assert bodies[2][field] == (second if mode == "structured" else int(second))
    assert all(
        {k: v for k, v in b.items() if k != field} == {k: v for k, v in bodies[0].items() if k != field}
        for b in bodies
    )


@pytest.mark.parametrize("status", [403, 404])
@respx.mock
async def test_stale_or_denied_person_does_not_break_location_search(service, status):
    denied = respx.get(BASE + "people/" + P).mock(return_value=httpx.Response(status, text="body-canary"))
    metadata = respx.post(BASE + "search/metadata").mock(return_value=response([]))
    with pytest.raises(ToolError, match="HTTP " + str(status)) as error:
        await call(service, "search_library", filters={"people_all": [P]})
    if status == 403:
        assert "person.read" in str(error.value)
    assert (await call(service, "search_location_assets", state="Hawaiʻi"))["complete"]
    assert denied.call_count == metadata.call_count == 1


@respx.mock
async def test_hidden_people_and_native_person_thumbnail_limits(service, settings):
    respx.get(BASE + "people/" + P).mock(return_value=httpx.Response(200, json=person(hidden=True)))
    thumb = respx.get(BASE + "people/" + P + "/thumbnail").mock(
        return_value=httpx.Response(200, content=b"PNG", headers={"content-type": "image/png"})
    )
    with pytest.raises(ToolError, match="hidden"):
        await call(service, "get_person_thumbnail", person_id=P)
    with pytest.raises(ToolError, match="hidden"):
        await call(service, "search_library", filters={"people_all": [P]})
    assert thumb.call_count == 0
    result = await service[0].call_tool("get_person_thumbnail", {"person_id": P, "include_hidden": True})
    assert (
        result.structured_content is None and len(result.content) == 1 and result.content[0].type == "image"
    )
    settings.max_image_bytes = 2
    with pytest.raises(ToolError, match="PayloadTooLarge"):
        await call(service, "get_person_thumbnail", person_id=P, include_hidden=True)
    assert thumb.call_count == 2


@pytest.mark.parametrize("mode", ["legacy", "structured"])
@pytest.mark.parametrize("reference_mode", ["near_time", "afternoon", "same_place", "similar"])
@respx.mock
async def test_explicit_reference_uses_capture_not_upload_and_preserves_scope(
    service, settings, mode, reference_mode
):
    settings.immich_search_api_mode = mode
    ref = photo(REF, "2026-03-08T07:30:00Z")  # Spring DST transition day in Chicago.
    read = respx.get(BASE + "assets/" + REF).mock(return_value=httpx.Response(200, json=ref))
    allow_people(P)
    endpoint = "search/smart" if reference_mode == "similar" else "search/metadata"
    route = respx.post(BASE + endpoint).mock(return_value=response([photo(uid(50))], mode=mode))
    filters = {
        "reference_asset_id": REF,
        "reference_mode": reference_mode,
        "people_all": [P],
        "state": "Hawaiʻi",
    }
    if reference_mode == "afternoon":
        filters["time_zone"] = "America/Chicago"
    result = await call(service, "search_library", filters=filters)
    effective = result["searchContext"]["effectiveFilters"]
    if reference_mode == "afternoon":
        assert effective["start_date"] == "2026-03-08T12:00:00-05:00"
        assert effective["end_date"] == "2026-03-08T17:59:59.999000-05:00"
    elif reference_mode == "near_time":
        assert effective["start_date"] == "2026-03-08T06:30:00+00:00"
        assert effective["end_date"] == "2026-03-08T08:30:00+00:00"
    elif reference_mode == "same_place":
        assert effective["city"] == "Test City" and effective["country"] == "United States"
        assert "not a geographic radius" in result["searchContext"]["placePrecision"]
    else:
        body = json.loads(route.calls[0].request.content)
        assert body["queryAssetId"] == REF and "query" not in body
        assert result["partial"] and result["continuation"] is None
    assert effective["people_all"] == [P] and effective["state"] == "Hawaiʻi"
    assert result["searchContext"]["reference"]["id"] == REF
    assert read.call_count == route.call_count == 1


@pytest.mark.parametrize(
    "reference,extra,reason",
    [
        (photo(REF), {"reference_mode": "afternoon"}, "IANA"),
        (photo(REF), {"reference_mode": "afternoon", "time_zone": "Mars/Olympus"}, "IANA"),
        (photo(REF) | {"fileCreatedAt": None}, {"reference_mode": "near_time"}, "capture time"),
        (photo(REF) | {"exifInfo": {}}, {"reference_mode": "same_place"}, "location is missing"),
        (photo(REF), {"reference_mode": "same_place", "state": "Other"}, "conflicts"),
        (photo(REF), {"reference_mode": "near_time", "start_date": "2030-01-01"}, "conflict"),
    ],
)
@respx.mock
async def test_missing_or_conflicting_reference_metadata_never_widens(service, reference, extra, reason):
    respx.get(BASE + "assets/" + REF).mock(return_value=httpx.Response(200, json=reference))
    with pytest.raises(ToolError, match=reason):
        await call(service, "search_library", filters={"reference_asset_id": REF} | extra)
    assert len(respx.calls) == 1


@pytest.mark.parametrize("days,selected", [([2, 2, 4, 6, 8], 4), ([2, 3, 4, 6, 8], 5)])
@respx.mock
async def test_sampling_different_days_bounded_pool_and_fewer_no_images(service, days, selected):
    allow_people(P, Q)
    records = [photo(uid(60 + n), f"2026-01-{day:02d}T12:00:00Z") for n, day in enumerate(days)]

    def upstream(request):
        body = json.loads(request.content)
        assert body["personIds"] == [P, Q] and body["state"] == "Hawaiʻi" and body["type"] == "IMAGE"
        assert "query" not in body and "ocr" not in body
        lo, hi = datetime.fromisoformat(body["takenAfter"]), datetime.fromisoformat(body["takenBefore"])
        matches = [a for a in records if lo <= datetime.fromisoformat(a["fileCreatedAt"]) <= hi]
        return response(matches[: body["size"]])

    metadata = respx.post(BASE + "search/metadata").mock(side_effect=upstream)
    result = await call(
        service,
        "sample_photo_candidates",
        filters={
            "people_all": [P, Q],
            "state": "Hawaiʻi",
            "start_date": "2026-01-01",
            "end_date": "2026-01-09",
        },
        visual_preference="sunsets",
        candidate_limit=8,
        selection_count=5,
    )
    assert (
        metadata.call_count == 4 and sum(json.loads(c.request.content)["size"] for c in metadata.calls) == 8
    )
    assert result["candidateCount"] == 5 and len(result["suggestedSelection"]) == selected
    assert result["samplingFinished"] and result["partial"] and not result["complete"]
    assert all("Not visually assessed" in a["uncertainty"] for a in result["suggestedSelection"])
    assert {a["assetId"] for a in result["suggestedSelection"]} <= {a["id"] for a in result["candidates"]}
    assert len(respx.calls) == 6  # two authorized people + four metadata bins, zero images/smart calls


@respx.mock
async def test_sampling_retains_success_on_partial_failure_and_deduplicates(service):
    metadata = respx.post(BASE + "search/metadata").mock(
        side_effect=[
            response([photo(uid(70), "2026-01-03T00:00:00Z")]),
            response([photo(uid(70), "2026-01-03T00:00:00Z")]),
            httpx.Response(503, text="body-canary"),
        ]
    )
    result = await call(
        service,
        "sample_photo_candidates",
        filters={"state": "Hawaiʻi", "start_date": "2026-01-01", "end_date": "2026-01-09"},
    )
    assert result["candidateCount"] == 1 and len(result["suggestedSelection"]) == 1
    assert not result["samplingFinished"] and result["partial"] and not result["complete"]
    assert "HTTP 503" in result["error"] and "Do not automatically retry" in result["error"]
    assert "body-canary" not in json.dumps(result) and metadata.call_count == 3


@pytest.mark.parametrize(
    "status,attempts,category",
    [
        (400, 1, "ImmichBadRequest"),
        (422, 1, "ImmichValidationError"),
        (401, 1, "InvalidImmichCredential"),
        (403, 1, "ImmichForbidden"),
        (429, 3, "ImmichRateLimited"),
        (500, 3, "ImmichUnavailable"),
        (503, 3, "ImmichUnavailable"),
        ("timeout", 3, "ImmichTimeout"),
        ("json", 1, "MalformedImmichResponse"),
    ],
)
@respx.mock
async def test_people_raw_mcp_errors_and_logs_sanitized(
    settings, monkeypatch, caplog, status, attempts, category
):
    settings.http_max_retries = 2
    route = respx.get(BASE + "search/person")
    if status == "timeout":
        route.mock(side_effect=httpx.ReadTimeout("private-body-canary"))
    else:
        route.mock(
            return_value=httpx.Response(
                status if isinstance(status, int) else 200, text="private-body-canary"
            )
        )
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):
        with capture_logs() as logs:
            result = await tool_call(http, "user-a", "find_people", {"name": "private-name-canary"})
    wire = result.json()["result"]
    assert wire["isError"] and "structuredContent" not in wire
    text = wire["content"][0]["text"]
    assert category in text and "operation=search/person" in text and "correlation_id=" in text
    assert "Do not automatically retry" in text and route.call_count == attempts
    if status == 403:
        assert "person.read" in text
    encoded = json.dumps([wire, logs]) + caplog.text
    assert all(
        canary not in encoded
        for canary in [
            "private-name-canary",
            "private-body-canary",
            "api-key-a",
            "INVALID_ARGUMENT",
            "Traceback",
        ]
    )


@respx.mock
async def test_wire_account_scope_names_references_continuations_thumbnails_and_revocation(
    settings, monkeypatch
):
    settings.immich_search_api_mode = "structured"
    seen, revoked = [], set()

    def upstream(request):
        key, path = request.headers["x-api-key"], request.url.path
        seen.append((key, path))
        assert "authorization" not in request.headers and "x-immich-share-key" not in request.headers
        if key in revoked:
            return httpx.Response(401)
        own = P if key == "api-key-a" else Q
        if path.endswith("search/person"):
            return httpx.Response(200, json=[person(own, "Same")])
        if path.startswith("/api/people/"):
            if path.split("/")[3] != own:
                return httpx.Response(403)
            if path.endswith("thumbnail"):
                return httpx.Response(200, content=own.encode(), headers={"content-type": "image/png"})
            return httpx.Response(200, json=person(own, "Same"))
        if path == "/api/assets/" + REF:
            return httpx.Response(200, json=photo(REF)) if key == "api-key-a" else httpx.Response(403)
        if path.endswith("search/metadata"):
            body = json.loads(request.content)
            assert body["filter"]["personIds"] == {"all": [own]}
            assert body["filter"]["state"] == {"eq": "Hawaiʻi"}
            return response(
                [photo(uid(80) if key == "api-key-a" else uid(81))],
                "002" if "cursor" not in body else None,
                "structured",
            )
        raise AssertionError("Unexpected path")

    respx.route(host="photo.example.com").mock(side_effect=upstream)
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):

        async def invoke(user, name, args):
            return (await tool_call(http, user, name, args)).json()["result"]

        for user, own in [("user-a", P), ("user-b", Q)]:
            names = await invoke(user, "find_people", {"name": "Same"})
            assert names["structuredContent"]["people"][0]["id"] == own
            image = await invoke(user, "get_person_thumbnail", {"person_id": own})
            assert image["content"][0]["type"] == "image" and "structuredContent" not in image
        assert (await invoke("user-b", "get_person_thumbnail", {"person_id": P}))["isError"]
        assert (
            await invoke(
                "user-b",
                "search_library",
                {"filters": {"reference_asset_id": REF, "reference_mode": "similar"}},
            )
        )["isError"]
        first = await invoke(
            "user-a",
            "search_library",
            {
                "filters": {
                    "people_all": [P],
                    "state": "Hawaiʻi",
                    "reference_asset_id": REF,
                    "reference_mode": "near_time",
                }
            },
        )
        handle = first["structuredContent"]["continuation"]
        before = len(seen)
        assert (await invoke("user-b", "search_library", {"continuation": handle}))["isError"]
        assert (await invoke("unconnected", "find_people", {"name": "Same"}))["isError"]
        assert len(seen) == before
        next_page = await invoke("user-a", "search_library", {"continuation": handle})
        assert next_page["structuredContent"]["complete"] and next_page["structuredContent"]["returned"] == 0
        assert seen.count(("api-key-a", "/api/assets/" + REF)) == 2
        revoked.add("api-key-a")
        assert (await invoke("user-a", "find_people", {"name": "Same"}))["isError"]
        assert not (await invoke("user-b", "find_people", {"name": "Same"})).get("isError", False)


async def test_new_tool_schemas_and_guidance_are_self_contained(service):
    tools = {t.name: t for t in await service[0].list_tools()}
    expected = {
        "find_people",
        "list_people",
        "get_person_thumbnail",
        "search_library",
        "sample_photo_candidates",
    }
    assert expected <= tools.keys()
    for name in expected:
        tool = tools[name]
        schema = tool.input_schema
        assert not {"user", "owner", "credential", "api_key", "url", "body"} & schema["properties"].keys()
        assert tool.annotations.read_only_hint
    schema = json.dumps(tools["search_library"].input_schema)
    assert all(
        key in schema
        for key in ["people_all", "people_any", "people_none", "reference_asset_id", "time_zone"]
    )
    assert '"additionalProperties": false' in schema
    assert (
        "person.read" in tools["find_people"].description
        and "not verified" in tools["search_library"].description
    )
    assert "structured v3.2" in tools["search_library"].description
    assert "person_id" in tools["search_assets"].input_schema["properties"]


@respx.mock
async def test_wire_rejects_nested_scope_override_without_echoing_it(settings, monkeypatch):
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):
        result = await tool_call(
            http, "user-a", "search_library", {"filters": {"owner": "private-owner-canary"}}
        )
    assert result.json()["result"]["isError"] and not respx.calls
    # SDK input validation may name the rejected field; it must never execute it as scope.
    assert "private-owner-canary" not in result.text


@pytest.mark.parametrize("next_value", ["002", "", 2])
@respx.mock
async def test_discovery_malformed_or_repeated_cursor_remains_incomplete(service, settings, next_value):
    settings.immich_search_api_mode = "structured"
    route = respx.post(BASE + "search/metadata").mock(
        side_effect=[
            response([photo(uid(90))], "002", "structured"),
            response([photo(uid(91))], next_value, "structured"),
        ]
    )
    first = await call(service, "search_library", filters={"state": "Hawaiʻi"})
    with pytest.raises(ToolError, match="MalformedImmichResponse.*Enumeration incomplete"):
        await call(service, "search_library", continuation=first["continuation"])
    assert route.call_count == 2


@respx.mock
async def test_person_authorization_is_not_cached_between_pages(service):
    people = respx.get(BASE + "people/" + P).mock(
        side_effect=[httpx.Response(200, json=person()), httpx.Response(404)]
    )
    metadata = respx.post(BASE + "search/metadata").mock(return_value=response([photo(uid(92))], "2"))
    first = await call(service, "search_library", filters={"people_all": [P]})
    with pytest.raises(ToolError, match="HTTP 404.*Enumeration incomplete"):
        await call(service, "search_library", continuation=first["continuation"])
    assert people.call_count == 2 and metadata.call_count == 1


@respx.mock
async def test_near_time_intersection_and_exif_local_afternoon(service):
    reference = photo(REF, "2026-11-01T06:30:00Z")
    reference["exifInfo"]["timeZone"] = "America/Chicago"
    respx.get(BASE + "assets/" + REF).mock(return_value=httpx.Response(200, json=reference))
    metadata = respx.post(BASE + "search/metadata").mock(return_value=response([]))
    result = await call(
        service,
        "search_library",
        filters={
            "reference_asset_id": REF,
            "reference_mode": "near_time",
            "window_minutes": 30,
            "start_date": "2026-11-01T06:20:00Z",
        },
    )
    effective = result["searchContext"]["effectiveFilters"]
    assert effective["start_date"] == "2026-11-01T06:20:00+00:00"
    assert effective["end_date"] == "2026-11-01T07:00:00+00:00"
    result = await call(
        service, "search_library", filters={"reference_asset_id": REF, "reference_mode": "afternoon"}
    )
    assert result["searchContext"]["effectiveFilters"]["start_date"] == "2026-11-01T12:00:00-06:00"
    assert metadata.call_count == 2


@respx.mock
async def test_hidden_labels_omitted_and_semantic_reference_removed(service):
    hidden = photo(uid(93))
    hidden["people"] = [person(P, "Visible"), person(Q, "Hidden", True)]
    respx.post(BASE + "search/metadata").mock(return_value=response([hidden]))
    result = await call(service, "search_library", filters={"state": "Hawaiʻi"})
    assert [p["id"] for p in result["assets"][0]["detectedPeople"]] == [P]
    result = await call(
        service, "search_library", filters={"state": "Hawaiʻi", "include_hidden_people": True}
    )
    assert len(result["assets"][0]["detectedPeople"]) == 2
    respx.get(BASE + "assets/" + REF).mock(return_value=httpx.Response(200, json=photo(REF)))
    respx.post(BASE + "search/smart").mock(return_value=response([photo(REF), hidden, hidden]))
    result = await call(
        service, "search_library", filters={"reference_asset_id": REF, "reference_mode": "similar"}
    )
    assert [a["id"] for a in result["assets"]] == [uid(93)] and result["partial"]


@pytest.mark.parametrize(
    "args",
    [
        {"candidate_limit": 49},
        {"selection_count": 13},
        {"time_bins": 7},
        {"min_gap_minutes": -1},
        {"time_zone": "Mars/Olympus"},
        {"filters": {"query": "sunsets"}},
        {"filters": {"media_type": "VIDEO", "start_date": "2026-01-01", "end_date": "2026-02-01"}},
        {"filters": {"state": "Hawaiʻi"}},
    ],
)
@respx.mock
async def test_sampling_invalid_bounds_or_required_semantics_do_not_issue_queries(service, args):
    kwargs = {"filters": {"state": "Hawaiʻi", "start_date": "2026-01-01", "end_date": "2026-02-01"}} | args
    with pytest.raises(ToolError, match="ImmichValidationError"):
        await call(service, "sample_photo_candidates", **kwargs)
    assert not respx.calls


@respx.mock
async def test_missing_dates_no_unsupported_quality_claim_and_empty_sampling(service):
    route = respx.post(BASE + "search/metadata").mock(
        return_value=response([photo(uid(94)) | {"fileCreatedAt": None}])
    )
    args = {"filters": {"start_date": "2026-01-01", "end_date": "2026-02-01"}}
    result = await call(service, "sample_photo_candidates", **args)
    assert result["candidateCount"] == 1 and result["suggestedSelection"] == []
    route.mock(return_value=response([]))
    result = await call(service, "sample_photo_candidates", **args)
    assert result["candidateCount"] == 0 and result["samplingFinished"] and result["partial"]
    assert route.call_count == 8


@respx.mock
async def test_legacy_single_any_and_existing_single_person_shape(service):
    allow_people(P)
    route = respx.post(BASE + "search/metadata").mock(return_value=response([photo(uid(95))]))
    await call(service, "search_library", filters={"people_any": [P]})
    old = await service[0].call_tool("search_assets", {"person_id": P})
    assert isinstance(old.structured_content["result"], list)
    assert old.structured_content["result"][0]["id"] == uid(95)
    assert "continuation" not in old.structured_content
    assert all(json.loads(c.request.content)["personIds"] == [P] for c in route.calls)


@respx.mock
async def test_raw_tool_list_exposes_nested_contract_and_rejects_invalid_values_safely(
    settings, monkeypatch, caplog
):
    app = await authenticated_app(settings, monkeypatch)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.com") as http,
    ):
        listing = await http.post(
            "/mcp",
            headers={"Authorization": "Bearer user-a", "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        tools = {t["name"]: t for t in listing.json()["result"]["tools"]}
        schema = tools["search_library"]["inputSchema"]
        assert schema["additionalProperties"] is False
        assert schema["$defs"]["DiscoveryFilters"]["additionalProperties"] is False
        assert "visual_preference" in schema["properties"]
        with capture_logs() as logs:
            invalid = await tool_call(
                http, "user-a", "search_library", {"filters": {"people_all": "private-name-canary"}}
            )
        assert invalid.json()["result"]["isError"]
        assert "private-name-canary" not in invalid.text + json.dumps(logs) + caplog.text
    assert not respx.calls


@respx.mock
async def test_sampling_spacing_uses_real_time_across_dst_fold(service):
    route = respx.post(BASE + "search/metadata").mock(
        return_value=response(
            [photo(uid(96), "2026-11-01T01:30:00-05:00"), photo(uid(97), "2026-11-01T01:30:00-06:00")]
        )
    )
    result = await call(
        service,
        "sample_photo_candidates",
        filters={"start_date": "2026-11-01T00:00:00-05:00", "end_date": "2026-11-02T00:00:00-06:00"},
        time_zone="America/Chicago",
        candidate_limit=2,
        selection_count=2,
        time_bins=1,
        min_gap_minutes=30,
    )
    assert len(result["suggestedSelection"]) == 2 and route.call_count == 1
