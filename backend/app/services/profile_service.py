import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.gallery_item import GalleryItem
from app.models.garment_design import GarmentDesign
from app.models.rating import Rating
from app.models.user import User
from app.models.user_follow import UserFollow
from app.models.user_profile import UserProfile
from app.schemas.profile import ProfileRead
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


def _to_reputation_tier(score: float) -> str:
    if score < 20:
        return "newcomer"
    if score < 45:
        return "rising"
    if score < 75:
        return "established"
    return "icon"


def _compute_reputation_score(
    *,
    followers_count: int,
    published_count: int,
    likes_received_count: int,
    rating_average: float,
    rating_count: int,
) -> float:
    weighted = (
        followers_count * 3.0
        + published_count * 4.0
        + likes_received_count * 0.5
        + rating_count * 0.75
        + max(0.0, rating_average - 5.0) * 6.0
    )
    return round(min(100.0, weighted), 1)


def build_profile_read(db: Session, user_id: uuid.UUID) -> ProfileRead:
    profile = get_profile_for_user(db, user_id)

    designs_count = int(
        db.scalar(
            select(func.count())
            .select_from(GarmentDesign)
            .where(GarmentDesign.user_id == user_id)
        )
        or 0
    )
    published_count = int(
        db.scalar(
            select(func.count())
            .select_from(GalleryItem)
            .where(GalleryItem.user_id == user_id)
        )
        or 0
    )
    followers_count = int(
        db.scalar(
            select(func.count())
            .select_from(UserFollow)
            .where(UserFollow.following_id == user_id)
        )
        or 0
    )

    likes_received_count = int(
        db.scalar(
            select(func.coalesce(func.sum(GalleryItem.likes_count), 0))
            .select_from(GalleryItem)
            .where(GalleryItem.user_id == user_id)
        )
        or 0
    )

    rating_average_raw = db.scalar(
        select(func.avg(Rating.score))
        .select_from(Rating)
        .join(GalleryItem, GalleryItem.id == Rating.gallery_item_id)
        .where(GalleryItem.user_id == user_id)
    )
    rating_average = float(rating_average_raw or 0.0)
    rating_count = int(
        db.scalar(
            select(func.count())
            .select_from(Rating)
            .join(GalleryItem, GalleryItem.id == Rating.gallery_item_id)
            .where(GalleryItem.user_id == user_id)
        )
        or 0
    )

    reputation_score = _compute_reputation_score(
        followers_count=followers_count,
        published_count=published_count,
        likes_received_count=likes_received_count,
        rating_average=rating_average,
        rating_count=rating_count,
    )

    return ProfileRead(
        id=profile.id,
        user_id=profile.user_id,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        cover_url=profile.cover_url,
        style_tags=profile.style_tags or [],
        designs_count=designs_count,
        published_count=published_count,
        followers_count=followers_count,
        likes_received_count=likes_received_count,
        rating_average=rating_average,
        rating_count=rating_count,
        reputation_score=reputation_score,
        reputation_tier=_to_reputation_tier(reputation_score),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
