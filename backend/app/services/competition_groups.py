"""Scalable weekly competition groups (≤50k eligible participants each)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.competition import (
    CompetitionGroup,
    CompetitionGroupMember,
    CompetitionWeek,
)
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.rating import Rating
from app.services.competition_clock import (
    competition_week_end,
    competition_week_start,
    ensure_utc,
)

GROUP_CAPACITY = 50_000
_log = logging.getLogger(__name__)


def ensure_competition_week(db: Session, *, now: datetime | None = None) -> CompetitionWeek:
    start = competition_week_start(now)
    end = competition_week_end(start)
    row = db.get(CompetitionWeek, start)
    if row is not None:
        return row
    row = CompetitionWeek(week_start=start, week_end=end, status="open")
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.get(CompetitionWeek, start)
        if existing is None:
            raise
        return existing
    return row


def _stable_bucket(user_id: uuid.UUID, week_start: datetime, modulus: int) -> int:
    if modulus <= 1:
        return 0
    raw = f"{week_start.isoformat()}:{user_id}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % modulus


def list_group_rows(db: Session, week_start: datetime) -> list[CompetitionGroup]:
    return list(
        db.scalars(
            select(CompetitionGroup)
            .where(CompetitionGroup.week_start == week_start)
            .order_by(CompetitionGroup.group_index.asc())
        ).all()
    )


def _create_group(db: Session, week_start: datetime, group_index: int) -> CompetitionGroup | None:
    group = CompetitionGroup(
        week_start=week_start, group_index=group_index, participant_count=0
    )
    try:
        with db.begin_nested():
            db.add(group)
            db.flush()
        return group
    except IntegrityError:
        return None


def _lock_week(db: Session, week_start: datetime) -> CompetitionWeek:
    row = db.execute(
        select(CompetitionWeek)
        .where(CompetitionWeek.week_start == week_start)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None:
        ensure_competition_week(db, now=week_start)
        row = db.execute(
            select(CompetitionWeek)
            .where(CompetitionWeek.week_start == week_start)
            .with_for_update()
        ).scalar_one()
    return row


def assign_participant(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> CompetitionGroupMember:
    """Assign user to one weekly group. Sticky; capacity enforced transactionally."""
    week = ensure_competition_week(db, now=now)
    week = _lock_week(db, week.week_start)

    existing = db.scalar(
        select(CompetitionGroupMember).where(
            CompetitionGroupMember.week_start == week.week_start,
            CompetitionGroupMember.user_id == user_id,
        )
    )
    if existing is not None:
        return existing

    if week.status != "open":
        raise RuntimeError("Competition week is locked")

    for _ in range(12):
        groups = list_group_rows(db, week.week_start)
        underfilled = [g for g in groups if int(g.participant_count or 0) < GROUP_CAPACITY]
        if not underfilled:
            next_index = (max((g.group_index for g in groups), default=-1) + 1)
            created = _create_group(db, week.week_start, next_index)
            if created is None:
                # Concurrent creator won the unique index — retry with refreshed rows.
                continue
            underfilled = [created]

        # Fill least-loaded groups first; break ties deterministically.
        min_count = min(int(g.participant_count or 0) for g in underfilled)
        candidates = [g for g in underfilled if int(g.participant_count or 0) == min_count]
        pick = candidates[_stable_bucket(user_id, week.week_start, len(candidates))]

        bumped = db.execute(
            update(CompetitionGroup)
            .where(
                CompetitionGroup.id == pick.id,
                CompetitionGroup.participant_count < GROUP_CAPACITY,
            )
            .values(participant_count=CompetitionGroup.participant_count + 1)
        )
        if bumped.rowcount != 1:
            continue

        member = CompetitionGroupMember(
            week_start=week.week_start,
            group_id=pick.id,
            user_id=user_id,
        )
        try:
            with db.begin_nested():
                db.add(member)
                db.flush()
            return member
        except IntegrityError:
            # Another request enrolled this user; undo the reserved seat.
            db.execute(
                update(CompetitionGroup)
                .where(CompetitionGroup.id == pick.id)
                .values(
                    participant_count=CompetitionGroup.participant_count - 1,
                )
            )
            again = db.scalar(
                select(CompetitionGroupMember).where(
                    CompetitionGroupMember.week_start == week.week_start,
                    CompetitionGroupMember.user_id == user_id,
                )
            )
            if again is not None:
                return again
            raise

    raise RuntimeError("Could not assign competition group")


def enroll_on_activity(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> CompetitionGroupMember | None:
    """Auto-enroll after publish/like/comment/rate. Safe no-op if week is locked."""
    try:
        return assign_participant(db, user_id, now=now)
    except RuntimeError as exc:
        _log.info("competition_enroll_skipped user_id=%s reason=%s", user_id, exc)
        return None


def is_eligible_participant(
    db: Session,
    user_id: uuid.UUID,
    *,
    week_start: datetime,
    week_end: datetime,
) -> bool:
    """Actual weekly activity — not lifetime inactive registrations."""
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    published = db.scalar(
        select(GalleryItem.id)
        .where(
            GalleryItem.user_id == user_id,
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
            GalleryItem.created_at >= start,
            GalleryItem.created_at < end,
        )
        .limit(1)
    )
    if published is not None:
        return True
    liked = db.scalar(
        select(GalleryLike.id)
        .where(
            GalleryLike.user_id == user_id,
            GalleryLike.created_at >= start,
            GalleryLike.created_at < end,
        )
        .limit(1)
    )
    if liked is not None:
        return True
    commented = db.scalar(
        select(GalleryComment.id)
        .where(
            GalleryComment.user_id == user_id,
            GalleryComment.moderation_status == "ok",
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
        )
        .limit(1)
    )
    if commented is not None:
        return True
    rated = db.scalar(
        select(Rating.id)
        .where(
            Rating.user_id == user_id,
            Rating.created_at >= start,
            Rating.created_at < end,
        )
        .limit(1)
    )
    return rated is not None


def get_membership(
    db: Session, user_id: uuid.UUID, *, week_start: datetime
) -> CompetitionGroupMember | None:
    return db.scalar(
        select(CompetitionGroupMember).where(
            CompetitionGroupMember.week_start == week_start,
            CompetitionGroupMember.user_id == user_id,
        )
    )


def ensure_participant_if_eligible(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> CompetitionGroupMember | None:
    """Legacy helper — prefer enroll_on_activity at write paths; status is read-only."""
    week_start = competition_week_start(now)
    existing = get_membership(db, user_id, week_start=week_start)
    if existing is not None:
        return existing
    week = db.get(CompetitionWeek, week_start)
    week_end = competition_week_end(week_start) if week is None else week.week_end
    if not is_eligible_participant(
        db, user_id, week_start=week_start, week_end=week_end
    ):
        return None
    return enroll_on_activity(db, user_id, now=now)


def enroll_users_active_this_week(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    limit: int = 500,
) -> int:
    """Catch up people who engaged this week but missed sticky enroll (older clients).

    Live boards call this so Top Design / Designer / Commenter reflect real FashionRise
    activity instead of only the first couple of auto-enrolled accounts.
    """
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    ids: set[uuid.UUID] = set()
    for query in (
        select(GalleryItem.user_id).where(
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
            GalleryItem.created_at >= start,
            GalleryItem.created_at < end,
        ),
        select(GalleryLike.user_id).where(
            GalleryLike.created_at >= start,
            GalleryLike.created_at < end,
        ),
        select(GalleryComment.user_id).where(
            GalleryComment.moderation_status == "ok",
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
        ),
        select(Rating.user_id).where(
            Rating.created_at >= start,
            Rating.created_at < end,
        ),
        # Owners of looks that received engagement this week — so their designs can rank.
        select(GalleryItem.user_id)
        .join(GalleryLike, GalleryLike.gallery_item_id == GalleryItem.id)
        .where(
            GalleryLike.created_at >= start,
            GalleryLike.created_at < end,
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        ),
        select(GalleryItem.user_id)
        .join(GalleryComment, GalleryComment.gallery_item_id == GalleryItem.id)
        .where(
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
            GalleryComment.moderation_status == "ok",
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        ),
        select(GalleryItem.user_id)
        .join(Rating, Rating.gallery_item_id == GalleryItem.id)
        .where(
            Rating.created_at >= start,
            Rating.created_at < end,
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        ),
    ):
        ids.update(db.scalars(query.limit(limit)).all())
        if len(ids) >= limit:
            break
    enrolled = 0
    for user_id in list(ids)[:limit]:
        before = get_membership(db, user_id, week_start=start)
        if before is not None:
            continue
        if enroll_on_activity(db, user_id, now=start) is not None:
            enrolled += 1
    if enrolled:
        db.commit()
    return enrolled


def required_group_count(participant_total: int) -> int:
    if participant_total <= 0:
        return 1
    return max(1, (int(participant_total) + GROUP_CAPACITY - 1) // GROUP_CAPACITY)
