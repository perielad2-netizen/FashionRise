"""Gallery unique impressions for FashionRise Fair Discovery.

Revision ID: 031
Revises: 030
Create Date: 2026-11-16

Adds per-viewer unique impression rows + counters on gallery_items so Discover
can boost new designs and rank by engagement relative to exposure. No awards
or login-streak tables (PR3).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gallery_items",
        sa.Column(
            "impressions_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "gallery_items",
        sa.Column(
            "unique_impressions_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "gallery_impressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("viewer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["gallery_item_id"], ["gallery_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "gallery_item_id",
            "viewer_user_id",
            name="uq_gallery_impressions_item_viewer",
        ),
    )
    op.create_index(
        "ix_gallery_impressions_gallery_item_id",
        "gallery_impressions",
        ["gallery_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_gallery_impressions_viewer_user_id",
        "gallery_impressions",
        ["viewer_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_gallery_impressions_viewer_user_id", table_name="gallery_impressions")
    op.drop_index("ix_gallery_impressions_gallery_item_id", table_name="gallery_impressions")
    op.drop_table("gallery_impressions")
    op.drop_column("gallery_items", "unique_impressions_count")
    op.drop_column("gallery_items", "impressions_count")
