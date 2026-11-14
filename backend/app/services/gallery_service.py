import uuid
from pathlib import Path

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.gallery_comment import GalleryComment
from app.models.gallery_comment_like import GalleryCommentLike
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.rating import Rating
from app.models.user import User
from app.models.user_follow import UserFollow
from app.models.user_friendship import FRIENDSHIP_ACCEPTED, UserFriendship
from app.schemas.gallery import (
    GalleryCommentCreate,
    GalleryCommentRead,
    GalleryCreate,
    GalleryRead,
    GallerySort,
)
from app.services import ai_service


def to_gallery_read(
    item: GalleryItem,
    *,
    liked_by_me: bool | None = None,
    my_score: int | None = None,
) -> GalleryRead:
    base = GalleryRead.model_validate(item)
    image_path = f"/gallery/{item.id}/image" if item.look_id is not None else None
    return base.model_copy(
        update={"liked_by_me": liked_by_me, "my_score": my_score, "image_path": image_path}
    )


def to_gallery_reads_for_viewer(
    db: Session, items: list[GalleryItem], viewer: User | None
) -> list[GalleryRead]:
    """Attach liked_by_me / my_score in one pass for Runway list cards."""
    if not items:
        return []
    liked_ids: set[uuid.UUID] = set()
    my_scores: dict[uuid.UUID, int] = {}
    if viewer is not None:
        ids = [item.id for item in items]
        liked_ids = set(
            db.scalars(
                select(GalleryLike.gallery_item_id).where(
                    GalleryLike.user_id == viewer.id,
                    GalleryLike.gallery_item_id.in_(ids),
                )
            ).all()
        )
        for gallery_item_id, score in db.execute(
            select(Rating.gallery_item_id, Rating.score).where(
                Rating.user_id == viewer.id,
                Rating.gallery_item_id.in_(ids),
            )
        ):
            my_scores[gallery_item_id] = int(score)
    return [
        to_gallery_read(
            item,
            liked_by_me=(item.id in liked_ids) if viewer is not None else None,
            my_score=my_scores.get(item.id) if viewer is not None else None,
        )
        for item in items
    ]


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


def _accepted_friend_ids(db: Session, viewer_id: uuid.UUID) -> list[uuid.UUID]:
    rows = db.scalars(
        select(UserFriendship).where(
            UserFriendship.status == FRIENDSHIP_ACCEPTED,
            or_(
                UserFriendship.user_low_id == viewer_id,
                UserFriendship.user_high_id == viewer_id,
            ),
        )
    ).all()
    out: list[uuid.UUID] = []
    for row in rows:
        other = row.user_high_id if row.user_low_id == viewer_id else row.user_low_id
        out.append(other)
    return out


