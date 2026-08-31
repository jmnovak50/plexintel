"""Private Immich credential provider boundary."""

from typing import Protocol

from app.immich.models import AuthenticatedUser, PrivateImmichCredential


class PrivateImmichCredentialProvider(Protocol):
    async def credential_for(self, user: AuthenticatedUser) -> PrivateImmichCredential | None: ...


class UnsupportedDelegationProvider:
    async def credential_for(self, user: AuthenticatedUser) -> None:
        return None
