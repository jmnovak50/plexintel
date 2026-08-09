from __future__ import annotations

import hmac
import json
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.services.agent_tool_service import (
    AgentRecommendationScore,
    AgentRecommendationsResponse,
    AgentUsersResponse,
    LibraryItem,
    LibrarySearchResponse,
    RecentLibraryAdditionsResponse,
    WatchHistoryResponse,
    get_agent_library_item,
    get_agent_recommendation_score,
    get_agent_recommendations,
    get_recent_library_additions,
    get_agent_watch_history,
    list_agent_users,
    search_agent_library,
)
from api.services.app_settings import get_setting_value
from api.services.mcp_auth import (
    MCPAuthContext,
    MCPOAuthSettings,
    MCPTokenValidation,
    MCPTokenStatus,
    build_oauth_challenge,
    get_mcp_oauth_settings,
    resolve_context_from_email,
    validate_bearer_token,
)
from api.services.poster_service import build_public_poster_url, fetch_poster_image_for_rating_key
from api.services.poster_markup_service import (
    build_poster_gallery_payload,
    build_poster_markup_payload as _build_poster_markup_payload,
    coerce_gallery_entries,
)

logger = logging.getLogger(__name__)

mcp_auth_context: ContextVar[MCPAuthContext | None] = ContextVar("mcp_auth_context", default=None)


POSTER_RESPONSE_INSTRUCTIONS = (
    "After get_poster_image or get_poster_gallery returns, paste the returned plain text "
    "Markdown tool result directly into the final response. Poster gallery URLs should use "
    "thumbnail-sized poster URLs returned by the tool. Do not convert thumbnail URLs back to "
    "original poster URLs. Never respond with only poster titles. Never tell the user to "
    "expand the tool result. Never use the local MCP URL as an image src."
)

USER_IDENTITY_INSTRUCTIONS = (
    "User-specific tools (get_recommendations, get_recommendation_score, get_watch_history) "
    "automatically scope to the authenticated user. Do not pass a user argument for "
    '"my recommendations", "what should I watch", or similar first-person requests.'
)


class MCPUserAccessError(ValueError):
    pass


@dataclass(frozen=True)
class MCPRuntimeSettings:
    enabled: bool
    auth_mode: str
    api_key: str | None
    allowed_origins: tuple[str, ...]
    oauth_issuer_url: str | None
    oauth_audience: str | None
    oauth_email_claim: str
    oauth_resource_url: str | None
    oauth_required_scopes: tuple[str, ...]
    trusted_user_email_header: str | None


mcp_runtime_settings_context: ContextVar[MCPRuntimeSettings | None] = ContextVar(
    "mcp_runtime_settings_context",
    default=None,
)


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
    oauth_settings = get_mcp_oauth_settings()
    return MCPRuntimeSettings(
        enabled=bool(get_setting_value("mcp.enabled", default=False)),
        auth_mode=str(get_setting_value("mcp.auth_mode", default="static") or "static"),
        api_key=get_setting_value("mcp.api_key"),
        allowed_origins=_split_allowed_origins(get_setting_value("mcp.allowed_origins")),
        oauth_issuer_url=oauth_settings.issuer_url,
        oauth_audience=oauth_settings.audience,
        oauth_email_claim=oauth_settings.email_claim,
        oauth_resource_url=oauth_settings.resource_url,
        oauth_required_scopes=oauth_settings.required_scopes,
        trusted_user_email_header=_normalize_optional_header(
            get_setting_value("mcp.trusted_user_email_header", default="X-OpenWebUI-User-Email")
        ),
    )


