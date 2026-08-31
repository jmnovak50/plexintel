from pydantic import AnyHttpUrl

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from app.auth.oidc import OIDCJWTVerifier
from app.config import Settings
from app.immich.client import ImmichClient
from app.mcp.tools.shared import register_shared_tools


def create_mcp_server(settings: Settings, client: ImmichClient, verifier: OIDCJWTVerifier) -> MCPServer:
    server = MCPServer(
        "Immich MCP",
        instructions=(
            "Read Immich public album shares. Share keys are capability credentials; do not reveal them. "
            "Private-library tools are unavailable until Immich supports safe per-user delegation."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.oidc_issuer)),
            resource_server_url=AnyHttpUrl(str(settings.mcp_public_url)),
            required_scopes=settings.required_scopes,
        ),
        token_verifier=verifier,
    )
    register_shared_tools(server, client, settings)
    return server

