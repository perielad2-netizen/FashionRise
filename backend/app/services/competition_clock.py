"""Worldwide weekly competition clock — Sunday 00:00 UTC → next Sunday 00:00 UTC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def competition_week_start(now: datetime | None = None) -> datetime:
    """Inclusive start of the current competition week (Sunday 00:00 UTC)."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    days_since_sunday = (now_utc.weekday() + 1) % 7
    start = now_utc - timedelta(days=days_since_sunday)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def competition_week_end(week_start: datetime) -> datetime:
    """Exclusive end — next Sunday 00:00 UTC."""
    return ensure_utc(week_start) + timedelta(days=7)


def previous_week_start(now: datetime | None = None) -> datetime:
    return competition_week_start(now) - timedelta(days=7)


def days_remaining(now: datetime | None = None) -> float:
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    end = competition_week_end(competition_week_start(now_utc))
    return max(0.0, (end - now_utc).total_seconds() / 86400.0)


def seconds_remaining(now: datetime | None = None) -> int:
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    end = competition_week_end(competition_week_start(now_utc))
    return max(0, int((end - now_utc).total_seconds()))


def week_key(week_start: datetime) -> str:
    return ensure_utc(week_start).strftime("%Y-%m-%d")
