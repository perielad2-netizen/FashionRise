"""Named reusable body measurement profiles

Revision ID: 017
Revises: 016
Create Date: 2026-11-06

Owner-scoped named body measurements (height/bust/waist/hip/inseam) that can be
reused across Create Real Design drafts for different people / clients.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "body_measurement_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("units", sa.String(length=8), nullable=False, server_default="cm"),
        sa.Column("sample_size", sa.String(length=32), nullable=True),
        sa.Column(
            "measurements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    )
    op.create_index(
        "ix_body_measurement_profiles_owner_id",
        "body_measurement_profiles",
        ["owner_id"],
    )
    op.create_index(
        "ix_body_measurement_profiles_owner_default",
        "body_measurement_profiles",
        ["owner_id", "is_default"],
    )


def downgrade() -> None:
    op.drop_index("ix_body_measurement_profiles_owner_default", table_name="body_measurement_profiles")
    op.drop_index("ix_body_measurement_profiles_owner_id", table_name="body_measurement_profiles")
    op.drop_table("body_measurement_profiles")
