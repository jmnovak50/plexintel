import base64
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent

from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError
from app.mcp.tools.albums import _compact_asset
from app.mcp.tools.connection import READ_ONLY, private_credential, private_error


def register_asset_tools(
    server: MCPServer,
    client: ImmichClient,
    provider: SQLiteCredentialProvider,
    settings: Settings,
) -> None:
    @server.tool(annotations=READ_ONLY)
    async def get_asset_metadata(asset_id: str) -> dict[str, Any]:
        """Read metadata for an asset visible to the authenticated user's Immich account."""
        credential = await private_credential(provider, settings)
        try:
            return await client.get_asset_metadata(credential, asset_id)
        except ImmichError as exc:
            raise private_error(exc, "asset metadata reading (requires asset.read)", settings) from exc

    @server.tool(structured_output=False, annotations=READ_ONLY)
    async def get_asset_thumbnail(
        asset_id: str, size: str = "preview", edited: bool | None = None
    ) -> list[ImageContent]:
        """Return a broadly compatible image preview for viewing, vision analysis, and display.

        Use this tool whenever the model needs to inspect, describe, analyze, or show
        an Immich image. Prefer this over get_asset_image for normal visual use because
        the original asset may be HEIC or another format unsupported by some vision models.
        """
        credential = await private_credential(provider, settings)
        try:
            image = await client.get_asset_thumbnail(credential, asset_id, size=size, edited=edited)
        except ImmichError as exc:
            raise private_error(exc, "asset viewing (requires asset.view)", settings) from exc
        return [_image_content(image.data, image.mime_type)]

    @server.tool(structured_output=False, annotations=READ_ONLY)
    async def get_asset_image(
        asset_id: str, edited: bool | None = None
    ) -> list[ImageContent]:
        """Return the original Immich image in its native file format.

        The original asset may be HEIC or another format unsupported by some vision models.
        Do not use this tool for ordinary visual inspection, image description, or display.
        Use get_asset_thumbnail instead unless the user explicitly requests the original
        or native image file."""
        credential = await private_credential(provider, settings)
        try:
            image = await client.get_asset_image(credential, asset_id, edited=edited)
        except ImmichError as exc:
            raise private_error(exc, "original asset reading (requires asset.download)", settings) from exc
        return [_image_content(image.data, image.mime_type)]

    @server.tool(annotations=READ_ONLY)
    async def search_assets(
        query: str | None = None,
        city: str | None = None,
        country: str | None = None,
        person_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        media_type: str | None = None,
        favorite: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search visible assets using current Immich smart/metadata search filters."""
        if limit < 1:
            raise ValueError("limit must be positive")
        limit = min(limit, settings.private_tool_max_items)
        credential = await private_credential(provider, settings)
        try:
            assets = await client.search_assets(
                credential, query=query, city=city, country=country, person_id=person_id,
                start_date=start_date, end_date=end_date, media_type=media_type,
                favorite=favorite, limit=limit,
            )
        except ImmichError as exc:
            raise private_error(exc, "asset search (requires asset.read)", settings) from exc
        return [_compact_asset(asset) for asset in assets]

    @server.tool(annotations=READ_ONLY)
    async def get_recent_assets(limit: int = 25) -> list[dict[str, Any]]:
        """Return recent timeline assets visible to the authenticated user's Immich account."""
        if limit < 1:
            raise ValueError("limit must be positive")
        limit = min(limit, settings.private_tool_max_items)
        credential = await private_credential(provider, settings)
        try:
            assets = await client.get_recent_assets(credential, limit=limit)
        except ImmichError as exc:
            raise private_error(exc, "recent asset reading (requires asset.read)", settings) from exc
        return [_compact_asset(asset) for asset in assets]


def _image_content(data: bytes, mime_type: str) -> ImageContent:
    return ImageContent(
        type="image", data=base64.b64encode(data).decode("ascii"), mime_type=mime_type
    )
