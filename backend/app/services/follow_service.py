import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.user import User
from app.models.user_follow import UserFollow
from app.models.user_profile import UserProfile
from app.schemas.profile import FollowerListItem


def list_following_ids(db: Session, follower_id: uuid.UUID) -> list[uuid.UUID]:
    q = (
        select(UserFollow.following_id)
        .where(UserFollow.follower_id == follower_id)
        .order_by(UserFollow.created_at.desc())
    )
    return list(db.scalars(q).all())


def _people_rows(
    db: Session,
    *,
    user_ids: list[uuid.UUID],
    viewer_id: uuid.UUID | None,
) -> list[FollowerListItem]:
    if not user_ids:
        return []
    users = {
        row.id: row
        for row in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    }
    profiles = {
        row.user_id: row
        for row in db.scalars(
            select(UserProfile).where(UserProfile.user_id.in_(user_ids))
        ).all()
    }
    following_ids: set[uuid.UUID] = set()
    if viewer_id is not None:
        following_ids = set(
            db.scalars(
                select(UserFollow.following_id).where(
                    UserFollow.follower_id == viewer_id,
                    UserFollow.following_id.in_(user_ids),
                )
            ).all()
        )
    out: list[FollowerListItem] = []
    for uid in user_ids:
        user = users.get(uid)
        if user is None:
            continue
        profile = profiles.get(uid)
        out.append(
            FollowerListItem(
                user_id=uid,
                username=user.username,
                display_name=(profile.display_name if profile else None) or user.username,
                avatar_url=profile.avatar_url if profile else None,
                following=uid in following_ids,
            )
        )
    return out


def list_followers(
    db: Session,
    user_id: uuid.UUID,
    *,
    viewer_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FollowerListItem]:
    target = db.get(User, user_id)
    if not target:
        raise NotFoundError("User not found")
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    follower_ids = list(
        db.scalars(
            select(UserFollow.follower_id)
            .where(UserFollow.following_id == user_id)
            .order_by(UserFollow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return _people_rows(db, user_ids=follower_ids, viewer_id=viewer_id)


def list_following_people(
    db: Session,
    user_id: uuid.UUID,
    *,
    viewer_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FollowerListItem]:
    target = db.get(User, user_id)
    if not target:
        raise NotFoundError("User not found")
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    following_ids = list(
        db.scalars(
            select(UserFollow.following_id)
            .where(UserFollow.follower_id == user_id)
            .order_by(UserFollow.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return _people_rows(db, user_ids=following_ids, viewer_id=viewer_id)


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
