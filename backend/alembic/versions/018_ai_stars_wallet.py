"""AI Stars wallet on users

Revision ID: 018
Revises: 017
Create Date: 2026-11-06

Per-user Stars balance for AI spend gating. New users start at 10;
Magic costs 10. Owner emails get ai_stars_unlimited.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EMAILS = (
    "perielad@gmail.com",
    "perielad2@gmail.com",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("ai_stars", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "users",
        sa.Column(
            "ai_stars_unlimited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Existing accounts get one free Magic (starter balance). Owners get unlimited.
    conn = op.get_bind()
    for email in _OWNER_EMAILS:
        conn.execute(
            sa.text(
                "UPDATE users SET ai_stars_unlimited = true, ai_stars = 999999 "
                "WHERE lower(email) = lower(:email)"
            ),
            {"email": email},
        )


def downgrade() -> None:
    op.drop_column("users", "ai_stars_unlimited")
    op.drop_column("users", "ai_stars")
