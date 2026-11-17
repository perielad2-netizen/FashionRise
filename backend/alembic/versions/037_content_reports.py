"""User content reports for FashionRise Social looks/designers.

Revision ID: 037
Revises: 036
Create Date: 2026-11-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reported_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gallery_item_id"], ["gallery_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reported_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("reporter_id", "gallery_item_id", name="uq_content_reports_reporter_item"),
        sa.CheckConstraint(
            "reason IN ("
            "'sexual_content', 'harassment', 'hate', 'spam', 'impersonation', 'other'"
            ")",
            name="ck_content_reports_reason",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'reviewed', 'actioned', 'dismissed')",
            name="ck_content_reports_status",
        ),
    )
    op.create_index("ix_content_reports_reporter_id", "content_reports", ["reporter_id"])
    op.create_index("ix_content_reports_gallery_item_id", "content_reports", ["gallery_item_id"])
    op.create_index("ix_content_reports_reported_user_id", "content_reports", ["reported_user_id"])
    op.create_index("ix_content_reports_status", "content_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_content_reports_status", table_name="content_reports")
    op.drop_index("ix_content_reports_reported_user_id", table_name="content_reports")
    op.drop_index("ix_content_reports_gallery_item_id", table_name="content_reports")
    op.drop_index("ix_content_reports_reporter_id", table_name="content_reports")
    op.drop_table("content_reports")
