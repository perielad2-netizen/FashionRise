"""Persisted Google Play financial reconcile runs and findings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GooglePlayReconcileRun(Base):
    __tablename__ = "google_play_reconcile_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_would_recover: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_recovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sandbox_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    production_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class GooglePlayReconcileFinding(Base):
    __tablename__ = "google_play_reconcile_findings"
    __table_args__ = (
        UniqueConstraint("iap_purchase_id", name="uq_google_play_reconcile_findings_purchase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    iap_purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iap_purchases.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    order_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entitlement: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stars_outstanding: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_recovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refund_total_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    refund_total_units: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GooglePlayReconcileCursor(Base):
    """Single-row fair-rotation cursor (id=1)."""

    __tablename__ = "google_play_reconcile_cursor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    last_purchase_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_purchase_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
