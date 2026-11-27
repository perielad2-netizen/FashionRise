"""Google Play IAP purchase_token + RTDN notification ledger.

Revision ID: 046
Revises: 045
Create Date: 2026-11-27

- purchase_token / obfuscated_account_id on iap_purchases (Android consumables)
- iap_google_notifications for RTDN / voided-purchase idempotency

Does not enable Google purchasing (fail-closed via env flags).
Does not change Apple StoreKit / ASN behavior.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "iap_purchases",
        sa.Column("purchase_token", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "iap_purchases",
        sa.Column("obfuscated_account_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_iap_purchases_purchase_token",
        "iap_purchases",
        ["purchase_token"],
        unique=False,
    )
    # Exactly-once Android credit key — NULL tokens (iOS rows) excluded.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_iap_purchases_android_purchase_token
        ON iap_purchases (purchase_token)
        WHERE purchase_token IS NOT NULL AND platform = 'android'
        """
    )

    op.create_table(
        "iap_google_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("purchase_token", sa.String(length=512), nullable=True),
        sa.Column("order_id", sa.String(length=255), nullable=True),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("package_name", sa.String(length=128), nullable=True),
        sa.Column(
            "iap_purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("iap_purchases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "processing_state",
            sa.String(length=32),
            nullable=False,
            server_default="received",
        ),
        sa.Column(
            "audit_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.UniqueConstraint("message_id", name="uq_iap_google_notifications_message_id"),
    )
    op.create_index(
        "ix_iap_google_notifications_purchase_token",
        "iap_google_notifications",
        ["purchase_token"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_iap_google_notifications_purchase_token",
        table_name="iap_google_notifications",
    )
    op.drop_table("iap_google_notifications")
    op.execute("DROP INDEX IF EXISTS uq_iap_purchases_android_purchase_token")
    op.drop_index("ix_iap_purchases_purchase_token", table_name="iap_purchases")
    op.drop_column("iap_purchases", "obfuscated_account_id")
    op.drop_column("iap_purchases", "purchase_token")
