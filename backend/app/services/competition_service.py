"""Competition status + standings — read-only for GET (no financial/group side effects)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.competition import (
    CompetitionAward,
    CompetitionGroup,
    CompetitionWeek,
)
from app.models.user import User
from app.services.competition_awards import AWARD_DEFS, CATEGORY_LABELS
from app.services.competition_clock import (
    competition_week_end,
    competition_week_start,
    days_remaining,
    ensure_utc,
    seconds_remaining,
    week_key,
)
from app.services.competition_groups import get_membership, list_group_rows
from app.services.competition_scoring import (
    design_engagement_scores,
    designer_scores_from_designs,
)


def _username_map(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.username).where(User.id.in_(user_ids))).all()
    return {row.id: row.username for row in rows}


def build_competition_status(
    db: Session,
    user: User | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Read-only status. Does not enroll, settle, or credit Stars."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    week_start = competition_week_start(now_utc)
    week_end = competition_week_end(week_start)
    week = db.get(CompetitionWeek, week_start)
    status = week.status if week is not None else "open"
    groups = list_group_rows(db, week_start) if week is not None else []

    member = None
    standing = None
    top_designs: list[dict] = []
    top_designers: list[dict] = []
    if user is not None:
        member = get_membership(db, user.id, week_start=week_start)
        if member is not None:
            group = db.get(CompetitionGroup, member.group_id)
            all_designs = design_engagement_scores(
                db,
                week_start=week_start,
                week_end=week_end,
                group_id=member.group_id,
            )
            designers = designer_scores_from_designs(all_designs)
            rank = next(
                (i + 1 for i, row in enumerate(designers) if row.user_id == user.id),
                None,
            )
            my_score = next(
                (row.score for row in designers if row.user_id == user.id),
                0,
            )
            standing = {
                "group_index": group.group_index if group else None,
                "group_id": str(member.group_id),
                "participant_count": int(group.participant_count or 0) if group else 0,
                "designer_rank": rank,
                "designer_score": my_score,
            }
            names = _username_map(
                db,
                [d.user_id for d in all_designs[:10]] + [d.user_id for d in designers[:10]],
            )
            top_designs = [
                {
                    "gallery_item_id": str(d.gallery_item_id),
                    "user_id": str(d.user_id),
                    "username": names.get(d.user_id),
                    "score": d.score,
                }
                for d in all_designs[:10]
            ]
            top_designers = [
                {
                    "user_id": str(d.user_id),
                    "username": names.get(d.user_id),
                    "score": d.score,
                }
                for d in designers[:10]
            ]

    from app.services.fashionrise_reward_gates import (
        parse_weekly_rewards_launch_week_start,
        week_eligible_for_weekly_rewards,
        weekly_rewards_enabled,
    )

    stars_by_id = {cid: stars for cid, stars in AWARD_DEFS}
    launch = parse_weekly_rewards_launch_week_start()
    rewards_live = week_eligible_for_weekly_rewards(week_start)
    publish_note = "Publish anytime. Designs compete in the week they are published."
    if not weekly_rewards_enabled() or not rewards_live:
        publish_note += " Weekly Star prizes are not active yet."
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_key": week_key(week_start),
        "status": status,
        "days_remaining": round(days_remaining(now_utc), 2),
        "seconds_remaining": seconds_remaining(now_utc),
        "group_count": len(groups),
        "standing": standing,
        "top_designs": top_designs,
        "top_designers": top_designers,
        "award_categories": [
            {"id": cid, "label": CATEGORY_LABELS[cid], "stars": stars_by_id[cid]}
            for cid, _ in AWARD_DEFS
        ],
        "runway_note": "Worldwide Runway Top 10/20/50 stays global — groups affect weekly prizes only.",
        "publish_note": publish_note,
        "weekly_rewards_enabled": rewards_live,
        "weekly_rewards_launch_week_start": launch.date().isoformat() if launch else None,
    }


def list_week_awards(
    db: Session,
    *,
    week_start: datetime | None = None,
    group_index: int | None = None,
) -> list[dict]:
    start = competition_week_start(week_start) if week_start else previous_locked_or_current(db)
    q = select(CompetitionAward).where(CompetitionAward.week_start == start)
    if group_index is not None:
        group = db.scalar(
            select(CompetitionGroup).where(
                CompetitionGroup.week_start == start,
                CompetitionGroup.group_index == group_index,
            )
        )
        if group is None:
            return []
        q = q.where(CompetitionAward.group_id == group.id)
    rows = list(db.scalars(q.order_by(CompetitionAward.stars_amount.desc())).all())
    names = _username_map(db, [r.user_id for r in rows])
    group_indexes = {g.id: g.group_index for g in list_group_rows(db, start)}
    return [
        {
            "category": r.category,
            "label": CATEGORY_LABELS.get(r.category, r.category),
            "user_id": str(r.user_id),
            "username": names.get(r.user_id),
            "gallery_item_id": str(r.gallery_item_id) if r.gallery_item_id else None,
            "stars_amount": r.stars_amount,
            "score": r.score,
            "group_index": group_indexes.get(r.group_id),
            "week_start": r.week_start.isoformat(),
        }
        for r in rows
    ]


def previous_locked_or_current(db: Session) -> datetime:
    locked = db.scalars(
        select(CompetitionWeek)
        .where(CompetitionWeek.status == "locked")
        .order_by(CompetitionWeek.week_start.desc())
        .limit(1)
    ).first()
    if locked is not None:
        return locked.week_start
    return competition_week_start()
