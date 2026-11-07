import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


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
    stars_credited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship()
