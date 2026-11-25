"""AI provider cost accounting models (OpenAI + FASHN financial intelligence)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

if TYPE_CHECKING:
    pass

PROVIDER_OPENAI = "openai"
PROVIDER_FASHN = "fashn"

COST_KIND_ACTUAL = "actual"
COST_KIND_ESTIMATED = "estimated"
COST_KIND_UNAVAILABLE = "unavailable"

CREDITS_KIND_ACTUAL = "actual"
CREDITS_KIND_UNAVAILABLE = "unavailable"
CREDITS_KIND_ESTIMATED_FALLBACK = "estimated_fallback"

OPERATOR_EXPENSE_CATEGORIES: tuple[str, ...] = (
    "hosting",
    "storage",
    "fashn_invoice",
    "openai_invoice",
    "store_commission",
    "other",
)


class ProviderPricingVersion(Base):
    __tablename__ = "provider_pricing_versions"
    __table_args__ = (
        CheckConstraint(
            "unit_amount >= 0", name="ck_provider_pricing_versions_unit_amount_nonneg"
        ),
        CheckConstraint(
            "provider IN ('openai', 'fashn', 'hosting', 'other')",
            name="ck_provider_pricing_versions_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    pricing_key: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    unit_label: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="documented")
    operator_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FashnPredictionCost(Base):
    """One FASHN prediction — idempotent on provider prediction_id."""

    __tablename__ = "fashn_prediction_costs"
    __table_args__ = (
        UniqueConstraint("prediction_id", name="uq_fashn_prediction_costs_prediction_id"),
        CheckConstraint(
            "credits_consumed IS NULL OR credits_consumed >= 0",
            name="ck_fashn_prediction_costs_credits_nonneg",
        ),
        CheckConstraint(
            "credits_kind IN ('actual', 'unavailable', 'estimated_fallback')",
            name="ck_fashn_prediction_costs_credits_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prediction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generation_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_status: Mapped[str] = mapped_column(String(32), nullable=False)
    credits_consumed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CREDITS_KIND_UNAVAILABLE
    )
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    pricing_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AiProviderOperation(Base):
    """Per-provider-call operation ledger (OpenAI usage estimates / FASHN ops)."""

    __tablename__ = "ai_provider_operations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ai_provider_operations_idempotency_key"),
        CheckConstraint(
            "provider IN ('openai', 'fashn')",
            name="ck_ai_provider_operations_provider",
        ),
        CheckConstraint(
            "cost_kind IN ('actual', 'estimated', 'unavailable')",
            name="ck_ai_provider_operations_cost_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    feature: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True
    )
    provider_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_consumed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    cost_kind: Mapped[str] = mapped_column(String(32), nullable=False, default=COST_KIND_ESTIMATED)
    pricing_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    final_status: Mapped[str] = mapped_column(String(32), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OpenAiCostDaily(Base):
    """Synced OpenAI organization/project daily costs (actual cash reporting)."""

    __tablename__ = "openai_cost_daily"
    __table_args__ = (
        UniqueConstraint("raw_fingerprint", name="uq_openai_cost_daily_raw_fingerprint"),
        CheckConstraint("amount >= 0", name="ck_openai_cost_daily_amount_nonneg"),
        CheckConstraint(
            "scope IN ('organization', 'project')",
            name="ck_openai_cost_daily_scope",
        ),
        CheckConstraint(
            "attribution IN ('project', 'organization_unattributed', 'global')",
            name="ck_openai_cost_daily_attribution",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    line_item: Mapped[str | None] = mapped_column(String(256), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="organization")
    attribution: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    raw_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FashnCreditSnapshot(Base):
    __tablename__ = "fashn_credit_snapshots"
    __table_args__ = (
        CheckConstraint(
            "credits_total >= 0 AND credits_subscription >= 0 AND credits_on_demand >= 0",
            name="ck_fashn_credit_snapshots_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    credits_total: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_subscription: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_on_demand: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_value_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    pricing_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OperatorExpenseRecord(Base):
    """Bounded operator-entered cash expenses (hosting, invoices, etc.)."""

    __tablename__ = "operator_expense_records"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_operator_expense_records_amount_nonneg"),
        CheckConstraint(
            "category IN ('hosting', 'storage', 'fashn_invoice', 'openai_invoice', "
            "'store_commission', 'other')",
            name="ck_operator_expense_records_category",
        ),
        CheckConstraint(
            "kind IN ('actual', 'estimated')",
            name="ck_operator_expense_records_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="usd")
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default=COST_KIND_ACTUAL)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProviderSyncRun(Base):
    __tablename__ = "provider_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('openai', 'fashn')",
            name="ck_provider_sync_runs_provider",
        ),
        CheckConstraint(
            "status IN ('success', 'partial', 'failed', 'skipped_disabled', "
            "'skipped_missing_credentials')",
            name="ck_provider_sync_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    sync_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
