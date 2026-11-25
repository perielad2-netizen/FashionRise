"""Durable audit ledger for administrative ADD-ONLY Stars grants."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

ADMIN_GRANT_REASONS: tuple[str, ...] = (
    "CUSTOMER_APPRECIATION",
    "TECHNICAL_COMPENSATION",
    "PROMOTIONAL_GIFT",
    "WELCOME_BONUS",
    "COMPETITION_REWARD",
    "INTERNAL_TESTING",
    "OTHER",
)

ADMIN_GRANT_SOURCE = "ADMIN_GRANT"
ADMIN_GRANT_STATUS_COMPLETED = "completed"


class AdminStarsGrant(Base):
    """One successful administrative Stars credit.

    Idempotency is enforced by unique ``idempotency_key``. There is no signed
    delta API — amount is always a positive credit. Rows are never edited or
    deleted via the admin UI.
    """

    __tablename__ = "admin_stars_grants"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_admin_stars_grants_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ADMIN_GRANT_SOURCE, server_default=ADMIN_GRANT_SOURCE
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ADMIN_GRANT_STATUS_COMPLETED,
        server_default=ADMIN_GRANT_STATUS_COMPLETED,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_id])
    actor: Mapped["User"] = relationship(foreign_keys=[actor_id])
