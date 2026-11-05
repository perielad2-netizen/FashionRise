"""Append-only AI consent ↔ croquis/source binding (Stage C P0-5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.personal_croquis import PersonalCroquis
    from app.models.private_media_asset import PrivateMediaAsset
    from app.models.user import User
    from app.models.user_consent_event import UserConsentEvent


class PersonalCroquisAiConsentBinding(Base):
    """Binds an AI-provider consent event to exactly one croquis source photo."""

    __tablename__ = "personal_croquis_ai_consent_bindings"
    __table_args__ = (
        UniqueConstraint(
            "consent_id",
            "croquis_id",
            "source_asset_id",
            name="uq_personal_croquis_ai_consent_binding_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_consent_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    croquis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personal_croquis.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("private_media_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    notice_version: Mapped[str] = mapped_column(String(64), nullable=False)
    notice_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship()
    consent: Mapped[UserConsentEvent] = relationship()
    croquis: Mapped[PersonalCroquis] = relationship()
    source_asset: Mapped[PrivateMediaAsset] = relationship()
