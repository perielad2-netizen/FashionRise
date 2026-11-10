import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


# Purchase lifecycle (consumable Stars). Transitions are monotonic except
# refunded/revoked → refund_reversed after a verified REFUND_REVERSED.
STATUS_ACTIVE = "active"
STATUS_BLOCKED = "blocked"  # ASN refund/revoke before credit — never credited
STATUS_REFUNDED = "refunded"
STATUS_REVOKED = "revoked"
STATUS_REFUND_REVERSED = "refund_reversed"


class IapPurchase(Base):
    """Verified App Store / Play Store purchase that credited Stars (idempotent)."""

    __tablename__ = "iap_purchases"
    __table_args__ = (
        UniqueConstraint("platform", "transaction_id", name="uq_iap_purchases_platform_txn"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # ios | android
    product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    original_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=STATUS_ACTIVE)
    stars_credited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_clawed_back: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stars_restored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()
