"""Friend design handoff — collaboration thread, transfers, and asset grants."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ASSET_KIND_FABRIC = "fabric"
ASSET_KIND_CROQUIS = "croquis"

SHARE_STATUS_PENDING = "pending"
SHARE_STATUS_ACCEPTED = "accepted"
SHARE_STATUS_REJECTED = "rejected"


class DesignCollaboration(Base):
    """Unordered friend pair that can pass designs back and forth."""

    __tablename__ = "design_collaborations"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_design_collaborations_pair"),
        CheckConstraint("user_low_id <> user_high_id", name="ck_design_collaborations_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_low_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    origin_design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garment_designs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesignShareTransfer(Base):
    """One send of a design from friend A → friend B (pending until accepted)."""

    __tablename__ = "design_share_transfers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected')",
            name="ck_design_share_transfers_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("design_collaborations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garment_designs.id", ondelete="SET NULL"), nullable=True
    )
    received_design_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("garment_designs.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SHARE_STATUS_PENDING, index=True
    )
    source_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SharedAssetGrant(Base):
    """Read access to a fabric or croquis granted inside a design collaboration."""

    __tablename__ = "shared_asset_grants"
    __table_args__ = (
        UniqueConstraint(
            "collaboration_id",
            "grantee_id",
            "asset_kind",
            "asset_id",
            name="uq_shared_asset_grants_target",
        ),
        CheckConstraint(
            "asset_kind IN ('fabric', 'croquis')",
            name="ck_shared_asset_grants_kind",
        ),
        CheckConstraint("granter_id <> grantee_id", name="ck_shared_asset_grants_not_self"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("design_collaborations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    grantee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
