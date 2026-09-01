from mcp.server.auth.middleware.auth_context import get_access_token

from app.immich.models import AuthenticatedUser


def current_user() -> AuthenticatedUser:
    token = get_access_token()
    if token is None or not token.subject:
        raise PermissionError("Authenticated MCP request required")
    claims = token.claims or {}
    identity_namespace = claims.get("identity_namespace")
    if not isinstance(identity_namespace, str) or not identity_namespace:
        raise PermissionError("Authenticated MCP identity namespace is unavailable")
    return AuthenticatedUser(
        identity_namespace=identity_namespace,
        issuer=str(claims.get("iss") or ""),
        sub=token.subject,
        email=claims.get("email"),
        preferred_username=claims.get("preferred_username"),
        scopes=token.scopes,
    )
