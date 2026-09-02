import json

import httpx
import pytest
import respx

from app.immich.client import (
    ImmichClient,
    ImmichForbidden,
    ImmichRateLimited,
    ImmichTimeout,
    ImmichUnavailable,
    InvalidImmichCredential,
    InvalidShareLink,
)
from app.immich.models import PrivateImmichCredential


def credential(value: str = "user-key") -> PrivateImmichCredential:
    return PrivateImmichCredential(kind="api_key", token=value)


@pytest.mark.asyncio
@respx.mock
async def test_api_key_header_and_auth_mode_isolation(settings):
    private = respx.get("https://photo.example.com/api/users/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "email": "u@example.com", "name": "User"})
    )
    shared = respx.get("https://photo.example.com/api/shared-links/me").mock(return_value=httpx.Response(401))
    client = ImmichClient(settings)
    assert (await client.get_current_user(credential()))["id"] == "u1"
    assert private.calls[0].request.headers["x-api-key"] == "user-key"
    assert "x-immich-share-key" not in private.calls[0].request.headers
    with pytest.raises(InvalidShareLink):
        await client.get_shared_link("share-key")
    assert shared.calls[0].request.headers["x-immich-share-key"] == "share-key"
    assert "x-api-key" not in shared.calls[0].request.headers
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, InvalidImmichCredential),
        (403, ImmichForbidden),
        (429, ImmichRateLimited),
        (500, ImmichUnavailable),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_private_status_mapping(settings, status, error):
    respx.get("https://photo.example.com/api/users/me").mock(return_value=httpx.Response(status))
    client = ImmichClient(settings)
    with pytest.raises(error):
        await client.get_current_user(credential())
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, InvalidImmichCredential),
        (403, ImmichForbidden),
        (429, ImmichRateLimited),
        (500, ImmichUnavailable),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_private_streaming_image_status_mapping(settings, status, error):
    respx.get("https://photo.example.com/api/assets/x1/thumbnail").mock(return_value=httpx.Response(status))
    client = ImmichClient(settings)
    with pytest.raises(error):
        await client.get_asset_thumbnail(credential(), "x1")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_private_timeout(settings):
    request = httpx.Request("GET", "https://photo.example.com/api/users/me")
    respx.get("https://photo.example.com/api/users/me").mock(
        side_effect=httpx.ReadTimeout("timed out", request=request)
    )
    client = ImmichClient(settings)
    with pytest.raises(ImmichTimeout):
        await client.get_current_user(credential())
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_private_album_search_recent_and_webp(settings):
    albums = respx.get("https://photo.example.com/api/albums").mock(
        return_value=httpx.Response(200, json=[{"id": "a1", "albumName": "Trip"}])
    )
    search = respx.post("https://photo.example.com/api/search/metadata").mock(
        side_effect=[
            httpx.Response(200, json={"assets": {"items": [{"id": "x1"}], "nextCursor": None}}),
            httpx.Response(200, json={"assets": {"items": [{"id": "x2"}], "nextCursor": None}}),
        ]
    )
    thumb = respx.get("https://photo.example.com/api/assets/x1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"WEBP", headers={"content-type": "image/webp"})
    )
    client = ImmichClient(settings)
    assert (await client.list_albums(credential()))[0]["id"] == "a1"
    assets, _ = await client.list_album_assets(credential(), "a1", limit=10, offset=0)
    assert assets == [{"id": "x1"}]
    assert search.calls[0].request.headers["x-api-key"] == "user-key"
    assert json.loads(search.calls[0].request.content) == {
        "albumIds": ["a1"],
        "order": "asc",
        "page": 1,
        "size": 10,
    }
    assert (await client.get_recent_assets(credential(), limit=10))[0]["id"] == "x2"
    assert json.loads(search.calls[1].request.content) == {
        "visibility": "timeline",
        "order": "desc",
        "size": 10,
        "withExif": True,
    }
    image = await client.get_asset_thumbnail(credential(), "x1")
    assert image.mime_type == "image/webp"
    assert thumb.calls[0].request.headers["x-api-key"] == "user-key"
    assert albums.called
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_album_search_scope_does_not_fill_from_other_albums(settings):
    album_a = [{"id": f"a-{index}"} for index in range(3)]
    album_b = [{"id": f"b-{index}"} for index in range(4)]

    def search_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        items = album_a if body.get("albumIds") == ["album-a"] else album_a + album_b
        return httpx.Response(200, json={"assets": {"items": items, "nextPage": None}})

    search = respx.post("https://photo.example.com/api/search/metadata").mock(side_effect=search_response)
    client = ImmichClient(settings)
    assets, next_page = await client.list_album_assets(credential(), "album-a", limit=50, offset=0)

    assert assets == album_a
    assert len(assets) == 3
    assert next_page is None
    assert json.loads(search.calls[0].request.content)["size"] == 50
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_album_search_uses_one_based_next_page_pagination(settings):
    first_page = [{"id": f"x-{index}"} for index in range(1000)]
    second_page = [{"id": f"x-{index}"} for index in range(1000, 1010)]
    search = respx.post("https://photo.example.com/api/search/metadata").mock(
        side_effect=[
            httpx.Response(200, json={"assets": {"items": first_page, "nextPage": "2"}}),
            httpx.Response(200, json={"assets": {"items": second_page, "nextPage": None}}),
        ]
    )
    client = ImmichClient(settings)
    assets, next_page = await client.list_album_assets(credential(), "album-a", limit=10, offset=995)

    assert [asset["id"] for asset in assets] == [f"x-{index}" for index in range(995, 1005)]
    assert next_page is None
    assert [json.loads(call.request.content)["page"] for call in search.calls] == [1, 2]
    assert all(json.loads(call.request.content)["albumIds"] == ["album-a"] for call in search.calls)
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_exact_filename_lookup_uses_metadata_and_full_casefold_match(settings):
    metadata = respx.post("https://photo.example.com/api/search/metadata").mock(
        return_value=httpx.Response(
            200,
            json={
                "assets": {
                    "items": [
                        {"id": "partial", "originalFileName": "copy-IMG_0818.heic"},
                        {"id": "correct", "originalFileName": "IMG_0818.HEIC"},
                        {"id": "other", "originalFileName": "IMG_0819.heic"},
                    ],
                    "nextPage": None,
                }
            },
        )
    )
    smart = respx.post("https://photo.example.com/api/search/smart").mock(return_value=httpx.Response(500))
    client = ImmichClient(settings)
    assets, has_more = await client.find_assets_by_filename(credential(), "IMG_0818.heic", album_id="album-a")

    assert assets == [{"id": "correct", "originalFileName": "IMG_0818.HEIC"}]
    assert has_more is False
    assert metadata.call_count == 1
    assert smart.call_count == 0
    assert json.loads(metadata.calls[0].request.content) == {
        "originalFileName": "IMG_0818.heic",
        "order": "asc",
        "page": 1,
        "size": 1000,
        "withExif": True,
        "albumIds": ["album-a"],
    }
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_filename_lookup_album_scope_and_duplicate_order(settings):
    def search_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        items = [
            {"id": "late", "originalFileName": "same.heic", "fileCreatedAt": "2025-02-01"},
            {"id": "early-b", "originalFileName": "SAME.HEIC", "fileCreatedAt": "2025-01-01"},
            {"id": "early-a", "originalFileName": "same.heic", "fileCreatedAt": "2025-01-01"},
        ]
        if body.get("albumIds") == ["album-a"]:
            items = [items[0]]
        return httpx.Response(200, json={"assets": {"items": items, "nextPage": None}})

    respx.post("https://photo.example.com/api/search/metadata").mock(side_effect=search_response)
    client = ImmichClient(settings)

    scoped, scoped_more = await client.find_assets_by_filename(credential(), "same.heic", album_id="album-a")
    duplicates, duplicates_more = await client.find_assets_by_filename(credential(), "same.heic", limit=2)

    assert [asset["id"] for asset in scoped] == ["late"]
    assert scoped_more is False
    assert [asset["id"] for asset in duplicates] == ["early-a", "early-b"]
    assert duplicates_more is True
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_semantic_search_still_uses_smart_with_flat_filters(settings):
    smart = respx.post("https://photo.example.com/api/search/smart").mock(
        return_value=httpx.Response(200, json={"assets": {"items": [{"id": "smart"}], "nextPage": None}})
    )
    metadata = respx.post("https://photo.example.com/api/search/metadata").mock(
        return_value=httpx.Response(500)
    )
    client = ImmichClient(settings)
    assets = await client.search_assets(
        credential(), query="dog sleeping on a bed", city="Chicago", favorite=True, limit=5
    )

    assert assets == [{"id": "smart"}]
    assert smart.call_count == 1
    assert metadata.call_count == 0
    assert json.loads(smart.calls[0].request.content) == {
        "query": "dog sleeping on a bed",
        "size": 5,
        "withExif": True,
        "city": "Chicago",
        "isFavorite": True,
    }
    await client.aclose()
