from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.immich.client import (
    ExpiredShareLink,
    ImmichClient,
    ImmichForbidden,
    ImmichNotFound,
    ImmichRateLimited,
    ImmichTimeout,
    ImmichUnavailable,
    InvalidShareLink,
    MalformedImmichResponse,
    normalize_parallel_assets,
)


def link_payload(*, album_id="album-1", expires_at=None):
    return {
        "id": "link-1",
        "type": "ALBUM",
        "expiresAt": expires_at,
        "allowDownload": True,
        "showMetadata": True,
        "assets": [],
        "album": {"id": album_id, "albumName": "Summer", "assetCount": 2},
    }


@pytest.mark.asyncio
@respx.mock
async def test_expired_share_link(settings):
    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    respx.get("https://photo.example.com/api/shared-links/me").mock(
        return_value=httpx.Response(200, json=link_payload(expires_at=expired))
    )
    client = ImmichClient(settings)
    with pytest.raises(ExpiredShareLink):
        await client.get_shared_link("secret")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_invalid_share_link(settings):
    respx.get("https://photo.example.com/api/shared-links/me").mock(return_value=httpx.Response(401))
    client = ImmichClient(settings)
    with pytest.raises(InvalidShareLink):
        await client.get_shared_link("invalid")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_one_timeline_bucket(settings):
    respx.get("https://photo.example.com/api/timeline/buckets").mock(
        return_value=httpx.Response(200, json=[{"timeBucket": "2026-08-01", "count": 2}])
    )
    respx.get("https://photo.example.com/api/timeline/bucket").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": ["id1", "id2"],
                "fileCreatedAt": ["date1", "date2"],
                "city": ["Chicago", None],
                "isImage": [True, True],
            },
        )
    )
    client = ImmichClient(settings)
    assets = await client.list_shared_album_assets("secret", "album-1")
    assert assets == [
        {"id": "id1", "fileCreatedAt": "date1", "city": "Chicago", "isImage": True},
        {"id": "id2", "fileCreatedAt": "date2", "city": None, "isImage": True},
    ]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_multiple_timeline_buckets(settings):
    respx.get("https://photo.example.com/api/timeline/buckets").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"timeBucket": "2026-07-01", "count": 1},
                {"timeBucket": "2026-08-01", "count": 1},
            ],
        )
    )

    def bucket_response(request: httpx.Request):
        month = request.url.params["timeBucket"]
        suffix = "july" if month.startswith("2026-07") else "august"
        return httpx.Response(200, json={"id": [suffix], "isImage": [True]})

    respx.get("https://photo.example.com/api/timeline/bucket").mock(side_effect=bucket_response)
    client = ImmichClient(settings)
    assets = await client.list_shared_album_assets("secret", "album-1")
    assert [asset["id"] for asset in assets] == ["july", "august"]
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_empty_timeline(settings):
    respx.get("https://photo.example.com/api/timeline/buckets").mock(
        return_value=httpx.Response(200, json=[])
    )
    client = ImmichClient(settings)
    assert await client.list_shared_album_assets("secret", "album-1") == []
    await client.aclose()


def test_malformed_parallel_array_data():
    with pytest.raises(MalformedImmichResponse, match="inconsistent"):
        normalize_parallel_assets({"id": ["one", "two"], "city": ["Chicago"]})


def test_missing_parallel_arrays_are_allowed():
    assert normalize_parallel_assets({"id": ["one"], "isImage": [True]}) == [
        {"id": "one", "isImage": True}
    ]


@pytest.mark.asyncio
@respx.mock
async def test_webp_thumbnail_preserves_mime(settings):
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"webp", headers={"content-type": "image/webp"})
    )
    client = ImmichClient(settings)
    image = await client.get_shared_asset_thumbnail("secret", "id1")
    assert image.data == b"webp"
    assert image.mime_type == "image/webp"
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, InvalidShareLink),
        (403, ImmichForbidden),
        (404, ImmichNotFound),
        (429, ImmichRateLimited),
        (500, ImmichUnavailable),
        (503, ImmichUnavailable),
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_upstream_status_mapping(settings, status, error):
    respx.get("https://photo.example.com/api/shared-links/me").mock(return_value=httpx.Response(status))
    client = ImmichClient(settings)
    with pytest.raises(error):
        await client.get_shared_link("secret")
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_timeout_behavior(settings):
    request = httpx.Request("GET", "https://photo.example.com/api/shared-links/me")
    respx.get("https://photo.example.com/api/shared-links/me").mock(
        side_effect=httpx.ReadTimeout("timed out", request=request)
    )
    client = ImmichClient(settings)
    with pytest.raises(ImmichTimeout):
        await client.get_shared_link("secret")
    await client.aclose()

