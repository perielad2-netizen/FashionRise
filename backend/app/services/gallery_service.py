import uuid
from pathlib import Path

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.models.user_follow import UserFollow
from app.schemas.gallery import GalleryCommentCreate, GalleryCreate, GalleryRead, GallerySort
from app.services import ai_service


def to_gallery_read(item: GalleryItem, *, liked_by_me: bool | None = None) -> GalleryRead:
    base = GalleryRead.model_validate(item)
    image_path = f"/gallery/{item.id}/image" if item.look_id is not None else None
    return base.model_copy(update={"liked_by_me": liked_by_me, "image_path": image_path})


def create_gallery_item(db: Session, user: User, data: GalleryCreate) -> GalleryItem:
    if data.look_id is not None:
        raise ValidationAppError("Publish looks via POST /looks/{id}/publish")
    if data.design_id is None:
        raise ValidationAppError("design_id is required")
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


def publish_look(
    db: Session,
    user: User,
    *,
    look_id: uuid.UUID,
    title: str,
    design_id: uuid.UUID | None,
) -> GalleryItem:
    # Lazy import avoids looks_service ↔ gallery_service cycle.
    from app.services.looks_service import pick_look_image_job_for_owner

    existing = db.scalar(select(GalleryItem).where(GalleryItem.look_id == look_id))
    if existing is not None:
        if existing.user_id != user.id:
            raise ConflictError("Look is already on the Runway")
        # Idempotent re-publish updates title / keeps the same item.
        existing.title = title[:300]
        if design_id is not None:
            existing.design_id = design_id
        existing.visibility = "public"
        existing.moderation_status = "ok"
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    job = pick_look_image_job_for_owner(db, user, look_id)
    if job is None:
        raise NotFoundError("Look image not available to publish")

    safe_design_id = design_id
    if safe_design_id is not None:
        design = db.get(GarmentDesign, safe_design_id)
        if design is None or design.user_id != user.id:
            safe_design_id = None

    item = GalleryItem(
        design_id=safe_design_id,
        look_id=look_id,
        user_id=user.id,
        title=title[:300],
        image_url=None,
        visibility="public",
        moderation_status="ok",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def unpublish_look(db: Session, user: User, look_id: uuid.UUID) -> None:
    item = db.scalar(
        select(GalleryItem).where(GalleryItem.look_id == look_id, GalleryItem.user_id == user.id)
    )
    if item is None:
        raise NotFoundError("Look is not on the Runway")
    db.delete(item)
    db.commit()


def gallery_item_id_for_look(db: Session, look_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(GalleryItem.id).where(GalleryItem.look_id == look_id))


def map_runway_ids(db: Session, look_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not look_ids:
        return {}
    rows = db.execute(
        select(GalleryItem.look_id, GalleryItem.id).where(GalleryItem.look_id.in_(look_ids))
    ).all()
    out: dict[uuid.UUID, uuid.UUID] = {}
    for look_id, item_id in rows:
        if look_id is not None:
            out[look_id] = item_id
    return out


def resolve_gallery_image_file(db: Session, gallery_item_id: uuid.UUID) -> Path:
    from app.services.looks_service import pick_look_image_job_for_owner

    item = get_gallery_item(db, gallery_item_id)
    if item.look_id is None:
        raise NotFoundError("Gallery image not available")
    owner = db.get(User, item.user_id)
    if owner is None:
        raise NotFoundError("Gallery image not available")
    job = pick_look_image_job_for_owner(db, owner, item.look_id)
    if job is None:
        raise NotFoundError("Gallery image not available")
    return ai_service.resolve_completed_job_image_path(job)


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


def list_following_feed(
    db: Session, *, viewer: User, limit: int = 50, offset: int = 0
) -> list[GalleryItem]:
    sub = select(UserFollow.following_id).where(UserFollow.follower_id == viewer.id)
    q = (
        _public_gallery_base()
        .where(GalleryItem.user_id.in_(sub))
        .order_by(GalleryItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
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


def add_gallery_comment(
    db: Session, user: User, gallery_item_id: uuid.UUID, data: GalleryCommentCreate
) -> GalleryComment:
    item = get_gallery_item(db, gallery_item_id)
    row = GalleryComment(gallery_item_id=item.id, user_id=user.id, body=data.body)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
