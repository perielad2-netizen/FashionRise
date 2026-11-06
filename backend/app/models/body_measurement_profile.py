"""Named reusable body measurement profiles for Create Real Design."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class BodyMeasurementProfile(Base):
    """Owner-private named body measurements reusable across techpack drafts.

    Example names: \"Me\", \"Mom\", \"Client — Anna\". Values are body points only
    (height/bust/waist/hip/inseam) — finished garment POMs stay on the draft and
    are proposed by AI from ease + vision.
    """

    __tablename__ = "body_measurement_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    units: Mapped[str] = mapped_column(String(8), nullable=False, default="cm")
    sample_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="body_measurement_profiles")
