"""Versioned consent / attestation events (Create My Croquis Stage A)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

PURPOSE_ADULTS_BETA = "adults_beta"
PURPOSE_CROQUIS_STORAGE = "croquis_storage"
PURPOSE_CROQUIS_AI_PROVIDER = "croquis_ai_provider"
ALLOWED_CONSENT_PURPOSES = frozenset(
    {PURPOSE_ADULTS_BETA, PURPOSE_CROQUIS_STORAGE, PURPOSE_CROQUIS_AI_PROVIDER}
)


class UserConsentEvent(Base):
    """Immutable record of adults attestation or storage/AI consent.

    Final legal copy is not approved; ``consent_version`` / ``text_hash`` identify
    draft placeholders only. Server validates purpose, version, owner, and age.
    """

    __tablename__ = "user_consent_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    adults_attested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="consent_events")
