"""techpack_ai_runs for Create Real Design V2 AI generations

Revision ID: 009
Revises: 008
Create Date: 2026-10-26

Tracks explicit user-confirmed AI runs with cost/idempotency metadata.
Does not alter techpack_drafts rows (V2 schema lives in JSONB spec).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "techpack_ai_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confirm_token", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("cost_usd_cents", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "request",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["techpack_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_techpack_ai_runs_user_idem"),
    )
    op.create_index("ix_techpack_ai_runs_draft_id", "techpack_ai_runs", ["draft_id"], unique=False)
    op.create_index("ix_techpack_ai_runs_user_id", "techpack_ai_runs", ["user_id"], unique=False)
    op.create_index(
        "ix_techpack_ai_runs_user_created",
        "techpack_ai_runs",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_techpack_ai_runs_user_created", table_name="techpack_ai_runs")
    op.drop_index("ix_techpack_ai_runs_user_id", table_name="techpack_ai_runs")
    op.drop_index("ix_techpack_ai_runs_draft_id", table_name="techpack_ai_runs")
    op.drop_table("techpack_ai_runs")
