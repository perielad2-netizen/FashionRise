"""user_follows for creator following + following gallery feed

Revision ID: 003
Revises: 002
Create Date: 2026-05-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("following_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["following_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "following_id"),
    )
    op.create_index("ix_user_follows_follower_id", "user_follows", ["follower_id"], unique=False)
    op.create_index("ix_user_follows_following_id", "user_follows", ["following_id"], unique=False)


def downgrade() -> None:
    # if_exists: tolerate stamped-but-partial DBs (indexes/table may never have been created).
    op.drop_index("ix_user_follows_following_id", table_name="user_follows", if_exists=True)
    op.drop_index("ix_user_follows_follower_id", table_name="user_follows", if_exists=True)
    op.drop_table("user_follows", if_exists=True)
