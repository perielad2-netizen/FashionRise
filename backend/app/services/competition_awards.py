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
from app.services.competition_groups import (
    _lock_week,
    ensure_competition_week,
    list_group_rows,
)
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

SETTLE_LOOKBACK_WEEKS = 12


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
    """Credit Stars once per payout_key. Returns True when newly credited.

    Server-authoritative Social reward gates fail closed here — not only in the
    scheduler — so retries/restarts cannot credit when disabled.
    """
    from app.services.fashionrise_reward_gates import (
        competition_payout_key_week_start,
        streak_day_is_reward_eligible,
        streak_rewards_enabled,
        week_eligible_for_weekly_rewards,
        weekly_rewards_enabled,
    )

    if reason.startswith("competition_"):
        if not weekly_rewards_enabled():
            return False
        # Respect launch boundary on the actual credit path (not only settle()).
        week_start = competition_payout_key_week_start(payout_key)
        if week_start is None or not week_eligible_for_weekly_rewards(week_start):
            return False
    if reason == "login_streak":
        if not streak_rewards_enabled():
            return False
        # Fail closed without a valid activation boundary (checked via streak path too).
        from app.services.fashionrise_reward_gates import parse_streak_rewards_start_date
        from app.services.login_streak import utc_today

        if parse_streak_rewards_start_date() is None:
            return False
        if not streak_day_is_reward_eligible(utc_today()):
            return False

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
    from app.services.fashionrise_reward_gates import week_eligible_for_weekly_rewards

    if not week_eligible_for_weekly_rewards(week_start):
        return []

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
    """Settle one week under row lock — concurrent workers cannot double-pay."""
    week = _lock_week(db, week_start)
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


def outstanding_past_weeks(db: Session, *, now: datetime | None = None) -> list[CompetitionWeek]:
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    current = competition_week_start(now_utc)
    return list(
        db.scalars(
            select(CompetitionWeek)
            .where(
                CompetitionWeek.week_start < current,
                CompetitionWeek.status != "locked",
            )
            .order_by(CompetitionWeek.week_start.asc())
        ).all()
    )


def tick_competitions(db: Session, *, now: datetime | None = None) -> dict:
    """Open current week; settle every outstanding past week in order (catch-up safe)."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    current = ensure_competition_week(db, now=now_utc)
    db.flush()

    # Materialize the immediately previous week if missing so empty downtime still advances.
    prev = previous_week_start(now_utc)
    if db.get(CompetitionWeek, prev) is None and competition_week_start(now_utc) > prev:
        ensure_competition_week(db, now=prev)
        db.flush()

    # Also walk lookback for any open rows created before downtime.
    settled_keys: list[str] = []
    for week in outstanding_past_weeks(db, now=now_utc):
        lock_and_settle_week(db, week.week_start)
        settled_keys.append(week_key(week.week_start))
        db.flush()

    return {
        "current_week_start": current.week_start.isoformat(),
        "current_status": current.status,
        "settled_previous": bool(settled_keys),
        "settled_weeks": settled_keys,
    }
