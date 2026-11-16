"""Weekly competition clock helpers."""

from datetime import datetime, timezone

from app.services.competition_clock import (
    competition_week_end,
    competition_week_start,
    days_remaining,
    previous_week_start,
)


def test_week_starts_sunday_utc():
    # Wednesday
    now = datetime(2026, 11, 18, 15, 30, tzinfo=timezone.utc)
    start = competition_week_start(now)
    assert start == datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)
    assert competition_week_end(start) == datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc)


def test_sunday_midnight_is_new_week():
    now = datetime(2026, 11, 22, 0, 0, tzinfo=timezone.utc)
    assert competition_week_start(now) == now
    assert previous_week_start(now) == datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)


def test_days_remaining_exclusive_end():
    now = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)  # Sat noon
    remaining = days_remaining(now)
    assert 0.4 < remaining < 0.6
