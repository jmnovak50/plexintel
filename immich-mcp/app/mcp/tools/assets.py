import base64
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent

from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError, ImmichValidationError
from app.immich.location import LocationSearch, location_value
from app.mcp.tools import connection
from app.mcp.tools.albums import _compact_asset
from app.mcp.tools.connection import READ_ONLY, private_credential, private_error


def register_asset_tools(
    server: MCPServer,
    client: ImmichClient,
    provider: SQLiteCredentialProvider,
    settings: Settings,
) -> None:
    locations = LocationSearch(client)

    @server.tool(annotations=READ_ONLY)
    async def get_location_suggestions(
        field: Literal["country", "state", "city"],
        country: str | None = None,
        state: str | None = None,
        contains: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Discover stored capture-location spellings from this user's searchable assets.

        Use for 'taken in [place]' before search_location_assets when spelling or geography
        is uncertain. Country may scope state/city suggestions; state may scope cities.
        Values retain Unicode/accents; contains is a local case-insensitive substring filter,
        not alias resolution. Nulls are omitted. An empty list is not proof a trip never occurred.
        Resolve meaningful ambiguity (e.g. Georgia country/state, Hawaii state/island) with
        the user. Do not substitute a city, album name, or global place lookup for a region.
        Returned suggestions are bounded; follow nextOffset with identical arguments if needed.
        """
        credential = await private_credential(provider, settings)
        try:
            if limit < 1 or offset < 0 or offset > 100_000:
                raise ImmichValidationError("limit must be positive and offset between 0 and 100000")
            location_value(contains)
            values = await client.location_suggestions(
                credential, field=field, country=location_value(country), state=location_value(state)
            )
            if contains is not None:
                values = [v for v in values if contains.casefold() in v.casefold()]
            limit = min(limit, settings.private_tool_max_items)
            selected = values[offset : offset + limit]
            more = offset + len(selected) < len(values)
            return {
                "field": field,
                "values": selected,
                "returned": len(selected),
                "hasMore": more,
                "nextOffset": offset + len(selected) if more else None,
                "source": "authenticated searchable asset metadata; null values omitted",
            }
        except ImmichError as exc:
            raise private_error(exc, "location suggestions (requires asset.read)", settings) from None

    @server.tool(annotations=READ_ONLY)
    async def search_location_assets(
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        media_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        """Search one page of capture-location metadata, without downloading any images.

        Use for 'taken in Hawaii' or any city/state/province/country, not visual descriptions.
        Supply at least one exact stored location value (discover via get_location_suggestions).
        Location fields combine with AND. Omit media_type to enumerate photos AND videos;
        use IMAGE and limit=2 for a two-photo sample. Capture dates are inclusive ISO bounds;
        date-only values mean midnight UTC. Default page size is 50, capped by server limits.
        To enumerate all matching accessible metadata, pass ONLY the returned continuation
        on subsequent calls. The account, filters, order and size are fixed; handles are single
        use, expire after a bounded interval, and are lost on process restart/worker change.
        Only complete=true establishes traversal completion; errors or stopReason mean partial.
        No authoritative total or transactional snapshot is promised. Missing/incorrect GPS or
        reverse-geocoding can exclude real trip items; zero matches does not disprove a trip.
        Metadata enumeration and photo selection are separate: fetch only a few matching
        get_asset_thumbnail candidates, reuse successes, display the requested two photos,
        and call them a sample. Native image retrieval and visible rendering are separate checks.
        """
        credential = await private_credential(provider, settings)
        user = connection.current_user()
        try:
            result = await locations.page(
                credential,
                identity=(user.identity_namespace, user.sub),
                city=city,
                state=state,
                country=country,
                media_type=media_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                continuation=continuation,
            )
        except ImmichError as exc:
            raise private_error(exc, "location search (requires asset.read)", settings) from None
        result["assets"] = [_compact_asset(asset) for asset in result["assets"]]
        return result

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
        asset_id: str,
        size: Literal["thumbnail", "preview", "fullsize"] = "preview",
        edited: bool | None = None,
    ) -> list[ImageContent]:
        """Return a broadly compatible image preview for viewing, vision analysis, and display.

        Use this tool whenever the model needs to inspect, describe, analyze, or show
        an Immich image. Prefer this over get_asset_image for normal visual use because
        the original asset may be HEIC or another format unsupported by some vision models.
        Fetch only one image for a one-photo request. Explicitly use size='thumbnail'
        for initial browsing/highlight candidates, and size='preview' only for more detail.
        The preview default is retained for existing callers. Reuse successful image results;
        follow server batch limits and do not automatically retry failures. Native image
        content is returned once; visible attachment rendering is the client's responsibility.
        """
        credential = await private_credential(provider, settings)
        try:
            image = await client.get_asset_thumbnail(credential, asset_id, size=size, edited=edited)
        except ImmichError as exc:
            raise private_error(exc, "asset viewing (requires asset.view)", settings) from exc
        return [_image_content(image.data, image.mime_type)]

    @server.tool(structured_output=False, annotations=READ_ONLY)
    async def get_asset_image(asset_id: str, edited: bool | None = None) -> list[ImageContent]:
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
        state: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a bounded list of visible assets; this list does not establish completeness.

        query uses semantic visual search ('tropical beach'), requiring Immich smart search.
        For 'taken in [place]' use search_location_assets and get_location_suggestions.
        For mixed intent ('beaches photographed in Hawaii'), resolve location metadata first,
        then use query='beaches' WITH state/country/city constraints if semantic search works.
        Never remove location constraints after a failure or call unrestricted visual matches
        verified location photos. Omit query for a bounded metadata sample. No images download.
        """
        if limit < 1:
            raise ValueError("limit must be positive")
        limit = min(limit, settings.private_tool_max_items)
        credential = await private_credential(provider, settings)
        try:
            assets = await client.search_assets(
                credential,
                query=query,
                city=city,
                state=state,
                country=country,
                person_id=person_id,
                start_date=start_date,
                end_date=end_date,
                media_type=media_type,
                favorite=favorite,
                limit=limit,
            )
        except ImmichError as exc:
            raise private_error(exc, "asset search (requires asset.read)", settings) from exc
        return [_compact_asset(asset) for asset in assets]

    @server.tool(annotations=READ_ONLY)
    async def find_asset_by_filename(
        original_file_name: str,
        album_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve visible Immich assets deterministically by original filename.

        Use this for requests containing exact filenames such as IMG_0818.heic.
        Optionally supply an album ID to restrict the lookup to that exact album.
        Matching is case-insensitive but requires the complete filename. This does not
        perform semantic image search. Multiple matches are returned as an explicit
        ambiguity; never select one arbitrarily.
        """
        if not original_file_name.strip():
            raise ValueError("original_file_name must not be empty")
        credential = await private_credential(provider, settings)
        try:
            assets, has_more_matches = await client.find_assets_by_filename(
                credential,
                original_file_name,
                album_id=album_id,
                limit=settings.private_tool_max_items,
            )
        except ImmichError as exc:
            raise private_error(exc, "filename lookup (requires asset.read)", settings) from exc
        ambiguous = len(assets) > 1 or has_more_matches
        return {
            "originalFileName": original_file_name.strip(),
            "albumId": album_id,
            "status": "ambiguous" if ambiguous else ("unique" if assets else "not_found"),
            "returned": len(assets),
            "hasMoreMatches": has_more_matches,
            "assets": [_compact_asset(asset) for asset in assets],
        }

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
    return ImageContent(type="image", data=base64.b64encode(data).decode("ascii"), mime_type=mime_type)
