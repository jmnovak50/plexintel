from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.mealie.errors import (
    MealieForbidden,
    MealieInvalidResponse,
    MealieNotFound,
    MealieUnauthorized,
    MealieUnavailable,
)
from app.mealie.resolver import OperationDescriptor
from app.security.destinations import DestinationPolicy


class MealieClient:
    def __init__(
        self,
        settings: Settings,
        destinations: DestinationPolicy,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.destinations = destinations
        timeout = httpx.Timeout(
            settings.mealie_read_timeout_seconds,
            connect=settings.mealie_connect_timeout_seconds,
        )
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def execute(
        self,
        base_url: str,
        token: str,
        operation: OperationDescriptor,
        *,
        path_values: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
    ) -> Any:
        path = operation.path
        for name in operation.path_parameters:
            if not path_values or name not in path_values:
                raise ValueError(f"missing path value: {name}")
            path = path.replace("{" + name + "}", quote(str(path_values[name]), safe=""))
        safe_query = {
            key: value
            for key, value in (query or {}).items()
            if key in operation.query_parameters and value is not None
        }
        return await self.request_json(
            base_url,
            token,
            operation.method,
            path,
            params=safe_query,
            operation=operation.capability,
        )

    async def request_json(
        self,
        base_url: str,
        token: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        operation: str,
        schema_response: bool = False,
    ) -> Any:
        destination = await self.destinations.validate(base_url)
        url = destination.base_url + path
        maximum = (
            self.settings.mealie_max_schema_bytes
            if schema_response
            else self.settings.mealie_max_response_bytes
        )
        attempts = 1 + (self.settings.mealie_max_retries if method.upper() in {"GET", "HEAD"} else 0)
        for attempt in range(attempts):
            try:
                async with self._client.stream(
                    method,
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                ) as response:
                    if response.is_redirect:
                        raise MealieUnavailable(f"Mealie refused redirect for operation={operation}")
                    if response.status_code == 401:
                        raise MealieUnauthorized(f"Mealie rejected credential for operation={operation}")
                    if response.status_code == 403:
                        raise MealieForbidden(f"Mealie denied operation={operation}")
                    if response.status_code == 404:
                        raise MealieNotFound(f"Mealie resource not found for operation={operation}")
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt + 1 < attempts:
                            await asyncio.sleep(0.1 * (2**attempt))
                            continue
                        raise MealieUnavailable(
                            f"Mealie unavailable for operation={operation}; status={response.status_code}"
                        )
                    if response.status_code >= 400:
                        raise MealieUnavailable(
                            f"Mealie request failed for operation={operation}; status={response.status_code}"
                        )
                    declared = response.headers.get("content-length")
                    if declared:
                        try:
                            if int(declared) > maximum:
                                raise MealieInvalidResponse(
                                    f"Mealie response too large for operation={operation}"
                                )
                        except ValueError as exc:
                            raise MealieInvalidResponse(
                                f"Mealie returned an invalid content length for operation={operation}"
                            ) from exc
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > maximum:
                            raise MealieInvalidResponse(
                                f"Mealie response too large for operation={operation}"
                            )
                        chunks.append(chunk)
                    try:
                        return json.loads(b"".join(chunks))
                    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                        raise MealieInvalidResponse(
                            f"Mealie returned invalid JSON for operation={operation}"
                        ) from exc
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
                raise MealieUnavailable(f"Mealie network failure for operation={operation}") from exc
        raise AssertionError("unreachable")