def list_circle_feed(
    db: Session, *, viewer: User, limit: int = 50, offset: int = 0
) -> list[GalleryItem]:
    """Friends + own published looks only — default Runway home feed."""
    friend_ids = _accepted_friend_ids(db, viewer.id)
    allowed = [viewer.id, *friend_ids]
    q = (
        _public_gallery_base()
        .where(GalleryItem.user_id.in_(allowed))
        .order_by(GalleryItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(q).all())


def list_top_worldwide(db: Session, *, limit: int = 10) -> list[GalleryItem]:
    """Worldwide rankings board (likes, then rating). Caps at Top 50."""
    cap = max(1, min(int(limit or 10), 50))
    q = (
        _public_gallery_base()
        .order_by(
            GalleryItem.likes_count.desc(),
            GalleryItem.rating_average.desc().nulls_last(),
            GalleryItem.rating_count.desc(),
            GalleryItem.created_at.desc(),
        )
        .limit(cap)
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
    if item.user_id == user.id:
        raise ForbiddenError("You can’t like your own Runway look")
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
    from app.services import push_service as push_service

    push_service.notify_runway_like(
        db, owner_id=item.user_id, actor=user, look_title=item.title
    )


def remove_gallery_like(db: Session, user: User, gallery_item_id: uuid.UUID) -> None:
    item = get_gallery_item(db, gallery_item_id)
    if item.user_id == user.id:
        raise ForbiddenError("You can’t unlike your own Runway look")
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


def to_comment_read(
    row: GalleryComment, *, liked_by_me: bool | None = None
) -> GalleryCommentRead:
    username = None
    if getattr(row, "user", None) is not None:
        username = row.user.username
    return GalleryCommentRead.model_validate(row).model_copy(
        update={"username": username, "liked_by_me": liked_by_me}
    )


def to_comment_reads_for_viewer(
    db: Session, rows: list[GalleryComment], viewer: User | None
) -> list[GalleryCommentRead]:
    if not rows:
        return []
    liked_ids: set[uuid.UUID] = set()
    if viewer is not None:
        ids = [row.id for row in rows]
        liked_ids = set(
            db.scalars(
                select(GalleryCommentLike.comment_id).where(
                    GalleryCommentLike.user_id == viewer.id,
                    GalleryCommentLike.comment_id.in_(ids),
                )
            ).all()
        )
    return [
        to_comment_read(
            row,
            liked_by_me=(row.id in liked_ids) if viewer is not None else None,
        )
        for row in rows
    ]


def list_gallery_comments(db: Session, gallery_item_id: uuid.UUID) -> list[GalleryComment]:
    get_gallery_item(db, gallery_item_id)
    q = (
        select(GalleryComment)
        .options(joinedload(GalleryComment.user))
        .where(
            GalleryComment.gallery_item_id == gallery_item_id,
            GalleryComment.moderation_status == "ok",
        )
        .order_by(GalleryComment.created_at.asc())
    )
    return list(db.scalars(q).unique().all())


def get_gallery_comment(db: Session, comment_id: uuid.UUID) -> GalleryComment:
    row = db.scalar(
        select(GalleryComment)
        .options(joinedload(GalleryComment.user))
        .where(GalleryComment.id == comment_id)
    )
    if row is None or row.moderation_status != "ok":
        raise NotFoundError("Comment not found")
    # Parent look must still be public.
    get_gallery_item(db, row.gallery_item_id)
    return row


def add_gallery_comment(
    db: Session, user: User, gallery_item_id: uuid.UUID, data: GalleryCommentCreate
) -> GalleryComment:
    item = get_gallery_item(db, gallery_item_id)
    body = " ".join((data.body or "").split()).strip()
    if not body:
        raise ValidationAppError("Comment cannot be empty")
    if len(body) > 4000:
        raise ValidationAppError("Comment is too long")
    row = GalleryComment(gallery_item_id=item.id, user_id=user.id, body=body, likes_count=0)
    db.add(row)
    db.commit()
    db.refresh(row)
    from app.services import push_service as push_service

    push_service.notify_runway_comment(
        db,
        owner_id=item.user_id,
        actor=user,
        look_title=item.title,
        snippet=body,
    )
    # Reload with author for Runway username chip.
    loaded = db.scalar(
        select(GalleryComment)
        .options(joinedload(GalleryComment.user))
        .where(GalleryComment.id == row.id)
    )
    return loaded or row


def add_comment_like(db: Session, user: User, comment_id: uuid.UUID) -> GalleryComment:
    row = get_gallery_comment(db, comment_id)
    if row.user_id == user.id:
        raise ForbiddenError("You can’t like your own comment")
    existing = db.scalar(
        select(GalleryCommentLike).where(
            GalleryCommentLike.user_id == user.id,
            GalleryCommentLike.comment_id == row.id,
        )
    )
    if existing:
        raise ConflictError("Already liked")
    db.add(GalleryCommentLike(user_id=user.id, comment_id=row.id))
    row.likes_count += 1
    db.commit()
    db.refresh(row)
    from app.services import push_service as push_service

    push_service.notify_comment_like(db, author_id=row.user_id, actor=user, snippet=row.body)
    return get_gallery_comment(db, row.id)


def remove_comment_like(db: Session, user: User, comment_id: uuid.UUID) -> GalleryComment:
    row = get_gallery_comment(db, comment_id)
    like = db.scalar(
        select(GalleryCommentLike).where(
            GalleryCommentLike.user_id == user.id,
            GalleryCommentLike.comment_id == row.id,
        )
    )
    if not like:
        raise NotFoundError("Like not found")
    db.delete(like)
    row.likes_count = max(0, row.likes_count - 1)
    db.commit()
    db.refresh(row)
    return get_gallery_comment(db, row.id)
