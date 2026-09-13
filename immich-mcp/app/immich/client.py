import asyncio
import hashlib
from collections.abc import Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from time import monotonic
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx
import structlog

from app.config import Settings
from app.immich.models import (
    ImagePayload,
    ImmichCredential,
    PrivateImmichCredential,
    ShareCredential,
    SharedLink,
    TimelineBucket,
)

log = structlog.get_logger(__name__)


class ImmichError(Exception):
    """A sanitized error safe to return across the tool boundary."""

    def with_diagnostic(self, diagnostic: dict[str, Any]) -> "ImmichError":
        self.diagnostic = dict(diagnostic)
        self.args = (f"{self.args[0]} [{', '.join(f'{k}={v}' for k, v in diagnostic.items())}]",)
        return self


class ImmichValidationError(ImmichError):
    pass


class ImmichBadRequest(ImmichError):
    pass


class ImmichNetworkError(ImmichError):
    pass


class InvalidShareLink(ImmichError):
    pass


class ImmichUnauthorized(ImmichError):
    pass


class InvalidImmichCredential(ImmichUnauthorized):
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


class ImmichImageBusy(ImmichError):
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
        self._image_slots = asyncio.Semaphore(settings.image_max_concurrency)
        # Only active/waiting credentials are retained, as digests, never image data.
        self._credential_image_slots: dict[bytes, tuple[asyncio.Semaphore, int]] = {}
        self._client = client or httpx.AsyncClient(
            base_url=str(settings.immich_base_url).rstrip("/") + "/api/",
            timeout=timeout,
            verify=settings.tls_verify,
            follow_redirects=False,
            headers={"User-Agent": "immich-mcp/0.2"},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(
        self,
        path: str,
        *,
        share_key: str | None = None,
        credential: ImmichCredential | None = None,
        send_credential: bool = True,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        if share_key and credential:
            raise ValueError("only one Immich credential may be supplied")
        auth = credential or (ShareCredential(token=share_key) if share_key else None)
        return await self._request(
            "GET", path, credential=auth, send_credential=send_credential, params=params
        )

    async def _post(
        self,
        path: str,
        *,
        credential: ImmichCredential,
        json_body: Mapping[str, Any],
    ) -> httpx.Response:
        return await self._request("POST", path, credential=credential, json_body=json_body)

    async def _get_image(
        self,
        path: str,
        *,
        credential: ImmichCredential,
        send_credential: bool = True,
        params: Mapping[str, Any] | None = None,
    ) -> ImagePayload:
        """Bound image work separately from metadata and emit body-free diagnostics."""
        started = monotonic()
        diagnostic: dict[str, Any] = {
            "operation": self._operation(path),
            "correlation_id": uuid4().hex,
            "tool": (
                "get_shared_asset_image"
                if credential.kind == "share"
                else "get_asset_image"
                if path.endswith("/original")
                else "get_asset_thumbnail"
            ),
            "size": (params or {}).get("size", "original" if path.endswith("/original") else "default"),
            "status": None,
            "attempts": 0,
            "bytes": 0,
            "error_category": None,
        }
        try:
            async with self._image_admission(credential):
                try:
                    async with asyncio.timeout(self.settings.image_total_timeout_seconds):
                        return await self._download_image(
                            path,
                            credential=credential,
                            send_credential=send_credential,
                            params=params,
                            diagnostic=diagnostic,
                        )
                except TimeoutError as exc:
                    raise ImmichTimeout("Immich image exceeded the total retrieval deadline") from exc
        except asyncio.CancelledError:
            diagnostic["error_category"] = "cancelled"
            raise
        except Exception as exc:
            diagnostic["error_category"] = (
                type(exc).__name__ if isinstance(exc, ImmichError) else "unexpected"
            )
            if isinstance(exc, ImmichError):
                raise exc.with_diagnostic(
                    {
                        "operation": diagnostic["operation"],
                        "correlation_id": diagnostic["correlation_id"],
                        "status": diagnostic["status"],
                        "attempts": diagnostic["attempts"],
                        "duration_ms": round((monotonic() - started) * 1000),
                        "error_category": type(exc).__name__,
                    }
                ) from None
            raise
        finally:
            log.info(
                "immich_image_retrieval", **diagnostic, duration_ms=round((monotonic() - started) * 1000)
            )

    @asynccontextmanager
    async def _image_admission(self, credential: ImmichCredential):
        key = hashlib.sha256(f"{credential.kind}:{credential.token}".encode()).digest()
        semaphore, users = self._credential_image_slots.get(
            key, (asyncio.Semaphore(self.settings.image_per_credential_concurrency), 0)
        )
        self._credential_image_slots[key] = (semaphore, users + 1)
        try:
            async with AsyncExitStack() as stack:
                try:
                    async with asyncio.timeout(self.settings.image_queue_timeout_seconds):
                        # Acquire the per-credential slot first so one account's waiters
                        # cannot reserve every global slot and block unrelated accounts.
                        await stack.enter_async_context(semaphore)
                        await stack.enter_async_context(self._image_slots)
                except TimeoutError as exc:
                    raise ImmichImageBusy(
                        "Image capacity is busy; finish the current batch before continuing"
                    ) from exc
                yield
        finally:
            _, users = self._credential_image_slots[key]
            if users == 1:
                del self._credential_image_slots[key]
            else:
                self._credential_image_slots[key] = (semaphore, users - 1)

    async def _download_image(
        self,
        path: str,
        *,
        credential: ImmichCredential,
        send_credential: bool,
        params: Mapping[str, Any] | None,
        diagnostic: dict[str, Any],
    ) -> ImagePayload:
        """Reject oversized streams; keep the existing retry budget inside admission."""
        headers = self._credential_headers(credential) if send_credential else None
        retries = self.settings.http_max_retries
        for attempt in range(retries + 1):
            diagnostic.update(attempts=attempt + 1, status=None, bytes=0)
            try:
                async with self._client.stream(
                    "GET", path, headers=headers, params=params, follow_redirects=False
                ) as response:
                    diagnostic["status"] = response.status_code
                    if 300 <= response.status_code < 400:
                        raise ImmichError("Immich image redirect was not followed; use thumbnail or preview")
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                        await asyncio.sleep(0.05 * (2**attempt))
                        continue
                    self._raise_for_status(response, credential)
                    mime = response.headers.get("content-type", "").split(";", 1)[0].strip()
                    if not mime.startswith("image/"):
                        raise MalformedImmichResponse("Immich asset did not return an image")
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_length = int(content_length)
                        except ValueError:
                            declared_length = -1
                        if declared_length > self.settings.max_image_bytes:
                            raise PayloadTooLarge("Immich image exceeds the configured response limit")
                    chunks: list[bytes] = []
                    received = 0
                    async for chunk in response.aiter_bytes():
                        received += len(chunk)
                        diagnostic["bytes"] = received
                        if received > self.settings.max_image_bytes:
                            raise PayloadTooLarge("Immich image exceeds the configured response limit")
                        chunks.append(chunk)
                    return ImagePayload(data=b"".join(chunks), mime_type=mime)
            except httpx.TimeoutException as exc:
                if attempt < retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichTimeout("Immich request timed out") from exc
            except httpx.RequestError:
                if attempt < retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichNetworkError("Immich could not be reached") from None
        raise ImmichUnavailable("Immich request failed")  # pragma: no cover

    async def _request(
        self,
        method: str,
        path: str,
        *,
        credential: ImmichCredential | None = None,
        send_credential: bool = True,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        diagnostic = {
            "operation": self._operation(path),
            "correlation_id": uuid4().hex,
            "api_mode": ("structured" if "filter" in (json_body or {}) else "legacy")
            if path in {"search/metadata", "search/smart"}
            else "n/a",
            "configured_api_mode": self.settings.immich_search_api_mode,
            "status": None,
            "attempts": 0,
        }
        started = monotonic()
        try:
            response = await self._request_attempts(
                method,
                path,
                credential=credential,
                send_credential=send_credential,
                params=params,
                json_body=json_body,
                diagnostic=diagnostic,
            )
            diagnostic["duration_ms"] = round((monotonic() - started) * 1000)
            response.extensions["immich_diagnostic"] = dict(diagnostic)
            return response
        except ImmichError as exc:
            diagnostic["duration_ms"] = round((monotonic() - started) * 1000)
            diagnostic["error_category"] = type(exc).__name__
            raise exc.with_diagnostic(diagnostic) from None
        finally:
            log.info("immich_request", **diagnostic)

    @staticmethod
    def _operation(path: str) -> str:
        # Never log IDs, paths containing filenames, queries, or caller-supplied URLs.
        if path in {
            "search/metadata",
            "search/smart",
            "search/suggestions",
            "server/version",
            "server/ping",
            "users/me",
            "albums",
            "shared-links/me",
            "timeline/buckets",
            "timeline/bucket",
        }:
            return path
        if path.startswith("assets/"):
            return (
                "assets/thumbnail"
                if path.endswith("/thumbnail")
                else "assets/original"
                if path.endswith("/original")
                else "assets/metadata"
            )
        return "immich/read"

    async def _request_attempts(
        self,
        method: str,
        path: str,
        *,
        credential: ImmichCredential | None,
        send_credential: bool,
        params: Mapping[str, Any] | None,
        json_body: Mapping[str, Any] | None,
        diagnostic: dict[str, Any],
    ) -> httpx.Response:
        headers = self._credential_headers(credential) if send_credential else None
        retries = self.settings.http_max_retries if method == "GET" else 0
        for attempt in range(retries + 1):
            diagnostic.update(attempts=attempt + 1, status=None)
            try:
                response = await self._client.request(
                    method, path, headers=headers, params=params, json=json_body, follow_redirects=False
                )
            except httpx.TimeoutException as exc:
                if attempt < retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichTimeout("Immich request timed out") from exc
            except httpx.RequestError:
                if attempt < retries:
                    await asyncio.sleep(0.05 * (2**attempt))
                    continue
                raise ImmichNetworkError("Immich could not be reached") from None

            diagnostic["status"] = response.status_code
            if 300 <= response.status_code < 400:
                raise ImmichError("Immich redirect was not followed")
            if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
                await asyncio.sleep(0.05 * (2**attempt))
                continue
            self._raise_for_status(response, credential)
            return response
        raise ImmichUnavailable("Immich request failed")  # pragma: no cover

    @staticmethod
    def _credential_headers(credential: ImmichCredential | None) -> dict[str, str] | None:
        if credential is None:
            return None
        if credential.kind == "share":
            return {"x-immich-share-key": credential.token}
        if credential.kind == "api_key":
            return {"x-api-key": credential.token}
        return {"x-immich-session-token": credential.token}

    @staticmethod
    def _raise_for_status(response: httpx.Response, credential: ImmichCredential | None) -> None:
        status = response.status_code
        if status < 400:
            return
        # Fixed messages only: upstream bodies and request details are never reflected.
        if status == 400:
            # Smart search can also use 400 for an unmet operation precondition (e.g. disabled ML).
            # Status alone cannot establish that the caller's arguments were malformed.
            raise ImmichBadRequest("Immich rejected the request or operation precondition (HTTP 400)")
        if status == 422:
            raise ImmichValidationError("Immich rejected request validation (HTTP 422)")
        if status == 401:
            if credential and credential.kind == "share":
                raise InvalidShareLink("Invalid or expired Immich share credential (HTTP 401)")
            if credential and credential.kind in {"api_key", "session"}:
                raise InvalidImmichCredential("The stored Immich credential is no longer valid (HTTP 401)")
            raise ImmichUnauthorized("Immich authentication is required (HTTP 401)")
        if status == 403:
            raise ImmichForbidden("Immich denied this operation (HTTP 403)")
        if status == 404:
            raise ImmichNotFound("Immich resource was not found (HTTP 404)")
        if status == 429:
            raise ImmichRateLimited("Immich rate limit exceeded (HTTP 429)")
        if status >= 500:
            raise ImmichUnavailable(f"Immich upstream service failed (HTTP {status})")
        raise ImmichError(f"Immich request failed with status {status}")

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            diagnostic = response.extensions.get("immich_diagnostic", {"status": response.status_code})
            log.info("immich_invalid_json", **diagnostic, error_category="MalformedImmichResponse")
            raise MalformedImmichResponse("Immich returned invalid JSON").with_diagnostic(
                diagnostic
            ) from None

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
        # The query credential is required by Immich for public thumbnails; retaining the
        # share auth context ensures a 401 is classified correctly without adding a second key.
        return await self._get_image(
            f"assets/{quote(asset_id, safe='')}/thumbnail",
            credential=ShareCredential(token=share_key),
            send_credential=False,
            params=params,
        )

    async def get_current_user(self, credential: PrivateImmichCredential) -> dict[str, Any]:
        return self._dict_json(await self._get("users/me", credential=credential), "current user")

    async def list_albums(self, credential: PrivateImmichCredential) -> list[dict[str, Any]]:
        payload = self._json(await self._get("albums", credential=credential))
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise MalformedImmichResponse("Immich returned malformed albums")
        return payload

    async def get_album(self, credential: PrivateImmichCredential, album_id: str) -> dict[str, Any]:
        response = await self._get(f"albums/{quote(album_id, safe='')}", credential=credential)
        return self._dict_json(response, "album")

    async def list_album_assets(
        self, credential: PrivateImmichCredential, album_id: str, *, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], str | None]:
        body: dict[str, Any] = {
            "albumIds": [album_id],
            "order": "asc",
            "page": 1,
            "size": min(max(offset + limit, 1), 1000),
        }
        collected: list[dict[str, Any]] = []
        next_page: str | None = None
        seen_pages: set[str] = set()
        for _ in range(100):
            items, next_page = await self._metadata_search_page(credential, body)
            collected.extend(items)
            if len(collected) >= offset + limit or not next_page:
                return collected[offset : offset + limit], next_page
            if next_page in seen_pages or int(next_page) <= body["page"]:
                raise MalformedImmichResponse("Immich search pagination repeated a page")
            seen_pages.add(next_page)
            try:
                body["page"] = int(next_page)
            except ValueError as exc:
                raise MalformedImmichResponse("Immich returned an invalid search page") from exc
        raise MalformedImmichResponse("Immich search pagination exceeded safety limit")

    async def get_asset_metadata(self, credential: PrivateImmichCredential, asset_id: str) -> dict[str, Any]:
        response = await self._get(f"assets/{quote(asset_id, safe='')}", credential=credential)
        return self._dict_json(response, "asset metadata")

    async def get_asset_thumbnail(
        self,
        credential: PrivateImmichCredential,
        asset_id: str,
        *,
        size: str = "preview",
        edited: bool | None = None,
    ) -> ImagePayload:
        if size not in {"fullsize", "preview", "thumbnail"}:
            raise ValueError("size must be fullsize, preview, or thumbnail")
        params: dict[str, Any] = {"size": size}
        if edited is not None:
            params["edited"] = str(edited).lower()
        return await self._get_image(
            f"assets/{quote(asset_id, safe='')}/thumbnail", credential=credential, params=params
        )

    async def get_asset_image(
        self, credential: PrivateImmichCredential, asset_id: str, *, edited: bool | None = None
    ) -> ImagePayload:
        params = None if edited is None else {"edited": str(edited).lower()}
        return await self._get_image(
            f"assets/{quote(asset_id, safe='')}/original", credential=credential, params=params
        )

    async def search_assets(
        self,
        credential: PrivateImmichCredential,
        *,
        query: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        person_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        media_type: str | None = None,
        favorite: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = self._search_filters(
            city=city,
            state=state,
            country=country,
            person_id=person_id,
            start_date=start_date,
            end_date=end_date,
            media_type=media_type,
            favorite=favorite,
        )
        if query:
            body: dict[str, Any] = {"query": query, "size": limit, "withExif": True}
            body.update(filters)
            payload = self._json(await self._post("search/smart", credential=credential, json_body=body))
            items, _ = self._search_asset_page(payload)
            return items
        body = {
            "size": limit,
            "withExif": True,
            "order": "desc",
        }
        body.update(filters)
        items, _ = await self._metadata_search_page(credential, body)
        return items

    async def find_assets_by_filename(
        self,
        credential: PrivateImmichCredential,
        original_file_name: str,
        *,
        album_id: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return bounded, case-insensitive exact filename matches in stable order."""
        requested_name = original_file_name.strip()
        if not requested_name:
            raise ValueError("original_file_name must not be empty")
        body: dict[str, Any] = {
            "originalFileName": requested_name,
            "order": "asc",
            "page": 1,
            "size": 1000,
            "withExif": True,
        }
        if album_id is not None:
            body["albumIds"] = [album_id]

        matches: list[dict[str, Any]] = []
        seen_pages: set[str] = set()
        requested_casefold = requested_name.casefold()
        for _ in range(100):
            items, next_page = await self._metadata_search_page(credential, body)
            for item in items:
                candidate = item.get("originalFileName")
                if isinstance(candidate, str) and candidate.casefold() == requested_casefold:
                    matches.append(item)
                    if len(matches) > limit:
                        return self._sort_filename_matches(matches)[:limit], True
            if not next_page:
                return self._sort_filename_matches(matches), False
            if next_page in seen_pages or int(next_page) <= body["page"]:
                raise MalformedImmichResponse("Immich search pagination repeated a page")
            seen_pages.add(next_page)
            try:
                body["page"] = int(next_page)
            except ValueError as exc:
                raise MalformedImmichResponse("Immich returned an invalid search page") from exc
        raise MalformedImmichResponse("Immich search pagination exceeded safety limit")

    async def get_recent_assets(
        self, credential: PrivateImmichCredential, *, limit: int
    ) -> list[dict[str, Any]]:
        body = {
            "visibility": "timeline",
            "order": "desc",
            "size": limit,
            "withExif": True,
        }
        items, _ = await self._metadata_search_page(credential, body)
        return items

    async def _metadata_search_page(
        self, credential: PrivateImmichCredential, body: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], str | None]:
        payload = self._json(await self._post("search/metadata", credential=credential, json_body=body))
        return self._search_asset_page(payload)

    async def location_search_page(
        self,
        credential: PrivateImmichCredential,
        body: dict[str, Any],
        mode: str,
    ) -> tuple[list[dict[str, Any]], str | None]:
        response = await self._post("search/metadata", credential=credential, json_body=body)
        try:
            payload = self._json(response)
            if not isinstance(payload, dict) or not isinstance(payload.get("assets", payload), dict):
                raise MalformedImmichResponse("Immich returned malformed search results")
            page = payload.get("assets", payload)
            items = self._search_items(page)
            if len(items) > body["size"]:
                raise MalformedImmichResponse("Immich returned more assets than the requested page size")
            return items, self._search_continuation(page, mode)
        except ImmichError as exc:
            if not hasattr(exc, "diagnostic"):
                raise exc.with_diagnostic(response.extensions["immich_diagnostic"]) from None
            raise

    async def location_suggestions(
        self,
        credential: PrivateImmichCredential,
        *,
        field: str,
        country: str | None = None,
        state: str | None = None,
    ) -> list[str]:
        if field not in {"city", "state", "country"}:
            raise ImmichValidationError("field must be city, state, or country")
        # Immich only applies country to states/cities and state to cities.
        if (country is not None and field == "country") or (state is not None and field != "city"):
            raise ImmichValidationError(
                "Suggestion scope: country filters states/cities; state filters cities"
            )
        params = {"type": field}
        if country is not None:
            params["country"] = country
        if state is not None:
            params["state"] = state
        response = await self._get("search/suggestions", credential=credential, params=params)
        payload = self._json(response)
        if not isinstance(payload, list) or any(v is not None and not isinstance(v, str) for v in payload):
            raise MalformedImmichResponse("Immich returned malformed location suggestions").with_diagnostic(
                response.extensions["immich_diagnostic"]
            )
        # Null is not evidence of an actual place or even of missing GPS. Do not normalize accents.
        return sorted({v for v in payload if isinstance(v, str) and v.strip()}, key=str.casefold)

    @classmethod
    def _search_asset_page(cls, payload: Any) -> tuple[list[dict[str, Any]], str | None]:
        if not isinstance(payload, dict):
            raise MalformedImmichResponse("Immich returned malformed search results")
        # Current SearchResponseDto wraps the asset page under `assets`; accepting the
        # page directly retains compatibility with older Immich search responses.
        page = payload.get("assets", payload)
        if not isinstance(page, dict):
            raise MalformedImmichResponse("Immich returned malformed asset search results")
        # Existing semantic, filename, album and recent callers use legacy numeric pages.
        # Do not reinterpret an opaque (even numeric-looking) cursor as a page.
        next_page = cls._search_continuation(page, "legacy")
        return cls._search_items(page), next_page

    @staticmethod
    def _search_continuation(page: dict[str, Any], mode: str) -> str | None:
        field, other = ("nextCursor", "nextPage") if mode == "structured" else ("nextPage", "nextCursor")
        value = page.get(field)
        if page.get(other) is not None:
            raise MalformedImmichResponse("Immich returned continuation for a different search contract")
        if value is None:
            return None
        if mode == "structured":
            if not isinstance(value, str) or not value or len(value) > 8192:
                raise MalformedImmichResponse("Immich returned an invalid search cursor")
        elif (
            type(value) not in {str, int}
            or not str(value).isascii()
            or not str(value).isdigit()
            or len(str(value)) > 9
            or int(value) < 2
        ):
            raise MalformedImmichResponse("Immich returned an invalid search page")
        return str(value)

    @staticmethod
    def _search_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise MalformedImmichResponse("Immich returned malformed search results")
        items = payload["items"]
        if not all(isinstance(item, dict) for item in items):
            raise MalformedImmichResponse("Immich search contained invalid assets")
        return items

    @staticmethod
    def _search_filters(**values: Any) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if values.get("city") is not None:
            filters["city"] = values["city"]
        if values.get("state") is not None:
            filters["state"] = values["state"]
        if values.get("country") is not None:
            filters["country"] = values["country"]
        if values.get("person_id") is not None:
            filters["personIds"] = [values["person_id"]]
        if values.get("start_date") is not None:
            filters["takenAfter"] = values["start_date"]
        if values.get("end_date") is not None:
            filters["takenBefore"] = values["end_date"]
        if values.get("media_type") is not None:
            media_type = str(values["media_type"]).upper()
            if media_type not in {"IMAGE", "VIDEO", "AUDIO", "OTHER"}:
                raise ValueError("media_type must be IMAGE, VIDEO, AUDIO, or OTHER")
            filters["type"] = media_type
        if values.get("favorite") is not None:
            filters["isFavorite"] = values["favorite"]
        return filters

    @staticmethod
    def _sort_filename_matches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            items,
            key=lambda item: (
                str(item.get("fileCreatedAt") or ""),
                str(item.get("id") or ""),
            ),
        )

    def _dict_json(self, response: httpx.Response, name: str) -> dict[str, Any]:
        payload = self._json(response)
        if not isinstance(payload, dict):
            raise MalformedImmichResponse(f"Immich returned malformed {name}")
        return payload

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
