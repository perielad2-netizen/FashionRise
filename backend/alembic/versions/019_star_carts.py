"""Stars shop carts

Revision ID: 019
Revises: 018
Create Date: 2026-11-06

Cart + line items for Stars packages. Checkout remains disabled in app config.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "star_carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
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
    op.create_index("ix_star_carts_user_id", "star_carts", ["user_id"])

    op.create_table(
        "star_cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "cart_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("star_carts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("package_sku", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
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
        sa.UniqueConstraint("cart_id", "package_sku", name="uq_star_cart_item_sku"),
    )
    op.create_index("ix_star_cart_items_cart_id", "star_cart_items", ["cart_id"])


def downgrade() -> None:
    op.drop_index("ix_star_cart_items_cart_id", table_name="star_cart_items")
    op.drop_table("star_cart_items")
    op.drop_index("ix_star_carts_user_id", table_name="star_carts")
    op.drop_table("star_carts")
