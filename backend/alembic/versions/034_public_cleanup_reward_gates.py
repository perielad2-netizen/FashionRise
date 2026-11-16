"""Public My Models cleanup queue + streak reward-eligible columns.

Revision ID: 034
Revises: 033
Create Date: 2026-11-16

Reward enable flags remain config-only. This migration adds:
- ``public_media_cleanup_queue`` (durable / quarantine public unlink)
- ``login_streaks.reward_streak`` + ``last_reward_checkin_date``
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "public_media_cleanup_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("croquis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("source_url_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_public_media_cleanup_queue_owner_id",
        "public_media_cleanup_queue",
        ["owner_id"],
    )
    op.create_index(
        "ix_public_media_cleanup_queue_storage_key",
        "public_media_cleanup_queue",
        ["storage_key"],
    )
    op.create_index(
        "ix_public_media_cleanup_queue_pending",
        "public_media_cleanup_queue",
        ["status", "processed_at", "enqueued_at"],
    )

    op.add_column(
        "login_streaks",
        sa.Column("reward_streak", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "login_streaks",
        sa.Column("last_reward_checkin_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("login_streaks", "last_reward_checkin_date")
    op.drop_column("login_streaks", "reward_streak")
    op.drop_index("ix_public_media_cleanup_queue_pending", table_name="public_media_cleanup_queue")
    op.drop_index(
        "ix_public_media_cleanup_queue_storage_key", table_name="public_media_cleanup_queue"
    )
    op.drop_index("ix_public_media_cleanup_queue_owner_id", table_name="public_media_cleanup_queue")
    op.drop_table("public_media_cleanup_queue")
