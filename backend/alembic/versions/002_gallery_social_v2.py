"""gallery likes and comments (V2 social)

Revision ID: 002
Revises: 001
Create Date: 2026-05-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gallery_likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["gallery_item_id"], ["gallery_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "gallery_item_id", name="uq_gallery_likes_user_item"),
    )
    op.create_index(op.f("ix_gallery_likes_gallery_item_id"), "gallery_likes", ["gallery_item_id"], unique=False)
    op.create_index(op.f("ix_gallery_likes_user_id"), "gallery_likes", ["user_id"], unique=False)

    op.create_table(
        "gallery_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gallery_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("moderation_status", sa.String(length=32), server_default=sa.text("'ok'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["gallery_item_id"], ["gallery_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_gallery_comments_gallery_item_id"), "gallery_comments", ["gallery_item_id"], unique=False
    )
    op.create_index(op.f("ix_gallery_comments_user_id"), "gallery_comments", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_gallery_comments_user_id"), table_name="gallery_comments", if_exists=True)
    op.drop_index(
        op.f("ix_gallery_comments_gallery_item_id"), table_name="gallery_comments", if_exists=True
    )
    op.drop_table("gallery_comments", if_exists=True)
    op.drop_index(op.f("ix_gallery_likes_user_id"), table_name="gallery_likes", if_exists=True)
    op.drop_index(op.f("ix_gallery_likes_gallery_item_id"), table_name="gallery_likes", if_exists=True)
    op.drop_table("gallery_likes", if_exists=True)
