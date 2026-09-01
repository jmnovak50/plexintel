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
    PayloadTooLarge,
    normalize_parallel_assets,
)


class CountingAsyncStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.yielded = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            self.yielded += 1
            yield chunk

    async def aclose(self):
        self.closed = True


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
    route = respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"webp", headers={"content-type": "image/webp"})
    )
    client = ImmichClient(settings)
    image = await client.get_shared_asset_thumbnail("secret", "id1")
    assert image.data == b"webp"
    assert image.mime_type == "image/webp"
    assert route.calls[0].request.url.params["key"] == "secret"
    assert "x-immich-share-key" not in route.calls[0].request.headers
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_content_length_under_image_limit(settings):
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(
            200, content=b"jpeg", headers={"content-type": "image/jpeg", "content-length": "4"}
        )
    )
    client = ImmichClient(settings)
    image = await client.get_shared_asset_thumbnail("secret", "id1")
    assert image.data == b"jpeg" and image.mime_type == "image/jpeg"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_content_length_over_limit_aborts_before_body(settings):
    limited = settings.model_copy(update={"max_image_bytes": 1024})
    stream = CountingAsyncStream([b"not-read"])
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(
            200,
            stream=stream,
            headers={"content-type": "image/jpeg", "content-length": "1025"},
        )
    )
    client = ImmichClient(limited)
    with pytest.raises(PayloadTooLarge):
        await client.get_shared_asset_thumbnail("secret", "id1")
    assert stream.yielded == 0 and stream.closed
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_stream_without_content_length_under_limit(settings):
    limited = settings.model_copy(update={"max_image_bytes": 1024})
    stream = CountingAsyncStream([b"a" * 400, b"b" * 400])
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(200, stream=stream, headers={"content-type": "image/png"})
    )
    client = ImmichClient(limited)
    image = await client.get_shared_asset_thumbnail("secret", "id1")
    assert len(image.data) == 800 and image.mime_type == "image/png"
    assert stream.yielded == 2 and stream.closed
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_stream_without_content_length_stops_at_limit(settings):
    limited = settings.model_copy(update={"max_image_bytes": 1024})
    stream = CountingAsyncStream([b"a" * 700, b"b" * 400, b"must-not-be-read"])
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(200, stream=stream, headers={"content-type": "image/jpeg"})
    )
    client = ImmichClient(limited)
    with pytest.raises(PayloadTooLarge):
        await client.get_shared_asset_thumbnail("secret", "id1")
    assert stream.yielded == 2 and stream.closed
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_image_rejects_non_image_before_reading(settings):
    stream = CountingAsyncStream([b'{"error":"no"}'])
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(
            200, stream=stream, headers={"content-type": "application/json"}
        )
    )
    client = ImmichClient(settings)
    with pytest.raises(MalformedImmichResponse):
        await client.get_shared_asset_thumbnail("secret", "id1")
    assert stream.yielded == 0 and stream.closed
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, InvalidShareLink), (403, ImmichForbidden), (429, ImmichRateLimited),
     (500, ImmichUnavailable)],
)
@pytest.mark.asyncio
@respx.mock
async def test_streaming_shared_image_status_mapping(settings, status, error):
    respx.get("https://photo.example.com/api/assets/id1/thumbnail").mock(
        return_value=httpx.Response(status)
    )
    client = ImmichClient(settings)
    with pytest.raises(error):
        await client.get_shared_asset_thumbnail("secret", "id1")
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
