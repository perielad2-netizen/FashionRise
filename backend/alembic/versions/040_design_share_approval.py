"""Design share transfers require recipient approval.

Revision ID: 040
Revises: 039
Create Date: 2026-11-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "design_share_transfers",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "design_share_transfers",
        sa.Column("source_title", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "design_share_transfers",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_design_share_transfers_status",
        "design_share_transfers",
        "status IN ('pending', 'accepted', 'rejected')",
    )
    op.create_index(
        "ix_design_share_transfers_status",
        "design_share_transfers",
        ["status"],
    )
    # Rows created before approval existed already delivered the design copy.
    op.execute(
        "UPDATE design_share_transfers SET status = 'accepted', "
        "responded_at = COALESCE(responded_at, created_at) "
        "WHERE received_design_id IS NOT NULL AND status = 'pending'"
    )


def downgrade() -> None:
    op.drop_index("ix_design_share_transfers_status", table_name="design_share_transfers")
    op.drop_constraint("ck_design_share_transfers_status", "design_share_transfers", type_="check")
    op.drop_column("design_share_transfers", "responded_at")
    op.drop_column("design_share_transfers", "source_title")
    op.drop_column("design_share_transfers", "status")
