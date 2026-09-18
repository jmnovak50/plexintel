from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConnectionStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    degraded = "degraded"
    invalid = "invalid"
    disabled = "disabled"


class SchemaSource(str, enum.Enum):
    live = "live"
    cached = "cached"


class MealieConnection(Base):
    __tablename__ = "mealie_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "name", name="uq_connection_owner_name"),
        Index("ix_connection_owner", "tenant_id", "user_id"),
        Index(
            "uq_connection_owner_default",
            "tenant_id",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default = 1"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column()
    user_id: Mapped[uuid.UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(String(2048))
    encrypted_api_token: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    mealie_user_id: Mapped[str | None] = mapped_column(String(128))
    mealie_version: Mapped[str | None] = mapped_column(String(64))
    openapi_schema_hash: Mapped[str | None] = mapped_column(String(64))
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    schema_source: Mapped[SchemaSource | None] = mapped_column(Enum(SchemaSource))
    status: Mapped[ConnectionStatus] = mapped_column(Enum(ConnectionStatus), default=ConnectionStatus.pending)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"MealieConnection(id={self.id!r}, tenant_id={self.tenant_id!r}, "
            f"user_id={self.user_id!r}, name={self.name!r}, status={self.status!r})"
        )


class AccountOAuthState(Base):
    __tablename__ = "account_oauth_states"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nonce: Mapped[str] = mapped_column(String(256))
    code_verifier: Mapped[str] = mapped_column(String(256))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountSession(Base):
    __tablename__ = "account_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str] = mapped_column(String(2048))
    email: Mapped[str | None] = mapped_column(String(320))
    preferred_username: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
