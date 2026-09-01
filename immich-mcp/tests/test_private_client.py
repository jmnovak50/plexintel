import httpx
import pytest
import respx

from app.immich.client import (
    ImmichClient, ImmichForbidden, ImmichRateLimited, ImmichTimeout, ImmichUnavailable,
    InvalidImmichCredential,
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
    shared = respx.get("https://photo.example.com/api/shared-links/me").mock(
        return_value=httpx.Response(401)
    )
    client = ImmichClient(settings)
    assert (await client.get_current_user(credential()))["id"] == "u1"
    assert private.calls[0].request.headers["x-api-key"] == "user-key"
    assert "x-immich-share-key" not in private.calls[0].request.headers
    with pytest.raises(Exception):
        await client.get_shared_link("share-key")
    assert shared.calls[0].request.headers["x-immich-share-key"] == "share-key"
    assert "x-api-key" not in shared.calls[0].request.headers
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, InvalidImmichCredential), (403, ImmichForbidden), (429, ImmichRateLimited), (500, ImmichUnavailable)],
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
    [(401, InvalidImmichCredential), (403, ImmichForbidden), (429, ImmichRateLimited),
     (500, ImmichUnavailable)],
)
@pytest.mark.asyncio
@respx.mock
async def test_private_streaming_image_status_mapping(settings, status, error):
    respx.get("https://photo.example.com/api/assets/x1/thumbnail").mock(
        return_value=httpx.Response(status)
    )
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
    assert b'"albumIds":{"any":["a1"]}' in search.calls[0].request.content
    assert (await client.get_recent_assets(credential(), limit=10))[0]["id"] == "x2"
    image = await client.get_asset_thumbnail(credential(), "x1")
    assert image.mime_type == "image/webp"
    assert thumb.calls[0].request.headers["x-api-key"] == "user-key"
    assert albums.called
    await client.aclose()
