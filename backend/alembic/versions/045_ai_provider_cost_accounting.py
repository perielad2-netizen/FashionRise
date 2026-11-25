"""AI provider cost accounting (OpenAI + FASHN financial intelligence).

Revision ID: 045
Revises: 044
Create Date: 2026-11-26

Persists:
- Versioned provider pricing (FASHN credit USD rate, etc.)
- Per-prediction FASHN credit consumption (idempotent)
- OpenAI organization/project daily costs from Costs API sync
- FASHN credit balance snapshots
- Bounded operator-entered operational expenses
- Provider sync run health

Does not enable live provider sync (fail-closed via env flags).
Does not change Stars balances, generation behavior, or pricing.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_pricing_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("pricing_key", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="usd"),
        sa.Column("unit_amount", sa.Numeric(18, 8), nullable=False),
        sa.Column("unit_label", sa.String(64), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="documented"),
        sa.Column("operator_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "unit_amount >= 0", name="ck_provider_pricing_versions_unit_amount_nonneg"
        ),
        sa.CheckConstraint(
            "provider IN ('openai', 'fashn', 'hosting', 'other')",
            name="ck_provider_pricing_versions_provider",
        ),
    )
    op.create_index(
        "ix_provider_pricing_versions_provider_key",
        "provider_pricing_versions",
        ["provider", "pricing_key", "effective_from"],
    )

    op.create_table(
        "fashn_prediction_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prediction_id", sa.String(128), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("generation_mode", sa.String(64), nullable=True),
        sa.Column("resolution", sa.String(64), nullable=True),
        sa.Column("output_count", sa.Integer(), nullable=True),
        sa.Column("final_status", sa.String(32), nullable=False),
        sa.Column("credits_consumed", sa.Integer(), nullable=True),
        sa.Column(
            "credits_kind",
            sa.String(32),
            nullable=False,
            server_default="unavailable",
        ),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("pricing_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "prediction_id", name="uq_fashn_prediction_costs_prediction_id"
        ),
        sa.CheckConstraint(
            "credits_consumed IS NULL OR credits_consumed >= 0",
            name="ck_fashn_prediction_costs_credits_nonneg",
        ),
        sa.CheckConstraint(
            "credits_kind IN ('actual', 'unavailable', 'estimated_fallback')",
            name="ck_fashn_prediction_costs_credits_kind",
        ),
    )
    op.create_index(
        "ix_fashn_prediction_costs_user_id", "fashn_prediction_costs", ["user_id"]
    )
    op.create_index(
        "ix_fashn_prediction_costs_job_id", "fashn_prediction_costs", ["job_id"]
    )
    op.create_index(
        "ix_fashn_prediction_costs_occurred_at",
        "fashn_prediction_costs",
        ["occurred_at"],
    )
    op.create_index(
        "ix_fashn_prediction_costs_feature", "fashn_prediction_costs", ["feature"]
    )

    op.create_table(
        "ai_provider_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("feature", sa.String(64), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_request_id", sa.String(128), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("image_units", sa.Integer(), nullable=True),
        sa.Column("credits_consumed", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("actual_cost_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column(
            "cost_kind",
            sa.String(32),
            nullable=False,
            server_default="estimated",
        ),
        sa.Column("pricing_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("final_status", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(32), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_ai_provider_operations_idempotency_key"
        ),
        sa.CheckConstraint(
            "provider IN ('openai', 'fashn')",
            name="ck_ai_provider_operations_provider",
        ),
        sa.CheckConstraint(
            "cost_kind IN ('actual', 'estimated', 'unavailable')",
            name="ck_ai_provider_operations_cost_kind",
        ),
    )
    op.create_index(
        "ix_ai_provider_operations_user_id", "ai_provider_operations", ["user_id"]
    )
    op.create_index(
        "ix_ai_provider_operations_occurred_at",
        "ai_provider_operations",
        ["occurred_at"],
    )
    op.create_index(
        "ix_ai_provider_operations_provider_feature",
        "ai_provider_operations",
        ["provider", "feature"],
    )

    op.create_table(
        "openai_cost_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=True),
        sa.Column("line_item", sa.String(256), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="usd"),
        sa.Column("amount", sa.Numeric(18, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 8), nullable=True),
        sa.Column("quantity_unit", sa.String(64), nullable=True),
        sa.Column(
            "scope",
            sa.String(32),
            nullable=False,
            server_default="organization",
        ),
        sa.Column("attribution", sa.String(32), nullable=False, server_default="global"),
        sa.Column("raw_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "raw_fingerprint", name="uq_openai_cost_daily_raw_fingerprint"
        ),
        sa.CheckConstraint("amount >= 0", name="ck_openai_cost_daily_amount_nonneg"),
        sa.CheckConstraint(
            "scope IN ('organization', 'project')",
            name="ck_openai_cost_daily_scope",
        ),
        sa.CheckConstraint(
            "attribution IN ('project', 'organization_unattributed', 'global')",
            name="ck_openai_cost_daily_attribution",
        ),
    )
    op.create_index(
        "ix_openai_cost_daily_bucket_start", "openai_cost_daily", ["bucket_start"]
    )
    op.create_index(
        "ix_openai_cost_daily_project_id", "openai_cost_daily", ["project_id"]
    )

    op.create_table(
        "fashn_credit_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("credits_total", sa.Integer(), nullable=False),
        sa.Column("credits_subscription", sa.Integer(), nullable=False),
        sa.Column("credits_on_demand", sa.Integer(), nullable=False),
        sa.Column("estimated_value_usd", sa.Numeric(18, 8), nullable=True),
        sa.Column("pricing_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "credits_total >= 0 AND credits_subscription >= 0 AND credits_on_demand >= 0",
            name="ck_fashn_credit_snapshots_nonneg",
        ),
    )
    op.create_index(
        "ix_fashn_credit_snapshots_captured_at",
        "fashn_credit_snapshots",
        ["captured_at"],
    )

    op.create_table(
        "operator_expense_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="usd"),
        sa.Column("amount", sa.Numeric(18, 8), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="actual"),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="operator"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount >= 0", name="ck_operator_expense_records_amount_nonneg"),
        sa.CheckConstraint(
            "category IN ('hosting', 'storage', 'fashn_invoice', 'openai_invoice', "
            "'store_commission', 'other')",
            name="ck_operator_expense_records_category",
        ),
        sa.CheckConstraint(
            "kind IN ('actual', 'estimated')",
            name="ck_operator_expense_records_kind",
        ),
    )
    op.create_index(
        "ix_operator_expense_records_occurred_on",
        "operator_expense_records",
        ["occurred_on"],
    )

    op.create_table(
        "provider_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("sync_kind", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "provider IN ('openai', 'fashn')",
            name="ck_provider_sync_runs_provider",
        ),
        sa.CheckConstraint(
            "status IN ('success', 'partial', 'failed', 'skipped_disabled', 'skipped_missing_credentials')",
            name="ck_provider_sync_runs_status",
        ),
    )
    op.create_index(
        "ix_provider_sync_runs_provider_started",
        "provider_sync_runs",
        ["provider", "started_at"],
    )

    # Seed documented FASHN on-demand rate (not operator-confirmed cash rate).
    op.execute(
        """
        INSERT INTO provider_pricing_versions (
            id, provider, pricing_key, currency, unit_amount, unit_label,
            effective_from, effective_to, source, operator_confirmed, note
        ) VALUES (
            gen_random_uuid(),
            'fashn',
            'credit_on_demand',
            'usd',
            0.075,
            'per_credit',
            TIMESTAMPTZ '2024-01-01 00:00:00+00',
            NULL,
            'documented_help_center',
            false,
            'Documented on-demand USD 0.075/credit. Estimated monetary only until operator-confirmed invoice rate.'
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_provider_sync_runs_provider_started", table_name="provider_sync_runs")
    op.drop_table("provider_sync_runs")
    op.drop_index(
        "ix_operator_expense_records_occurred_on", table_name="operator_expense_records"
    )
    op.drop_table("operator_expense_records")
    op.drop_index(
        "ix_fashn_credit_snapshots_captured_at", table_name="fashn_credit_snapshots"
    )
    op.drop_table("fashn_credit_snapshots")
    op.drop_index("ix_openai_cost_daily_project_id", table_name="openai_cost_daily")
    op.drop_index("ix_openai_cost_daily_bucket_start", table_name="openai_cost_daily")
    op.drop_table("openai_cost_daily")
    op.drop_index(
        "ix_ai_provider_operations_provider_feature",
        table_name="ai_provider_operations",
    )
    op.drop_index(
        "ix_ai_provider_operations_occurred_at", table_name="ai_provider_operations"
    )
    op.drop_index("ix_ai_provider_operations_user_id", table_name="ai_provider_operations")
    op.drop_table("ai_provider_operations")
    op.drop_index("ix_fashn_prediction_costs_feature", table_name="fashn_prediction_costs")
    op.drop_index(
        "ix_fashn_prediction_costs_occurred_at", table_name="fashn_prediction_costs"
    )
    op.drop_index("ix_fashn_prediction_costs_job_id", table_name="fashn_prediction_costs")
    op.drop_index("ix_fashn_prediction_costs_user_id", table_name="fashn_prediction_costs")
    op.drop_table("fashn_prediction_costs")
    op.drop_index(
        "ix_provider_pricing_versions_provider_key",
        table_name="provider_pricing_versions",
    )
    op.drop_table("provider_pricing_versions")
