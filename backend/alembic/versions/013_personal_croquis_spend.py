"""Create My Croquis Stage C — spend reservations.

Revision ID: 013
Revises: 012
Create Date: 2026-10-31

Concurrency-safe croquis AI spend reservations. Gates remain OFF by default;
operator ceiling defaults to 0 (fail closed). Not applied in production until
separately authorized.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personal_croquis_spend_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("croquis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("estimate_cents", sa.Integer(), nullable=False),
        sa.Column("actual_cost_cents", sa.Integer(), nullable=True),
        sa.Column("provider_called", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_detail", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["croquis_id"], ["personal_croquis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["version_id"], ["personal_croquis_version.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_personal_croquis_spend_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_personal_croquis_spend_reservations_owner_id",
        "personal_croquis_spend_reservations",
        ["owner_id"],
    )
    op.create_index(
        "ix_personal_croquis_spend_reservations_croquis_id",
        "personal_croquis_spend_reservations",
        ["croquis_id"],
    )
    op.create_index(
        "ix_personal_croquis_spend_owner_status",
        "personal_croquis_spend_reservations",
        ["owner_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_personal_croquis_spend_owner_status",
        table_name="personal_croquis_spend_reservations",
    )
    op.drop_index(
        "ix_personal_croquis_spend_reservations_croquis_id",
        table_name="personal_croquis_spend_reservations",
    )
    op.drop_index(
        "ix_personal_croquis_spend_reservations_owner_id",
        table_name="personal_croquis_spend_reservations",
    )
    op.drop_table("personal_croquis_spend_reservations")
