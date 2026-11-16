"""Competition group capacity + sticky assignment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.user import User
from app.services.competition_clock import competition_week_start
from app.services.competition_groups import (
    GROUP_CAPACITY,
    assign_participant,
    ensure_competition_week,
    list_group_rows,
    required_group_count,
)
from tests.auth_test_helpers import register_with_invite


def test_required_group_count_scales():
    assert required_group_count(0) == 1
    assert required_group_count(50_000) == 1
    assert required_group_count(50_001) == 2
    assert required_group_count(100_000) == 2
    assert required_group_count(250_000) == 5
    assert required_group_count(1_000_000) == 20


def test_assignment_is_sticky_within_week(client, db_session):
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    ensure_competition_week(db_session, now=now)
    register_with_invite(client, db_session, "grp_a@example.com", "grpA")
    user = db_session.query(User).filter(User.email == "grp_a@example.com").one()
    first = assign_participant(db_session, user.id, now=now)
    second = assign_participant(db_session, user.id, now=now + timedelta(days=2))
    assert first.group_id == second.group_id
    assert first.id == second.id


def test_new_group_opens_when_capacity_full(client, db_session):
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    week = competition_week_start(now)
    ensure_competition_week(db_session, now=now)

    with patch("app.services.competition_groups.GROUP_CAPACITY", 2):
        users = []
        for i in range(3):
            register_with_invite(client, db_session, f"cap_{i}@example.com", f"cap{i}")
            users.append(db_session.query(User).filter(User.email == f"cap_{i}@example.com").one())
            assign_participant(db_session, users[-1].id, now=now)
        groups = list_group_rows(db_session, week)
        assert len(groups) >= 2
        assert sum(int(g.participant_count or 0) for g in groups) == 3
        assert all(int(g.participant_count or 0) <= 2 for g in groups)

    assert GROUP_CAPACITY == 50_000
