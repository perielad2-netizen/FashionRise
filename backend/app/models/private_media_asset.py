"""Owner-private media bytes for Create My Croquis (source + generated)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User

KIND_CROQUIS_SOURCE = "croquis_source"
KIND_CROQUIS_GENERATED = "croquis_generated"
ALLOWED_KINDS = frozenset({KIND_CROQUIS_SOURCE, KIND_CROQUIS_GENERATED})


class PrivateMediaAsset(Base):
    """Private croquis-related image identity. Bytes live under ``private_croquis/``.

    Soft ``deleted_at`` / ``erase_requested_at`` mark lifecycle; filesystem unlink
    is handled by the retention sweeper. Rows are retained as tombstones so
    historical version pins fail closed instead of remapping.
    """

    __tablename__ = "private_media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erase_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bytes_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleanup_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_cleanup_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship(back_populates="private_media_assets")
