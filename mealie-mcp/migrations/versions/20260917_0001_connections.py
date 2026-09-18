"""create per-user Mealie connections

Revision ID: 20260917_0001
Revises:
Create Date: 2026-09-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260917_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection_status = postgresql.ENUM(
        "pending",
        "active",
        "degraded",
        "invalid",
        "disabled",
        name="connectionstatus",
        create_type=False,
    )
    schema_source = postgresql.ENUM("live", "cached", name="schemasource", create_type=False)
    connection_status.create(op.get_bind(), checkfirst=True)
    schema_source.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "mealie_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("encrypted_api_token", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("mealie_user_id", sa.String(length=128), nullable=True),
        sa.Column("mealie_version", sa.String(length=64), nullable=True),
        sa.Column("openapi_schema_hash", sa.String(length=64), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("schema_source", schema_source, nullable=True),
        sa.Column("status", connection_status, nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "name", name="uq_connection_owner_name"),
    )
    op.create_index("ix_connection_owner", "mealie_connections", ["tenant_id", "user_id"])
    op.create_index(
        "uq_connection_owner_default",
        "mealie_connections",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index("uq_connection_owner_default", table_name="mealie_connections")
    op.drop_index("ix_connection_owner", table_name="mealie_connections")
    op.drop_table("mealie_connections")
    postgresql.ENUM(name="schemasource").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="connectionstatus").drop(op.get_bind(), checkfirst=True)
