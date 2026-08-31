from mcp.server.auth.middleware.auth_context import get_access_token

from app.immich.models import AuthenticatedUser


def current_user() -> AuthenticatedUser:
    token = get_access_token()
    if token is None or not token.subject:
        raise PermissionError("Authenticated MCP request required")
    claims = token.claims or {}
    return AuthenticatedUser(
        issuer=str(claims.get("iss") or ""),
        sub=token.subject,
        email=claims.get("email"),
        preferred_username=claims.get("preferred_username"),
        scopes=token.scopes,
    )
