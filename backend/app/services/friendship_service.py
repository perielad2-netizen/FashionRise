"""Runway Friends — private circle (separate from public Follow)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.user import User
from app.models.user_friendship import (
    FRIENDSHIP_ACCEPTED,
    FRIENDSHIP_PENDING,
    UserFriendship,
)
from app.models.user_profile import UserProfile
from app.schemas.friendship import FriendUserRead, FriendshipRead


def _pair_ids(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (a, b) if a.hex < b.hex else (b, a)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _friend_user_read(db: Session, user: User) -> FriendUserRead:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    display = (profile.display_name if profile and profile.display_name else None) or user.username
    avatar = profile.avatar_url if profile else None
    return FriendUserRead(
        user_id=user.id,
        username=user.username,
        display_name=display,
        avatar_url=avatar,
    )


def _friendship_read(db: Session, row: UserFriendship, viewer_id: uuid.UUID) -> FriendshipRead:
    other_id = row.addressee_id if row.requester_id == viewer_id else row.requester_id
    other = db.get(User, other_id)
    if other is None:
        raise NotFoundError("Friend account missing")
    return FriendshipRead(
        id=row.id,
        status=row.status,
        requester_id=row.requester_id,
        addressee_id=row.addressee_id,
        created_at=row.created_at,
        accepted_at=row.accepted_at,
        friend=_friend_user_read(db, other),
    )


def _find_pair(db: Session, a: uuid.UUID, b: uuid.UUID) -> UserFriendship | None:
    low, high = _pair_ids(a, b)
    return db.scalar(
        select(UserFriendship).where(
            UserFriendship.user_low_id == low,
            UserFriendship.user_high_id == high,
        )
    )


def resolve_target_user(
    db: Session,
    *,
    username: str | None = None,
    user_id: uuid.UUID | None = None,
) -> User:
    if user_id is not None:
        target = db.get(User, user_id)
        if target is None or not target.is_active:
            raise NotFoundError("User not found")
        return target
    name = (username or "").strip()
    if not name:
        raise ValidationAppError("Provide a username or user_id")
    target = db.scalar(select(User).where(User.username.ilike(name)))
    if target is None or not target.is_active:
        raise NotFoundError(f"No FashionRise user named “{name}”")
    return target


def list_friends(db: Session, user: User) -> list[FriendshipRead]:
    rows = db.scalars(
        select(UserFriendship)
        .where(
            UserFriendship.status == FRIENDSHIP_ACCEPTED,
            or_(
                UserFriendship.user_low_id == user.id,
                UserFriendship.user_high_id == user.id,
            ),
        )
        .order_by(UserFriendship.accepted_at.desc().nullslast(), UserFriendship.created_at.desc())
    ).all()
    return [_friendship_read(db, row, user.id) for row in rows]


def list_incoming_requests(db: Session, user: User) -> list[FriendshipRead]:
    rows = db.scalars(
        select(UserFriendship)
        .where(
            UserFriendship.status == FRIENDSHIP_PENDING,
            UserFriendship.addressee_id == user.id,
        )
        .order_by(UserFriendship.created_at.desc())
    ).all()
    return [_friendship_read(db, row, user.id) for row in rows]


def request_friend(
    db: Session,
    requester: User,
    *,
    username: str | None = None,
    user_id: uuid.UUID | None = None,
) -> FriendshipRead:
    target = resolve_target_user(db, username=username, user_id=user_id)
    if target.id == requester.id:
        raise ForbiddenError("You cannot add yourself as a friend")

    existing = _find_pair(db, requester.id, target.id)
    if existing is not None:
        if existing.status == FRIENDSHIP_ACCEPTED:
            raise ConflictError(f"You’re already friends with {target.username}")
        if existing.status == FRIENDSHIP_PENDING:
            if existing.requester_id == requester.id:
                raise ConflictError(f"Friend request to {target.username} is already pending")
            # They already asked you — accept instead of creating a duplicate.
            return accept_friend(db, requester, existing.id)
        raise ConflictError("Friendship is not available for this account")

    low, high = _pair_ids(requester.id, target.id)
    row = UserFriendship(
        id=uuid.uuid4(),
        user_low_id=low,
        user_high_id=high,
        requester_id=requester.id,
        addressee_id=target.id,
        status=FRIENDSHIP_PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _friendship_read(db, row, requester.id)


def accept_friend(db: Session, user: User, friendship_id: uuid.UUID) -> FriendshipRead:
    row = db.get(UserFriendship, friendship_id)
    if row is None:
        raise NotFoundError("Friend request not found")
    if row.addressee_id != user.id:
        raise ForbiddenError("Only the invited friend can accept this request")
    if row.status == FRIENDSHIP_ACCEPTED:
        return _friendship_read(db, row, user.id)
    if row.status != FRIENDSHIP_PENDING:
        raise ConflictError("This friend request can no longer be accepted")
    row.status = FRIENDSHIP_ACCEPTED
    row.accepted_at = _utcnow()
    db.commit()
    db.refresh(row)
    return _friendship_read(db, row, user.id)


def remove_friend(db: Session, user: User, friend_user_id: uuid.UUID) -> None:
    row = _find_pair(db, user.id, friend_user_id)
    if row is None:
        raise NotFoundError("Friendship not found")
    if user.id not in {row.user_low_id, row.user_high_id}:
        raise ForbiddenError("Not your friendship")
    db.delete(row)
    db.commit()


def ensure_accepted_friends(db: Session, user_a: User, user_b: User) -> UserFriendship:
    """Idempotent operator helper — create or upgrade to accepted friendship."""
    if user_a.id == user_b.id:
        raise ForbiddenError("Cannot friend yourself")
    existing = _find_pair(db, user_a.id, user_b.id)
    if existing is not None:
        if existing.status != FRIENDSHIP_ACCEPTED:
            existing.status = FRIENDSHIP_ACCEPTED
            existing.accepted_at = existing.accepted_at or _utcnow()
            db.commit()
            db.refresh(existing)
        return existing
    low, high = _pair_ids(user_a.id, user_b.id)
    row = UserFriendship(
        id=uuid.uuid4(),
        user_low_id=low,
        user_high_id=high,
        requester_id=user_a.id,
        addressee_id=user_b.id,
        status=FRIENDSHIP_ACCEPTED,
        accepted_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
