import uuid
from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.iap_purchase import IapPurchase
    from app.models.user import User


class IapGoogleNotification(Base):
    """Idempotent ledger for Google Play RTDN / Pub/Sub push messages."""

    __tablename__ = "iap_google_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    purchase_token: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    package_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    iap_purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("iap_purchases.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    audit_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    purchase: Mapped["IapPurchase | None"] = relationship()
    user: Mapped["User | None"] = relationship()
