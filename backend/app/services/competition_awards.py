"""Weekly Star awards — one prize per user, deterministic, idempotent payouts."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.competition import CompetitionAward, CompetitionGroup, CompetitionWeek, StarPayout
from app.models.user import User
from app.services import ai_stars
from app.services.competition_clock import (
    competition_week_end,
    competition_week_start,
    ensure_utc,
    previous_week_start,
    week_key,
)
from app.services.competition_groups import ensure_competition_week, list_group_rows
from app.services.competition_scoring import (
    ScoredDesign,
    ScoredUser,
    community_champion_scores,
    design_engagement_scores,
    designer_scores_from_designs,
    commenter_scores,
    rater_scores,
    supporter_scores,
)

_log = logging.getLogger(__name__)

# Highest value first so multi-qualified users keep the best prize.
AWARD_DEFS: list[tuple[str, int]] = [
    ("top_design", 50),
    ("top_designer", 50),
    ("community_champion", 50),
    ("top_supporter", 20),
    ("top_commenter", 20),
    ("top_rater", 20),
]

CATEGORY_LABELS = {
    "top_design": "Top Design",
    "top_designer": "Top Designer",
    "community_champion": "Community Champion",
    "top_supporter": "Top Supporter",
    "top_commenter": "Top Commenter",
    "top_rater": "Top Rater",
}


@dataclass(frozen=True)
class AwardPick:
    category: str
    stars: int
    user_id: uuid.UUID
    score: int
    gallery_item_id: uuid.UUID | None = None


def _pick_first_free(
    ranked: list[ScoredUser],
    *,
    awarded: set[uuid.UUID],
) -> ScoredUser | None:
    for row in ranked:
        if row.user_id in awarded:
            continue
        if row.score <= 0:
            continue
        return row
    return None


def _pick_top_design(
    ranked: list[ScoredDesign],
    *,
    awarded: set[uuid.UUID],
) -> ScoredDesign | None:
    for row in ranked:
        if row.user_id in awarded:
            continue
        if row.score <= 0:
            continue
        return row
    return None


def select_group_winners(
    db: Session,
    *,
    week_start: datetime,
    week_end: datetime,
    group_id: uuid.UUID,
) -> list[AwardPick]:
    designs = design_engagement_scores(
        db, week_start=week_start, week_end=week_end, group_id=group_id
    )
    designers = designer_scores_from_designs(designs)
    champions = community_champion_scores(
        db,
        week_start=week_start,
        week_end=week_end,
        group_id=group_id,
        design_scores=designs,
    )
    supporters = supporter_scores(
        db, week_start=week_start, week_end=week_end, group_id=group_id
    )
    commenters = commenter_scores(
        db, week_start=week_start, week_end=week_end, group_id=group_id
    )
    raters = rater_scores(db, week_start=week_start, week_end=week_end, group_id=group_id)

    awarded: set[uuid.UUID] = set()
    picks: list[AwardPick] = []

    for category, stars in AWARD_DEFS:
        if category == "top_design":
            win = _pick_top_design(designs, awarded=awarded)
            if win is None:
                continue
            awarded.add(win.user_id)
            picks.append(
                AwardPick(
                    category=category,
                    stars=stars,
                    user_id=win.user_id,
                    score=win.score,
                    gallery_item_id=win.gallery_item_id,
                )
            )
            continue

        pool = {
            "top_designer": designers,
            "community_champion": champions,
            "top_supporter": supporters,
            "top_commenter": commenters,
            "top_rater": raters,
        }[category]
        win_u = _pick_first_free(pool, awarded=awarded)
        if win_u is None:
            continue
        awarded.add(win_u.user_id)
        picks.append(
            AwardPick(
                category=category,
                stars=stars,
                user_id=win_u.user_id,
                score=win_u.score,
            )
        )
    return picks


def credit_payout_idempotent(
    db: Session,
    *,
    user_id: uuid.UUID,
    amount: int,
    payout_key: str,
    reason: str,
) -> bool:
    """Credit Stars once per payout_key. Returns True when newly credited."""
    existing = db.scalar(select(StarPayout).where(StarPayout.payout_key == payout_key))
    if existing is not None:
        return False
    user = db.get(User, user_id)
    if user is None:
        return False
    payout = StarPayout(
        payout_key=payout_key,
        user_id=user_id,
        amount=int(amount),
        reason=reason,
    )
    try:
        with db.begin_nested():
            db.add(payout)
            db.flush()
    except IntegrityError:
        return False
    ai_stars.credit_stars(db, user, int(amount), reason=reason)
    return True


def settle_group_awards(
    db: Session,
    *,
    week_start: datetime,
    group: CompetitionGroup,
) -> list[CompetitionAward]:
    week_end = competition_week_end(week_start)
    picks = select_group_winners(
        db, week_start=week_start, week_end=week_end, group_id=group.id
    )
    out: list[CompetitionAward] = []
    wk = week_key(week_start)
    for pick in picks:
        payout_key = f"competition:{wk}:g{group.group_index}:{pick.category}"
        existing = db.scalar(
            select(CompetitionAward).where(CompetitionAward.payout_key == payout_key)
        )
        if existing is not None:
            out.append(existing)
            continue
        award = CompetitionAward(
            week_start=week_start,
            group_id=group.id,
            category=pick.category,
            user_id=pick.user_id,
            gallery_item_id=pick.gallery_item_id,
            stars_amount=pick.stars,
            payout_key=payout_key,
            score=pick.score,
        )
        try:
            with db.begin_nested():
                db.add(award)
                db.flush()
        except IntegrityError:
            again = db.scalar(
                select(CompetitionAward).where(CompetitionAward.payout_key == payout_key)
            )
            if again is not None:
                out.append(again)
            continue
        credit_payout_idempotent(
            db,
            user_id=pick.user_id,
            amount=pick.stars,
            payout_key=payout_key,
            reason=f"competition_{pick.category}",
        )
        out.append(award)
    return out


def lock_and_settle_week(db: Session, week_start: datetime) -> CompetitionWeek:
    week = db.get(CompetitionWeek, week_start)
    if week is None:
        week = CompetitionWeek(
            week_start=week_start,
            week_end=competition_week_end(week_start),
            status="open",
        )
        try:
            with db.begin_nested():
                db.add(week)
                db.flush()
        except IntegrityError:
            week = db.get(CompetitionWeek, week_start)
            if week is None:
                raise
    if week.status == "locked":
        return week

    groups = list_group_rows(db, week_start)
    for group in groups:
        settle_group_awards(db, week_start=week_start, group=group)

    week.status = "locked"
    week.locked_at = datetime.now(timezone.utc)
    db.add(week)
    db.flush()
    _log.info("competition_week_locked week=%s groups=%s", week_key(week_start), len(groups))
    return week


def tick_competitions(db: Session, *, now: datetime | None = None) -> dict:
    """Open current week; lock+settle previous week once the new week has started."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    current = ensure_competition_week(db, now=now_utc)
    db.flush()

    prev = previous_week_start(now_utc)
    prev_row = db.get(CompetitionWeek, prev)
    settled = False
    if competition_week_start(now_utc) > prev:
        if prev_row is None:
            prev_row = CompetitionWeek(
                week_start=prev,
                week_end=competition_week_end(prev),
                status="open",
            )
            try:
                with db.begin_nested():
                    db.add(prev_row)
                    db.flush()
            except IntegrityError:
                prev_row = db.get(CompetitionWeek, prev)
        if prev_row is not None and prev_row.status != "locked":
            lock_and_settle_week(db, prev)
            settled = True

    return {
        "current_week_start": current.week_start.isoformat(),
        "current_status": current.status,
        "settled_previous": settled,
    }
