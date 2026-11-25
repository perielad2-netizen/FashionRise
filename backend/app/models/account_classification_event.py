"""Audit log for Admin 2.0 account classification changes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ACCOUNT_CLASSIFICATIONS: tuple[str, ...] = (
    "CUSTOMER",
    "OWNER",
    "ADMIN",
    "INTERNAL_TESTER",
    "QA_AUTOMATION",
    "DEMO_ACCOUNT",
    "UNCLASSIFIED",
)


class AccountClassificationEvent(Base):
    __tablename__ = "account_classification_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    from_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    to_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
