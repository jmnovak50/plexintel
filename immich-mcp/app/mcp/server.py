from pydantic import AnyHttpUrl

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from app.auth.oidc import OIDCJWTVerifier
from app.config import Settings
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient
from app.mcp.tools.albums import register_album_tools
from app.mcp.tools.assets import register_asset_tools
from app.mcp.tools.connection import register_connection_tools
from app.mcp.tools.shared import register_shared_tools


def create_mcp_server(
    settings: Settings,
    client: ImmichClient,
    verifier: OIDCJWTVerifier,
    provider: SQLiteCredentialProvider | None = None,
) -> MCPServer:
    server = MCPServer(
        "Immich MCP",
        instructions=(
            "Read Immich public album shares. Share keys are capability credentials; do not reveal them. "
            "Private tools use the authenticated user's separately connected Immich API key. "
            "The caller cannot choose another user's credential."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.oidc_issuer)),
            resource_server_url=AnyHttpUrl(str(settings.mcp_public_url)),
            required_scopes=settings.required_scopes,
        ),
        token_verifier=verifier,
    )
    register_shared_tools(server, client, settings)
    if provider is not None:
        register_connection_tools(server, provider, settings)
        register_album_tools(server, client, provider, settings)
        register_asset_tools(server, client, provider, settings)
    return server
