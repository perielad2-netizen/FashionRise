"""Apple Stars IAP Phase B — ASN V2, refund liability, purchase state.

Revision ID: 026
Revises: 025
Create Date: 2026-11-10

Adds:
- users.ai_stars_iap_debt (outstanding refund liability; balance never goes negative)
- iap_purchases status / original_transaction_id / environment / clawback tracking
- iap_apple_notifications (idempotent by notification_uuid)
- iap_stars_adjustments (idempotent financial events per purchase+kind)

Downgrade drops Phase B tables/columns. Safe only when no live Apple money events
exist; if production already processed refunds, restore from backup instead of
downgrade (see docs/deploy/APPLE-STARS-IAP-PHASE-B.md).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ai_stars_iap_debt",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "iap_purchases",
        sa.Column("original_transaction_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "iap_purchases",
        sa.Column("environment", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "iap_purchases",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "iap_purchases",
        sa.Column(
            "stars_clawed_back",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "iap_purchases",
        sa.Column(
            "stars_restored",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "iap_purchases",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_iap_purchases_original_transaction_id",
        "iap_purchases",
        ["original_transaction_id"],
    )
    op.create_index("ix_iap_purchases_status", "iap_purchases", ["status"])

    op.create_table(
        "iap_apple_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("notification_uuid", sa.String(length=64), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=True),
        sa.Column("original_transaction_id", sa.String(length=255), nullable=True),
        sa.Column("product_id", sa.String(length=128), nullable=True),
        sa.Column("app_account_token", sa.String(length=64), nullable=True),
        sa.Column("processing_state", sa.String(length=32), nullable=False),
        sa.Column("processing_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("iap_purchase_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["iap_purchase_id"], ["iap_purchases.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("notification_uuid", name="uq_iap_apple_notifications_uuid"),
    )
    op.create_index(
        "ix_iap_apple_notifications_transaction_id",
        "iap_apple_notifications",
        ["transaction_id"],
    )
    op.create_index(
        "ix_iap_apple_notifications_original_transaction_id",
        "iap_apple_notifications",
        ["original_transaction_id"],
    )
    op.create_index(
        "ix_iap_apple_notifications_iap_purchase_id",
        "iap_apple_notifications",
        ["iap_purchase_id"],
    )
    op.create_index(
        "ix_iap_apple_notifications_user_id",
        "iap_apple_notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_iap_apple_notifications_processing_state",
        "iap_apple_notifications",
        ["processing_state"],
    )

    op.create_table(
        "iap_stars_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("iap_purchase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("transaction_id", sa.String(length=255), nullable=False),
        sa.Column("adjustment_kind", sa.String(length=32), nullable=False),
        sa.Column("stars_delta_balance", sa.Integer(), nullable=False),
        sa.Column("stars_delta_debt", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("debt_after", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["iap_purchase_id"], ["iap_purchases.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["iap_apple_notifications.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "iap_purchase_id",
            "adjustment_kind",
            name="uq_iap_stars_adjustments_purchase_kind",
        ),
        sa.UniqueConstraint(
            "platform",
            "transaction_id",
            "adjustment_kind",
            name="uq_iap_stars_adjustments_platform_txn_kind",
        ),
    )
    op.create_index(
        "ix_iap_stars_adjustments_user_id", "iap_stars_adjustments", ["user_id"]
    )
    op.create_index(
        "ix_iap_stars_adjustments_iap_purchase_id",
        "iap_stars_adjustments",
        ["iap_purchase_id"],
    )


def downgrade() -> None:
    """Drops Phase B structures. Prefer backup+forward-fix if live refund rows exist."""
    op.drop_table("iap_stars_adjustments")
    op.drop_index(
        "ix_iap_apple_notifications_processing_state",
        table_name="iap_apple_notifications",
    )
    op.drop_index(
        "ix_iap_apple_notifications_user_id", table_name="iap_apple_notifications"
    )
    op.drop_index(
        "ix_iap_apple_notifications_iap_purchase_id",
        table_name="iap_apple_notifications",
    )
    op.drop_index(
        "ix_iap_apple_notifications_original_transaction_id",
        table_name="iap_apple_notifications",
    )
    op.drop_index(
        "ix_iap_apple_notifications_transaction_id",
        table_name="iap_apple_notifications",
    )
    op.drop_table("iap_apple_notifications")

    op.drop_index("ix_iap_purchases_status", table_name="iap_purchases")
    op.drop_index(
        "ix_iap_purchases_original_transaction_id", table_name="iap_purchases"
    )
    op.drop_column("iap_purchases", "updated_at")
    op.drop_column("iap_purchases", "stars_restored")
    op.drop_column("iap_purchases", "stars_clawed_back")
    op.drop_column("iap_purchases", "status")
    op.drop_column("iap_purchases", "environment")
    op.drop_column("iap_purchases", "original_transaction_id")
    op.drop_column("users", "ai_stars_iap_debt")
