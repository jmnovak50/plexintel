from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.services.agent_tool_service import (
    AgentRecommendationsResponse,
    AgentUsersResponse,
    LibraryItem,
    LibrarySearchResponse,
    WatchHistoryResponse,
    get_agent_library_item,
    get_agent_recommendations,
    get_agent_watch_history,
    list_agent_users,
    search_agent_library,
)
from api.services.app_settings import get_setting_value

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPRuntimeSettings:
    enabled: bool
    api_key: str | None
    allowed_origins: tuple[str, ...]


def _split_allowed_origins(value: Optional[str]) -> tuple[str, ...]:
    if not value:
        return ()
    parts = []
    for chunk in value.replace("\n", ",").split(","):
        normalized = chunk.strip()
        if normalized:
            parts.append(normalized)
    return tuple(parts)


def get_mcp_runtime_settings() -> MCPRuntimeSettings:
    return MCPRuntimeSettings(
        enabled=bool(get_setting_value("mcp.enabled", default=False)),
        api_key=get_setting_value("mcp.api_key"),
        allowed_origins=_split_allowed_origins(get_setting_value("mcp.allowed_origins")),
    )


def _extract_rpc_method(body: bytes) -> str | None:
    if not body:
        return None

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if isinstance(payload, list):
        return "batch"
    if not isinstance(payload, dict):
        return None

    method = payload.get("method")
    if method == "tools/call":
        tool_name = payload.get("params", {}).get("name")
        if tool_name:
            return f"tools/call:{tool_name}"
    return method


def _build_replay_receive(body: bytes) -> Receive:
    sent = False

    async def replay_receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return replay_receive


def _extract_caller(scope: Scope, headers: Headers) -> str:
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    origin = headers.get("origin")
    if origin:
        return origin
    client = scope.get("client")
    if client and client[0]:
        return str(client[0])
    return "unknown"


class MCPAccessControlApp:
    def __init__(self, runtime: "MCPServerRuntime"):
        self.runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return

        if scope["type"] != "http":
            await self.runtime.get_asgi_app()(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500
        headers = Headers(scope=scope)
        caller = _extract_caller(scope, headers)
        rpc_method = scope.get("method", "UNKNOWN")

        settings = get_mcp_runtime_settings()
        response = self._validate_request(headers=headers, settings=settings)
        if response is not None:
            status_code = response.status_code
            logger.info(
                "MCP request blocked method=%s caller=%s status=%s duration_ms=%.2f",
                rpc_method,
                caller,
                status_code,
                (time.perf_counter() - start) * 1000,
            )
            await response(scope, receive, send)
            return

        downstream_receive = receive
        if scope.get("method") == "POST":
            request = Request(scope, receive)
            body = await request.body()
            rpc_method = _extract_rpc_method(body) or rpc_method
            downstream_receive = _build_replay_receive(body)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.runtime.get_asgi_app()(scope, downstream_receive, send_wrapper)
        finally:
            logger.info(
                "MCP request method=%s caller=%s status=%s duration_ms=%.2f",
                rpc_method,
                caller,
                status_code,
                (time.perf_counter() - start) * 1000,
            )

    @staticmethod
    def _validate_request(headers: Headers, settings: MCPRuntimeSettings):
        if not settings.enabled:
            return JSONResponse({"detail": "MCP server is disabled"}, status_code=404)

        if not settings.api_key:
            return JSONResponse({"detail": "MCP server is not configured"}, status_code=503)

        authorization = headers.get("authorization")
        expected = f"Bearer {settings.api_key}"
        if authorization != expected:
            return JSONResponse({"detail": "Invalid or missing MCP bearer token"}, status_code=403)

        origin = headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return JSONResponse({"detail": "Origin is not allowed for MCP access"}, status_code=403)

        return None

    @staticmethod
    async def _handle_lifespan(receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


def _build_mcp_server() -> FastMCP:
    server_name = get_setting_value("mcp.server_name", default="PlexIntel")
    instructions = get_setting_value("mcp.instructions")

    mcp = FastMCP(
        server_name,
        instructions=instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool(
        name="list_users",
        description="List PlexIntel users by username or friendly name.",
        structured_output=True,
    )
    def mcp_list_users(
        username: Optional[str] = None,
        friendly_name: Optional[str] = None,
        limit: int = 200,
    ) -> AgentUsersResponse:
        return list_agent_users(username=username, friendly_name=friendly_name, limit=limit)

    @mcp.tool(
        name="get_recommendations",
        description="Fetch PlexIntel recommendations for a user.",
        structured_output=True,
    )
    def mcp_get_recommendations(
        user: str,
        media_type: Optional[str] = None,
        limit: int = 100,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> AgentRecommendationsResponse:
        return get_agent_recommendations(
            user=user,
            media_type=media_type,
            limit=limit,
            min_score=min_score,
            max_score=max_score,
        )

    @mcp.tool(
        name="search_library",
        description="Search the PlexIntel library catalog by free text.",
        structured_output=True,
    )
    def mcp_search_library(
        q: str,
        media_type: Optional[str] = None,
        sort_by: str = "title",
        sort_dir: str = "asc",
        limit: int = 20,
    ) -> LibrarySearchResponse:
        return search_agent_library(
            q=q,
            media_type=media_type,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
        )

    @mcp.tool(
        name="get_library_item",
        description="Fetch one PlexIntel library item by rating_key.",
        structured_output=True,
    )
    def mcp_get_library_item(rating_key: int) -> LibraryItem:
        return get_agent_library_item(rating_key=rating_key)

    @mcp.tool(
        name="get_watch_history",
        description="Return enriched Plex watch history records.",
        structured_output=True,
    )
    def mcp_get_watch_history(
        user: Optional[str] = None,
        limit: int = 200,
        engaged_only: bool = False,
    ) -> WatchHistoryResponse:
        return get_agent_watch_history(user=user, limit=limit, engaged_only=engaged_only)

    return mcp


class MCPServerRuntime:
    def __init__(self):
        self._server: FastMCP | None = None
        self._app: ASGIApp | None = None
        self._session_manager = None

    def _build(self) -> None:
        self._server = _build_mcp_server()
        self._app = self._server.streamable_http_app()
        self._session_manager = self._server.session_manager

    def get_asgi_app(self) -> ASGIApp:
        if self._app is None:
            self._build()
        return self._app

    @asynccontextmanager
    async def lifespan(self):
        self._build()
        try:
            async with self._session_manager.run():
                yield
        finally:
            self._server = None
            self._app = None
            self._session_manager = None


mcp_runtime = MCPServerRuntime()
mcp_mount_app = MCPAccessControlApp(mcp_runtime)
