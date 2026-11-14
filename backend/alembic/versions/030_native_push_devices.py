"""native_push_devices for FCM/APNs (separate from Web Push).

Revision ID: 030
Revises: 029
Create Date: 2026-11-13

Fail-closed: delivery stays off until NATIVE_PUSH_ANDROID_ENABLED /
NATIVE_PUSH_IOS_ENABLED and operator credentials are set. Never store auth tokens here.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "native_push_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("device_token", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("device_token", name="uq_native_push_devices_token"),
    )
    op.create_index("ix_native_push_devices_user_id", "native_push_devices", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_native_push_devices_user_id", table_name="native_push_devices")
    op.drop_table("native_push_devices")
