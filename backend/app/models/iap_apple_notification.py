"""App Store Server Notifications V2 receipts (idempotent by notification UUID)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.iap_purchase import IapPurchase
    from app.models.user import User


class IapAppleNotification(Base):
    """Durable ASN V2 receipt. Financial effects live on adjustments + purchase state."""

    __tablename__ = "iap_apple_notifications"
    __table_args__ = (
        UniqueConstraint("notification_uuid", name="uq_iap_apple_notifications_uuid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    signed_date_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Verified nested transaction fields (never trust client claims).
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    original_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    app_account_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # processing | applied | ignored | unmatched | failed | needs_reconciliation
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    iap_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iap_purchases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Safe non-secret audit crumbs only (no full JWS).
    audit_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    purchase: Mapped[IapPurchase | None] = relationship()
    user: Mapped[User | None] = relationship()
