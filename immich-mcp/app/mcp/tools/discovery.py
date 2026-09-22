"""Account-scoped people discovery and composed, bounded asset searches."""

import base64
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ImageContent

from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError, ImmichForbidden, ImmichValidationError
from app.immich.discovery import DiscoveryFilters, PhotoDiscovery, checked_id, text_value
from app.immich.location import LocationSearch
from app.mcp.tools import connection
from app.mcp.tools.connection import READ_ONLY, private_credential, private_error
from app.mcp.tools.events import register_event_tools


def compact_person(person: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": person["id"],
        "name": person["name"],
        "isHidden": person["isHidden"],
        "hasThumbnail": bool(person.get("thumbnailPath")),
    }


def register_discovery_tools(
    server: MCPServer,
    client: ImmichClient,
    provider: SQLiteCredentialProvider,
    settings: Settings,
    pages: LocationSearch,
) -> None:
    discovery = PhotoDiscovery(client, pages)
    register_event_tools(server, discovery, provider, settings)

    @server.tool(annotations=READ_ONLY)
    async def find_people(
        name: str,
        match: Literal["fuzzy", "exact"] = "fuzzy",
        include_hidden: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Resolve names to this account's Immich person records (requires person.read).

        Fuzzy name search supports partial/case/accent variants as upstream candidates, not
        guaranteed substring matching. Exact mode applies Unicode casefold equality locally.
        Never silently choose duplicate/similar names; use IDs and optional person thumbnails
        to ask for disambiguation. 'Me', family roles, account IDs/emails and pet names are not
        person mappings. Empty names use list_people(unnamed_only=true). Hidden people are
        excluded unless explicitly requested. Upstream caps fuzzy results at 100 without
        pagination; cap-hit means incomplete even after exact filtering. nextOffset pages only
        this bounded candidate set; repeat identical arguments. No names or identities cached.
        """
        credential = await private_credential(provider, settings)
        try:
            text_value(name)
            if limit < 1 or not 0 <= offset <= 100:
                raise ImmichValidationError("limit must be positive and offset between 0 and 100")
            raw = await client.find_people(credential, name, include_hidden=include_hidden)
            capped = len(raw) >= 100
            unique = {p["id"]: p for p in raw[:100] if include_hidden or not p["isHidden"]}
            people = [
                p for p in unique.values() if match != "exact" or p["name"].casefold() == name.casefold()
            ]
            selected = people[offset : offset + min(limit, settings.private_tool_max_items)]
            more = offset + len(selected) < len(people)
            return {
                "people": [compact_person(p) for p in selected],
                "returned": len(selected),
                "resolution": "incomplete"
                if capped
                else "ambiguous"
                if len(people) > 1
                else "candidate"
                if people
                else "not_found",
                "candidateCount": len(people),
                "match": match,
                "hasMore": more,
                "nextOffset": offset + len(selected) if more else None,
                "upstreamTruncated": capped,
                "complete": not capped and not more and offset == 0,
                "coverage": "Account-scoped fuzzy name candidates, at most 100; not an exhaustive identity directory",
                "identityCaveat": "A unique name candidate is not proof of a family role or pet identity; confirm ambiguous mappings",
            }
        except ImmichError as exc:
            raise private_error(
                exc, "people discovery (requires person.read, separately from asset.read)", settings
            ) from None

    @server.tool(annotations=READ_ONLY)
    async def list_people(
        page: int = 1, limit: int = 50, include_hidden: bool = False, unnamed_only: bool = False
    ) -> dict[str, Any]:
        """Browse one bounded page of this account's people, including unnamed records.

        Requires person.read. Hidden people are excluded by default. Follow nextPage with the
        same limit/include_hidden/unnamed_only; unnamed_only filters each upstream page locally,
        so an empty filtered page can have a nextPage. Stop on errors or safety limits and report
        incomplete enumeration. No snapshot, exact total, pet recognition or cross-user aliases.
        """
        credential = await private_credential(provider, settings)
        try:
            if not 1 <= page <= settings.location_search_max_pages or limit < 1:
                raise ImmichValidationError(
                    "People page exceeds the configured traversal bound or limit is not positive"
                )
            raw, more = await client.list_people_page(
                credential,
                page=page,
                size=min(limit, settings.private_tool_max_items),
                include_hidden=include_hidden,
            )
            people = {
                p["id"]: p
                for p in raw
                if (include_hidden or not p["isHidden"]) and (not unnamed_only or not p["name"].strip())
            }
            truncated = more and page >= settings.location_search_max_pages
            return {
                "people": [compact_person(p) for p in people.values()],
                "returned": len(people),
                "page": page,
                "hasMore": more,
                "nextPage": page + 1 if more and not truncated else None,
                "truncated": truncated,
                "stopReason": "page_limit" if truncated else None,
                "enumerationEnd": not more,
                "coverage": "One account-scoped page; enumerate all preceding pages before claiming completion",
            }
        except ImmichError as exc:
            raise private_error(
                exc, "people listing (requires person.read, separately from asset.read)", settings
            ) from None

    @server.tool(structured_output=False, annotations=READ_ONLY)
    async def get_person_thumbnail(person_id: str, include_hidden: bool = False) -> list[ImageContent]:
        """Read a small authorized person thumbnail to disambiguate Immich labels (person.read).

        Use a returned person ID, never an account ID. Hidden records require explicit opt-in.
        Existing image concurrency/byte/deadline limits apply. Native image retrieval does not
        establish visible client rendering; use supported attachments and never base64 in text.
        """
        credential = await private_credential(provider, settings)
        try:
            person_id = checked_id(person_id)
            person = await client.get_person(credential, person_id)
            if person["isHidden"] and not include_hidden:
                raise ImmichForbidden("This person is hidden; explicit include_hidden is required")
            image = await client.get_person_thumbnail(credential, person_id)
            return [
                ImageContent(
                    type="image", data=base64.b64encode(image.data).decode("ascii"), mime_type=image.mime_type
                )
            ]
        except ImmichError as exc:
            raise private_error(exc, "person thumbnail reading (requires person.read)", settings) from None

    @server.tool(annotations=READ_ONLY)
    async def search_library(
        filters: DiscoveryFilters | None = None,
        visual_preference: str | None = None,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        """Search accessible metadata with mandatory album/people/location/date/type/OCR filters.

        Use this composed path whenever a request combines an album or named person with location,
        dates, media type, OCR, or other criteria (for example Lucy in New Orleans within an album).
        Resolve album titles with list_albums/get_album and person names with find_people first.
        album_id is an authorized private/shared-with-me album UUID, never a public share key.
        people_all means together, people_any means either, and people_none excludes only available
        labels, never proves 'only us'. All supplied filters combine with AND. Multi-any/none require
        validated structured v3.2 API mode;
        unsupported combinations fail without dropping filters. People predicates require person.read
        as well as asset.read. OCR is sign/text evidence, not visual content or capture location.
        Optional visual_preference (e.g. sunsets) leaves metadata constraints intact for assistant
        ranking. Required query uses smart search: one bounded ranking, never exhaustive; failure
        stops with no unrestricted fallback. Lucy/dog similarity is a candidate, not verified identity.
        Metadata pages reuse search_location_assets continuation rules: send ONLY continuation;
        filters/preferences/account are fixed, IDs deduplicated, errors mean incomplete enumeration.
        Reference follow-ups require an explicit authorized reference_asset_id and reference_mode:
        similar (smart), near_time (default +/-60 capture minutes), afternoon (12–18 local, needs IANA
        time_zone or verified EXIF zone), same_place (exact available city/state/country, not radius).
        Reuse the actual ID for 'second one', never a global last-result. No images are downloaded.
        Bound thumbnail inspection, reuse successful reads, and verify visible attachments separately.
        """
        credential = await private_credential(provider, settings)
        user = connection.current_user()
        try:
            return await discovery.search(
                credential,
                (user.identity_namespace, user.sub),
                filters=filters,
                visual_preference=visual_preference,
                limit=limit,
                continuation=continuation,
            )
        except ImmichError as exc:
            raise private_error(
                exc,
                "library search (asset.read; album scope also requires album.read; person predicates also require person.read)",
                settings,
            ) from None

    @server.tool(annotations=READ_ONLY)
    async def sample_photo_candidates(
        filters: DiscoveryFilters,
        visual_preference: str | None = None,
        candidate_limit: int = 12,
        selection_count: int = 5,
        time_bins: int = 4,
        time_zone: str = "UTC",
        min_gap_minutes: int = 5,
    ) -> dict[str, Any]:
        """Collect a bounded, varied metadata candidate pool; download no images.

        Requires capture-date start/end (or a temporal reference), with all mandatory album/people/place/OCR
        constraints preserved. Split the interval into at most 6 bins, fetch newest matches per bin,
        at most 48 metadata candidates overall. This is a disclosed stratified sample, not the whole
        trip or global best. Use visual_preference for sunsets, expressions, scenes; required semantic
        query/similarity is unsupported here. Suggested IDs favor different days in explicit time_zone
        (default UTC), then spacing; min_gap_minutes is a selection constraint, not duplicate detection.
        Return fewer if needed, never unmatched filler. Inspect only a small subset with thumbnail tools;
        assistant judgments about expressions, focus, exposure and meaning need visual evidence, not
        invented scores. Preserve successful candidates/images on partial failure; stop on errors.
        People labels cannot prove 'only us' or pet identity. Visible rendering is a separate client check.
        """
        credential = await private_credential(provider, settings)
        user = connection.current_user()
        try:
            return await discovery.sample(
                credential,
                (user.identity_namespace, user.sub),
                filters=filters,
                visual_preference=visual_preference,
                candidate_limit=candidate_limit,
                selection_count=selection_count,
                time_bins=time_bins,
                time_zone=time_zone,
                min_gap_minutes=min_gap_minutes,
            )
        except ImmichError as exc:
            raise private_error(
                exc, "photo sampling (asset.read; person predicates also require person.read)", settings
            ) from None

    # MCP 2.1.1 otherwise includes rejected input values in deliberate validation errors.
    # Configure only these additive tools' argument models, never global SDK state. Keep
    # field/type guidance and isError semantics; raw HTTP tests guard this SDK boundary.
    for name in [
        "find_people",
        "list_people",
        "get_person_thumbnail",
        "search_library",
        "sample_photo_candidates",
    ]:
        tool = server._tool_manager.get_tool(name)
        tool.fn_metadata.arg_model.model_config.update(hide_input_in_errors=True, extra="forbid")
        tool.fn_metadata.arg_model.model_rebuild(force=True)
        tool.parameters = tool.fn_metadata.arg_model.model_json_schema()
