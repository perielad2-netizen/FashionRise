"""Owner-only Fitting Room model-compare paid budget + operation ledger.

Exactly one approved paid operation (default) with a hard cap on dispatched
provider requests. Replay-safe via idempotency; concurrent claims fail closed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

OP_STATUS_RUNNING = "running"
OP_STATUS_COMPLETED = "completed"
OP_STATUS_FAILED = "failed"
OP_STATUS_EXHAUSTED = "exhausted"

# Serialize paid compare claims (distinct from croquis spend lock).
MODEL_COMPARE_GLOBAL_LOCK_KEY = 0x46524D43  # "FRMC"


class FittingRoomModelCompareOperation(Base):
    """One paid A/B/C comparison attempt.

    ``dispatched_requests`` increments **before** each provider call so timeouts
    and ambiguous outcomes still consume budget. Successful outputs are tracked
    separately and never trigger automatic retries.
    """

    __tablename__ = "fitting_room_model_compare_operations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_fitting_room_model_compare_owner_idempotency",
        ),
        Index("ix_fitting_room_model_compare_owner_status", "owner_id", "status"),
        Index("ix_fitting_room_model_compare_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=OP_STATUS_RUNNING)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    arms_requested: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    dispatched_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_outputs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_provider_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    person_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    design_fingerprint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship()
