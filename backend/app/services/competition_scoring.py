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

MIN_COMMENT_CHARS = 12
MAX_QUALIFYING_COMMENTS_PER_DESIGN = 2
MAX_LIKES_PER_DESIGNER = 25
MAX_RATINGS_PER_DESIGNER = 25


def _normalize_comment(body: str) -> str:
    return " ".join((body or "").lower().split())


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
    """Unique liked designs, capped per designer so farming one creator does not dominate."""
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
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        )
    ).all()
    per_user_designer: dict[uuid.UUID, dict[uuid.UUID, set[uuid.UUID]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for liker_id, item_id, owner_id in rows:
        if liker_id == owner_id:
            continue
        per_user_designer[liker_id][owner_id].add(item_id)
    out: list[ScoredUser] = []
    for uid, by_designer in per_user_designer.items():
        score = 0
        for items in by_designer.values():
            score += min(len(items), MAX_LIKES_PER_DESIGNER)
        if score > 0:
            out.append(ScoredUser(user_id=uid, score=score))
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def commenter_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredUser]:
    """Meaningful comments only — length, uniqueness, per-design bound, distinct designers."""
    start = ensure_utc(week_start)
    end = ensure_utc(week_end)
    members = _member_ids(db, group_id)
    if not members:
        return []
    rows = db.execute(
        select(
            GalleryComment.user_id,
            GalleryComment.id,
            GalleryComment.gallery_item_id,
            GalleryItem.user_id,
            GalleryComment.body,
        )
        .join(GalleryItem, GalleryItem.id == GalleryComment.gallery_item_id)
        .where(
            GalleryComment.user_id.in_(members),
            GalleryComment.moderation_status == "ok",
            GalleryComment.created_at >= start,
            GalleryComment.created_at < end,
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        )
        .order_by(GalleryComment.created_at.asc(), GalleryComment.id.asc())
    ).all()

    scores: dict[uuid.UUID, int] = defaultdict(int)
    seen_bodies: dict[uuid.UUID, set[str]] = defaultdict(set)
    per_design: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(lambda: defaultdict(int))
    designers_touched: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)

    for commenter_id, _cid, item_id, owner_id, body in rows:
        if commenter_id == owner_id:
            continue
        text = (body or "").strip()
        if len(text) < MIN_COMMENT_CHARS:
            continue
        norm = _normalize_comment(text)
        if not norm or norm in seen_bodies[commenter_id]:
            continue
        if per_design[commenter_id][item_id] >= MAX_QUALIFYING_COMMENTS_PER_DESIGN:
            continue
        seen_bodies[commenter_id].add(norm)
        per_design[commenter_id][item_id] += 1
        designers_touched[commenter_id].add(owner_id)
        scores[commenter_id] += 1

    # Qualifying comments + unique designers (diversity over farming one creator).
    out: list[ScoredUser] = []
    for uid, comment_pts in scores.items():
        diversity = len(designers_touched[uid])
        out.append(ScoredUser(user_id=uid, score=comment_pts + diversity))
    out.sort(key=lambda row: (-row.score, str(row.user_id)))
    return out


def rater_scores(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[ScoredUser]:
    """Unique rated designs, capped per designer."""
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
            GalleryItem.visibility == "public",
            GalleryItem.moderation_status == "ok",
        )
    ).all()
    per_user_designer: dict[uuid.UUID, dict[uuid.UUID, set[uuid.UUID]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for rater_id, item_id, owner_id in rows:
        if rater_id == owner_id:
            continue
        per_user_designer[rater_id][owner_id].add(item_id)
    out: list[ScoredUser] = []
    for uid, by_designer in per_user_designer.items():
        score = 0
        for items in by_designer.values():
            score += min(len(items), MAX_RATINGS_PER_DESIGNER)
        if score > 0:
            out.append(ScoredUser(user_id=uid, score=score))
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
