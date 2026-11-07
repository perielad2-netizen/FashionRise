"""Private Runway friends circle (distinct from public Follow)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

FRIENDSHIP_PENDING = "pending"
FRIENDSHIP_ACCEPTED = "accepted"


class UserFriendship(Base):
    """Directed request that becomes a mutual friendship when accepted.

    Unique unordered pair via (user_low_id, user_high_id) so A↔B cannot
    create two competing rows.
    """

    __tablename__ = "user_friendships"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_user_friendships_pair"),
        CheckConstraint("user_low_id <> user_high_id", name="ck_user_friendships_not_self"),
        CheckConstraint(
            "requester_id = user_low_id OR requester_id = user_high_id",
            name="ck_user_friendships_requester_in_pair",
        ),
        CheckConstraint(
            "addressee_id = user_low_id OR addressee_id = user_high_id",
            name="ck_user_friendships_addressee_in_pair",
        ),
        CheckConstraint("requester_id <> addressee_id", name="ck_user_friendships_req_ne_addr"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_low_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=FRIENDSHIP_PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
