"""Apple IAP Phase B hardening — adjustment uniqueness per notification.

Revision ID: 027
Revises: 026
Create Date: 2026-11-10

Allows multiple REFUND cycles after REFUND_REVERSED (consumable semantics) while
keeping one financial adjustment per Apple notification UUID/row.

Downgrade restores the stricter per-kind uniqueness (safe only when ≤1 adjustment
per kind exists per purchase).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_iap_stars_adjustments_purchase_kind",
        "iap_stars_adjustments",
        type_="unique",
    )
    op.drop_constraint(
        "uq_iap_stars_adjustments_platform_txn_kind",
        "iap_stars_adjustments",
        type_="unique",
    )
    # One ledger row per ASN notification (NULL notification_id rare; still indexed).
    op.create_index(
        "uq_iap_stars_adjustments_notification_id",
        "iap_stars_adjustments",
        ["notification_id"],
        unique=True,
        postgresql_where=sa.text("notification_id IS NOT NULL"),
    )
    op.add_column(
        "iap_apple_notifications",
        sa.Column("signed_date_ms", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("iap_apple_notifications", "signed_date_ms")
    op.drop_index(
        "uq_iap_stars_adjustments_notification_id",
        table_name="iap_stars_adjustments",
    )
    op.create_unique_constraint(
        "uq_iap_stars_adjustments_platform_txn_kind",
        "iap_stars_adjustments",
        ["platform", "transaction_id", "adjustment_kind"],
    )
    op.create_unique_constraint(
        "uq_iap_stars_adjustments_purchase_kind",
        "iap_stars_adjustments",
        ["iap_purchase_id", "adjustment_kind"],
    )
