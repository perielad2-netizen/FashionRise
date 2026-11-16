import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.gallery_item import GalleryItem
    from app.models.user import User


class GalleryImpression(Base):
    """One unique Discover exposure per viewer × gallery item (no self-impressions)."""

    __tablename__ = "gallery_impressions"
    __table_args__ = (
        UniqueConstraint(
            "gallery_item_id",
            "viewer_user_id",
            name="uq_gallery_impressions_item_viewer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gallery_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gallery_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    viewer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gallery_item: Mapped["GalleryItem"] = relationship(back_populates="impressions")
    viewer: Mapped["User"] = relationship()
