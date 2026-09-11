from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl

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
            "The caller cannot choose another user's credential. "
            "Before using any private Immich tool, if the user's Immich connection state is not already "
            "known for this conversation, call get_immich_connection_status first. "
            "If get_immich_connection_status returns connected=false, do not attempt other private tools. "
            "Tell the user that their Immich account must be connected and direct them to the accountUrl "
            "returned by the tool. "
            "After the user says they have connected or reconnected their Immich account, call "
            "get_immich_connection_status again before continuing. "
            "For an exact filename use find_asset_by_filename, never semantic search; resolve ambiguity. "
            "Reuse known album/asset IDs and successful image results. For a one-photo request fetch "
            "one image only. For unspecified highlights, select "
            f"{settings.image_highlight_count} photos from at most {settings.image_candidate_limit} "
            "candidate thumbnails; state that this is a sample, not an exhaustive album review. "
            "Use get_asset_thumbnail with size='thumbnail' for initial browsing; request size='preview' "
            "only when more detail is needed. Shared-link image tools follow the same size guidance. "
            f"Use batches of at most {min(settings.image_per_credential_concurrency, settings.image_max_concurrency)} "
            "image calls, awaiting each batch before starting the next. Honor explicitly larger selections "
            "through bounded batches; never launch unbounded image fan-out. Keep successful results when "
            "some images fail. The server already retries transient upstream failures; do not automatically "
            "repeat failed calls or the whole selection. Report partial failures and stop on connection errors. "
            "For display, reuse a client-provided image attachment or file reference when available. "
            "Native MCP image content supports vision; visible rendering depends on the client. "
            "Never reproduce image base64 in prose, generated commands, or text tool arguments. "
            "Do not claim a photo is displayed unless a supported client display path was used. "
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
