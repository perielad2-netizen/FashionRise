"""User preference: prefer native push over Web Push when both exist.

Revision ID: 048
Revises: 047
Create Date: 2026-11-28

When true and the user has at least one active native device, notify_user
skips Web Push fan-out. Subscriptions are not deleted.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "prefer_native_push",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "native_push_devices",
        sa.Column(
            "destination_contract_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    op.drop_column("native_push_devices", "destination_contract_version")
    op.drop_column("users", "prefer_native_push")
