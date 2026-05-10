import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ai_job import AIJob
    from app.models.design_export import DesignExport
    from app.models.design_revision import DesignRevision
    from app.models.gallery_item import GalleryItem
    from app.models.garment_template import GarmentTemplate
    from app.models.user import User


class GarmentDesign(Base):
    __tablename__ = "garment_designs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    garment_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garment_templates.id", ondelete="SET NULL"), nullable=True
    )
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_definitions.id", ondelete="SET NULL"), nullable=True
    )
    color_palette_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("color_palettes.id", ondelete="SET NULL"), nullable=True
    )
    design_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'private'"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'draft'"))
    moderation_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'ok'"))
    moderation_labels: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="designs")
    template: Mapped["GarmentTemplate | None"] = relationship(back_populates="designs")
    gallery_items: Mapped[list["GalleryItem"]] = relationship(back_populates="design")
    exports: Mapped[list["DesignExport"]] = relationship(back_populates="design")
    ai_jobs: Mapped[list["AIJob"]] = relationship(back_populates="design")
    revisions: Mapped[list["DesignRevision"]] = relationship(back_populates="design")
