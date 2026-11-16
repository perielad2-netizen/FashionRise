"""Server-authoritative FashionRise Stars reward safety gates (fail closed)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import get_settings
from app.services.competition_clock import competition_week_start, ensure_utc


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
