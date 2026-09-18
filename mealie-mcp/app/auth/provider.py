from __future__ import annotations

from typing import Protocol

from mcp.server.auth.provider import AccessToken

from app.auth.principal import Principal


class IdentityProvider(Protocol):
    async def verify_token(self, token: str) -> AccessToken | None: ...

    def principal_from_access_token(self, token: AccessToken) -> Principal: ...

    async def warm(self) -> None: ...

    async def aclose(self) -> None: ...
