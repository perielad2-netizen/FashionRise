"""magic_look_meta for My Looks titles/favorites/archive

Revision ID: 006
Revises: 005
Create Date: 2026-10-26

Owner-scoped metadata for completed Magic looks. Look identity is either a
magic_operation_id (dual) or a single sketch_polish job id. Generated images
and ai_jobs rows remain the source of truth for artwork.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "magic_look_meta",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_magic_look_meta_user_id", "magic_look_meta", ["user_id"], unique=False)
    op.create_index(
        "ix_magic_look_meta_user_archived_favorite",
        "magic_look_meta",
        ["user_id", "is_archived", "is_favorite"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_magic_look_meta_user_archived_favorite", table_name="magic_look_meta")
    op.drop_index("ix_magic_look_meta_user_id", table_name="magic_look_meta")
    op.drop_table("magic_look_meta")
