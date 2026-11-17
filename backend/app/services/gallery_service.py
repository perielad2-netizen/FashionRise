import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.models.gallery_comment import GalleryComment
from app.models.gallery_comment_like import GalleryCommentLike
from app.models.gallery_impression import GalleryImpression
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.garment_design import GarmentDesign
from app.models.rating import Rating
from app.models.user import User
from app.models.user_follow import UserFollow
from app.models.user_friendship import FRIENDSHIP_ACCEPTED, UserFriendship
from app.models.user_profile import UserProfile
from app.schemas.gallery import (
    GalleryCommentCreate,
    GalleryCommentRead,
    GalleryCreate,
    GalleryRead,
    GallerySort,
)
from app.services import ai_service
from app.services.gallery_discover import (
    DISCOVER_WINDOW,
    ELIGIBLE_HARD_CAP,
    DiscoverCandidate,
    diversify_select_page,
    rank_discover_candidates,
)


def to_gallery_read(
    item: GalleryItem,
    *,
    liked_by_me: bool | None = None,
    my_score: int | None = None,
    username: str | None = None,
    avatar_url: str | None = None,
    comments_count: int | None = None,
) -> GalleryRead:
    base = GalleryRead.model_validate(item)
    image_path = f"/gallery/{item.id}/image" if item.look_id is not None else None
    author = username
    if author is None:
        # Prefer already-loaded relationship when present (no extra query).
        related = getattr(item, "user", None)
        if related is not None:
            author = getattr(related, "username", None)
    return base.model_copy(
        update={
            "liked_by_me": liked_by_me,
            "my_score": my_score,
            "image_path": image_path,
            "username": author,
            "avatar_url": avatar_url,
            "comments_count": max(0, int(comments_count or 0)),
        }
    )


def to_gallery_reads_for_viewer(
    db: Session, items: list[GalleryItem], viewer: User | None
) -> list[GalleryRead]:
    """Attach liked_by_me / my_score / author username in one pass for Runway cards."""
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

    usernames: dict[uuid.UUID, str] = {}
    avatar_urls: dict[uuid.UUID, str | None] = {}
    author_ids = list({item.user_id for item in items})
    if author_ids:
        for user_id, username in db.execute(
            select(User.id, User.username).where(User.id.in_(author_ids))
        ):
            usernames[user_id] = username
        for user_id, avatar_url in db.execute(
            select(UserProfile.user_id, UserProfile.avatar_url).where(
                UserProfile.user_id.in_(author_ids)
            )
        ):
            avatar_urls[user_id] = avatar_url

    comment_counts: dict[uuid.UUID, int] = {}
    ids = [item.id for item in items]
    if ids:
        for gallery_item_id, count in db.execute(
            select(GalleryComment.gallery_item_id, func.count())
            .where(
                GalleryComment.gallery_item_id.in_(ids),
                GalleryComment.moderation_status == "ok",
            )
            .group_by(GalleryComment.gallery_item_id)
        ):
            comment_counts[gallery_item_id] = int(count)

    return [
        to_gallery_read(
            item,
            liked_by_me=(item.id in liked_ids) if viewer is not None else None,
            my_score=my_scores.get(item.id) if viewer is not None else None,
            username=usernames.get(item.user_id),
            avatar_url=avatar_urls.get(item.user_id),
            comments_count=comment_counts.get(item.id, 0),
        )
        for item in items
    ]


