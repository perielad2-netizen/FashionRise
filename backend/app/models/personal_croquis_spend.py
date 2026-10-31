"""Create My Croquis Stage C — concurrency-safe spend reservations.

Independent of Magic / Techpack AI run tables. Operator ceiling defaults to 0
(fail closed). Open reservations count against ceilings until settled/released.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.personal_croquis import PersonalCroquis, PersonalCroquisVersion
    from app.models.user import User

RESERVATION_OPEN = "open"
RESERVATION_SETTLED = "settled"
RESERVATION_RELEASED = "released"
RESERVATION_RECONCILIATION = "reconciliation_required"


class PersonalCroquisSpendReservation(Base):
    __tablename__ = "personal_croquis_spend_reservations"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_personal_croquis_spend_owner_idempotency",
        ),
        Index("ix_personal_croquis_spend_owner_status", "owner_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    croquis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personal_croquis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personal_croquis_version.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RESERVATION_OPEN)
    estimate_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_called: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship()
    croquis: Mapped[PersonalCroquis] = relationship()
    version: Mapped[PersonalCroquisVersion | None] = relationship()