def _normalize_optional_header(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(part.strip() for part in parts)


def _extract_trusted_user_email(headers: Headers, configured_header: str | None) -> str | None:
    candidate_names = []
    if configured_header:
        candidate_names.append(configured_header.lower())
    candidate_names.extend(
        name
        for name in (
            "x-openwebui-user-email",
            "x-plexintel-user-email",
        )
        if name not in candidate_names
    )
    for name in candidate_names:
        value = headers.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def get_current_mcp_auth_context() -> MCPAuthContext | None:
    return mcp_auth_context.get()


def _mcp_auth_required_result() -> CallToolResult:
    runtime_settings = mcp_runtime_settings_context.get()
    oauth_settings = (
        MCPOAuthSettings(
            issuer_url=runtime_settings.oauth_issuer_url,
            audience=runtime_settings.oauth_audience,
            email_claim=runtime_settings.oauth_email_claim,
            resource_url=runtime_settings.oauth_resource_url,
            required_scopes=runtime_settings.oauth_required_scopes,
        )
        if runtime_settings
        else get_mcp_oauth_settings()
    )
    challenge = build_oauth_challenge(
        oauth_settings,
        error="insufficient_scope",
        description="Sign in to PlexIntel to continue",
    )
    return CallToolResult(
        content=[TextContent(type="text", text="Authentication required.")],
        **{"_meta": {"mcp/www_authenticate": [challenge]}},
        isError=True,
    )


class PlexIntelFastMCP(FastMCP):
    async def call_tool(self, name: str, arguments: dict[str, Any]):
        context = get_current_mcp_auth_context()
        if context is None or (context.auth_method == "jwt" and not context.plex_username):
            return _mcp_auth_required_result()
        return await super().call_tool(name, arguments)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def _resolve_mcp_user(requested_user: str | None) -> str:
    ctx = get_current_mcp_auth_context()
    normalized_request = (requested_user or "").strip() or None

    if ctx and ctx.plex_username:
        if normalized_request is None:
            return ctx.plex_username
        if ctx.is_admin or normalized_request == ctx.plex_username:
            return normalized_request
        raise MCPUserAccessError(f"Not authorized to query user '{normalized_request}'")

    if ctx and ctx.auth_method == "jwt" and ctx.email:
        raise MCPUserAccessError(
            f"No Plex user found for {ctx.email} — ensure plex_email is synced"
        )

    if normalized_request:
        return normalized_request
    raise MCPUserAccessError(
        "No authenticated Plex user is mapped for this MCP request. "
        "Configure Open WebUI MCP with Bearer auth plus a custom header "
        '{"X-OpenWebUI-User-Email": "{{USER_EMAIL}}"}, or provide a valid Authentik JWT.'
    )


def build_poster_markup_payload(
    rating_key: int,
    *,
    title: str | None = None,
    media_type: str | None = None,
    width: int = 180,
) -> dict[str, Any]:
    return _build_poster_markup_payload(
        rating_key,
        title=title,
        media_type=media_type,
        width=width,
        url_builder=build_public_poster_url,
    )


def build_poster_image_result(rating_key: int) -> CallToolResult:
    title = None
    media_type = None

    try:
        item = get_agent_library_item(rating_key=rating_key)
        title = item.title
        media_type = item.media_type
    except Exception:
        logger.info("MCP poster metadata lookup failed for rating_key=%s", rating_key, exc_info=True)

    metadata = {
        "rating_key": rating_key,
        "title": title,
        "media_type": media_type,
        "found": False,
    }
    display_title = title or f"rating_key {rating_key}"

    try:
        payload = fetch_poster_image_for_rating_key(rating_key)
    except Exception as exc:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Unable to fetch poster for {display_title}: {exc}",
                )
            ],
            structuredContent={**metadata, "error": str(exc)},
            isError=True,
        )

    if not payload:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Poster not found for {display_title}.",
                )
            ],
            structuredContent=metadata,
        )

    poster_payload = build_poster_markup_payload(
        rating_key,
        title=title,
        media_type=media_type,
        width=240,
    )

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=f"### {poster_payload['title']}\n{poster_payload['markdown']}",
            ),
        ]
    )


