import base64
import json
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations

from app.config import Settings
from app.immich.client import ImmichClient, InvalidShareLink
from app.immich.models import SharedAlbumResult
from app.immich.shares import resolve_share_input, validate_share_key

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def register_shared_tools(server: MCPServer, client: ImmichClient, settings: Settings) -> None:
    @server.tool(annotations=READ_ONLY)
    async def get_shared_album(
        share_url: str | None = None, share_key: str | None = None
    ) -> SharedAlbumResult:
        """Resolve an Immich public album share and return album metadata and permissions."""
        key = resolve_share_input(share_url=share_url, share_key=share_key, settings=settings)
        link = await _album_link(client, key)
        assert link.album is not None
        buckets = await client.get_timeline_buckets(key, link.album.id)
        count = sum(bucket.count for bucket in buckets)
        return SharedAlbumResult(
            shared_link=link.model_dump(by_alias=True, exclude={"assets", "album"}),
            album=link.album.model_dump(by_alias=True),
            album_id=link.album.id,
            asset_count=count,
            expiration=link.expires_at,
            permissions={
                "allowDownload": link.allow_download,
                "allowUpload": link.allow_upload,
                "showMetadata": link.show_metadata,
            },
        )

    @server.tool(annotations=READ_ONLY)
    async def list_shared_album_assets(
        share_url: str | None = None, share_key: str | None = None
    ) -> list[dict[str, Any]]:
        """Enumerate every asset in a public Immich album share via timeline buckets."""
        key = resolve_share_input(share_url=share_url, share_key=share_key, settings=settings)
        link = await _album_link(client, key)
        assert link.album is not None
        return await client.list_shared_album_assets(key, link.album.id)

    @server.tool(annotations=READ_ONLY)
    async def get_shared_asset_metadata(share_key: str, asset_id: str) -> dict[str, Any]:
        """Return metadata Immich exposes for an asset under shared-link authorization."""
        return await client.get_shared_asset_metadata(validate_share_key(share_key), asset_id)

    @server.tool(structured_output=False, annotations=READ_ONLY)
    async def get_shared_asset_image(
        share_key: str,
        asset_id: str,
        size: str | None = None,
        edited: bool | None = None,
    ) -> list[ImageContent]:
        """Fetch a shared asset thumbnail and return native MCP image content with its real MIME type."""
        image = await client.get_shared_asset_thumbnail(
            validate_share_key(share_key), asset_id, size=size, edited=edited
        )
        return [
            ImageContent(
                type="image",
                data=base64.b64encode(image.data).decode("ascii"),
                mime_type=image.mime_type,
            )
        ]

    @server.tool(annotations=READ_ONLY)
    async def get_shared_album_gallery(
        share_url: str | None = None,
        share_key: str | None = None,
        limit: int = 12,
        offset: int = 0,
    ) -> CallToolResult:
        """Return a bounded gallery with metadata and a small number of native MCP images."""
        if offset < 0 or limit < 0:
            raise ValueError("offset and limit must be non-negative")
        limit = min(limit, settings.gallery_max_items)
        key = resolve_share_input(share_url=share_url, share_key=share_key, settings=settings)
        link = await _album_link(client, key)
        assert link.album is not None
        all_assets = await client.list_shared_album_assets(key, link.album.id)
        page = all_assets[offset : offset + limit]
        structured = {
            "album": link.album.model_dump(by_alias=True),
            "total": len(all_assets),
            "offset": offset,
            "limit": limit,
            "returned": len(page),
            "assets": [
                {
                    **asset,
                    "imageTool": "get_shared_asset_image",
                    "imageToolArguments": {"asset_id": asset.get("id")},
                }
                for asset in page
            ],
        }
        content: list[TextContent | ImageContent] = [
            TextContent(type="text", text=json.dumps(structured, default=str, separators=(",", ":")))
        ]
        image_assets = [asset for asset in page if asset.get("isImage") is not False]
        for asset in image_assets[: settings.gallery_inline_image_limit]:
            image = await client.get_shared_asset_thumbnail(key, str(asset["id"]))
            content.append(
                ImageContent(
                    type="image",
                    data=base64.b64encode(image.data).decode("ascii"),
                    mime_type=image.mime_type,
                )
            )
        return CallToolResult(content=content, structured_content=structured)


async def _album_link(client: ImmichClient, key: str):
    link = await client.get_shared_link(key)
    if link.type.upper() != "ALBUM" or link.album is None:
        raise InvalidShareLink("Shared link is not an album share")
    return link