def _record_public_publish_consent_for_gallery(
    db: Session,
    user: User,
    *,
    attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> None:
    """Reuse Runway public-publish notice/version/hash for legacy POST /gallery."""
    import hashlib

    from app.core.config import get_settings
    from app.models.user_consent_event import PURPOSE_RUNWAY_SHARE, UserConsentEvent

    settings = get_settings()
    if not attested:
        raise ValidationAppError(
            "Confirm you have the rights to publish this content and authorize "
            "FashionRise to display it publicly."
        )
    expected_version = (settings.runway_share_consent_version or "").strip()
    notice = (settings.runway_share_notice_text or "").strip()
    if not expected_version or not notice:
        raise ValidationAppError("Public-publish consent is not configured on this server yet.")
    if notice_version != expected_version:
        raise ValidationAppError("Public-publish notice version is not current.")
    expected_hash = hashlib.sha256(notice.encode("utf-8")).hexdigest()
    if (notice_text_hash or "").lower() != expected_hash.lower():
        raise ValidationAppError("Public-publish notice text does not match the approved copy.")

    db.add(
        UserConsentEvent(
            id=uuid.uuid4(),
            owner_id=user.id,
            purpose=PURPOSE_RUNWAY_SHARE,
            consent_version=expected_version,
            adults_attested=False,
            text_hash=expected_hash,
        )
    )
    db.flush()


def create_gallery_item(db: Session, user: User, data: GalleryCreate) -> GalleryItem:
    if data.look_id is not None:
        raise ValidationAppError("Publish looks via POST /looks/{id}/publish")
    if data.design_id is None:
        raise ValidationAppError("design_id is required")
    design = db.get(GarmentDesign, data.design_id)
    if not design or design.user_id != user.id:
        raise ForbiddenError("You can only publish your own designs")
    visibility = (data.visibility or "public").strip().lower() or "public"
    if visibility == "public":
        _record_public_publish_consent_for_gallery(
            db,
            user,
            attested=bool(data.public_publish_attested),
            notice_version=(data.notice_version or "").strip(),
            notice_text_hash=(data.notice_text_hash or "").strip(),
        )
    item = GalleryItem(
        design_id=data.design_id,
        user_id=user.id,
        title=data.title,
        image_url=data.image_url,
        visibility=visibility,
    )
    db.add(item)
    if visibility == "public":
        from app.services.competition_groups import enroll_on_activity

        enroll_on_activity(db, user.id)
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
        from app.services.competition_groups import enroll_on_activity

        enroll_on_activity(db, user.id)
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
    from app.services.competition_groups import enroll_on_activity

    enroll_on_activity(db, user.id)
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


def _discover_eligible_filter():
    """All public, moderated-ok publishes — no hard age cut (endless Discover)."""
    return (
        GalleryItem.visibility == "public",
        GalleryItem.moderation_status == "ok",
    )


def _discover_projection():
    return (
        GalleryItem.id,
        GalleryItem.user_id,
        GalleryItem.likes_count,
        GalleryItem.rating_count,
        GalleryItem.unique_impressions_count,
        GalleryItem.created_at,
    )


def fetch_discover_candidate_rows(
    db: Session,
    *,
    cutoff: datetime | None = None,
    now: datetime,
    hard_cap: int = ELIGIBLE_HARD_CAP,
):
    """Bounded candidate set over all public publishes.

    Under the cap: load every eligible row. Over the cap: take a fair per-day
    quota across the recent stratify window (cold-start first), then backfill
    older under-seen looks so the endless feed is not newest-only.
    """
    filters = _discover_eligible_filter()
    total = int(
        db.scalar(select(func.count()).select_from(GalleryItem).where(*filters)) or 0
    )
    if total <= hard_cap:
        return list(
            db.execute(
                select(*_discover_projection())
                .where(*filters)
                .order_by(GalleryItem.created_at.desc())
            ).all()
        )

    window_start = cutoff if cutoff is not None else (now - DISCOVER_WINDOW)
    # Stratify across UTC day buckets inside the recent window.
    bucket_count = max(1, int(DISCOVER_WINDOW.total_seconds() // 86400) or 7)
    per_bucket = max(1, hard_cap // (bucket_count + 1))
    out: list = []
    seen: set[uuid.UUID] = set()
    for i in range(bucket_count):
        start = window_start + timedelta(days=i)
        end = min(start + timedelta(days=1), now + timedelta(seconds=1))
        bucket_rows = db.execute(
            select(*_discover_projection())
            .where(
                *filters,
                GalleryItem.created_at >= start,
                GalleryItem.created_at < end,
            )
            .order_by(
                GalleryItem.unique_impressions_count.asc(),
                (GalleryItem.likes_count + GalleryItem.rating_count).desc(),
                GalleryItem.created_at.desc(),
            )
            .limit(per_bucket)
        ).all()
        for row in bucket_rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)

    # Backfill older-than-window cold starts so legacy publishes stay discoverable.
    remaining = hard_cap - len(out)
    if remaining > 0:
        older_rows = db.execute(
            select(*_discover_projection())
            .where(*filters, GalleryItem.created_at < window_start)
            .order_by(
                GalleryItem.unique_impressions_count.asc(),
                (GalleryItem.likes_count + GalleryItem.rating_count).desc(),
                GalleryItem.created_at.desc(),
            )
            .limit(remaining)
        ).all()
        for row in older_rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            out.append(row)
    return out


def _viewer_seen_gallery_ids(
    db: Session, viewer_id: uuid.UUID, candidate_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Impression rows for this viewer among the current Discover candidate set."""
    if not candidate_ids:
        return set()
    rows = db.scalars(
        select(GalleryImpression.gallery_item_id).where(
            GalleryImpression.viewer_user_id == viewer_id,
            GalleryImpression.gallery_item_id.in_(candidate_ids),
        )
    ).all()
    return set(rows)


def list_discover_feed(
    db: Session,
    *,
    limit: int = 48,
    offset: int = 0,
    exclude_ids: list[uuid.UUID] | None = None,
    now: datetime | None = None,
    viewer: User | None = None,
) -> list[GalleryItem]:
    """Fair Discovery: all public publishes, per-page creator diversity, optional exclude.

    When ``viewer`` is signed in, already-impressed looks are demoted and a
    viewer+time explore salt rotates near-tied scores so the feed feels alive.
    """
    now_utc = now or datetime.now(timezone.utc)
    rank_rows = fetch_discover_candidate_rows(db, now=now_utc)
    candidates = [
        DiscoverCandidate(
            id=row.id,
            user_id=row.user_id,
            likes_count=int(row.likes_count or 0),
            rating_count=int(row.rating_count or 0),
            unique_impressions_count=int(row.unique_impressions_count or 0),
            created_at=row.created_at,
        )
        for row in rank_rows
    ]
    seen_ids: set[uuid.UUID] = set()
    viewer_id = viewer.id if viewer is not None else None
    if viewer_id is not None:
        seen_ids = _viewer_seen_gallery_ids(db, viewer_id, [c.id for c in candidates])
    scored = rank_discover_candidates(
        candidates,
        now=now_utc,
        viewer_id=viewer_id,
        seen_ids=seen_ids,
    )
    skip = list(exclude_ids or [])
    # One API response = one diversified page (≤2 looks/creator). Load-more uses exclude=.
    # Legacy offset paging skips prior full pages so caps reset per page, not mid-response.
    if offset > 0 and not skip:
        seen: list[uuid.UUID] = []
        consumed = 0
        guard = 0
        while consumed < offset and guard < offset + 5:
            guard += 1
            chunk = diversify_select_page(scored, limit=limit, exclude_ids=seen)
            if not chunk:
                return []
            take = min(len(chunk), offset - consumed)
            seen.extend(c.id for c in chunk[:take])
            consumed += take
            if take < len(chunk):
                break
        skip = seen
    page = diversify_select_page(scored, limit=limit, exclude_ids=skip)
    if not page:
        return []
    page_ids = [c.id for c in page]
    items = list(db.scalars(select(GalleryItem).where(GalleryItem.id.in_(page_ids))).all())
    by_id = {item.id: item for item in items}
    return [by_id[item_id] for item_id in page_ids if item_id in by_id]


def record_gallery_impressions(
    db: Session,
    viewer: User,
    gallery_item_ids: list[uuid.UUID],
) -> int:
    """Record unique Discover impressions. Concurrent-safe; skips self/duplicates."""
    from sqlalchemy.exc import IntegrityError

    if not gallery_item_ids:
        return 0
    # Preserve order, de-dupe request payload.
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for item_id in gallery_item_ids[:100]:
        if item_id in seen:
            continue
        seen.add(item_id)
        ordered.append(item_id)

    items = list(
        db.scalars(
            select(GalleryItem).where(
                GalleryItem.id.in_(ordered),
                GalleryItem.visibility == "public",
                GalleryItem.moderation_status == "ok",
            )
        ).all()
    )
    by_id = {item.id: item for item in items}
    recorded = 0
    for item_id in ordered:
        item = by_id.get(item_id)
        if item is None or item.user_id == viewer.id:
            continue
        try:
            # Savepoint so a race on the unique constraint does not abort the whole batch.
            # Counters use SQL +1 so concurrent *different* viewers cannot lose updates.
            def _insert_and_bump() -> None:
                db.add(
                    GalleryImpression(
                        gallery_item_id=item.id,
                        viewer_user_id=viewer.id,
                    )
                )
                db.flush()
                db.execute(
                    update(GalleryItem)
                    .where(GalleryItem.id == item.id)
                    .values(
                        impressions_count=GalleryItem.impressions_count + 1,
                        unique_impressions_count=GalleryItem.unique_impressions_count + 1,
                    )
                )

            if hasattr(db, "begin_nested"):
                with db.begin_nested():
                    _insert_and_bump()
            else:
                _insert_and_bump()
            recorded += 1
        except IntegrityError:
            # Concurrent duplicate for the same viewer×item — treat as already recorded.
            continue
    db.commit()
    return recorded


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
    from app.services.competition_groups import enroll_on_activity

    enroll_on_activity(db, user.id)
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
    from app.services.competition_groups import enroll_on_activity

    enroll_on_activity(db, user.id)
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
