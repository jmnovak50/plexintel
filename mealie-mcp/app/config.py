from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_network
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore", case_sensitive=False)

    environment: Literal["development", "test", "production"] = "development"
    deployment_mode: Literal["self_hosted", "saas"] = "self_hosted"
    database_url: str = "postgresql+asyncpg://mealie_mcp:mealie_mcp@postgres/mealie_mcp"

    oidc_issuer: AnyHttpUrl
    oidc_audience: str = Field(min_length=1)
    oidc_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    oidc_required_scopes: list[str] = Field(default_factory=lambda: ["mealie.read"])
    oidc_cache_seconds: int = Field(default=300, ge=30, le=86400)
    oidc_unknown_kid_refresh_seconds: int = Field(default=30, ge=5, le=3600)
    identity_namespace: str = Field(default="authentik", min_length=1, max_length=100)
    default_tenant_id: str = Field(default="self-hosted", min_length=1, max_length=100)

    mcp_public_url: AnyHttpUrl
    mcp_allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    mcp_allowed_origins: list[str] = Field(default_factory=list)

    credential_encryption_key: SecretStr
    mealie_private_networks: list[str] = Field(default_factory=list)
    mealie_allowed_hosts: list[str] = Field(default_factory=list)
    mealie_allow_http: bool = False
    mealie_connect_timeout_seconds: float = Field(default=5, gt=0, le=60)
    mealie_read_timeout_seconds: float = Field(default=20, gt=0, le=300)
    mealie_max_response_bytes: int = Field(default=5_000_000, ge=1024, le=50_000_000)
    mealie_max_schema_bytes: int = Field(default=10_000_000, ge=1024, le=50_000_000)
    mealie_max_retries: int = Field(default=1, ge=0, le=3)

    log_level: str = "INFO"

    @field_validator(
        "oidc_algorithms",
        "oidc_required_scopes",
        "mcp_allowed_hosts",
        "mcp_allowed_origins",
        "mealie_private_networks",
        "mealie_allowed_hosts",
        mode="before",
    )
    @classmethod
    def comma_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("oidc_algorithms")
    @classmethod
    def asymmetric_algorithms_only(cls, values: list[str]) -> list[str]:
        allowed = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}
        if not values or any(value not in allowed for value in values):
            raise ValueError("OIDC_ALGORITHMS must contain only approved asymmetric algorithms")
        return values

    @field_validator("mealie_private_networks")
    @classmethod
    def valid_networks(cls, values: list[str]) -> list[str]:
        for value in values:
            ip_network(value, strict=False)
        return values

    @model_validator(mode="after")
    def saas_invariants(self) -> Settings:
        if self.deployment_mode == "saas" and self.mealie_allow_http:
            raise ValueError("MEALIE_ALLOW_HTTP cannot be enabled in SaaS mode")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
