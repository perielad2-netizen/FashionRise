"""user_friendships for Runway private Friends circle

Revision ID: 021
Revises: 020
Create Date: 2026-11-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_friendships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_low_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_high_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("addressee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
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
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["addressee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_user_friendships_pair"),
        sa.CheckConstraint("user_low_id <> user_high_id", name="ck_user_friendships_not_self"),
        sa.CheckConstraint(
            "requester_id = user_low_id OR requester_id = user_high_id",
            name="ck_user_friendships_requester_in_pair",
        ),
        sa.CheckConstraint(
            "addressee_id = user_low_id OR addressee_id = user_high_id",
            name="ck_user_friendships_addressee_in_pair",
        ),
        sa.CheckConstraint("requester_id <> addressee_id", name="ck_user_friendships_req_ne_addr"),
    )
    op.create_index("ix_user_friendships_requester_id", "user_friendships", ["requester_id"])
    op.create_index("ix_user_friendships_addressee_id", "user_friendships", ["addressee_id"])
    op.create_index("ix_user_friendships_user_low_id", "user_friendships", ["user_low_id"])
    op.create_index("ix_user_friendships_user_high_id", "user_friendships", ["user_high_id"])
    op.create_index("ix_user_friendships_status", "user_friendships", ["status"])


def downgrade() -> None:
    op.drop_index("ix_user_friendships_status", table_name="user_friendships", if_exists=True)
    op.drop_index("ix_user_friendships_user_high_id", table_name="user_friendships", if_exists=True)
    op.drop_index("ix_user_friendships_user_low_id", table_name="user_friendships", if_exists=True)
    op.drop_index("ix_user_friendships_addressee_id", table_name="user_friendships", if_exists=True)
    op.drop_index("ix_user_friendships_requester_id", table_name="user_friendships", if_exists=True)
    op.drop_table("user_friendships", if_exists=True)
