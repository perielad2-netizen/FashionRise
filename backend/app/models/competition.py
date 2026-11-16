"""FashionRise weekly competitions — groups, awards, idempotent Star payouts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
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
    from app.models.gallery_item import GalleryItem
    from app.models.user import User


class CompetitionWeek(Base):
    __tablename__ = "competition_weeks"

    week_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    week_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'open'")
    )  # open | locked
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    groups: Mapped[list["CompetitionGroup"]] = relationship(
        back_populates="week", cascade="all, delete-orphan"
    )


class CompetitionGroup(Base):
    __tablename__ = "competition_groups"
    __table_args__ = (
        UniqueConstraint("week_start", "group_index", name="uq_competition_groups_week_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        ForeignKey("competition_weeks.week_start", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    week: Mapped["CompetitionWeek"] = relationship(back_populates="groups")
    members: Mapped[list["CompetitionGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    awards: Mapped[list["CompetitionAward"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class CompetitionGroupMember(Base):
    __tablename__ = "competition_group_members"
    __table_args__ = (
        UniqueConstraint("week_start", "user_id", name="uq_competition_group_members_week_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        ForeignKey("competition_weeks.week_start", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competition_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    group: Mapped["CompetitionGroup"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


class CompetitionAward(Base):
    __tablename__ = "competition_awards"
    __table_args__ = (
        UniqueConstraint(
            "week_start",
            "group_id",
            "category",
            name="uq_competition_awards_week_group_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        ForeignKey("competition_weeks.week_start", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("competition_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gallery_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gallery_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    stars_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payout_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    group: Mapped["CompetitionGroup"] = relationship(back_populates="awards")
    user: Mapped["User"] = relationship()
    gallery_item: Mapped["GalleryItem | None"] = relationship()


class StarPayout(Base):
    """Idempotent Stars credit ledger (competition awards, streaks, etc.)."""

    __tablename__ = "star_payouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payout_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LoginStreak(Base):
    __tablename__ = "login_streaks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_checkin_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lifetime_checkins: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
