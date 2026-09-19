from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.auth.dependencies import current_mcp_principal
from app.auth.provider import IdentityProvider
from app.config import Settings
from app.mealie.errors import MealieConnectionNotConfigured, MealieError
from app.services.connections import ConnectionService

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def register_connection_tools(
    server: MCPServer,
    settings: Settings,
    identity: IdentityProvider,
    connections: ConnectionService,
) -> None:
    @server.tool(annotations=READ_ONLY, structured_output=True)
    async def get_mealie_connection_status() -> dict[str, Any]:
        """Check whether the authenticated user has connected their Mealie account.

        Call this before private Mealie tools when connection state is unknown. If
        connected is false, direct the user to accountUrl and check again after they
        connect or reconnect. Never ask the user for their Mealie API token in chat.
        """
        status = await connections.default_status(current_mcp_principal(identity))
        account_url = str(settings.account_public_url)
        if status is None:
            return {
                "connected": False,
                "actionRequired": "connect_mealie_account",
                "message": (
                    "This user has not connected their Mealie account. "
                    "Ask them to visit accountUrl before continuing."
                ),
                "accountUrl": account_url,
            }
        return {
            "connected": True,
            "name": status.name,
            "server": status.server,
            "status": status.status.value,
            "version": status.version,
            "lastValidatedAt": (status.last_validated_at.isoformat() if status.last_validated_at else None),
            "capabilities": status.capabilities,
            "accountUrl": account_url,
        }


def private_error(exc: Exception, settings: Settings) -> Exception:
    if isinstance(exc, MealieConnectionNotConfigured):
        return ToolError(
            f"Mealie is not connected for this user. Visit {settings.account_public_url} "
            "to connect your Mealie account. Do not automatically retry this call."
        )
    if isinstance(exc, (MealieError, ValueError)):
        return ToolError(f"{type(exc).__name__}: {exc}. Do not automatically retry this call.")
    return exc
