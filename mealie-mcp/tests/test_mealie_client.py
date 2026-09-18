from __future__ import annotations

import httpx
import pytest
from conftest import public_resolver

from app.mealie.client import MealieClient
from app.mealie.errors import CapabilityUnavailable, MealieInvalidResponse, MealieUnavailable
from app.mealie.resolver import OperationDescriptor
from app.security.destinations import DestinationPolicy


@pytest.mark.asyncio
async def test_redirect_to_forbidden_destination_is_never_followed(settings):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    client = MealieClient(settings, DestinationPolicy(settings, public_resolver), http)
    with pytest.raises(MealieUnavailable, match="refused redirect"):
        await client.request_json(
            "https://mealie.example", "secret", "GET", "/api/recipes", operation="recipe.search"
        )
    assert calls == ["https://mealie.example/api/recipes"]
    await http.aclose()


@pytest.mark.asyncio
async def test_declared_and_streamed_response_limits_are_enforced(settings):
    oversized = settings.mealie_max_response_bytes + 1

    def declared(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"{}", headers={"content-length": str(oversized)})

    first_http = httpx.AsyncClient(transport=httpx.MockTransport(declared))
    first = MealieClient(settings, DestinationPolicy(settings, public_resolver), first_http)
    with pytest.raises(MealieInvalidResponse, match="too large"):
        await first.request_json(
            "https://mealie.example", "secret", "GET", "/api/recipes", operation="recipe.search"
        )
    await first_http.aclose()

    small = settings.model_copy(update={"mealie_max_response_bytes": 1024})

    def streamed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'"' + b"x" * 2000 + b'"')

    second_http = httpx.AsyncClient(transport=httpx.MockTransport(streamed))
    second = MealieClient(small, DestinationPolicy(small, public_resolver), second_http)
    with pytest.raises(MealieInvalidResponse, match="too large"):
        await second.request_json(
            "https://mealie.example", "secret", "GET", "/api/recipes", operation="recipe.search"
        )
    await second_http.aclose()


@pytest.mark.asyncio
async def test_execute_maps_semantic_parameters_and_never_silently_drops_them(settings):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"items": []})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = MealieClient(settings, DestinationPolicy(settings, public_resolver), http)
    operation = OperationDescriptor(
        capability="recipe.search",
        method="GET",
        path="/api/recipes",
        query_parameters=frozenset({"page", "pageSize"}),
        parameter_map={"page": "page", "page_size": "pageSize"},
    )
    await client.execute(
        "https://mealie.example",
        "secret",
        operation,
        query={"page": 2, "page_size": 30},
    )
    assert dict(requests[0].url.params) == {"page": "2", "pageSize": "30"}
    with pytest.raises(CapabilityUnavailable, match="search"):
        await client.execute(
            "https://mealie.example",
            "secret",
            operation,
            query={"search": "soup"},
        )
    assert len(requests) == 1
    await http.aclose()
