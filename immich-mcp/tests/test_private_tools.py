import httpx
import pytest
import respx
from mcp.types import ImageContent
from mcp.server.mcpserver.exceptions import ToolError

import app.mcp.tools.connection as connection
from app.auth.oidc import OIDCJWTVerifier
from app.credentials.crypto import CredentialCipher
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient
from app.immich.models import AuthenticatedUser
from app.mcp.server import create_mcp_server


def mcp_user(subject: str) -> AuthenticatedUser:
    return AuthenticatedUser(
        issuer="https://auth.example.com/application/o/immich-mcp/",
        sub=subject,
        email="same@example.com",
        scopes=["immich.read"],
    )


async def private_server(settings):
    provider = SQLiteCredentialProvider(
        settings.credential_db_path,
        CredentialCipher(settings.credential_encryption_key.get_secret_value()),
        settings.account_session_secret.get_secret_value(),
    )
    await provider.initialize()
    await provider.store_api_key(mcp_user("user-a"), "api-key-a", {"id": "ia"})
    await provider.store_api_key(mcp_user("user-b"), "api-key-b", {"id": "ib"})
    client = ImmichClient(settings)
    verifier = OIDCJWTVerifier(settings)
    server = create_mcp_server(settings, client, verifier, provider)
    return server, provider, client, verifier


@pytest.mark.asyncio
@respx.mock
async def test_mcp_identity_selects_credential_and_has_no_override(settings, monkeypatch):
    route = respx.get("https://photo.example.com/api/albums").mock(
        side_effect=lambda request: httpx.Response(
            200, json=[{"id": request.headers["x-api-key"], "albumName": "Mine"}]
        )
    )
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    await server.call_tool("list_albums", {})
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-b"))
    await server.call_tool("list_albums", {})
    assert [call.request.headers["x-api-key"] for call in route.calls] == ["api-key-a", "api-key-b"]
    # Unknown identity-shaped arguments are ignored by the SDK validator and cannot
    # influence the request-context identity selected by the tool.
    await server.call_tool("list_albums", {"subject": "user-a"})
    assert route.calls[-1].request.headers["x-api-key"] == "api-key-b"
    await verifier.aclose()
    await client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_private_mcp_tools_and_native_images(settings, monkeypatch):
    respx.get("https://photo.example.com/api/albums").mock(
        return_value=httpx.Response(200, json=[{"id": "a1", "albumName": "Trip", "assetCount": 1}])
    )
    respx.get("https://photo.example.com/api/albums/a1").mock(
        return_value=httpx.Response(200, json={"id": "a1", "albumName": "Trip"})
    )
    respx.get("https://photo.example.com/api/assets/x1").mock(
        return_value=httpx.Response(200, json={"id": "x1", "type": "IMAGE"})
    )
    respx.get("https://photo.example.com/api/assets/x1/thumbnail").mock(
        return_value=httpx.Response(200, content=b"WEBP", headers={"content-type": "image/webp"})
    )
    respx.get("https://photo.example.com/api/assets/x1/original").mock(
        return_value=httpx.Response(200, content=b"JPEG", headers={"content-type": "image/jpeg"})
    )
    respx.post("https://photo.example.com/api/search/metadata").mock(
        side_effect=[
            httpx.Response(200, json={"assets": {"items": [{"id": "x1", "type": "IMAGE"}], "nextCursor": None}}),
            httpx.Response(200, json={"assets": {"items": [{"id": "recent", "type": "IMAGE"}], "nextCursor": None}}),
        ]
    )
    respx.post("https://photo.example.com/api/search/smart").mock(
        return_value=httpx.Response(
            200, json={"assets": {"items": [{"id": "smart", "type": "IMAGE"}], "nextCursor": None}}
        )
    )
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("user-a"))
    status = await server.call_tool("get_immich_connection_status", {})
    assert status.structured_content["connected"] is True
    assert not (await server.call_tool("list_albums", {})).is_error
    assert not (await server.call_tool("get_album", {"album_id": "a1"})).is_error
    assert not (
        await server.call_tool("list_album_assets", {"album_id": "a1", "limit": 10, "offset": 0})
    ).is_error
    assert not (await server.call_tool("get_asset_metadata", {"asset_id": "x1"})).is_error
    thumb = await server.call_tool("get_asset_thumbnail", {"asset_id": "x1"})
    original = await server.call_tool("get_asset_image", {"asset_id": "x1"})
    assert isinstance(thumb.content[0], ImageContent) and thumb.content[0].mime_type == "image/webp"
    assert isinstance(original.content[0], ImageContent) and original.content[0].mime_type == "image/jpeg"
    assert not (await server.call_tool("search_assets", {"query": "snow", "limit": 5})).is_error
    assert not (await server.call_tool("get_recent_assets", {"limit": 5})).is_error
    await verifier.aclose()
    await client.aclose()


@pytest.mark.asyncio
async def test_disconnected_user_gets_account_link(settings, monkeypatch):
    server, _, client, verifier = await private_server(settings)
    monkeypatch.setattr(connection, "current_user", lambda: mcp_user("not-connected"))
    with pytest.raises(ToolError, match="mcp.example.com/account"):
        await server.call_tool("list_albums", {})
    await verifier.aclose()
    await client.aclose()
