import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ai_job import AIJob
    from app.models.design_export import DesignExport
    from app.models.design_revision import DesignRevision
    from app.models.gallery_comment import GalleryComment
    from app.models.gallery_item import GalleryItem
    from app.models.gallery_like import GalleryLike
    from app.models.garment_design import GarmentDesign
    from app.models.rating import Rating
    from app.models.refresh_token import RefreshToken
    from app.models.user_profile import UserProfile


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")
    designs: Mapped[list["GarmentDesign"]] = relationship(back_populates="user")
    gallery_items: Mapped[list["GalleryItem"]] = relationship(back_populates="user")
    ratings: Mapped[list["Rating"]] = relationship(back_populates="user")
    exports: Mapped[list["DesignExport"]] = relationship(back_populates="user")
    ai_jobs: Mapped[list["AIJob"]] = relationship(back_populates="user")
    revisions: Mapped[list["DesignRevision"]] = relationship(back_populates="user")
    gallery_likes: Mapped[list["GalleryLike"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    gallery_comments: Mapped[list["GalleryComment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
