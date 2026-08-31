from typing import Any

from mcp.server.mcpserver import MCPServer

from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError
from app.mcp.tools.connection import READ_ONLY, private_credential, private_error


ALBUM_COMPACT_FIELDS = (
    "id", "albumName", "assetCount", "createdAt", "updatedAt", "startDate", "endDate"
)


def register_album_tools(
    server: MCPServer,
    client: ImmichClient,
    provider: SQLiteCredentialProvider,
    settings: Settings,
) -> None:
    @server.tool(annotations=READ_ONLY)
    async def list_albums() -> list[dict[str, Any]]:
        """List albums visible to the authenticated user's connected Immich account."""
        credential = await private_credential(provider, settings)
        try:
            return [_select(album, ALBUM_COMPACT_FIELDS) for album in await client.list_albums(credential)]
        except ImmichError as exc:
            raise private_error(exc, "album listing (requires album.read)", settings) from exc

    @server.tool(annotations=READ_ONLY)
    async def get_album(album_id: str) -> dict[str, Any]:
        """Get an album visible to the authenticated user's connected Immich account."""
        credential = await private_credential(provider, settings)
        try:
            return await client.get_album(credential, album_id)
        except ImmichError as exc:
            raise private_error(exc, "album reading (requires album.read)", settings) from exc

    @server.tool(annotations=READ_ONLY)
    async def list_album_assets(
        album_id: str, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        """List a bounded page of assets in an album visible to the authenticated user."""
        limit, offset = _page(limit, offset, settings.private_tool_max_items)
        credential = await private_credential(provider, settings)
        try:
            assets, next_cursor = await client.list_album_assets(
                credential, album_id, limit=limit, offset=offset
            )
        except ImmichError as exc:
            raise private_error(exc, "album asset reading (requires asset.read)", settings) from exc
        return {
            "albumId": album_id,
            "offset": offset,
            "limit": limit,
            "returned": len(assets),
            "hasMore": bool(next_cursor),
            "assets": [_compact_asset(asset) for asset in assets],
        }


def _select(value: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: value.get(field) for field in fields}


def _compact_asset(asset: dict[str, Any]) -> dict[str, Any]:
    result = _select(
        asset,
        (
            "id", "type", "originalFileName", "fileCreatedAt", "localDateTime", "createdAt",
            "width", "height", "duration", "isFavorite", "visibility", "livePhotoVideoId",
        ),
    )
    exif = asset.get("exifInfo")
    if isinstance(exif, dict):
        result["city"] = exif.get("city")
        result["country"] = exif.get("country")
    return result


def _page(limit: int, offset: int, maximum: int) -> tuple[int, int]:
    if limit < 1 or offset < 0:
        raise ValueError("limit must be positive and offset must be non-negative")
    if offset > 100_000:
        raise ValueError("offset exceeds the safety limit")
    return min(limit, maximum), offset
