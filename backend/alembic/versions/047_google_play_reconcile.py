"""Google Play financial reconcile runs + persisted findings.

Revision ID: 047
Revises: 046
Create Date: 2026-11-27

Stores hourly reconcile run health and latest per-purchase decisions so Admin
overview never calls orders.get / products.get on page load.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_play_reconcile_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_requests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_would_recover", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_recovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sandbox_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("production_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "counts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "meta",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "status IN ('success', 'partial', 'failed', 'skipped_disabled', "
            "'skipped_backoff', 'skipped_lock')",
            name="ck_google_play_reconcile_runs_status",
        ),
        sa.CheckConstraint("scanned >= 0", name="ck_gpr_runs_scanned_nonneg"),
        sa.CheckConstraint("stars_recovered >= 0", name="ck_gpr_runs_recovered_nonneg"),
    )
    op.create_index(
        "ix_google_play_reconcile_runs_started_at",
        "google_play_reconcile_runs",
        ["started_at"],
    )

    op.create_table(
        "google_play_reconcile_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "iap_purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("iap_purchases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("order_id", sa.String(128), nullable=True),
        sa.Column("environment", sa.String(32), nullable=True),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("order_state", sa.String(64), nullable=True),
        sa.Column("entitlement", sa.String(32), nullable=True),
        sa.Column("stars_outstanding", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_recovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refund_total_currency", sa.String(8), nullable=True),
        sa.Column("refund_total_units", sa.String(32), nullable=True),
        sa.Column(
            "detail",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "inspected_at",
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
        sa.UniqueConstraint(
            "iap_purchase_id", name="uq_google_play_reconcile_findings_purchase"
        ),
    )
    op.create_index(
        "ix_google_play_reconcile_findings_decision",
        "google_play_reconcile_findings",
        ["decision"],
    )
    op.create_index(
        "ix_google_play_reconcile_findings_environment",
        "google_play_reconcile_findings",
        ["environment"],
    )

    op.create_table(
        "google_play_reconcile_cursor",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("last_purchase_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_purchase_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO google_play_reconcile_cursor (id, updated_at) VALUES (1, now()) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("google_play_reconcile_cursor")
    op.drop_index(
        "ix_google_play_reconcile_findings_environment",
        table_name="google_play_reconcile_findings",
    )
    op.drop_index(
        "ix_google_play_reconcile_findings_decision",
        table_name="google_play_reconcile_findings",
    )
    op.drop_table("google_play_reconcile_findings")
    op.drop_index(
        "ix_google_play_reconcile_runs_started_at",
        table_name="google_play_reconcile_runs",
    )
    op.drop_table("google_play_reconcile_runs")
