from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mcp.server.auth.middleware.auth_context import get_access_token

from app.auth.principal import Principal
from app.auth.provider import IdentityProvider

_bearer = HTTPBearer(auto_error=False)


async def current_rest_principal(
    request: Request,
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credential is None or credential.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer authentication required")
    identity: IdentityProvider = request.app.state.identity
    access = await identity.verify_token(credential.credentials)
    if access is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return identity.principal_from_access_token(access)


def current_mcp_principal(identity: IdentityProvider) -> Principal:
    access = get_access_token()
    if access is None:
        raise PermissionError("Authenticated MCP request required")
    return identity.principal_from_access_token(access)
