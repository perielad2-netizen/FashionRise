"""magic_look_meta.is_deleted tombstone for My Looks delete

Revision ID: 007
Revises: 006
Create Date: 2026-10-26

Additive tombstone so deleted looks stay excluded from the gallery without
erasing ai_jobs rows or generated image files.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "magic_look_meta",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "magic_look_meta",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_magic_look_meta_user_deleted",
        "magic_look_meta",
        ["user_id", "is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_magic_look_meta_user_deleted", table_name="magic_look_meta")
    op.drop_column("magic_look_meta", "deleted_at")
    op.drop_column("magic_look_meta", "is_deleted")
