"""Daily login streak — app visits + separate reward-eligible Stars cycle."""

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
    reward_streak: int = 0
    # 1..STREAK_REWARD_DAYS progress inside the current reward cycle (never 8/7).
    cycle_day: int = 0


def utc_today(now: datetime | None = None) -> date:
    return ensure_utc(now or datetime.now(timezone.utc)).date()


def cycle_day_from_streak(streak: int) -> int:
    """Map unbounded consecutive days onto a 1..7 reward-cycle progress."""
    if streak <= 0:
        return 0
    return ((int(streak) - 1) % STREAK_REWARD_DAYS) + 1


def _days_until_reward(reward_streak: int, *, rewards_live: bool) -> int:
    if not rewards_live:
        return STREAK_REWARD_DAYS
    if reward_streak <= 0:
        return STREAK_REWARD_DAYS
    rem = reward_streak % STREAK_REWARD_DAYS
    return STREAK_REWARD_DAYS if rem == 0 else STREAK_REWARD_DAYS - rem


def get_or_create_streak(db: Session, user_id) -> LoginStreak:
    row = db.get(LoginStreak, user_id)
    if row is not None:
        return row
    row = LoginStreak(
        user_id=user_id,
        current_streak=0,
        lifetime_checkins=0,
        reward_streak=0,
    )
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


def effective_reward_streak(row: LoginStreak, today: date) -> int:
    last = row.last_reward_checkin_date
    current = int(row.reward_streak or 0)
    if last is None:
        return 0
    gap = (today - last).days
    if gap > 1:
        return 0
    return current


def streak_status(db: Session, user: User, *, now: datetime | None = None) -> StreakStatus:
    from app.services.fashionrise_reward_gates import streak_day_is_reward_eligible

    today = utc_today(now)
    row = get_or_create_streak(db, user.id)
    current = effective_streak(row, today)
    rewards_live = streak_day_is_reward_eligible(today)
    reward_current = effective_reward_streak(row, today) if rewards_live else 0
    return StreakStatus(
        current_streak=current,
        last_checkin_date=row.last_checkin_date,
        lifetime_checkins=int(row.lifetime_checkins or 0),
        days_until_reward=_days_until_reward(reward_current, rewards_live=rewards_live),
        rewarded_this_checkin=False,
        stars_awarded=0,
        rewards_enabled=rewards_live,
        reward_streak=reward_current,
        cycle_day=cycle_day_from_streak(current),
    )


def record_daily_checkin(
    db: Session, user: User, *, now: datetime | None = None
) -> StreakStatus:
    """Authenticated app visit for the UTC calendar day — not token refresh spam.

    App-wide ``current_streak`` always advances. Reward Stars use a separate
    ``reward_streak`` that only counts days on/after the configured activation
    boundary while ``FASHIONRISE_STREAK_REWARDS_ENABLED`` is true.
    """
    from app.services.fashionrise_reward_gates import streak_day_is_reward_eligible

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
            reward_streak=status.reward_streak,
            cycle_day=status.cycle_day,
        )

    if last is not None and (today - last).days == 1:
        new_streak = int(row.current_streak or 0) + 1
    else:
        new_streak = 1

    row.current_streak = new_streak
    row.last_checkin_date = today
    row.lifetime_checkins = int(row.lifetime_checkins or 0) + 1

    rewards_live = streak_day_is_reward_eligible(today)
    new_reward_streak = int(row.reward_streak or 0)
    if rewards_live:
        last_reward = row.last_reward_checkin_date
        if last_reward is not None and (today - last_reward).days == 1:
            new_reward_streak = int(row.reward_streak or 0) + 1
        else:
            new_reward_streak = 1
        row.reward_streak = new_reward_streak
        row.last_reward_checkin_date = today
    # Days before activation / while disabled do not advance reward_streak.

    db.add(row)
    db.flush()

    rewarded = False
    stars = 0
    if rewards_live and new_reward_streak > 0 and new_reward_streak % STREAK_REWARD_DAYS == 0:
        period = new_reward_streak // STREAK_REWARD_DAYS
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
        days_until_reward=_days_until_reward(new_reward_streak, rewards_live=rewards_live),
        rewarded_this_checkin=rewarded,
        stars_awarded=stars,
        rewards_enabled=rewards_live,
        reward_streak=new_reward_streak if rewards_live else 0,
        cycle_day=cycle_day_from_streak(new_streak),
    )


def has_payout(db: Session, payout_key: str) -> bool:
    return db.scalar(select(StarPayout.id).where(StarPayout.payout_key == payout_key)) is not None
