"""Week-scoped competition scores — no historical likes carried into a new week."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.competition import CompetitionGroupMember
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.rating import Rating
from app.services.competition_clock import ensure_utc

MIN_COMMENT_CHARS = 8


@dataclass(frozen=True)
class ScoredDesign:
    gallery_item_id: uuid.UUID
    user_id: uuid.UUID
    score: int


@dataclass(frozen=True)
class ScoredUser:
    user_id: uuid.UUID
    score: int


def _member_ids(db: Session, group_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.scalars(
        select(CompetitionGroupMember.user_id).where(
            CompetitionGroupMember.group_id == group_id
        )
    ).all()
    return set(rows)


def _week_designs(
    db: Session, *, week_start: datetime, week_end: datetime, user_ids: set[uuid.UUID]
) -> list[GalleryItem]:
    if not user_ids:
        return []
    return list(
        db.scalars(
            select(GalleryItem).where(
                GalleryItem.user_id.in_(user_ids),
                GalleryItem.visibility == "public",
                GalleryItem.moderation_status == "ok",
                GalleryItem.created_at >= week_start,
                GalleryItem.created_at < week_end,
            )
        ).all()
    )


def design_engagement_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredDesign]:
    """Engagement recorded during the week on designs published in that week."""
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    members = _member_ids(db, group_id)
    designs = _week_designs(db, week_start=start, week_end=end, user_ids=members)
    if not designs:
        return []
    by_id = {d.id: d for d in designs}
    scores: dict[uuid.UUID, int] = defaultdict(int)

    likes = db.execute(
        select(GalleryLike.gallery_item_id, GalleryLike.user_id).where(
            GalleryLike.gallery_item_id.in_(by_id.keys()),
            GalleryLike.created_at >= start,
            GalleryLike.created_at < end,
        )
    ).all()
    for item_id, liker_id in likes:
        owner = by_id[item_id].user_id
        if liker_id == owner:
            continue
        scores[item_id] += 3

    ratings = db.execute(
        select(Rating.gallery_item_id, Rating.user_id, Rating.score).where(
            Rating.gallery_item_id.in_(by_id.keys()),
            Rating.created_at >= start,
            Rating.created_at < end,
        )
    ).all()
    for item_id, rater_id, score in ratings:
        owner = by_id[item_id].user_id
        if rater_id == owner:
            continue
        scores[item_id] += 2 + max(0, min(10, int(score or 0))) // 2

    comments = db.execute(
        select(GalleryComment.gallery_item_id, GalleryComment.user_id, GalleryComment.body).where(
            GalleryComment.gallery_item_id.in_(by_id.keys()),
            GalleryComment.moderation_status == "ok",
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
        )
    ).all()
    for item_id, commenter_id, body in comments:
        owner = by_id[item_id].user_id
        if commenter_id == owner:
            continue
        if len((body or "").strip()) < MIN_COMMENT_CHARS:
            continue
        scores[item_id] += 4

    out = [
        ScoredDesign(gallery_item_id=item_id, user_id=by_id[item_id].user_id, score=score)
        for item_id, score in scores.items()
        if score > 0
    ]
    out.sort(key=lambda row: (-row.score, str(row.gallery_item_id)))
    return out


def designer_scores_from_designs(designs: list[ScoredDesign]) -> list[ScoredUser]:
    totals: dict[uuid.UUID, int] = defaultdict(int)
    for row in designs:
        totals[row.user_id] += row.score
    out = [ScoredUser(user_id=uid, score=score) for uid, score in totals.items()]
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def supporter_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredUser]:
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    members = _member_ids(db, group_id)
    if not members:
        return []
    rows = db.execute(
        select(GalleryLike.user_id, GalleryLike.gallery_item_id, GalleryItem.user_id)
        .join(GalleryItem, GalleryItem.id == GalleryLike.gallery_item_id)
        .where(
            GalleryLike.user_id.in_(members),
            GalleryLike.created_at >= start,
            GalleryLike.created_at < end,
        )
    ).all()
    counts: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for liker_id, item_id, owner_id in rows:
        if liker_id == owner_id:
            continue
        counts[liker_id].add(item_id)
    out = [ScoredUser(user_id=uid, score=len(items)) for uid, items in counts.items()]
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def commenter_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredUser]:
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    members = _member_ids(db, group_id)
    if not members:
        return []
    rows = db.execute(
        select(GalleryComment.user_id, GalleryComment.id, GalleryItem.user_id, GalleryComment.body)
        .join(GalleryItem, GalleryItem.id == GalleryComment.gallery_item_id)
        .where(
            GalleryComment.user_id.in_(members),
            GalleryComment.moderation_status == "ok",
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
        )
    ).all()
    counts: dict[uuid.UUID, int] = defaultdict(int)
    for commenter_id, _cid, owner_id, body in rows:
        if commenter_id == owner_id:
            continue
        if len((body or "").strip()) < MIN_COMMENT_CHARS:
            continue
        counts[commenter_id] += 1
    out = [ScoredUser(user_id=uid, score=n) for uid, n in counts.items()]
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def rater_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredUser]:
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    members = _member_ids(db, group_id)
    if not members:
        return []
    rows = db.execute(
        select(Rating.user_id, Rating.gallery_item_id, GalleryItem.user_id)
        .join(GalleryItem, GalleryItem.id == Rating.gallery_item_id)
        .where(
            Rating.user_id.in_(members),
            Rating.created_at >= start,
            Rating.created_at < end,
        )
    ).all()
    counts: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for rater_id, item_id, owner_id in rows:
        if rater_id == owner_id:
            continue
        counts[rater_id].add(item_id)
    out = [ScoredUser(user_id=uid, score=len(items)) for uid, items in counts.items()]
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def community_champion_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
    design_scores: list[ScoredDesign],
) -> list[ScoredUser]:
    """Meaningful overall participation: publish quality + giving engagement."""
    totals: dict[uuid.UUID, int] = defaultdict(int)
    for row in designer_scores_from_designs(design_scores):
        totals[row.user_id] += row.score * 2
    for row in supporter_scores(db, week_start=week_start, week_end=week_end, group_id=group_id):
        totals[row.user_id] += row.score * 2
    for row in commenter_scores(db, week_start=week_start, week_end=week_end, group_id=group_id):
        totals[row.user_id] += row.score * 3
    for row in rater_scores(db, week_start=week_start, week_end=week_end, group_id=group_id):
        totals[row.user_id] += row.score * 2
    out = [ScoredUser(user_id=uid, score=score) for uid, score in totals.items() if score > 0]
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out
