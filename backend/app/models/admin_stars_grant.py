"""Durable audit ledger for administrative ADD-ONLY Stars grants."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

# Immutable absolute ceiling — cannot be raised via environment.
ABSOLUTE_GRANT_CEILING = 50_000
# PostgreSQL / SQLAlchemy Integer upper bound used for wallet overflow checks.
STARS_INT_MAX = 2_147_483_647


class AdminStarsGrant(Base):
    """One successful administrative Stars credit.

    Idempotency is enforced by unique ``idempotency_key``. There is no signed
    delta API — amount is always a positive credit. Rows are never edited or
    deleted via the admin UI. Actor/recipient FKs are SET NULL on user delete
    so audit history survives account deletion in anonymized form.
    """

    __tablename__ = "admin_stars_grants"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_admin_stars_grants_idempotency_key"),
        CheckConstraint("amount > 0", name="ck_admin_stars_grants_amount_positive"),
        CheckConstraint(
            "balance_before >= 0", name="ck_admin_stars_grants_balance_before_nonneg"
        ),
        CheckConstraint(
            "balance_after >= 0", name="ck_admin_stars_grants_balance_after_nonneg"
        ),
        CheckConstraint(
            "balance_after = balance_before + amount",
            name="ck_admin_stars_grants_balance_math",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ADMIN_GRANT_SOURCE,
        server_default=ADMIN_GRANT_SOURCE,
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

    recipient: Mapped["User | None"] = relationship(foreign_keys=[recipient_id])
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])
