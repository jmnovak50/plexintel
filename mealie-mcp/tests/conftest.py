from __future__ import annotations

import ipaddress
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

from app.auth.principal import Principal
from app.config import Settings
from app.db.base import Base
from app.db.session import Database

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        deployment_mode="saas",
        database_url="sqlite+aiosqlite://",
        oidc_issuer="https://auth.example.com/application/o/mealie-mcp/",
        oidc_audience="mealie-mcp-client",
        oidc_required_scopes=["mealie.read"],
        mcp_public_url="https://mcp.example.com/mcp",
        mcp_allowed_hosts=["mcp.example.com"],
        credential_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    )


@pytest_asyncio.fixture
async def database() -> Database:
    db = Database("sqlite+aiosqlite://")
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield db
    await db.aclose()


def principal(subject: str, tenant: str = "tenant") -> Principal:
    return Principal(
        subject=subject,
        user_id=uuid.uuid5(uuid.NAMESPACE_URL, f"user:{subject}"),
        tenant_id=uuid.uuid5(uuid.NAMESPACE_URL, f"tenant:{tenant}"),
        email=f"{subject}@example.com",
        scopes=frozenset({"mealie.read"}),
        issuer="https://auth.example.com/application/o/mealie-mcp/",
    )


async def public_resolver(hostname: str, port: int):
    return {ipaddress.ip_address("8.8.8.8")}
