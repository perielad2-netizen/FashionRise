"""techpack_ai_artifacts for Create Real Design V3 professional illustrations

Revision ID: 010
Revises: 009
Create Date: 2026-10-26

Stores owner-scoped AI illustration artifacts linked to techpack_ai_runs.
Does not alter techpack_drafts rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "techpack_ai_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("piece_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("source_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("look_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_state", sa.String(length=32), server_default="proposed", nullable=False),
        sa.Column(
            "metadata_",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["techpack_ai_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["draft_id"], ["techpack_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_techpack_ai_artifacts_run_id", "techpack_ai_artifacts", ["run_id"], unique=False)
    op.create_index("ix_techpack_ai_artifacts_draft_id", "techpack_ai_artifacts", ["draft_id"], unique=False)
    op.create_index("ix_techpack_ai_artifacts_user_id", "techpack_ai_artifacts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_techpack_ai_artifacts_user_id", table_name="techpack_ai_artifacts")
    op.drop_index("ix_techpack_ai_artifacts_draft_id", table_name="techpack_ai_artifacts")
    op.drop_index("ix_techpack_ai_artifacts_run_id", table_name="techpack_ai_artifacts")
    op.drop_table("techpack_ai_artifacts")
