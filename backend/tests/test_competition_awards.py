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
        look_id=uuid.uuid4(),
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


def test_settle_is_idempotent_on_retry(client, db_session, monkeypatch):
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_ENABLED", "true")
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_LAUNCH_WEEK_START", "2026-11-08")
    from app.core.config import get_settings

    get_settings.cache_clear()

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
    # Settle selects winners but does not credit until claim.
    assert int(a.ai_stars or 0) == before

    lock_and_settle_week(db_session, week)
    db_session.refresh(a)
    assert int(a.ai_stars or 0) == before

    from app.models.competition import CompetitionAward
    from app.services.competition_awards import claim_competition_award

    award = (
        db_session.query(CompetitionAward)
        .filter(CompetitionAward.user_id == a.id, CompetitionAward.week_start == week)
        .one()
    )
    claim_competition_award(db_session, a, award.id)
    db_session.refresh(a)
    assert int(a.ai_stars or 0) == before + int(award.stars_amount)
    get_settings.cache_clear()


def test_pending_and_claim_award_http(client, db_session, monkeypatch):
    """Winners see pending awards after settle; claim credits Stars once."""
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_ENABLED", "true")
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_LAUNCH_WEEK_START", "2026-11-08")
    from app.core.config import get_settings

    get_settings.cache_clear()

    week = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    tokens_a = register_with_invite(client, db_session, "claim_a@example.com", "claimA")
    register_with_invite(client, db_session, "claim_b@example.com", "claimB")
    a = _user(db_session, "claim_a@example.com", "claimA")
    b = _user(db_session, "claim_b@example.com", "claimB")
    assign_participant(db_session, a.id, now=week + timedelta(hours=1))
    assign_participant(db_session, b.id, now=week + timedelta(hours=1))
    item = _publish_item(db_session, a, created_at=week + timedelta(days=1), title="claim look")
    db_session.add(
        GalleryLike(user_id=b.id, gallery_item_id=item.id, created_at=week + timedelta(days=2))
    )
    db_session.flush()
    before = int(a.ai_stars or 0)

    lock_and_settle_week(db_session, week)
    db_session.commit()

    pending = client.get("/api/v1/competitions/awards/pending", headers=_auth(tokens_a))
    assert pending.status_code == 200
    rows = pending.json()
    assert len(rows) >= 1
    award_id = rows[0]["id"]
    stars = int(rows[0]["stars_amount"])

    claimed = client.post(
        f"/api/v1/competitions/awards/{award_id}/claim",
        headers=_auth(tokens_a),
    )
    assert claimed.status_code == 200
    body = claimed.json()
    assert body["already_claimed"] is False
    assert body["newly_credited"] is True
    assert body["ai_stars"] == before + stars

    again = client.post(
        f"/api/v1/competitions/awards/{award_id}/claim",
        headers=_auth(tokens_a),
    )
    assert again.status_code == 200
    assert again.json()["already_claimed"] is True
    assert again.json()["ai_stars"] == before + stars

    empty = client.get("/api/v1/competitions/awards/pending", headers=_auth(tokens_a))
    assert empty.status_code == 200
    assert empty.json() == []
    get_settings.cache_clear()


def test_tick_locks_previous_week_when_new_week_starts(client, db_session):
    prev = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=prev + timedelta(hours=1))
    now = datetime(2026, 11, 22, 0, 5, tzinfo=timezone.utc)
    result = tick_competitions(db_session, now=now)
    db_session.commit()
    assert result["settled_previous"] is True


def test_login_streak_rewards_every_seven_days(client, db_session, monkeypatch):
    # Explicit activation boundary required after #356 fail-closed gates.
    monkeypatch.setenv("FASHIONRISE_STREAK_REWARDS_ENABLED", "true")
    monkeypatch.setenv("FASHIONRISE_STREAK_REWARDS_START_DATE", "2026-11-01")
    from app.core.config import get_settings

    get_settings.cache_clear()
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
    get_settings.cache_clear()
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
    assert "Top Designs" in [c["label"] for c in body["award_categories"]]


def test_competition_category_board_endpoint(client, db_session):
    tokens = register_with_invite(client, db_session, "comp_board@example.com", "compBoard")
    res = client.get(
        "/api/v1/competitions/categories/top_designer/board",
        headers=_auth(tokens),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["category"] == "top_designer"
    assert body["label"] == "Top Designer"
    assert body["stars"] == 50
    assert isinstance(body["entries"], list)
    bad = client.get("/api/v1/competitions/categories/not_a_cat/board", headers=_auth(tokens))
    assert bad.status_code == 404


def test_top_designs_board_one_look_per_user(client, db_session):
    """Top Designs live board keeps only the best-scored look per designer."""
    from datetime import UTC, datetime, timedelta

    from app.models.gallery_item import GalleryItem
    from app.models.gallery_like import GalleryLike
    from app.models.rating import Rating
    from app.models.user import User
    from app.services.competition_clock import competition_week_start
    from app.services.competition_groups import enroll_on_activity
    from app.services.competition_service import build_category_board

    week = competition_week_start(datetime(2026, 11, 18, 12, tzinfo=UTC))
    author = register_with_invite(client, db_session, "tdedupe_a@example.com", "tdedupeA")
    fan = register_with_invite(client, db_session, "tdedupe_b@example.com", "tdedupeB")
    author_id = uuid.UUID(client.get("/api/v1/auth/me", headers=_auth(author)).json()["id"])
    fan_id = uuid.UUID(client.get("/api/v1/auth/me", headers=_auth(fan)).json()["id"])

    strong = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=author_id,
        title="strong look",
        image_url="https://example.com/s.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    weak = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=author_id,
        title="weak look",
        image_url="https://example.com/w.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    db_session.add_all([strong, weak])
    db_session.flush()
    enroll_on_activity(db_session, author_id, now=week + timedelta(hours=2))
    enroll_on_activity(db_session, fan_id, now=week + timedelta(hours=2))
    db_session.add(
        GalleryLike(user_id=fan_id, gallery_item_id=strong.id, created_at=week + timedelta(days=2))
    )
    db_session.add(
        Rating(
            user_id=fan_id,
            gallery_item_id=strong.id,
            score=10,
            created_at=week + timedelta(days=2),
        )
    )
    db_session.add(
        GalleryLike(user_id=fan_id, gallery_item_id=weak.id, created_at=week + timedelta(days=2))
    )
    db_session.commit()

    board = build_category_board(
        db_session,
        db_session.get(User, author_id),
        category="top_design",
        now=week + timedelta(days=3),
    )
    assert board["label"] == "Top Designs"
    user_ids = [e["user_id"] for e in board["entries"]]
    assert user_ids.count(str(author_id)) == 1
    assert all(int(e["score"]) > 0 for e in board["entries"])
    assert board["entries"][0]["gallery_item_id"] == str(strong.id)
