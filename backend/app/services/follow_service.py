import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.user import User
from app.models.user_follow import UserFollow
from app.models.user_profile import UserProfile


def list_following_ids(db: Session, follower_id: uuid.UUID) -> list[uuid.UUID]:
    q = (
        select(UserFollow.following_id)
        .where(UserFollow.follower_id == follower_id)
        .order_by(UserFollow.created_at.desc())
    )
    return list(db.scalars(q).all())


def is_following(db: Session, follower_id: uuid.UUID, following_id: uuid.UUID) -> bool:
    row = db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id,
            UserFollow.following_id == following_id,
        )
    )
    return row is not None


def follow_user(db: Session, follower: User, following_id: uuid.UUID) -> None:
    if follower.id == following_id:
        raise ForbiddenError("You cannot follow yourself")
    target = db.get(User, following_id)
    if not target:
        raise NotFoundError("User not found")
    if is_following(db, follower.id, following_id):
        raise ConflictError("Already following this user")
    db.add(UserFollow(follower_id=follower.id, following_id=following_id))
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == following_id))
    if profile is not None:
        profile.followers_count += 1
    db.commit()


def unfollow_user(db: Session, follower: User, following_id: uuid.UUID) -> None:
    row = db.scalar(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id,
            UserFollow.following_id == following_id,
        )
    )
    if not row:
        raise NotFoundError("Not following this user")
    db.delete(row)
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == following_id))
    if profile is not None:
        profile.followers_count = max(0, profile.followers_count - 1)
    db.commit()
