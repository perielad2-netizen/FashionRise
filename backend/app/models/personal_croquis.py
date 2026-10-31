"""Personal croquis library identity + append-only immutable versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.private_media_asset import PrivateMediaAsset
    from app.models.user import User
    from app.models.user_consent_event import UserConsentEvent

STATUS_AWAITING_UPLOAD = "awaiting_upload"
STATUS_UPLOADED = "uploaded"
STATUS_ARCHIVED = "archived"
STATUS_ERASED = "erased"

VERSION_STATUS_GENERATING = "generating"
VERSION_STATUS_FAILED = "failed"
VERSION_STATUS_REJECTED = "rejected"
VERSION_STATUS_ACCEPTED = "accepted"


class PersonalCroquis(Base):
    """Stable library identity for one subject-photo lineage (owner-private)."""

    __tablename__ = "personal_croquis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("private_media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_AWAITING_UPLOAD)
    storage_consent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_consent_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    adults_attestation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erase_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="personal_croquis")
    source_asset: Mapped[PrivateMediaAsset | None] = relationship(foreign_keys=[source_asset_id])
    storage_consent: Mapped[UserConsentEvent | None] = relationship(foreign_keys=[storage_consent_id])
    versions: Mapped[list[PersonalCroquisVersion]] = relationship(
        back_populates="croquis",
        order_by="PersonalCroquisVersion.version",
    )


class PersonalCroquisVersion(Base):
    """Append-only immutable ``(croquis_id, version) → generated_asset_id`` mapping.

    Accepted rows never mutate ``generated_asset_id``. Regeneration allocates
    ``version = max+1`` with a new asset id. No public Stage A generate endpoint.
    """

    __tablename__ = "personal_croquis_version"
    __table_args__ = (
        UniqueConstraint("croquis_id", "version", name="uq_personal_croquis_version_croquis_version"),
        Index(
            "uq_personal_croquis_version_owner_idempotency",
            "owner_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    croquis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personal_croquis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("private_media_assets.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=VERSION_STATUS_GENERATING)
    ai_consent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_consent_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geometry_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    croquis: Mapped[PersonalCroquis] = relationship(back_populates="versions")
    owner: Mapped[User] = relationship(back_populates="personal_croquis_versions")
    generated_asset: Mapped[PrivateMediaAsset | None] = relationship(
        foreign_keys=[generated_asset_id]
    )
    ai_consent: Mapped[UserConsentEvent | None] = relationship(foreign_keys=[ai_consent_id])
