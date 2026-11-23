import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.gallery_comment import GalleryComment
    from app.models.gallery_impression import GalleryImpression
    from app.models.gallery_like import GalleryLike
    from app.models.garment_design import GarmentDesign
    from app.models.rating import Rating
    from app.models.user import User


class GalleryItem(Base):
    __tablename__ = "gallery_items"
    __table_args__ = (
        CheckConstraint(
            "design_id IS NOT NULL OR look_id IS NOT NULL OR croquis_id IS NOT NULL",
            name="ck_gallery_items_design_look_or_croquis",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garment_designs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    look_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    croquis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personal_croquis.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'public'"))
    rating_average: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    likes_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    impressions_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    unique_impressions_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    moderation_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ok'"))
    moderation_labels: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    design: Mapped["GarmentDesign"] = relationship(back_populates="gallery_items")
    user: Mapped["User"] = relationship(back_populates="gallery_items")
    # cascade required: without it SQLAlchemy nulls ratings.gallery_item_id on
    # parent delete (IntegrityError) instead of removing rating rows.
    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="gallery_item", cascade="all, delete-orphan"
    )
    likes: Mapped[list["GalleryLike"]] = relationship(
        back_populates="gallery_item", cascade="all, delete-orphan"
    )
    comments: Mapped[list["GalleryComment"]] = relationship(
        back_populates="gallery_item", cascade="all, delete-orphan"
    )
    impressions: Mapped[list["GalleryImpression"]] = relationship(
        back_populates="gallery_item", cascade="all, delete-orphan"
    )
