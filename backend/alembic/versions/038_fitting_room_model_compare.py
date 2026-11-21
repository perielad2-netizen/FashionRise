"""Owner-only Fitting Room model-compare paid operation ledger.

Revision ID: 038
Revises: 037
Create Date: 2026-11-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fitting_room_model_compare_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=False),
        sa.Column("arms_requested", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dispatched_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_outputs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_provider_calls", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("person_fingerprint", sa.String(length=32), nullable=True),
        sa.Column("design_fingerprint", sa.String(length=32), nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_detail", sa.String(length=512), nullable=True),
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_fitting_room_model_compare_owner_idempotency",
        ),
    )
    op.create_index(
        "ix_fitting_room_model_compare_operations_owner_id",
        "fitting_room_model_compare_operations",
        ["owner_id"],
    )
    op.create_index(
        "ix_fitting_room_model_compare_owner_status",
        "fitting_room_model_compare_operations",
        ["owner_id", "status"],
    )
    op.create_index(
        "ix_fitting_room_model_compare_created_at",
        "fitting_room_model_compare_operations",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fitting_room_model_compare_created_at",
        table_name="fitting_room_model_compare_operations",
    )
    op.drop_index(
        "ix_fitting_room_model_compare_owner_status",
        table_name="fitting_room_model_compare_operations",
    )
    op.drop_index(
        "ix_fitting_room_model_compare_operations_owner_id",
        table_name="fitting_room_model_compare_operations",
    )
    op.drop_table("fitting_room_model_compare_operations")
