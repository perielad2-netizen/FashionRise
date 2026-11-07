"""gallery_comment_likes + comments.likes_count

Revision ID: 022
Revises: 021
Create Date: 2026-11-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gallery_comments",
        sa.Column(
            "likes_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_table(
        "gallery_comment_likes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["gallery_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "comment_id", name="uq_gallery_comment_likes_user_comment"),
    )
    op.create_index(
        "ix_gallery_comment_likes_user_id", "gallery_comment_likes", ["user_id"], unique=False
    )
    op.create_index(
        "ix_gallery_comment_likes_comment_id",
        "gallery_comment_likes",
        ["comment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_gallery_comment_likes_comment_id", table_name="gallery_comment_likes")
    op.drop_index("ix_gallery_comment_likes_user_id", table_name="gallery_comment_likes")
    op.drop_table("gallery_comment_likes")
    op.drop_column("gallery_comments", "likes_count")
