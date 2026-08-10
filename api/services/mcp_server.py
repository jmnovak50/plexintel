from __future__ import annotations

import base64
import hmac
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, Icon, ImageContent, TextContent, Tool as MCPTool, ToolAnnotations
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import Headers
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
from api.services.poster_service import (
    build_public_poster_url,
    fetch_poster_image_for_rating_key,
    resize_poster_image_to_width,
)
from api.services.poster_markup_service import (
    build_poster_gallery_payload,
    build_poster_markup_payload as _build_poster_markup_payload,
    coerce_gallery_entries,
)

logger = logging.getLogger(__name__)

mcp_auth_context: ContextVar[MCPAuthContext | None] = ContextVar("mcp_auth_context", default=None)

NATIVE_POSTER_WIDTH = 180
NATIVE_POSTER_MAX_BYTES = 512 * 1024
NATIVE_POSTER_GALLERY_MAX_ITEMS = 8
RECENT_ADDITIONS_WIDGET_URI = "ui://plexintel/recent-library-additions.html"
RECENT_ADDITIONS_WIDGET_MIME_TYPE = "text/html;profile=mcp-app"
RECENT_ADDITIONS_POSTER_WIDTH = 180
RECENT_ADDITIONS_POSTER_ORIGIN = "https://plexintel.kabolly.com"
RECENT_ADDITIONS_WIDGET_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "recent_library_additions.html"
)
NATIVE_POSTER_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)


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

RECENT_ADDITIONS_UI_INSTRUCTIONS = (
    "For visual recent-library requests with posters, a visual table, cards, or a gallery, "
    "first call get_recent_library_additions, then pass its resulting or filtered items and "
    "days to render_recent_library_additions. Do not call the render tool for ordinary data-only "
    "recent-additions requests. Continue using the native poster tools for individual-poster "
    "requests when native MCP image content is appropriate."
)


class RecentAdditionRenderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rating_key: int = Field(gt=0, strict=True)
    title: str
    media_type: str
    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    year: Optional[int] = None
    added_at: Optional[datetime] = None
    poster_url: Optional[str] = None


