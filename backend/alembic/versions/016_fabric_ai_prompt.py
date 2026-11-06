"""AI fabric prompt metadata on fabric_assets

Revision ID: 016
Revises: 015
Create Date: 2026-11-05

Adds optional AI-generation provenance so Magic / Try On can reuse a short
textile description without inventing fabric details.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fabric_assets",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="upload"),
    )
    op.add_column("fabric_assets", sa.Column("prompt_raw", sa.Text(), nullable=True))
    op.add_column(
        "fabric_assets",
        sa.Column("prompt_short", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "fabric_assets",
        sa.Column("color_hex", sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fabric_assets", "color_hex")
    op.drop_column("fabric_assets", "prompt_short")
    op.drop_column("fabric_assets", "prompt_raw")
    op.drop_column("fabric_assets", "source")
