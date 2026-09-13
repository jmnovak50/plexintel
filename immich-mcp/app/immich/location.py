"""Bounded metadata enumeration. Handles are private, short lived and process local."""

import hashlib
import json
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from typing import Any

from app.immich.client import ImmichClient, ImmichError, ImmichValidationError, MalformedImmichResponse
from app.immich.models import PrivateImmichCredential


@dataclass
class Traversal:
    owner: bytes
    mode: str
    body: dict[str, Any]
    expires: float
    seen_ids: set[str] = field(default_factory=set)
    seen_continuations: set[str] = field(default_factory=set)
    pages: int = 0


def location_value(value: str | None) -> str | None:
    if value is not None and (not value.strip() or len(value) > 256):
        raise ImmichValidationError("Location values must contain 1–256 characters")
    return value


def capture_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if len(value) == 10:
            value += "T00:00:00Z"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.isoformat()
    except (ValueError, OverflowError):
        raise ImmichValidationError("Capture dates must be ISO dates or datetimes with a timezone") from None


class LocationSearch:
    def __init__(self, client: ImmichClient):
        self.client = client
        self.settings = client.settings
        self._sessions: OrderedDict[str, Traversal] = OrderedDict()

    async def page(
        self,
        credential: PrivateImmichCredential,
        *,
        identity: tuple[str, str],
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        media_type: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int | None = None,
        continuation: str | None = None,
    ) -> dict[str, Any]:
        owner = hashlib.sha256(json.dumps([*identity, credential.kind, credential.token]).encode()).digest()
        now = monotonic()
        self._sessions = OrderedDict((k, v) for k, v in self._sessions.items() if v.expires > now)
        if continuation is not None:
            if any(v is not None for v in [city, state, country, media_type, start_date, end_date, limit]):
                raise ImmichValidationError(
                    "Send only continuation; its original filters, ordering and size are fixed"
                )
            session = self._sessions.get(continuation)
            if session is None or not secrets.compare_digest(session.owner, owner):
                raise ImmichValidationError(
                    "Continuation is invalid, expired, consumed or unavailable for this account; enumeration is incomplete"
                )
            # Consume before awaiting: concurrent/replayed calls cannot advance the same traversal twice.
            del self._sessions[continuation]
        else:
            filters = {
                k: v
                for k, v in {
                    "city": location_value(city),
                    "state": location_value(state),
                    "country": location_value(country),
                }.items()
                if v is not None
            }
            if not filters:
                raise ImmichValidationError(
                    "Supply at least one capture-location field: city, state, or country"
                )
            if limit is not None and (type(limit) is not int or limit < 1):
                raise ImmichValidationError("limit must be positive")
            size = min(
                limit or 50, self.settings.private_tool_max_items, self.settings.location_search_max_items
            )
            if media_type is not None:
                if media_type.upper() not in {"IMAGE", "VIDEO", "AUDIO", "OTHER"}:
                    raise ImmichValidationError("media_type must be IMAGE, VIDEO, AUDIO, or OTHER")
                filters["type"] = media_type.upper()
            start, end = capture_date(start_date), capture_date(end_date)
            if start and end and datetime.fromisoformat(start) > datetime.fromisoformat(end):
                raise ImmichValidationError("start_date must be on or before end_date")
            mode = self.settings.immich_search_api_mode
            body: dict[str, Any] = {"size": size, "withExif": True}
            if mode == "structured":
                structured = {k: {"eq": v} for k, v in filters.items()}
                if start or end:
                    structured["takenAt"] = {}
                    if start:
                        structured["takenAt"]["gte"] = start
                    if end:
                        structured["takenAt"]["lte"] = end
                body.update(filter=structured, orderBy={"field": "fileCreatedAt", "direction": "desc"})
            else:
                body.update(filters, order="desc", page=1)
                if start:
                    body["takenAfter"] = start
                if end:
                    body["takenBefore"] = end
            session = Traversal(owner, mode, body, now + self.settings.location_search_ttl_seconds)
            if mode == "legacy":
                session.seen_continuations.add("1")
        try:
            items, next_value = await self.client.location_search_page(credential, session.body, session.mode)
            if next_value is not None:
                if not items or next_value in session.seen_continuations:
                    raise MalformedImmichResponse(
                        "Immich search returned an empty or repeated continuation page"
                    )
                if session.mode == "legacy" and int(next_value) <= session.body["page"]:
                    raise MalformedImmichResponse("Immich search page did not advance")
            if any(not isinstance(v.get("id"), str) or not v["id"] or len(v["id"]) > 256 for v in items):
                raise MalformedImmichResponse("Immich search returned an invalid asset ID")
        except ImmichError as exc:
            # An error remains an MCP error, never an empty successful page or a complete traversal.
            exc.args = (
                f"{exc}. Enumeration incomplete; previously returned {len(session.seen_ids)} unique assets",
            )
            raise
        session.pages += 1
        unique = []
        truncated = False
        for item in items:
            if item["id"] in session.seen_ids:
                continue
            if len(session.seen_ids) >= self.settings.location_search_max_items:
                truncated = True
                break
            session.seen_ids.add(item["id"])
            unique.append(item)
        stop = None
        if truncated or (
            next_value is not None and len(session.seen_ids) >= self.settings.location_search_max_items
        ):
            stop = "item_limit"
        elif next_value is not None and session.pages >= self.settings.location_search_max_pages:
            stop = "page_limit"
        elif next_value is not None and session.expires <= monotonic():
            stop = "expired"
        token = None
        if next_value is not None and stop is None:
            session.seen_continuations.add(next_value)
            session.body["cursor" if session.mode == "structured" else "page"] = (
                next_value if session.mode == "structured" else int(next_value)
            )
            while len(self._sessions) >= self.settings.location_search_session_limit:
                self._sessions.popitem(last=False)
            token = secrets.token_urlsafe(32)
            self._sessions[token] = session
        complete = next_value is None and not truncated
        return {
            "assets": unique,
            "returned": len(unique),
            "returnedSoFar": len(session.seen_ids),
            "pagesRetrieved": session.pages,
            "pageSize": session.body["size"],
            "apiMode": session.mode,
            "continuation": token,
            "complete": complete,
            "partial": not complete,
            "hasMore": next_value is not None or truncated,
            "stopReason": stop,
            "completenessScope": "matching accessible capture-location metadata; not a transactional snapshot",
            "metadataCaveat": "Missing or incorrect GPS/reverse-geocoded metadata can exclude real trip photos and videos",
        }
