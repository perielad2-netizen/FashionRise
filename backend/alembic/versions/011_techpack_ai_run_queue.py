"""Index techpack AI runs for durable queue claiming.

Revision ID: 011
Revises: 010
Create Date: 2026-10-27

Status values remain stringly typed on TechpackAIRun.status:
queued | running | completed | failed | reconciliation_required
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_techpack_ai_runs_status_created",
        "techpack_ai_runs",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_techpack_ai_runs_status_created", table_name="techpack_ai_runs")
