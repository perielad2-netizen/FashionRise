"""iap_purchases for App Store / Play Store Stars

Revision ID: 024
Revises: 023
Create Date: 2026-11-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "iap_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("product_id", sa.String(length=128), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("stars_credited", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform", "transaction_id", name="uq_iap_purchases_platform_txn"),
    )
    op.create_index("ix_iap_purchases_user_id", "iap_purchases", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_iap_purchases_user_id", table_name="iap_purchases")
    op.drop_table("iap_purchases")
