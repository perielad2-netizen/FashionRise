"""Account classification for Admin 2.0 (independent of is_admin).

Revision ID: 043
Revises: 042
Create Date: 2026-11-25

Adds operator-authored customer classification + audit history.
Does NOT auto-classify existing accounts (remain unclassified).
Does NOT grant or revoke admin permissions.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CLASSIFICATIONS = (
    "CUSTOMER",
    "OWNER",
    "ADMIN",
    "INTERNAL_TESTER",
    "QA_AUTOMATION",
    "DEMO_ACCOUNT",
    "UNCLASSIFIED",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_classification",
            sa.String(32),
            nullable=False,
            server_default="UNCLASSIFIED",
        ),
    )
    op.add_column(
        "users",
        sa.Column("account_classification_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "account_classification_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "account_classification_updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_account_classification",
        "users",
        ["account_classification"],
    )

    op.create_table(
        "account_classification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("from_classification", sa.String(32), nullable=False),
        sa.Column("to_classification", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_account_classification_events_user_id",
        "account_classification_events",
        ["user_id"],
    )
    op.create_index(
        "ix_account_classification_events_created_at",
        "account_classification_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_classification_events_created_at",
        table_name="account_classification_events",
    )
    op.drop_index(
        "ix_account_classification_events_user_id",
        table_name="account_classification_events",
    )
    op.drop_table("account_classification_events")
    op.drop_index("ix_users_account_classification", table_name="users")
    op.drop_column("users", "account_classification_updated_by_id")
    op.drop_column("users", "account_classification_updated_at")
    op.drop_column("users", "account_classification_note")
    op.drop_column("users", "account_classification")
