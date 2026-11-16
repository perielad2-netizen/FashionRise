"""Server-authoritative FashionRise Stars reward safety gates (fail closed)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.core.config import get_settings
from app.services.competition_clock import competition_week_start, ensure_utc, week_key


def weekly_rewards_enabled() -> bool:
    return bool(get_settings().fashionrise_weekly_rewards_enabled)


def streak_rewards_enabled() -> bool:
    return bool(get_settings().fashionrise_streak_rewards_enabled)


def parse_weekly_rewards_launch_week_start() -> datetime | None:
    """First Sunday UTC week that may receive prizes.

    Mid-week configured timestamps snap to the **next** Sunday so a mid-week
    enable never awards a partial in-progress competition week.
    Empty / invalid → None (fail closed).
    """
    raw = (get_settings().fashionrise_weekly_rewards_launch_week_start or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:
            dt = datetime.fromisoformat(raw + "T00:00:00+00:00")
        else:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    dt = ensure_utc(dt)
    sunday = competition_week_start(dt)
    if dt > sunday:
        return sunday + timedelta(days=7)
    return sunday


def week_eligible_for_weekly_rewards(week_start: datetime) -> bool:
    """True only when rewards are enabled and week_start >= launch Sunday boundary."""
    if not weekly_rewards_enabled():
        return False
    launch = parse_weekly_rewards_launch_week_start()
    if launch is None:
        return False
    return ensure_utc(week_start) >= launch


def parse_streak_rewards_start_date() -> date | None:
    """UTC calendar date when streak days become reward-eligible.

    Empty / invalid → None (fail closed when rewards are enabled).
    """
    raw = (get_settings().fashionrise_streak_rewards_start_date or "").strip()
    if not raw:
        return None
    try:
        if len(raw) >= 10:
            return date.fromisoformat(raw[:10])
    except ValueError:
        return None
    return None


def streak_day_is_reward_eligible(day: date) -> bool:
    """True when streak Stars are enabled and ``day`` is on/after the start boundary."""
    if not streak_rewards_enabled():
        return False
    start = parse_streak_rewards_start_date()
    if start is None:
        return False
    return day >= start


def competition_payout_key_week_start(payout_key: str) -> datetime | None:
    """Parse ``competition:YYYY-MM-DD:...`` payout keys → week_start Sunday UTC."""
    if not payout_key.startswith("competition:"):
        return None
    parts = payout_key.split(":")
    if len(parts) < 2:
        return None
    try:
        dt = datetime.fromisoformat(parts[1] + "T00:00:00+00:00")
    except ValueError:
        return None
    start = competition_week_start(dt)
    if week_key(start) != parts[1]:
        # Require exact Sunday key form used by settlement.
        return None
    return start
