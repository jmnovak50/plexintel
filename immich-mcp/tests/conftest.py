import pytest
from cryptography.fernet import Fernet

from app.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        immich_base_url="https://photo.example.com",
        oidc_issuer="https://auth.example.com/application/o/immich-mcp/",
        oidc_client_id="immich-mcp",
        oidc_audience="immich-mcp",
        identity_namespace="authentik",
        mcp_public_url="https://mcp.example.com/mcp",
        credential_db_path=tmp_path / "credentials.sqlite3",
        credential_encryption_key=Fernet.generate_key().decode("ascii"),
        account_oidc_issuer="https://auth.example.com/application/o/immich-mcp-account/",
        account_oidc_client_id="immich-mcp-account",
        account_oidc_client_secret="account-test-secret",
        account_redirect_uri="https://mcp.example.com/account/callback",
        account_public_url="https://mcp.example.com/account",
        account_session_secret="test-session-secret-that-is-long-enough",
        account_cookie_secure=False,
        http_max_retries=0,
    )
