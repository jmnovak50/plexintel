from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    immich_base_url: AnyHttpUrl
    oidc_issuer: AnyHttpUrl
    oidc_client_id: str
    oidc_client_secret: SecretStr | None = None
    oidc_audience: str | None = None
    oidc_required_scope: str = "immich.read"
    mcp_public_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000/mcp")

    private_access_enabled: bool = True
    credential_db_path: Path = Path("/data/credentials.sqlite3")
    credential_encryption_key: SecretStr | None = None
    account_oidc_client_id: str | None = None
    account_oidc_client_secret: SecretStr | None = None
    account_redirect_uri: AnyHttpUrl | None = None
    account_public_url: AnyHttpUrl | None = None
    account_session_secret: SecretStr | None = None
    account_cookie_secure: bool = True
    account_session_ttl_seconds: int = Field(default=28_800, ge=300, le=604_800)
    account_oauth_state_ttl_seconds: int = Field(default=600, ge=60, le=1800)
    account_oidc_scopes: str = "openid profile email"
    private_tool_max_items: int = Field(default=100, ge=1, le=1000)

    tls_verify: bool = True
    http_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    http_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    http_max_retries: int = Field(default=2, ge=0, le=5)
    max_image_bytes: int = Field(default=10_000_000, ge=1024, le=50_000_000)
    gallery_inline_image_limit: int = Field(default=6, ge=0, le=12)
    gallery_max_items: int = Field(default=50, ge=1, le=200)
    allowed_hosts: str = "localhost:*,127.0.0.1:*"
    allowed_origins: str = ""
    log_level: str = "INFO"

    @field_validator(
        "oidc_issuer", "immich_base_url", "mcp_public_url", "account_redirect_uri", "account_public_url"
    )
    @classmethod
    def no_url_credentials(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return value
        parts = urlsplit(str(value))
        if parts.username or parts.password:
            raise ValueError("URL credentials are not allowed")
        if parts.scheme not in {"http", "https"}:
            raise ValueError("only http(s) URLs are allowed")
        return value

    @model_validator(mode="after")
    def default_audience(self) -> "Settings":
        if self.oidc_audience is None:
            self.oidc_audience = self.oidc_client_id
        if self.private_access_enabled:
            missing = [
                name
                for name, value in {
                    "CREDENTIAL_ENCRYPTION_KEY": self.credential_encryption_key,
                    "ACCOUNT_OIDC_CLIENT_ID": self.account_oidc_client_id,
                    "ACCOUNT_OIDC_CLIENT_SECRET": self.account_oidc_client_secret,
                    "ACCOUNT_REDIRECT_URI": self.account_redirect_uri,
                    "ACCOUNT_PUBLIC_URL": self.account_public_url,
                    "ACCOUNT_SESSION_SECRET": self.account_session_secret,
                }.items()
                if value is None
                or (isinstance(value, str) and not value.strip())
                or (isinstance(value, SecretStr) and not value.get_secret_value())
            ]
            if missing:
                raise ValueError("private access requires: " + ", ".join(missing))
            try:
                Fernet(self.credential_encryption_key.get_secret_value().encode("ascii"))  # type: ignore[union-attr]
            except (ValueError, TypeError) as exc:
                raise ValueError("CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key") from exc
            if len(self.account_session_secret.get_secret_value()) < 32:  # type: ignore[union-attr]
                raise ValueError("ACCOUNT_SESSION_SECRET must be at least 32 characters")
        return self

    @property
    def immich_origin(self) -> str:
        parts = urlsplit(str(self.immich_base_url))
        default = (parts.scheme == "https" and parts.port in (None, 443)) or (
            parts.scheme == "http" and parts.port in (None, 80)
        )
        authority = parts.hostname if default else f"{parts.hostname}:{parts.port}"
        return f"{parts.scheme}://{authority}"

    @property
    def required_scopes(self) -> list[str]:
        return [scope for scope in self.oidc_required_scope.split() if scope]

    @property
    def account_scopes(self) -> list[str]:
        return [scope for scope in self.account_oidc_scopes.split() if scope]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
