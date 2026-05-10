import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileUpdate


def get_profile_for_user(db: Session, user_id: uuid.UUID) -> UserProfile:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if not profile:
        raise NotFoundError("Profile not found")
    return profile


def update_own_profile(db: Session, user: User, data: ProfileUpdate) -> UserProfile:
    profile = get_profile_for_user(db, user.id)
    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.bio is not None:
        profile.bio = data.bio
    if data.avatar_url is not None:
        profile.avatar_url = data.avatar_url
    if data.cover_url is not None:
        profile.cover_url = data.cover_url
    if data.style_tags is not None:
        profile.style_tags = list(data.style_tags)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_public_profile(db: Session, user_id: uuid.UUID) -> UserProfile:
    profile = get_profile_for_user(db, user_id)
    return profile
