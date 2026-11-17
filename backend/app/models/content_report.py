"""User-submitted reports for FashionRise Social looks / designers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.gallery_item import GalleryItem
    from app.models.user import User

REPORT_REASONS = (
    "sexual_content",
    "harassment",
    "hate",
    "spam",
    "impersonation",
    "other",
)


class ContentReport(Base):
    """One report per reporter × gallery look."""

    __tablename__ = "content_reports"
    __table_args__ = (
        UniqueConstraint(
            "reporter_id",
            "gallery_item_id",
            name="uq_content_reports_reporter_item",
        ),
        CheckConstraint(
            "reason IN (" + ", ".join(f"'{r}'" for r in REPORT_REASONS) + ")",
            name="ck_content_reports_reason",
        ),
        CheckConstraint(
            "status IN ('open', 'reviewed', 'actioned', 'dismissed')",
            name="ck_content_reports_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gallery_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gallery_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])
    reported_user: Mapped["User"] = relationship(foreign_keys=[reported_user_id])
    gallery_item: Mapped["GalleryItem"] = relationship()