def _coerce_gallery_entries(
    rating_keys: Optional[list[int]] = None,
    items: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    return coerce_gallery_entries(rating_keys=rating_keys, items=items)


def build_poster_gallery_result(
    rating_keys: Optional[list[int]] = None,
    items: Optional[list[dict[str, Any]]] = None,
) -> CallToolResult:
    entries = _coerce_gallery_entries(rating_keys=rating_keys, items=items)

    for entry in entries:
        title = entry.get("title")
        media_type = entry.get("media_type")
        if not title or not media_type:
            try:
                item = get_agent_library_item(rating_key=entry["rating_key"])
                title = title or item.title
                media_type = media_type or item.media_type
            except Exception:
                logger.info(
                    "MCP gallery metadata lookup failed for rating_key=%s",
                    entry["rating_key"],
                    exc_info=True,
                )
        entry["title"] = title
        entry["media_type"] = media_type

    gallery_payload = build_poster_gallery_payload(
        entries,
        width=180,
        url_builder=build_public_poster_url,
    )

    return CallToolResult(
        content=[TextContent(type="text", text=gallery_payload["markdown"])],
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


def _format_auth_caller(context: MCPAuthContext | None, fallback: str) -> str:
    if context and context.email:
        return context.email
    if context and context.plex_username:
        return context.plex_username
    return fallback


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

        body = b""
        if scope.get("method") == "POST":
            request = Request(scope, receive)
            body = await request.body()
            rpc_method = _extract_rpc_method(body) or rpc_method

        settings = get_mcp_runtime_settings()
        auth_result = self._authenticate_request(headers=headers, settings=settings)
        auth_result = self._enrich_auth_context(headers=headers, settings=settings, auth_result=auth_result)
        if auth_result.response is not None:
            status_code = auth_result.response.status_code
            logger.info(
                "MCP request blocked method=%s caller=%s status=%s duration_ms=%.2f",
                rpc_method,
                caller,
                status_code,
                (time.perf_counter() - start) * 1000,
            )
            await auth_result.response(scope, _build_replay_receive(body) if body else receive, send)
            return

        auth_token = mcp_auth_context.set(auth_result.context)
        settings_token = mcp_runtime_settings_context.set(settings)
        downstream_receive = receive
        if body:
            downstream_receive = _build_replay_receive(body)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.runtime.get_asgi_app()(scope, downstream_receive, send_wrapper)
        finally:
            mcp_runtime_settings_context.reset(settings_token)
            mcp_auth_context.reset(auth_token)
            logger.info(
                "MCP request method=%s caller=%s status=%s duration_ms=%.2f",
                rpc_method,
                _format_auth_caller(auth_result.context, caller),
                status_code,
                (time.perf_counter() - start) * 1000,
            )

    @dataclass(frozen=True)
    class _AuthResult:
        response: JSONResponse | None
        context: MCPAuthContext | None

    def _authenticate_request(self, headers: Headers, settings: MCPRuntimeSettings) -> _AuthResult:
        if not settings.enabled:
            return self._AuthResult(
                response=JSONResponse({"detail": "MCP server is disabled"}, status_code=404),
                context=None,
            )

        origin = headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return self._AuthResult(
                response=JSONResponse({"detail": "Origin is not allowed for MCP access"}, status_code=403),
                context=None,
            )

        authorization = headers.get("authorization")
        bearer_token = _extract_bearer_token(authorization)
        auth_mode = settings.auth_mode

        if auth_mode == "jwt":
            return self._authenticate_jwt(bearer_token, settings)
        if auth_mode == "static":
            return self._authenticate_static(bearer_token, settings)
        if auth_mode == "jwt_or_static":
            if bearer_token and settings.api_key and hmac.compare_digest(bearer_token, settings.api_key):
                return self._AuthResult(
                    response=None,
                    context=MCPAuthContext(auth_method="static"),
                )
            if not bearer_token or _looks_like_jwt(bearer_token):
                return self._authenticate_jwt(bearer_token, settings)
            return self._authenticate_static(bearer_token, settings)

        return self._AuthResult(
            response=JSONResponse({"detail": "Unsupported MCP auth mode"}, status_code=503),
            context=None,
        )

    def _authenticate_jwt(
        self,
        bearer_token: str | None,
        settings: MCPRuntimeSettings,
    ) -> _AuthResult:
        oauth_settings = MCPOAuthSettings(
            issuer_url=settings.oauth_issuer_url,
            audience=settings.oauth_audience,
            email_claim=settings.oauth_email_claim,
            resource_url=settings.oauth_resource_url,
            required_scopes=settings.oauth_required_scopes,
        )
        if not settings.oauth_issuer_url or not settings.oauth_resource_url or not settings.oauth_required_scopes:
            return self._AuthResult(
                response=JSONResponse({"detail": "MCP OAuth resource server is not configured"}, status_code=503),
                context=None,
            )
        if not bearer_token:
            return self._AuthResult(response=None, context=None)

        validation = validate_bearer_token(bearer_token, oauth_settings)
        if validation.status is MCPTokenStatus.CONFIGURATION_ERROR:
            logger.warning("MCP OAuth token could not be validated because OAuth is unavailable")
            return self._AuthResult(response=None, context=None)
        if validation.status is not MCPTokenStatus.VALID:
            return self._AuthResult(response=None, context=None)
        return self._AuthResult(response=None, context=validation.context)

    def _authenticate_static(self, bearer_token: str | None, settings: MCPRuntimeSettings) -> _AuthResult:
        if not settings.api_key:
            return self._AuthResult(response=None, context=None)
        if bearer_token is None or not hmac.compare_digest(bearer_token, settings.api_key):
            return self._AuthResult(response=None, context=None)
        return self._AuthResult(
            response=None,
            context=MCPAuthContext(auth_method="static"),
        )

    def _enrich_auth_context(
        self,
        headers: Headers,
        settings: MCPRuntimeSettings,
        auth_result: _AuthResult,
    ) -> _AuthResult:
        if auth_result.response is not None or auth_result.context is None:
            return auth_result
        if auth_result.context.auth_method == "jwt":
            return auth_result
        if auth_result.context.plex_username:
            return auth_result

        email = _extract_trusted_user_email(headers, settings.trusted_user_email_header)
        if not email:
            return auth_result

        enriched = resolve_context_from_email(email, auth_result.context.auth_method)
        return self._AuthResult(response=None, context=enriched)

    @staticmethod
    async def _handle_lifespan(receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


class MCPPathCompatibilityMiddleware:
    """Route the canonical /mcp path through Starlette's slash-requiring ASGI mount."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            root_path = scope.get("root_path", "")
            if scope.get("path") == f"{root_path}/mcp":
                scope = dict(scope)
                scope["path"] = f"{scope['path']}/"
                if scope.get("raw_path") == f"{root_path}/mcp".encode():
                    scope["raw_path"] = f"{root_path}/mcp/".encode()
        await self.app(scope, receive, send)


def _build_mcp_server() -> FastMCP:
    server_name = get_setting_value("mcp.server_name", default="PlexIntel")
    instructions = get_setting_value("mcp.instructions")
    instruction_parts = [part for part in (instructions, USER_IDENTITY_INSTRUCTIONS, POSTER_RESPONSE_INSTRUCTIONS) if part]
    instructions = "\n\n".join(instruction_parts)

    mcp = PlexIntelFastMCP(
        server_name,
        instructions=instructions,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    oauth_settings = get_mcp_oauth_settings()
    tool_annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    def oauth_tool_meta() -> dict[str, Any]:
        return {
            "securitySchemes": [
                {"type": "oauth2", "scopes": list(oauth_settings.required_scopes)}
            ]
        }

    @mcp.tool(
        name="list_users",
        description="List PlexIntel users by username or friendly name.",
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_list_users(
        username: Optional[str] = None,
        friendly_name: Optional[str] = None,
        limit: int = 200,
    ) -> AgentUsersResponse:
        return list_agent_users(username=username, friendly_name=friendly_name, limit=limit)

    @mcp.tool(
        name="get_recommendations",
        description=(
            "Fetch PlexIntel recommendations for the authenticated user. Use view='shows' for clean "
            "TV show-level recommendations, view='seasons' for season rollups, "
            "view='movies' for movies, or view='episodes' for individual episodes. "
            "The media_type argument remains supported for backward compatibility "
            "(movie, episode, show, and series map to the matching view). Results "
            "include rating_key values; call get_poster_image with a rating_key "
            "when the user asks to see a poster. Omit user to scope to the authenticated user."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_recommendations(
        user: Optional[str] = None,
        view: Optional[str] = None,
        media_type: Optional[str] = None,
        limit: int = 100,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> AgentRecommendationsResponse:
        resolved_user = _resolve_mcp_user(user)
        return get_agent_recommendations(
            user=resolved_user,
            view=view,
            media_type=media_type,
            limit=limit,
            min_score=min_score,
            max_score=max_score,
        )

    @mcp.tool(
        name="get_recommendation_score",
        description=(
            "Fetch the raw PlexIntel recommendation score for one user and one exact "
            "library rating_key. Use this to enrich arbitrary library results, including "
            "recent additions, with a user-specific score. This lookup is not filtered by "
            "the recommendation display threshold or feedback visibility rules. "
            "Omit user to scope to the authenticated user."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_recommendation_score(
        user: Optional[str] = None,
        *,
        rating_key: int,
    ) -> AgentRecommendationScore:
        resolved_user = _resolve_mcp_user(user)
        return get_agent_recommendation_score(user=resolved_user, rating_key=rating_key)

    @mcp.tool(
        name="search_library",
        description=(
            "Search the PlexIntel library catalog by free text. Results include rating_key values; "
            "call get_poster_image with a rating_key when the user asks to see a poster."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
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
        description=(
            "Fetch one PlexIntel library item by rating_key. Call get_poster_image with "
            "the same rating_key when the user asks to see its poster."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_library_item(rating_key: int) -> LibraryItem:
        return get_agent_library_item(rating_key=rating_key)

    @mcp.tool(
        name="get_poster_image",
        description=(
            "Return a plain text Markdown poster block for a PlexIntel library item by rating_key. "
            "Use this when the user asks to display, show, or view a movie or show poster. "
            "The final assistant response must paste the returned tool text exactly."
        ),
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_poster_image(rating_key: int) -> CallToolResult:
        return build_poster_image_result(rating_key)

    @mcp.tool(
        name="get_poster_gallery",
        description=(
            "Return a completed plain text Markdown poster gallery for multiple PlexIntel library items. "
            "Pass either rating_keys or items containing rating_key and optional title. Use this "
            "for recent additions or any response with several posters. The final assistant "
            "response must paste the returned tool text exactly."
        ),
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_poster_gallery(
        rating_keys: Optional[list[int]] = None,
        items: Optional[list[dict[str, Any]]] = None,
    ) -> CallToolResult:
        return build_poster_gallery_result(rating_keys=rating_keys, items=items)

    @mcp.tool(
        name="get_recent_library_additions",
        description=(
            "Return recently added PlexIntel library items across the whole library. "
            "Use this for questions like 'what was added in the last 7 days?' "
            "or 'show me recent movies or TV shows'. This does not require a user. "
            "Results include rating_key values; call get_poster_image with a rating_key "
            "when the user asks to see a poster."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_recent_library_additions(
        media_type: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 50,
    ) -> RecentLibraryAdditionsResponse:
        return get_recent_library_additions(media_type=media_type, days=days, limit=limit)

    @mcp.tool(
        name="get_watch_history",
        description=(
            "Return enriched Plex watch history records for the authenticated user. "
            "Omit user to scope to the authenticated user."
        ),
        structured_output=True,
        annotations=tool_annotations,
        meta=oauth_tool_meta(),
    )
    def mcp_get_watch_history(
        user: Optional[str] = None,
        limit: int = 200,
        engaged_only: bool = False,
    ) -> WatchHistoryResponse:
        resolved_user = _resolve_mcp_user(user)
        return get_agent_watch_history(user=resolved_user, limit=limit, engaged_only=engaged_only)

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
