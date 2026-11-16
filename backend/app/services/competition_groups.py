"""Scalable weekly competition groups (≤50k eligible participants each)."""

from __future__ import annotations

import hashlib
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


def _create_group(db: Session, week_start: datetime, group_index: int) -> CompetitionGroup:
    group = CompetitionGroup(
        week_start=week_start, group_index=group_index, participant_count=0
    )
    db.add(group)
    db.flush()
    return group


def assign_participant(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> CompetitionGroupMember:
    """Assign user to one weekly group. Sticky for the week; capacity-aware for newcomers."""
    week = ensure_competition_week(db, now=now)
    if week.status != "open":
        # Still allow read of existing membership after lock; no new assigns mid-settle.
        existing = db.scalar(
            select(CompetitionGroupMember).where(
                CompetitionGroupMember.week_start == week.week_start,
                CompetitionGroupMember.user_id == user_id,
            )
        )
        if existing is not None:
            return existing
        raise RuntimeError("Competition week is locked")

    existing = db.scalar(
        select(CompetitionGroupMember).where(
            CompetitionGroupMember.week_start == week.week_start,
            CompetitionGroupMember.user_id == user_id,
        )
    )
    if existing is not None:
        return existing

    groups = list_group_rows(db, week.week_start)
    if not groups:
        groups = [_create_group(db, week.week_start, 0)]

    underfilled = [g for g in groups if int(g.participant_count or 0) < GROUP_CAPACITY]
    if not underfilled:
        next_index = max(g.group_index for g in groups) + 1
        underfilled = [_create_group(db, week.week_start, next_index)]
        groups.append(underfilled[0])

    pick = underfilled[_stable_bucket(user_id, week.week_start, len(underfilled))]
    member = CompetitionGroupMember(
        week_start=week.week_start,
        group_id=pick.id,
        user_id=user_id,
    )
    try:
        with db.begin_nested():
            db.add(member)
            db.flush()
            db.execute(
                update(CompetitionGroup)
                .where(CompetitionGroup.id == pick.id)
                .values(participant_count=CompetitionGroup.participant_count + 1)
            )
            db.flush()
    except IntegrityError:
        again = db.scalar(
            select(CompetitionGroupMember).where(
                CompetitionGroupMember.week_start == week.week_start,
                CompetitionGroupMember.user_id == user_id,
            )
        )
        if again is None:
            raise
        return again
    return member


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


def ensure_participant_if_eligible(
    db: Session,
    user_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> CompetitionGroupMember | None:
    week = ensure_competition_week(db, now=now)
    existing = db.scalar(
        select(CompetitionGroupMember).where(
            CompetitionGroupMember.week_start == week.week_start,
            CompetitionGroupMember.user_id == user_id,
        )
    )
    if existing is not None:
        return existing
    if not is_eligible_participant(
        db, user_id, week_start=week.week_start, week_end=week.week_end
    ):
        return None
    return assign_participant(db, user_id, now=now)


def required_group_count(participant_total: int) -> int:
    if participant_total <= 0:
        return 1
    return max(1, (int(participant_total) + GROUP_CAPACITY - 1) // GROUP_CAPACITY)
