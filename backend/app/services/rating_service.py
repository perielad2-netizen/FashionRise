import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.gallery_item import GalleryItem
from app.models.rating import Rating
from app.models.user import User
from app.schemas.rating import RatingCreate


def upsert_rating(db: Session, user: User, data: RatingCreate) -> Rating:
    item = db.get(GalleryItem, data.gallery_item_id)
    if not item or item.visibility != "public":
        raise NotFoundError("Gallery item not found")
    existing = db.scalar(
        select(Rating).where(
            Rating.gallery_item_id == data.gallery_item_id,
            Rating.user_id == user.id,
        )
    )
    if existing:
        existing.score = data.score
        db.add(existing)
        db.commit()
        db.refresh(existing)
        _recompute_item_rating(db, data.gallery_item_id)
        return existing
    r = Rating(gallery_item_id=data.gallery_item_id, user_id=user.id, score=data.score)
    db.add(r)
    db.commit()
    db.refresh(r)
    _recompute_item_rating(db, data.gallery_item_id)
    return r


def _recompute_item_rating(db: Session, gallery_item_id: uuid.UUID) -> None:
    item = db.get(GalleryItem, gallery_item_id)
    if not item:
        return
    agg = db.execute(
        select(func.avg(Rating.score), func.count(Rating.id)).where(Rating.gallery_item_id == gallery_item_id)
    ).one()
    avg, cnt = agg[0], int(agg[1] or 0)
    item.rating_average = float(avg) if avg is not None else None
    item.rating_count = cnt
    db.add(item)
    db.commit()


def list_ratings_for_gallery(db: Session, gallery_item_id: uuid.UUID) -> list[Rating]:
    item = db.get(GalleryItem, gallery_item_id)
    if not item or item.visibility != "public" or item.moderation_status != "ok":
        raise NotFoundError("Gallery item not found")
    return list(
        db.scalars(
            select(Rating)
            .where(Rating.gallery_item_id == gallery_item_id)
            .order_by(Rating.created_at.desc())
        ).all()
    )
