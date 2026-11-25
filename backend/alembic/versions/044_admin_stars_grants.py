"""Admin ADD-ONLY Stars grants ledger.

Revision ID: 044
Revises: 043
Create Date: 2026-11-25

Stores durable audit rows for positive-only administrative Stars credits.
Does not change existing wallets. No signed adjustment / deduction API.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_stars_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="ADMIN_GRANT",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_admin_stars_grants_idempotency_key"),
        sa.CheckConstraint("amount > 0", name="ck_admin_stars_grants_amount_positive"),
    )
    op.create_index(
        "ix_admin_stars_grants_recipient_id", "admin_stars_grants", ["recipient_id"]
    )
    op.create_index("ix_admin_stars_grants_actor_id", "admin_stars_grants", ["actor_id"])
    op.create_index(
        "ix_admin_stars_grants_created_at", "admin_stars_grants", ["created_at"]
    )


def downgrade() -> None:
    # Safe only when no legitimate grant rows must be preserved in production.
    # Documented separately — do not auto-run against live financial data.
    op.drop_index("ix_admin_stars_grants_created_at", table_name="admin_stars_grants")
    op.drop_index("ix_admin_stars_grants_actor_id", table_name="admin_stars_grants")
    op.drop_index("ix_admin_stars_grants_recipient_id", table_name="admin_stars_grants")
    op.drop_table("admin_stars_grants")
