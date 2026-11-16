"""Durable public upload cleanup queue (FashionRise My Models copies)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublicMediaCleanupQueue(Base):
    """Pending / quarantined public FashionRise-model byte unlinks.

    No FK to ``users`` / ``gallery_items`` so account deletion can cascade DB
    rows while leaving enough key metadata for the sweeper to retry unlinks.

    ``status``:
    - ``pending`` — durable unlink still required
    - ``done`` — file removed or verifiably absent
    - ``quarantined`` — key/URL could not be safely mapped; not treated as successful
      file cleanup (fail-closed provenance for operators)
    """

    __tablename__ = "public_media_cleanup_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    croquis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    gallery_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    # Non-sensitive provenance when the original URL/key could not be mapped safely.
    source_url_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enqueued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
