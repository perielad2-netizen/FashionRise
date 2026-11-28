"""Native push destination contract version (per device).

Revision ID: 048
Revises: 047
Create Date: 2026-11-28

``destination_contract_version`` on ``native_push_devices``:
- 1 (default / existing installs): legacy-safe URLs (friends=1 preserved;
  item/comment → Social feed root)
- 2 (this FE registers on upsert): full typed FashionRise destinations

Account-wide Web Push suppression was deliberately NOT added.
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
