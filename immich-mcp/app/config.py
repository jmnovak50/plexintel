from functools import lru_cache
from urllib.parse import urlsplit

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

    @field_validator("oidc_issuer", "immich_base_url", "mcp_public_url")
    @classmethod
    def no_url_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
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


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
