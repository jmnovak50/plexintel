import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from app.config import Settings
from app.immich.models import ImagePayload, SharedLink, TimelineBucket

log = structlog.get_logger(__name__)


class ImmichError(Exception):
    """A sanitized error safe to return across the tool boundary."""


class InvalidShareLink(ImmichError):
    pass


class ExpiredShareLink(ImmichError):
    pass


class ImmichForbidden(ImmichError):
    pass


class ImmichNotFound(ImmichError):
    pass


class ImmichRateLimited(ImmichError):
    pass


class ImmichUnavailable(ImmichError):
    pass


class ImmichTimeout(ImmichError):
    pass


class MalformedImmichResponse(ImmichError):
    pass


class PayloadTooLarge(ImmichError):
    pass


class ImmichClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        timeout = httpx.Timeout(
            settings.http_timeout_seconds,
            connect=settings.http_connect_timeout_seconds,
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=str(settings.immich_base_url).rstrip("/") + "/api/",
            timeout=timeout,
            verify=settings.tls_verify,
            follow_redirects=False,
            headers={"User-Agent": "immich-mcp/0.1"},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(
        self,
        path: str,
        *,
        share_key: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        headers = {"x-immich-share-key": share_key} if share_key else None
        for attempt in range(self.settings.http_max_retries + 1):
            try:
                response = await self._client.get(path, headers=headers, params=params)
            except httpx.TimeoutException as exc:
                if attempt < self.settings.http_max_retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichTimeout("Immich request timed out") from exc
            except httpx.RequestError as exc:
                if attempt < self.settings.http_max_retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichUnavailable("Immich could not be reached") from exc

            if response.status_code in {429, 500, 502, 503, 504} and attempt < self.settings.http_max_retries:
                await asyncio.sleep(0.05 * (2**attempt))
                continue
            self._raise_for_status(response)
            return response
        raise ImmichUnavailable("Immich request failed")  # pragma: no cover

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == 401:
            raise InvalidShareLink("Invalid or expired Immich share credential")
        if status == 403:
            raise ImmichForbidden("Immich denied this shared-link operation")
        if status == 404:
            raise ImmichNotFound("Immich resource was not found")
        if status == 429:
            raise ImmichRateLimited("Immich rate limit exceeded")
        if status >= 500:
            raise ImmichUnavailable("Immich upstream service failed")
        raise ImmichError(f"Immich request failed with status {status}")

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise MalformedImmichResponse("Immich returned invalid JSON") from exc

    async def get_shared_link(self, share_key: str) -> SharedLink:
        response = await self._get("shared-links/me", share_key=share_key)
        try:
            link = SharedLink.model_validate(self._json(response))
        except Exception as exc:
            raise MalformedImmichResponse("Immich returned malformed shared-link metadata") from exc
        if link.is_expired():
            raise ExpiredShareLink("Immich share link has expired")
        return link

    async def ping(self) -> bool:
        response = await self._get("server/ping")
        return response.status_code == 200

    async def get_timeline_buckets(self, share_key: str, album_id: str) -> list[TimelineBucket]:
        raw_items = await self._get_paginated_list(
            "timeline/buckets", share_key, {"albumId": album_id, "order": "asc"}
        )
        try:
            return [TimelineBucket.model_validate(item) for item in raw_items]
        except Exception as exc:
            raise MalformedImmichResponse("Immich returned malformed timeline buckets") from exc

    async def get_timeline_bucket(
        self, share_key: str, album_id: str, time_bucket: str
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"albumId": album_id, "order": "asc", "timeBucket": time_bucket}
        all_assets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _ in range(100):
            response = await self._get("timeline/bucket", share_key=share_key, params=params)
            payload = self._json(response)
            vector, next_value = self._unwrap_vector(payload)
            all_assets.extend(normalize_parallel_assets(vector))
            if not next_value or next_value in seen:
                return all_assets
            seen.add(next_value)
            params["cursor" if not str(next_value).isdigit() else "page"] = next_value
        raise MalformedImmichResponse("Immich pagination exceeded safety limit")

    async def list_shared_album_assets(self, share_key: str, album_id: str) -> list[dict[str, Any]]:
        buckets = await self.get_timeline_buckets(share_key, album_id)
        assets: list[dict[str, Any]] = []
        for bucket in buckets:
            assets.extend(await self.get_timeline_bucket(share_key, album_id, bucket.time_bucket))
        return assets

    async def get_shared_asset_metadata(self, share_key: str, asset_id: str) -> dict[str, Any]:
        response = await self._get(f"assets/{quote(asset_id, safe='')}", share_key=share_key)
        payload = self._json(response)
        if not isinstance(payload, dict):
            raise MalformedImmichResponse("Immich returned malformed asset metadata")
        return payload

    async def get_shared_asset_thumbnail(
        self,
        share_key: str,
        asset_id: str,
        *,
        size: str | None = None,
        edited: bool | None = None,
    ) -> ImagePayload:
        params: dict[str, Any] = {"key": share_key}
        if size:
            params["size"] = size
        if edited is not None:
            params["edited"] = str(edited).lower()
        response = await self._get(f"assets/{quote(asset_id, safe='')}/thumbnail", params=params)
        mime = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
        if not mime.startswith("image/"):
            raise MalformedImmichResponse("Immich thumbnail did not return an image")
        if len(response.content) > self.settings.max_image_bytes:
            raise PayloadTooLarge("Immich image exceeds the configured response limit")
        return ImagePayload(data=response.content, mime_type=mime)

    async def _get_paginated_list(
        self, path: str, share_key: str, base_params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        params = dict(base_params)
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _ in range(100):
            response = await self._get(path, share_key=share_key, params=params)
            payload = self._json(response)
            if isinstance(payload, list):
                if not all(isinstance(item, dict) for item in payload):
                    raise MalformedImmichResponse("Immich list contains invalid entries")
                output.extend(payload)
                return output
            if not isinstance(payload, dict):
                raise MalformedImmichResponse("Immich returned a malformed paginated list")
            items = payload.get("items", payload.get("results", payload.get("buckets", [])))
            if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
                raise MalformedImmichResponse("Immich returned malformed page items")
            output.extend(items)
            next_value = payload.get("nextCursor", payload.get("nextPage"))
            if next_value in (None, "", False) or str(next_value) in seen:
                return output
            seen.add(str(next_value))
            params["cursor" if payload.get("nextCursor") is not None else "page"] = next_value
        raise MalformedImmichResponse("Immich pagination exceeded safety limit")

    @staticmethod
    def _unwrap_vector(payload: Any) -> tuple[dict[str, Any], str | None]:
        if not isinstance(payload, dict):
            raise MalformedImmichResponse("Immich returned malformed timeline data")
        if isinstance(payload.get("assets"), dict):
            vector = payload["assets"]
        elif isinstance(payload.get("items"), dict):
            vector = payload["items"]
        else:
            vector = payload
        next_value = payload.get("nextCursor", payload.get("nextPage"))
        return vector, None if next_value in (None, "", False) else str(next_value)


def normalize_parallel_assets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    ids = payload.get("id")
    if ids is None:
        if not payload or all(key in {"nextCursor", "nextPage"} for key in payload):
            return []
        raise MalformedImmichResponse("Timeline response is missing id array")
    if not isinstance(ids, list):
        raise MalformedImmichResponse("Timeline id field is not an array")
    length = len(ids)
    vector_fields: dict[str, list[Any]] = {}
    for key, value in payload.items():
        if key in {"nextCursor", "nextPage"}:
            continue
        if not isinstance(value, list):
            continue
        if len(value) != length:
            raise MalformedImmichResponse(f"Timeline field {key!r} has inconsistent array length")
        vector_fields[key] = value
    return [{key: values[index] for key, values in vector_fields.items()} for index in range(length)]
