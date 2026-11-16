"""Weekly awards: one prize per user, idempotent Stars, week-scoped scores."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.rating import Rating
from app.models.user import User
from app.services.competition_awards import (
    lock_and_settle_week,
    select_group_winners,
    tick_competitions,
)
from app.services.competition_clock import competition_week_start
from app.services.competition_groups import assign_participant, ensure_competition_week
from app.services.login_streak import record_daily_checkin
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _user(db, email: str, username: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _publish_item(db, user: User, *, created_at: datetime, title: str) -> GalleryItem:
    item = GalleryItem(
        user_id=user.id,
        title=title,
        image_url="https://example.com/look.png",
        visibility="public",
        moderation_status="ok",
        created_at=created_at,
    )
    db.add(item)
    db.flush()
    return item


def test_one_award_per_user_prefers_highest_prize(client, db_session):
    week = competition_week_start(datetime(2026, 11, 18, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))

    register_with_invite(client, db_session, "aw_a@example.com", "awA")
    register_with_invite(client, db_session, "aw_b@example.com", "awB")
    register_with_invite(client, db_session, "aw_c@example.com", "awC")
    a = _user(db_session, "aw_a@example.com", "awA")
    b = _user(db_session, "aw_b@example.com", "awB")
    c = _user(db_session, "aw_c@example.com", "awC")

    for u in (a, b, c):
        assign_participant(db_session, u.id, now=week + timedelta(hours=2))

    item_a = _publish_item(db_session, a, created_at=week + timedelta(days=1), title="A look")
    item_b = _publish_item(db_session, b, created_at=week + timedelta(days=1), title="B look")

    # A gets dominant design engagement; also gives many likes (would win supporter too).
    for _ in range(5):
        fan = User(
            email=f"fan_{uuid.uuid4().hex[:8]}@example.com",
            username=f"fan_{uuid.uuid4().hex[:8]}",
            hashed_password="x",
        )
        db_session.add(fan)
        db_session.flush()
        assign_participant(db_session, fan.id, now=week + timedelta(hours=3))
        db_session.add(
            GalleryLike(
                user_id=fan.id,
                gallery_item_id=item_a.id,
                created_at=week + timedelta(days=2),
            )
        )
        db_session.add(
            Rating(
                user_id=fan.id,
                gallery_item_id=item_a.id,
                score=9,
                created_at=week + timedelta(days=2),
            )
        )

    db_session.add(
        GalleryLike(
            user_id=a.id,
            gallery_item_id=item_b.id,
            created_at=week + timedelta(days=2),
        )
    )
    db_session.add(
        GalleryLike(
            user_id=c.id,
            gallery_item_id=item_b.id,
            created_at=week + timedelta(days=2),
        )
    )
    db_session.flush()

    member = assign_participant(db_session, a.id, now=week + timedelta(hours=2))
    picks = select_group_winners(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
    )
    by_user: dict[uuid.UUID, list[str]] = {}
    for pick in picks:
        by_user.setdefault(pick.user_id, []).append(pick.category)
    assert all(len(cats) == 1 for cats in by_user.values())
    assert picks[0].category == "top_design"
    assert picks[0].user_id == a.id
    assert picks[0].stars == 50


def test_settle_is_idempotent_on_retry(client, db_session):
    week = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    register_with_invite(client, db_session, "idem_a@example.com", "idemA")
    register_with_invite(client, db_session, "idem_b@example.com", "idemB")
    a = _user(db_session, "idem_a@example.com", "idemA")
    b = _user(db_session, "idem_b@example.com", "idemB")
    assign_participant(db_session, a.id, now=week + timedelta(hours=1))
    assign_participant(db_session, b.id, now=week + timedelta(hours=1))
    item = _publish_item(db_session, a, created_at=week + timedelta(days=1), title="idem look")
    db_session.add(
        GalleryLike(user_id=b.id, gallery_item_id=item.id, created_at=week + timedelta(days=2))
    )
    db_session.flush()
    before = int(a.ai_stars or 0)

    lock_and_settle_week(db_session, week)
    db_session.refresh(a)
    mid = int(a.ai_stars or 0)
    assert mid >= before

    lock_and_settle_week(db_session, week)
    db_session.refresh(a)
    assert int(a.ai_stars or 0) == mid


def test_tick_locks_previous_week_when_new_week_starts(client, db_session):
    prev = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=prev + timedelta(hours=1))
    now = datetime(2026, 11, 22, 0, 5, tzinfo=timezone.utc)
    result = tick_competitions(db_session, now=now)
    db_session.commit()
    assert result["settled_previous"] is True


def test_login_streak_rewards_every_seven_days(client, db_session):
    tokens = register_with_invite(client, db_session, "streak@example.com", "streakUser")
    user = _user(db_session, "streak@example.com", "streakUser")
    before = int(user.ai_stars or 0)
    start = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    for i in range(7):
        status = record_daily_checkin(db_session, user, now=start + timedelta(days=i))
    assert status.current_streak == 7
    assert status.rewarded_this_checkin is True
    assert status.stars_awarded == 10
    db_session.refresh(user)
    assert int(user.ai_stars or 0) == before + 10

    # Same day again — no double credit.
    again = record_daily_checkin(db_session, user, now=start + timedelta(days=6))
    assert again.rewarded_this_checkin is False
    db_session.refresh(user)
    assert int(user.ai_stars or 0) == before + 10

    # Miss a day → reset.
    missed = record_daily_checkin(db_session, user, now=start + timedelta(days=8))
    assert missed.current_streak == 1

    # Check-in endpoint (uses server "now"; still authenticated).
    res = client.post("/api/v1/competitions/streak/check-in", headers=_auth(tokens))
    assert res.status_code == 200
    body = res.json()
    assert body["current_streak"] >= 1
    assert body["reward_stars"] == 10


def test_competition_status_endpoint(client, db_session):
    tokens = register_with_invite(client, db_session, "comp_status@example.com", "compStatus")
    res = client.get("/api/v1/competitions/status", headers=_auth(tokens))
    assert res.status_code == 200, res.text
    body = res.json()
    assert "week_start" in body
    assert "seconds_remaining" in body
    assert body["publish_note"]
    assert "Top Design" in [c["label"] for c in body["award_categories"]]
