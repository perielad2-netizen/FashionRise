"""Idempotent Stars wallet adjustments tied to verified Apple IAP events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.iap_apple_notification import IapAppleNotification
    from app.models.iap_purchase import IapPurchase
    from app.models.user import User


class IapStarsAdjustment(Base):
    """Financial adjustment for one Apple notification (or internal reconcile).

    Uniqueness is enforced on ``notification_id`` (partial unique index) so a
    single ASN UUID can never adjust the wallet twice, while a later REFUND
    after REFUND_REVERSED may create a new row under a new notification.
    """

    __tablename__ = "iap_stars_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    iap_purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iap_purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("iap_apple_notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # REFUND | REVOKE | REFUND_REVERSED
    adjustment_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # Positive = Stars added to wallet (or debt reduced); negative = Stars removed / debt added.
    stars_delta_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_delta_debt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    debt_after: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()
    purchase: Mapped["IapPurchase"] = relationship()
    notification: Mapped["IapAppleNotification | None"] = relationship()
