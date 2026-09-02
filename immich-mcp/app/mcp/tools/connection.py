from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.auth.dependencies import current_user
from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichForbidden, InvalidImmichCredential
from app.immich.models import PrivateImmichCredential

READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def register_connection_tools(
    server: MCPServer, provider: SQLiteCredentialProvider, settings: Settings
) -> None:
    @server.tool(annotations=READ_ONLY)
    async def get_immich_connection_status() -> dict[str, Any]:
        """Check whether the authenticated user has connected their personal Immich account.

        Call this before using private Immich tools when the user's connection state is unknown.

        If connected is false, do not call other private Immich tools. Tell the user to visit
        the returned accountUrl to connect their Immich account, then check this tool again
        after they complete the connection.
        """
        status = await provider.status_for(current_user())
        if status is None:
            return {
                "connected": False,
                "actionRequired": "connect_immich_account",
                "message": (
                    "This user has not connected their Immich account. "
                    "Ask them to visit accountUrl before continuing."
                ),
                "accountUrl": str(settings.account_public_url)}
        return {
            "connected": True,
            "immichUserId": status.immich_user_id,
            "email": status.immich_email,
            "name": status.immich_name,
            # Backward-compatible output name; this is validation performed on connect/reconnect.
            "lastValidatedAt": status.validated_at_on_connect.isoformat(),
            "accountUrl": str(settings.account_public_url),
        }


async def private_credential(
    provider: SQLiteCredentialProvider, settings: Settings
) -> PrivateImmichCredential:
    credential = await provider.credential_for(current_user())
    if credential is None:
        raise ToolError(
            f"Immich is not connected for this user. Visit {settings.account_public_url} "
            "to connect your Immich account."
        )
    return credential


def private_error(exc: Exception, operation: str, settings: Settings) -> Exception:
    if isinstance(exc, InvalidImmichCredential):
        return ToolError(
            f"The stored Immich credential is no longer valid. Reconnect Immich at "
            f"{settings.account_public_url}."
        )
    if isinstance(exc, ImmichForbidden):
        return ToolError(
            f"Immich denied {operation}; the user's API key lacks the required permission."
        )
    return exc
