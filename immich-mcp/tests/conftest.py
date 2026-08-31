import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        immich_base_url="https://photo.example.com",
        oidc_issuer="https://auth.example.com/application/o/immich-mcp/",
        oidc_client_id="immich-mcp",
        oidc_audience="immich-mcp",
        mcp_public_url="https://mcp.example.com/mcp",
        http_max_retries=0,
    )

