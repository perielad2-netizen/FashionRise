"""Competition award claim-to-receive Stars.

Revision ID: 042
Revises: 041
Create Date: 2026-11-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "competition_awards",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Awards that already have a StarPayout were auto-credited — mark claimed so
    # winners are not asked to claim Stars they already received.
    op.execute(
        """
        UPDATE competition_awards AS a
        SET claimed_at = COALESCE(p.created_at, a.created_at)
        FROM star_payouts AS p
        WHERE p.payout_key = a.payout_key
          AND a.claimed_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("competition_awards", "claimed_at")