class RecentAdditionsRenderResponse(BaseModel):
    items: list[RecentAdditionRenderItem]
    count: int = Field(ge=0)
    days: Optional[int] = Field(default=None, ge=1)


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
    """FastMCP with support for ChatGPT's top-level tool security extension.

    MCP SDK 1.27 does not expose ``securitySchemes`` through ``FastMCP.tool``,
    but its protocol ``Tool`` model intentionally permits extension fields.
    Keep registration and response serialization inside the SDK while promoting
    the registered schemes onto that protocol model.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._tool_security_schemes: dict[str, list[dict[str, Any]]] = {}
        self._tool_output_schemas: dict[str, dict[str, Any]] = {}

    def set_tool_output_schema(self, name: str, schema: dict[str, Any]) -> None:
        """Attach an explicit protocol output schema to a registered FastMCP tool."""
        self._tool_output_schemas[name] = schema

    def tool(
        self,
        name: str | None = None,
        title: str | None = None,
        description: str | None = None,
        annotations: ToolAnnotations | None = None,
        icons: list[Icon] | None = None,
        meta: dict[str, Any] | None = None,
        structured_output: bool | None = None,
        *,
        security_schemes: list[dict[str, Any]] | None = None,
    ) -> Callable[[Any], Any]:
        register = super().tool(
            name=name,
            title=title,
            description=description,
            annotations=annotations,
            icons=icons,
            meta=meta,
            structured_output=structured_output,
        )

        def decorator(fn: Any) -> Any:
            registered = register(fn)
            if security_schemes is not None:
                tool_name = name or fn.__name__
                self._tool_security_schemes[tool_name] = [dict(scheme) for scheme in security_schemes]
            return registered

        return decorator

    async def list_tools(self) -> list[MCPTool]:
        tools = await super().list_tools()
        discovered_tools = []
        for tool in tools:
            updates: dict[str, Any] = {}
            if tool.name in self._tool_security_schemes:
                updates["securitySchemes"] = self._tool_security_schemes[tool.name]
            if tool.name in self._tool_output_schemas:
                updates["outputSchema"] = self._tool_output_schemas[tool.name]
            discovered_tools.append(tool.model_copy(update=updates, deep=True) if updates else tool)
        return discovered_tools

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


def _read_recent_additions_widget() -> str:
    return RECENT_ADDITIONS_WIDGET_PATH.read_text(encoding="utf-8")


def build_recent_additions_render_result(
    items: list[RecentAdditionRenderItem],
    *,
    days: int | None = None,
) -> CallToolResult:
    rendered_items: list[RecentAdditionRenderItem] = []
    for item in items:
        canonical_url = build_public_poster_url(
            item.rating_key,
            width=RECENT_ADDITIONS_POSTER_WIDTH,
        )
        if item.poster_url is not None and item.poster_url != canonical_url:
            raise ValueError(
                "poster_url must be omitted or match PlexIntel's public poster URL "
                f"for rating_key {item.rating_key}."
            )
        rendered_items.append(item.model_copy(update={"poster_url": canonical_url}))

    payload = RecentAdditionsRenderResponse(
        items=rendered_items,
        count=len(rendered_items),
        days=days,
    )
    window_text = f" from the past {days} days" if days is not None else ""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=(
                    f"Displaying {payload.count} PlexIntel library additions"
                    f"{window_text}."
                ),
            )
        ],
        structuredContent=payload.model_dump(mode="json"),
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


class NativePosterError(ValueError):
    pass


def _native_poster_error(message: str) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        isError=True,
    )


def _validate_native_rating_key(rating_key: Any) -> int:
    if isinstance(rating_key, bool) or not isinstance(rating_key, int) or rating_key <= 0:
        raise NativePosterError("rating_key must be a positive integer.")
    return rating_key


def _native_poster_label(
    rating_key: int,
    *,
    title: str | None,
    year: int | None,
) -> str:
    label = (title or "").strip() or f"rating_key {rating_key}"
    if year is not None:
        label = f"{label} ({year})"
    return label


def _detect_native_image_mime(content: bytes) -> str:
    try:
        with Image.open(BytesIO(content)) as image:
            detected_mime = Image.MIME.get(image.format or "")
            image.verify()
    except Exception as exc:
        raise NativePosterError("The poster response did not contain a valid image.") from exc

    if detected_mime not in NATIVE_POSTER_MIME_TYPES:
        raise NativePosterError(
            f"The poster image type {detected_mime or 'unknown'} is not supported."
        )
    return detected_mime


def _fetch_native_poster(rating_key: int) -> tuple[bytes, str] | None:
    payload = fetch_poster_image_for_rating_key(rating_key)
    if not payload:
        return None

    resized = resize_poster_image_to_width(
        payload["content"],
        payload.get("content_type"),
        width=NATIVE_POSTER_WIDTH,
    )
    content = resized["content"]
    if len(content) > NATIVE_POSTER_MAX_BYTES:
        raise NativePosterError(
            f"The resized poster exceeds the {NATIVE_POSTER_MAX_BYTES}-byte native image limit."
        )
    return content, _detect_native_image_mime(content)


def _native_image_content(content: bytes, mime_type: str) -> ImageContent:
    return ImageContent(
        type="image",
        data=base64.b64encode(content).decode("ascii"),
        mimeType=mime_type,
    )


def build_poster_image_native_result(rating_key: int) -> CallToolResult:
    try:
        rating_key = _validate_native_rating_key(rating_key)
    except NativePosterError as exc:
        return _native_poster_error(str(exc))

    title = None
    media_type = None
    year = None
    try:
        item = get_agent_library_item(rating_key=rating_key)
        title = item.title
        media_type = item.media_type
        year = item.year
    except Exception:
        logger.info(
            "MCP native poster metadata lookup failed for rating_key=%s",
            rating_key,
            exc_info=True,
        )

    label = _native_poster_label(rating_key, title=title, year=year)
    metadata = {
        "rating_key": rating_key,
        "title": title,
        "year": year,
        "media_type": media_type,
        "found": False,
    }
    try:
        poster = _fetch_native_poster(rating_key)
    except Exception as exc:
        message = str(exc) if isinstance(exc, NativePosterError) else "Unable to fetch the poster."
        return CallToolResult(
            content=[TextContent(type="text", text=f"Poster unavailable for {label}: {message}")],
            structuredContent={**metadata, "error": message},
            isError=True,
        )

    if poster is None:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Poster unavailable for {label}.")],
            structuredContent=metadata,
        )

    content, mime_type = poster
    return CallToolResult(
        content=[
            TextContent(type="text", text=f"Poster for {label}."),
            _native_image_content(content, mime_type),
        ],
        structuredContent={**metadata, "found": True},
    )


def build_poster_gallery_native_result(
    rating_keys: Optional[list[int]] = None,
    items: Optional[list[dict[str, Any]]] = None,
) -> CallToolResult:
    requested_count = len(rating_keys or []) + len(items or [])
    if requested_count > NATIVE_POSTER_GALLERY_MAX_ITEMS:
        return _native_poster_error(
            "Native poster galleries are limited to "
            f"{NATIVE_POSTER_GALLERY_MAX_ITEMS} requested items."
        )

    try:
        for rating_key in rating_keys or []:
            _validate_native_rating_key(rating_key)
        for item in items or []:
            if not isinstance(item, dict):
                raise NativePosterError("Each gallery item must be an object with a rating_key.")
            rating_key = item.get("rating_key", item.get("ratingKey"))
            _validate_native_rating_key(rating_key)
    except NativePosterError as exc:
        return _native_poster_error(str(exc))

    entries = coerce_gallery_entries(
        rating_keys=rating_keys,
        items=items,
        max_items=NATIVE_POSTER_GALLERY_MAX_ITEMS + 1,
    )
    if not entries:
        return _native_poster_error("Provide at least one valid rating_key.")
    if len(entries) > NATIVE_POSTER_GALLERY_MAX_ITEMS:
        return _native_poster_error(
            f"Native poster galleries are limited to {NATIVE_POSTER_GALLERY_MAX_ITEMS} items."
        )
    try:
        for entry in entries:
            entry["rating_key"] = _validate_native_rating_key(entry["rating_key"])
    except NativePosterError as exc:
        return _native_poster_error(str(exc))

    result_content: list[TextContent | ImageContent] = []
    result_items: list[dict[str, Any]] = []
    for entry in entries:
        rating_key = entry["rating_key"]
        title = entry.get("title")
        media_type = entry.get("media_type")
        year = None
        try:
            item = get_agent_library_item(rating_key=rating_key)
            title = title or item.title
            media_type = media_type or item.media_type
            year = item.year
        except Exception:
            logger.info(
                "MCP native gallery metadata lookup failed for rating_key=%s",
                rating_key,
                exc_info=True,
            )

        label = _native_poster_label(rating_key, title=title, year=year)
        item_metadata = {
            "rating_key": rating_key,
            "title": title,
            "year": year,
            "media_type": media_type,
            "found": False,
        }
        try:
            poster = _fetch_native_poster(rating_key)
        except Exception as exc:
            message = str(exc) if isinstance(exc, NativePosterError) else "Unable to fetch the poster."
            result_content.append(
                TextContent(type="text", text=f"Poster unavailable for {label}: {message}")
            )
            result_items.append({**item_metadata, "error": message})
            continue

        if poster is None:
            result_content.append(
                TextContent(type="text", text=f"Poster unavailable for {label}.")
            )
            result_items.append(item_metadata)
            continue

        content, mime_type = poster
        result_content.extend(
            [
                TextContent(type="text", text=f"Poster for {label}."),
                _native_image_content(content, mime_type),
            ]
        )
        result_items.append({**item_metadata, "found": True})

    return CallToolResult(
        content=result_content,
        structuredContent={"count": len(result_items), "items": result_items},
    )


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
            await auth_result.response(scope, receive, send)
            return

        auth_token = mcp_auth_context.set(auth_result.context)
        settings_token = mcp_runtime_settings_context.set(settings)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.runtime.get_asgi_app()(scope, receive, send_wrapper)
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
    """Alias canonical /mcp to the slash-requiring mount without touching the request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            root_path = scope.get("root_path", "")
            original_path = scope.get("path", "")
            mounted_path = f"{root_path}/mcp"
            is_no_slash_alias = original_path == mounted_path
            if is_no_slash_alias or original_path == f"{mounted_path}/":
                headers = Headers(scope=scope)
                logger.info(
                    "MCP boundary original_path=%s content_type=%s content_length=%s "
                    "transfer_encoding=%s authorization_present=%s no_slash_alias=%s",
                    original_path,
                    headers.get("content-type"),
                    headers.get("content-length"),
                    headers.get("transfer-encoding"),
                    "authorization" in headers,
                    is_no_slash_alias,
                )
            if is_no_slash_alias:
                scope = dict(scope)
                scope["path"] = f"{scope['path']}/"
        await self.app(scope, receive, send)


