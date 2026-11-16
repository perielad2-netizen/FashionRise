"""Daily login streak — 7 consecutive UTC calendar days → 10 Stars (repeats)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.competition import LoginStreak, StarPayout
from app.models.user import User
from app.services.competition_awards import credit_payout_idempotent
from app.services.competition_clock import ensure_utc

STREAK_REWARD_DAYS = 7
STREAK_REWARD_STARS = 10


@dataclass(frozen=True)
class StreakStatus:
    current_streak: int
    last_checkin_date: date | None
    lifetime_checkins: int
    days_until_reward: int
    rewarded_this_checkin: bool
    stars_awarded: int
    rewards_enabled: bool = False


def utc_today(now: datetime | None = None) -> date:
    return ensure_utc(now or datetime.now(timezone.utc)).date()


def _days_until_reward(current: int) -> int:
    if current <= 0:
        return STREAK_REWARD_DAYS
    rem = current % STREAK_REWARD_DAYS
    return STREAK_REWARD_DAYS if rem == 0 else STREAK_REWARD_DAYS - rem


def get_or_create_streak(db: Session, user_id) -> LoginStreak:
    row = db.get(LoginStreak, user_id)
    if row is not None:
        return row
    row = LoginStreak(user_id=user_id, current_streak=0, lifetime_checkins=0)
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        again = db.get(LoginStreak, user_id)
        if again is None:
            raise
        return again
    return row


def effective_streak(row: LoginStreak, today: date) -> int:
    last = row.last_checkin_date
    current = int(row.current_streak or 0)
    if last is None:
        return 0
    gap = (today - last).days
    if gap > 1:
        return 0
    return current


def streak_status(db: Session, user: User, *, now: datetime | None = None) -> StreakStatus:
    from app.services.fashionrise_reward_gates import streak_rewards_enabled

    today = utc_today(now)
    row = get_or_create_streak(db, user.id)
    current = effective_streak(row, today)
    return StreakStatus(
        current_streak=current,
        last_checkin_date=row.last_checkin_date,
        lifetime_checkins=int(row.lifetime_checkins or 0),
        days_until_reward=_days_until_reward(current),
        rewarded_this_checkin=False,
        stars_awarded=0,
        rewards_enabled=streak_rewards_enabled(),
    )


def record_daily_checkin(
    db: Session, user: User, *, now: datetime | None = None
) -> StreakStatus:
    """Authenticated app visit for the UTC calendar day — not token refresh spam."""
    today = utc_today(now)
    get_or_create_streak(db, user.id)
    # Serialize same-user check-ins so concurrent foreground visits cannot double-count.
    row = db.execute(
        select(LoginStreak).where(LoginStreak.user_id == user.id).with_for_update()
    ).scalar_one()
    last = row.last_checkin_date

    if last == today:
        status = streak_status(db, user, now=now)
        return StreakStatus(
            current_streak=status.current_streak,
            last_checkin_date=status.last_checkin_date,
            lifetime_checkins=status.lifetime_checkins,
            days_until_reward=status.days_until_reward,
            rewarded_this_checkin=False,
            stars_awarded=0,
            rewards_enabled=status.rewards_enabled,
        )

    if last is not None and (today - last).days == 1:
        new_streak = int(row.current_streak or 0) + 1
    else:
        new_streak = 1

    row.current_streak = new_streak
    row.last_checkin_date = today
    row.lifetime_checkins = int(row.lifetime_checkins or 0) + 1
    db.add(row)
    db.flush()

    rewarded = False
    stars = 0
    from app.services.fashionrise_reward_gates import streak_rewards_enabled

    # Visits still advance the streak while rewards are disabled; Stars credit
    # only when the server gate is on (no retroactive dump of prior cycles).
    if (
        streak_rewards_enabled()
        and new_streak > 0
        and new_streak % STREAK_REWARD_DAYS == 0
    ):
        period = new_streak // STREAK_REWARD_DAYS
        payout_key = f"streak:{user.id}:{today.isoformat()}:cycle{period}"
        rewarded = credit_payout_idempotent(
            db,
            user_id=user.id,
            amount=STREAK_REWARD_STARS,
            payout_key=payout_key,
            reason="login_streak",
        )
        if rewarded:
            stars = STREAK_REWARD_STARS

    db.commit()
    return StreakStatus(
        current_streak=new_streak,
        last_checkin_date=today,
        lifetime_checkins=int(row.lifetime_checkins or 0),
        days_until_reward=_days_until_reward(new_streak),
        rewarded_this_checkin=rewarded,
        stars_awarded=stars,
        rewards_enabled=streak_rewards_enabled(),
    )


def has_payout(db: Session, payout_key: str) -> bool:
    return db.scalar(select(StarPayout.id).where(StarPayout.payout_key == payout_key)) is not None
