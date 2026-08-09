from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.services.mcp_auth import get_mcp_oauth_settings


router = APIRouter()


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
async def oauth_protected_resource_metadata() -> JSONResponse:
    settings = get_mcp_oauth_settings()
    if not settings.resource_url or not settings.issuer_url or not settings.required_scopes:
        return JSONResponse(
            {
                "detail": (
                    "MCP OAuth protected-resource metadata is unavailable because the resource, issuer, "
                    "or required scopes are not configured."
                )
            },
            status_code=503,
        )
    return JSONResponse(
        {
            "resource": settings.resource_url,
            "authorization_servers": [settings.issuer_url],
            "scopes_supported": list(settings.required_scopes),
        }
    )