def _build_mcp_server() -> FastMCP:
    server_name = get_setting_value("mcp.server_name", default="PlexIntel")
    instructions = get_setting_value("mcp.instructions")
    instruction_parts = [
        part
        for part in (
            instructions,
            USER_IDENTITY_INSTRUCTIONS,
            POSTER_RESPONSE_INSTRUCTIONS,
            RECENT_ADDITIONS_UI_INSTRUCTIONS,
        )
        if part
    ]
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

    def oauth_tool_security_schemes() -> list[dict[str, Any]]:
        return [{"type": "oauth2", "scopes": list(oauth_settings.required_scopes)}]

    @mcp.resource(
        RECENT_ADDITIONS_WIDGET_URI,
        name="recent-library-additions",
        title="PlexIntel recent library additions",
        description="Responsive PlexIntel poster table for finalized recent library additions.",
        mime_type=RECENT_ADDITIONS_WIDGET_MIME_TYPE,
        meta={
            "ui": {
                "prefersBorder": True,
                "csp": {
                    "resourceDomains": [RECENT_ADDITIONS_POSTER_ORIGIN],
                },
            },
            "openai/widgetPrefersBorder": True,
            "openai/widgetCSP": {
                "resource_domains": [RECENT_ADDITIONS_POSTER_ORIGIN],
            },
        },
    )
    def recent_library_additions_widget() -> str:
        return _read_recent_additions_widget()

    @mcp.tool(
        name="list_users",
        description="List PlexIntel users by username or friendly name.",
        structured_output=True,
        annotations=tool_annotations,
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
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
        security_schemes=oauth_tool_security_schemes(),
    )
    def mcp_get_poster_gallery(
        rating_keys: Optional[list[int]] = None,
        items: Optional[list[dict[str, Any]]] = None,
    ) -> CallToolResult:
        return build_poster_gallery_result(rating_keys=rating_keys, items=items)

    @mcp.tool(
        name="get_poster_image_native",
        description=(
            "Returns the selected poster as native MCP image content for direct display "
            "alongside the library-item metadata."
        ),
        annotations=tool_annotations,
        security_schemes=oauth_tool_security_schemes(),
    )
    def mcp_get_poster_image_native(rating_key: int) -> CallToolResult:
        return build_poster_image_native_result(rating_key)

    @mcp.tool(
        name="get_poster_gallery_native",
        description=(
            "Returns native MCP poster images in library-item order, with a text label "
            "immediately before each corresponding image. Pass either rating_keys or items "
            "containing rating_key and optional title."
        ),
        annotations=tool_annotations,
        security_schemes=oauth_tool_security_schemes(),
    )
    def mcp_get_poster_gallery_native(
        rating_keys: Optional[list[int]] = None,
        items: Optional[list[dict[str, Any]]] = None,
    ) -> CallToolResult:
        return build_poster_gallery_native_result(rating_keys=rating_keys, items=items)

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
        security_schemes=oauth_tool_security_schemes(),
    )
    def mcp_get_recent_library_additions(
        media_type: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 50,
    ) -> RecentLibraryAdditionsResponse:
        return get_recent_library_additions(media_type=media_type, days=days, limit=limit)

    @mcp.tool(
        name="render_recent_library_additions",
        description=(
            "Render finalized recent PlexIntel library additions as a visual poster table or "
            "responsive card list. Always call get_recent_library_additions first, review or "
            "filter its records, then pass those items and its days value to this tool. Use this "
            "when the user asks for recent additions with posters, a visual table, cards, or a "
            "gallery. For an individual-poster request, continue using the existing native poster "
            "tools when native MCP image content is appropriate."
        ),
        annotations=tool_annotations,
        meta={
            "ui": {"resourceUri": RECENT_ADDITIONS_WIDGET_URI},
            "openai/outputTemplate": RECENT_ADDITIONS_WIDGET_URI,
            "openai/toolInvocation/invoking": "Preparing recent additions…",
            "openai/toolInvocation/invoked": "Recent additions ready.",
        },
        security_schemes=oauth_tool_security_schemes(),
    )
    def mcp_render_recent_library_additions(
        items: list[RecentAdditionRenderItem],
        days: Annotated[int | None, Field(ge=1)] = None,
    ) -> CallToolResult:
        return build_recent_additions_render_result(items, days=days)

    mcp.set_tool_output_schema(
        "render_recent_library_additions",
        RecentAdditionsRenderResponse.model_json_schema(),
    )

    @mcp.tool(
        name="get_watch_history",
        description=(
            "Return enriched Plex watch history records for the authenticated user. "
            "Omit user to scope to the authenticated user."
        ),
        structured_output=True,
        annotations=tool_annotations,
        security_schemes=oauth_tool_security_schemes(),
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
