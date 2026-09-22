"""Explicit discovery criteria and bounded temporal sampling over the shared search adapter."""

from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field

from app.immich.client import ImmichClient, ImmichError, ImmichValidationError, MalformedImmichResponse
from app.immich.location import LocationSearch, capture_date, location_value
from app.immich.models import PrivateImmichCredential
from app.mcp.tools.albums import _compact_asset

DETECTION_CAVEAT = (
    "People predicates describe Immich labels/detections, not everyone visibly present. "
    "Excluded names may be unrecognized or undetected; matching both people does not prove 'only us'. "
    "Visual similarity does not verify a person's or pet's identity. OCR text does not prove capture location."
)


class DiscoveryFilters(BaseModel):
    """All supplied fields are mandatory; visual preferences belong outside this object."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    album_id: str | None = Field(
        default=None,
        description="Resolved accessible private/shared-with-me album ID; combined with every other filter",
    )
    people_all: list[str] | None = Field(
        default=None, description="All these resolved Immich person IDs together"
    )
    people_any: list[str] | None = Field(
        default=None, description="At least one of these resolved person IDs"
    )
    people_none: list[str] | None = Field(
        default=None, description="None matched by available person metadata"
    )
    include_hidden_people: bool = False
    city: str | None = None
    state: str | None = None
    country: str | None = None
    start_date: str | None = Field(
        default=None, description="Inclusive ISO capture-time lower bound; a date means midnight UTC"
    )
    end_date: str | None = Field(
        default=None, description="Inclusive ISO capture-time upper bound; a date means midnight UTC"
    )
    media_type: Literal["IMAGE", "VIDEO", "AUDIO", "OTHER"] | None = None
    ocr: str | None = Field(
        default=None, description="Required OCR full-text match, not a visual concept or GPS evidence"
    )
    query: str | None = Field(
        default=None, description="Required semantic concept; requires healthy Immich smart search"
    )
    reference_asset_id: str | None = None
    reference_mode: Literal["similar", "near_time", "afternoon", "same_place"] | None = None
    time_zone: str | None = Field(
        default=None,
        description="IANA zone for afternoon (or verified reference EXIF timeZone); never inferred from account",
    )
    window_minutes: int = Field(default=60, description="near_time: minutes before and after capture, 1–1440")


def checked_id(value: str) -> str:
    try:
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError
        return str(parsed)
    except (ValueError, AttributeError):
        raise ImmichValidationError("Use a valid Immich UUIDv4 ID from an authorized result") from None


def text_value(value: str | None) -> str | None:
    if value is not None and (not value.strip() or len(value) > 512):
        raise ImmichValidationError("Text clues must contain 1–512 characters")
    return value


def zone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ImmichValidationError("Supply a valid IANA time_zone such as America/Chicago") from None


def capture_instant(asset: dict[str, Any]) -> datetime:
    value = asset.get("fileCreatedAt")
    try:
        if not isinstance(value, str):
            raise TypeError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (ValueError, TypeError):
        raise ImmichValidationError(
            "Reference capture time is missing or lacks a timezone; supply explicit capture-date bounds"
        ) from None


def compact_candidate(asset: dict[str, Any], *, include_hidden: bool = False) -> dict[str, Any]:
    result = _compact_asset(asset)
    people = asset.get("people")
    result["detectedPeople"] = (
        [
            {"id": p["id"], "name": p.get("name")}
            for p in people
            if isinstance(p, dict)
            and isinstance(p.get("id"), str)
            and (include_hidden or p.get("isHidden") is not True)
        ]
        if isinstance(people, list)
        else None
    )
    result["peopleEvidence"] = (
        "Returned Immich labels only; empty/null does not prove absence of people. "
        "Hidden labels omitted unless explicitly requested"
    )
    return result


class PhotoDiscovery:
    def __init__(self, client: ImmichClient, pages: LocationSearch):
        self.client, self.pages, self.settings = client, pages, client.settings

    async def prepare(
        self, credential: PrivateImmichCredential, criteria: DiscoveryFilters, visual_preference: str | None
    ) -> tuple[DiscoveryFilters, dict[str, Any]]:
        f = criteria.model_copy(deep=True)
        text_value(visual_preference)
        for name in ["city", "state", "country"]:
            location_value(getattr(f, name))
        for name in ["query", "ocr"]:
            text_value(getattr(f, name))
        if f.album_id is not None:
            f.album_id = checked_id(f.album_id)
        for name in ["people_all", "people_any", "people_none"]:
            values = getattr(f, name)
            if values is not None:
                if not values or len(values) > 12:
                    raise ImmichValidationError("People lists must contain 1–12 resolved IDs")
                setattr(f, name, list(dict.fromkeys(checked_id(v) for v in values)))
        all_ids, any_ids, none_ids = (
            set(f.people_all or []),
            set(f.people_any or []),
            set(f.people_none or []),
        )
        if len(all_ids | any_ids | none_ids) > 12:
            raise ImmichValidationError("At most 12 distinct people may be specified")
        if all_ids & none_ids or (any_ids and any_ids <= none_ids):
            raise ImmichValidationError("People predicates contradict each other")
        if bool(f.reference_asset_id) != bool(f.reference_mode):
            raise ImmichValidationError("Supply reference_asset_id and reference_mode together")
        if f.time_zone is not None and f.reference_mode != "afternoon":
            raise ImmichValidationError(
                "time_zone is used only with reference_mode=afternoon; use explicit offsets in other date bounds"
            )
        if not 1 <= f.window_minutes <= 1440 or (
            "window_minutes" in f.model_fields_set and f.reference_mode != "near_time"
        ):
            raise ImmichValidationError("window_minutes (1–1440) applies only to near_time")
        if f.reference_mode == "similar" and f.query is not None:
            raise ImmichValidationError(
                "Choose either reference similarity or a semantic query; neither is silently ignored"
            )
        f.start_date, f.end_date = capture_date(f.start_date), capture_date(f.end_date)
        reference = None
        if f.reference_asset_id:
            f.reference_asset_id = checked_id(f.reference_asset_id)
            reference = await self.client.get_asset_metadata(credential, f.reference_asset_id)
            if reference.get("id") != f.reference_asset_id:
                raise MalformedImmichResponse("Immich returned a different reference asset")
            if f.reference_mode == "same_place":
                exif = reference.get("exifInfo") or {}
                if not isinstance(exif, dict):
                    raise MalformedImmichResponse("Reference EXIF is malformed")
                known = {
                    key: exif[key]
                    for key in ["city", "state", "country"]
                    if isinstance(exif.get(key), str) and exif[key].strip()
                }
                if not known:
                    raise ImmichValidationError(
                        "Reference capture location is missing; no same-place search was performed"
                    )
                for key, value in known.items():
                    if getattr(f, key) is not None and getattr(f, key) != value:
                        raise ImmichValidationError(
                            "Explicit location conflicts with the reference; clarify the intended place"
                        )
                    setattr(f, key, location_value(value))
            if f.reference_mode in {"near_time", "afternoon"}:
                captured = capture_instant(reference)
                if f.reference_mode == "near_time":
                    lower, upper = (
                        captured - timedelta(minutes=f.window_minutes),
                        captured + timedelta(minutes=f.window_minutes),
                    )
                else:
                    exif = reference.get("exifInfo") or {}
                    tz = f.time_zone or (exif.get("timeZone") if isinstance(exif, dict) else None)
                    if not isinstance(tz, str):
                        raise ImmichValidationError(
                            "Afternoon needs an explicit IANA time_zone or a valid reference EXIF timeZone"
                        )
                    f.time_zone = tz
                    local = captured.astimezone(zone(tz))
                    lower = datetime.combine(local.date(), time(12), zone(tz))
                    # Upstream dates are millisecond precision and inclusive in both contracts.
                    upper = datetime.combine(local.date(), time(18), zone(tz)) - timedelta(milliseconds=1)
                if f.start_date:
                    lower = max(lower, datetime.fromisoformat(f.start_date))
                if f.end_date:
                    upper = min(upper, datetime.fromisoformat(f.end_date))
                f.start_date, f.end_date = lower.isoformat(), upper.isoformat()
        if (
            f.start_date
            and f.end_date
            and datetime.fromisoformat(f.start_date) > datetime.fromisoformat(f.end_date)
        ):
            raise ImmichValidationError("Capture-date intervals conflict or start after their end")
        context = {
            "effectiveFilters": f.model_dump(exclude_none=True),
            "visualPreference": visual_preference,
            "preferenceHandling": "Assistant judgment on bounded candidates; preference is not an upstream filter",
            "personIds": sorted(all_ids | any_ids | none_ids),
            "includeHiddenPeople": f.include_hidden_people,
            "referenceAssetId": f.reference_asset_id,
            "detectionCaveat": DETECTION_CAVEAT,
        }
        if f.album_id is not None:
            context["albumId"] = f.album_id
        if reference:
            context["reference"] = compact_candidate(reference, include_hidden=f.include_hidden_people)
            if f.reference_mode == "same_place":
                context["placePrecision"] = (
                    "Exact stored administrative fields, not a geographic radius or identical venue"
                )
        return f, context

    def body(self, f: DiscoveryFilters, size: int, *, album_id: str | None = None) -> dict[str, Any]:
        if album_id is not None and f.album_id is not None and album_id != f.album_id:
            raise ImmichValidationError("Album scopes conflict; no album constraint was dropped")
        effective_album_id = album_id or f.album_id
        filters = {
            k: v
            for k, v in {
                "city": f.city,
                "state": f.state,
                "country": f.country,
                "type": f.media_type,
                "takenAfter": f.start_date,
                "takenBefore": f.end_date,
                "ocr": f.ocr,
            }.items()
            if v is not None
        }
        people = {
            op: getattr(f, name)
            for op, name in [("all", "people_all"), ("any", "people_any"), ("none", "people_none")]
            if getattr(f, name)
        }
        return self.client.metadata_search_body(
            filters,
            size,
            self.settings.immich_search_api_mode,
            people=people,
            query=f.query,
            query_asset_id=f.reference_asset_id if f.reference_mode == "similar" else None,
            with_people=True,
            album_id=effective_album_id,
        )

    async def search(
        self,
        credential: PrivateImmichCredential,
        identity: tuple[str, str],
        *,
        filters: DiscoveryFilters | None = None,
        visual_preference: str | None = None,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        if continuation is not None:
            if filters is not None or visual_preference is not None or limit is not None:
                raise ImmichValidationError(
                    "Send only continuation; mandatory filters and preferences stay fixed"
                )
            result = await self.pages.page(
                credential, identity=identity, continuation=continuation, _kind="discovery"
            )
        else:
            if limit is not None and limit < 1:
                raise ImmichValidationError("limit must be positive")
            f, context = await self.prepare(credential, filters or DiscoveryFilters(), visual_preference)
            size = min(
                limit or 50, self.settings.private_tool_max_items, self.settings.location_search_max_items
            )
            body = self.body(f, size)
            await self.client.authorize_discovery_context(credential, context, reference_checked=True)
            if f.query is not None or f.reference_mode == "similar":
                items, _ = await self.client.discovery_search_page(
                    credential, body, self.settings.immich_search_api_mode, smart=True
                )
                unique = {}
                for item in items:
                    if not isinstance(item.get("id"), str) or not item["id"]:
                        raise MalformedImmichResponse("Immich returned an invalid asset ID")
                    if item["id"] != f.reference_asset_id:
                        unique.setdefault(item["id"], item)
                result = {
                    "assets": list(unique.values()),
                    "returned": len(unique),
                    "returnedSoFar": len(unique),
                    "complete": False,
                    "partial": True,
                    "continuation": None,
                    "stopReason": "ranked_sample",
                    "apiMode": self.settings.immich_search_api_mode,
                    "searchContext": context,
                    "coverage": "One bounded semantic ranking; never exhaustive, even with fewer than the limit",
                }
            else:
                result = await self.pages.page(
                    credential,
                    identity=identity,
                    _body=body,
                    _context=context,
                    _kind="discovery",
                    _context_checked=True,
                )
        result["assets"] = [
            compact_candidate(a, include_hidden=result["searchContext"]["includeHiddenPeople"])
            for a in result["assets"]
        ]
        return result

    async def sample(
        self,
        credential: PrivateImmichCredential,
        identity: tuple[str, str],
        *,
        filters: DiscoveryFilters,
        visual_preference: str | None,
        candidate_limit: int,
        selection_count: int,
        time_bins: int,
        time_zone: str,
        min_gap_minutes: int,
        album_id: str | None = None,
        authorization_failure_is_fatal: bool = False,
    ) -> dict[str, Any]:
        if not 1 <= selection_count <= candidate_limit <= min(48, self.settings.private_tool_max_items):
            raise ImmichValidationError(
                "Require 1 <= selection_count <= candidate_limit <= min(48, private page cap)"
            )
        if not 1 <= time_bins <= min(6, candidate_limit) or not 0 <= min_gap_minutes <= 1440:
            raise ImmichValidationError(
                "time_bins must be 1–6 and <= candidate_limit; min_gap_minutes must be 0–1440"
            )
        tz = zone(time_zone)
        f, context = await self.prepare(credential, filters, visual_preference)
        if album_id:
            context["albumId"] = checked_id(album_id)
        if f.query is not None or f.reference_mode == "similar":
            raise ImmichValidationError(
                "Temporal sampling supports metadata constraints; use visual_preference for optional visual ranking"
            )
        if f.media_type not in {None, "IMAGE"} or not f.start_date or not f.end_date:
            raise ImmichValidationError(
                "Photo sampling needs start_date/end_date and IMAGE (or omitted media_type)"
            )
        f.media_type = "IMAGE"
        context["effectiveFilters"] = f.model_dump(exclude_none=True)
        lower, upper = datetime.fromisoformat(f.start_date), datetime.fromisoformat(f.end_date)
        span = upper.astimezone(UTC) - lower.astimezone(UTC)
        if span < timedelta(milliseconds=time_bins):
            raise ImmichValidationError("Sampling interval is too short for the requested time bins")
        # Validate contract before requests, then authorize once for this bounded operation.
        self.body(f, 1, album_id=album_id)
        await self.client.authorize_discovery_context(credential, context, reference_checked=True)
        pool, intervals = {}, []
        failure = None
        for index in range(time_bins):
            start = lower.astimezone(UTC) + span * index / time_bins
            end = lower.astimezone(UTC) + span * (index + 1) / time_bins
            # Adjacent inclusive bins can overlap at a boundary. IDs are deduplicated, never called distinct events.
            branch = f.model_copy(update={"start_date": start.isoformat(), "end_date": end.isoformat()})
            size = candidate_limit // time_bins + (index < candidate_limit % time_bins)
            try:
                page = await self.pages.page(
                    credential,
                    identity=identity,
                    _body=self.body(branch, size, album_id=album_id),
                    _context=context,
                    _kind="discovery",
                    _context_checked=True,
                )
            except ImmichError as exc:
                if authorization_failure_is_fatal and getattr(exc, "diagnostic", {}).get("status") in {
                    401,
                    403,
                    404,
                }:
                    raise
                if not pool:
                    raise
                failure = f"{type(exc).__name__}: {exc}. Do not automatically retry this call."
                break
            self.pages.discard(page["continuation"])
            intervals.append(
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "returned": page["returned"],
                    "complete": page["complete"],
                }
            )
            for item in page["assets"]:
                if item["id"] not in pool:
                    candidate = compact_candidate(item, include_hidden=f.include_hidden_people)
                    candidate["candidateReason"] = (
                        f"Metadata match from time interval {index + 1} of {time_bins}; newest within that interval"
                    )
                    pool[item["id"]] = candidate
        # Dates/spacing are explainable diversity preferences, never a visual quality score.
        dated = []
        for item in pool.values():
            try:
                dated.append((capture_instant(item).astimezone(tz), item))
            except ImmichValidationError:
                pass
        dated.sort(key=lambda pair: (pair[0].astimezone(UTC), pair[1]["id"]))
        chosen, days = [], set()
        for distinct_days in [True, False]:
            for moment, item in dated:
                if len(chosen) >= selection_count:
                    break
                if any(item["id"] == other["id"] for _, other in chosen):
                    continue
                if distinct_days and moment.date() in days:
                    continue
                if any(
                    abs(moment.astimezone(UTC) - prior.astimezone(UTC)) < timedelta(minutes=min_gap_minutes)
                    for prior, _ in chosen
                ):
                    continue
                chosen.append((moment, item))
                days.add(moment.date())
        return {
            "candidates": list(pool.values()),
            "candidateCount": len(pool),
            "requestedSelectionCount": selection_count,
            "suggestedSelection": [
                {
                    "assetId": a["id"],
                    "reason": "Capture-day variety then temporal spacing within this candidate pool",
                    "uncertainty": "Not visually assessed; review expressions, relevance and technical quality with bounded thumbnails",
                }
                for _, a in chosen
            ],
            "searchContext": context,
            "intervals": intervals,
            "timeZone": time_zone,
            "minimumSpacingMinutes": min_gap_minutes,
            "samplingFinished": failure is None,
            "complete": False,
            "partial": True,
            "error": failure,
            "coverage": "Bounded stratified time sample; newest within each interval, not global best or exhaustive duplicate detection",
            "display": "No images downloaded. Inspect a small subset with existing image tools; reuse successes and verify visible attachments separately",
        }
