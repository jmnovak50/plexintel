from __future__ import annotations

import httpx
import pytest
from conftest import public_resolver

from app.mealie.client import MealieClient
from app.mealie.errors import MealieInvalidResponse, MealieUnavailable
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
