import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.gallery import GalleryCommentCreate, GalleryCreate, GallerySort


def create_gallery_item(db: Session, user: User, data: GalleryCreate) -> GalleryItem:
    design = db.get(GarmentDesign, data.design_id)
    if not design or design.user_id != user.id:
        raise ForbiddenError("You can only publish your own designs")
    item = GalleryItem(
        design_id=data.design_id,
        user_id=user.id,
        title=data.title,
        image_url=data.image_url,
        visibility=data.visibility,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _public_gallery_base() -> Select:
    return select(GalleryItem).where(
        GalleryItem.visibility == "public",
        GalleryItem.moderation_status == "ok",
    )


def list_public_gallery(
    db: Session, *, limit: int = 50, offset: int = 0, sort: GallerySort = "newest"
) -> list[GalleryItem]:
    q = _public_gallery_base()
    if sort == "top_rated":
        q = q.order_by(GalleryItem.rating_average.desc().nulls_last(), GalleryItem.created_at.desc())
    elif sort == "trending":
        q = q.order_by(
            GalleryItem.likes_count.desc(),
            GalleryItem.rating_average.desc().nulls_last(),
            GalleryItem.created_at.desc(),
        )
    else:
        q = q.order_by(GalleryItem.created_at.desc())
    q = q.limit(limit).offset(offset)
    return list(db.scalars(q).all())


def get_gallery_item(db: Session, item_id: uuid.UUID) -> GalleryItem:
    item = db.get(GalleryItem, item_id)
    if not item:
        raise NotFoundError("Gallery item not found")
    if item.visibility != "public" or item.moderation_status != "ok":
        raise NotFoundError("Gallery item not found")
    return item


def user_has_liked(db: Session, user_id: uuid.UUID, gallery_item_id: uuid.UUID) -> bool:
    q = select(func.count()).select_from(GalleryLike).where(
        GalleryLike.user_id == user_id,
        GalleryLike.gallery_item_id == gallery_item_id,
    )
    return int(db.scalar(q) or 0) > 0


def list_user_gallery(db: Session, user_id: uuid.UUID) -> list[GalleryItem]:
    q = (
        select(GalleryItem)
        .where(
            GalleryItem.user_id == user_id,
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        )
        .order_by(GalleryItem.created_at.desc())
    )
    return list(db.scalars(q).all())


def add_gallery_like(db: Session, user: User, gallery_item_id: uuid.UUID) -> None:
    item = get_gallery_item(db, gallery_item_id)
    existing = db.scalar(
        select(GalleryLike).where(
            GalleryLike.user_id == user.id,
            GalleryLike.gallery_item_id == item.id,
        )
    )
    if existing:
        raise ConflictError("Already liked")
    db.add(GalleryLike(user_id=user.id, gallery_item_id=item.id))
    item.likes_count += 1
    db.commit()


def remove_gallery_like(db: Session, user: User, gallery_item_id: uuid.UUID) -> None:
    item = get_gallery_item(db, gallery_item_id)
    like = db.scalar(
        select(GalleryLike).where(
            GalleryLike.user_id == user.id,
            GalleryLike.gallery_item_id == item.id,
        )
    )
    if not like:
        raise NotFoundError("Like not found")
    db.delete(like)
    item.likes_count = max(0, item.likes_count - 1)
    db.commit()


def list_gallery_comments(db: Session, gallery_item_id: uuid.UUID) -> list[GalleryComment]:
    get_gallery_item(db, gallery_item_id)
    q = (
        select(GalleryComment)
        .where(
            GalleryComment.gallery_item_id == gallery_item_id,
            GalleryComment.moderation_status == "ok",
        )
        .order_by(GalleryComment.created_at.asc())
    )
    return list(db.scalars(q).all())


def add_gallery_comment(db: Session, user: User, gallery_item_id: uuid.UUID, data: GalleryCommentCreate) -> GalleryComment:
    item = get_gallery_item(db, gallery_item_id)
    row = GalleryComment(gallery_item_id=item.id, user_id=user.id, body=data.body)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
