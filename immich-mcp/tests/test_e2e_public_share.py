import httpx
import pytest
import respx
from mcp.types import ImageContent

from app.auth.oidc import OIDCJWTVerifier
from app.immich.client import ImmichClient
from app.immich.shares import extract_share_key
from app.mcp.server import create_mcp_server


@pytest.mark.asyncio
@respx.mock
async def test_share_url_to_normalized_assets_and_thumbnail(settings):
    respx.get("https://photo.example.com/api/shared-links/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "share-1",
                "type": "ALBUM",
                "expiresAt": None,
                "allowDownload": True,
                "showMetadata": True,
                "assets": [],
                "album": {"id": "album-1", "albumName": "Trip", "assetCount": 1},
            },
        )
    )
    respx.get("https://photo.example.com/api/timeline/buckets").mock(
        return_value=httpx.Response(200, json=[{"timeBucket": "2026-08-01", "count": 1}])
    )
    respx.get("https://photo.example.com/api/timeline/bucket").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": ["asset-1"],
                "fileCreatedAt": ["2026-08-02T12:00:00Z"],
                "city": ["Chicago"],
                "country": ["United States"],
                "ratio": [1.5],
                "isImage": [True],
                "livePhotoVideoId": [None],
                "visibility": ["timeline"],
            },
        )
    )
    thumb_route = respx.get("https://photo.example.com/api/assets/asset-1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"WEBP", headers={"content-type": "image/webp"})
    )

    key = extract_share_key("https://photo.example.com/share/SHARE123", settings)
    client = ImmichClient(settings)
    link = await client.get_shared_link(key)
    assets = await client.list_shared_album_assets(key, link.album.id)  # type: ignore[union-attr]
    image = await client.get_shared_asset_thumbnail(key, assets[0]["id"])

    assert assets[0]["city"] == "Chicago"
    assert assets[0]["visibility"] == "timeline"
    assert image.mime_type == "image/webp"
    assert image.data == b"WEBP"
    assert thumb_route.calls[0].request.url.params["key"] == "SHARE123"
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_mcp_image_tool_returns_native_webp_content(settings):
    respx.get("https://photo.example.com/api/assets/asset-1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"WEBP", headers={"content-type": "image/webp"})
    )
    client = ImmichClient(settings)
    verifier = OIDCJWTVerifier(settings)
    server = create_mcp_server(settings, client, verifier)
    result = await server.call_tool(
        "get_shared_asset_image", {"share_key": "SHARE123", "asset_id": "asset-1"}
    )
    assert len(result.content) == 1
    assert isinstance(result.content[0], ImageContent)
    assert result.content[0].mime_type == "image/webp"
    await verifier.aclose()
    await client.aclose()
