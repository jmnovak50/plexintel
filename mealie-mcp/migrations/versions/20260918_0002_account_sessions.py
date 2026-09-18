"""add browser account OAuth state and sessions

Revision ID: 20260918_0002
Revises: 20260917_0001
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "20260918_0002"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=256), nullable=False),
        sa.Column("code_verifier", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_oauth_states_state_hash",
        "account_oauth_states",
        ["state_hash"],
        unique=True,
    )
    op.create_index(
        "ix_account_oauth_states_expires_at",
        "account_oauth_states",
        ["expires_at"],
    )
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("preferred_username", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_sessions_token_hash",
        "account_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_account_sessions_expires_at",
        "account_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_sessions_expires_at", table_name="account_sessions")
    op.drop_index("ix_account_sessions_token_hash", table_name="account_sessions")
    op.drop_table("account_sessions")
    op.drop_index("ix_account_oauth_states_expires_at", table_name="account_oauth_states")
    op.drop_index("ix_account_oauth_states_state_hash", table_name="account_oauth_states")
    op.drop_table("account_oauth_states")
