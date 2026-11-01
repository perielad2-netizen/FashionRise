"""techpack_drafts + techpack_exports for Create Real Design

Revision ID: 008
Revises: 007
Create Date: 2026-10-26

Owner-scoped editable tech-pack drafts keyed by Magic look_id.
No FK cascade from looks/meta — deleting a look must not erase drafts.
PDF bytes live under private storage (not /static/uploads).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "techpack_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("look_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("style_code", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column(
            "verification",
            sa.String(length=32),
            server_default=sa.text("'UNVERIFIED'"),
            nullable=False,
        ),
        sa.Column(
            "spec",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("front_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("back_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["design_id"], ["garment_designs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_techpack_drafts_user_id", "techpack_drafts", ["user_id"], unique=False)
    op.create_index("ix_techpack_drafts_look_id", "techpack_drafts", ["look_id"], unique=False)
    op.create_index(
        "ix_techpack_drafts_user_look",
        "techpack_drafts",
        ["user_id", "look_id"],
        unique=False,
    )
    op.create_index(
        "ix_techpack_drafts_user_updated",
        "techpack_drafts",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "techpack_exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verification", sa.String(length=32), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["techpack_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_techpack_exports_draft_id", "techpack_exports", ["draft_id"], unique=False)
    op.create_index("ix_techpack_exports_user_id", "techpack_exports", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_techpack_exports_user_id", table_name="techpack_exports")
    op.drop_index("ix_techpack_exports_draft_id", table_name="techpack_exports")
    op.drop_table("techpack_exports")
    op.drop_index("ix_techpack_drafts_user_updated", table_name="techpack_drafts")
    op.drop_index("ix_techpack_drafts_user_look", table_name="techpack_drafts")
    op.drop_index("ix_techpack_drafts_look_id", table_name="techpack_drafts")
    op.drop_index("ix_techpack_drafts_user_id", table_name="techpack_drafts")
    op.drop_table("techpack_drafts")
