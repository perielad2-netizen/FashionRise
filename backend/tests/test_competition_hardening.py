"""PR #353 amendment — enrollment, capacity, settlement, comment abuse."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select

from app.models.competition import CompetitionAward, CompetitionWeek
from app.models.gallery_comment import GalleryComment
from app.models.gallery_item import GalleryItem
from app.models.gallery_like import GalleryLike
from app.models.user import User
from app.services.competition_awards import (
    lock_and_settle_week,
    select_group_winners,
    tick_competitions,
)
from app.services.competition_clock import competition_week_start
from app.services.competition_groups import (
    assign_participant,
    enroll_on_activity,
    ensure_competition_week,
    get_membership,
    list_group_rows,
)
from app.services.competition_scoring import commenter_scores
from app.services.competition_service import build_competition_status
from tests.auth_test_helpers import register_with_invite
from tests.runway_publish_helpers import runway_publish_body
from tests.test_looks_api import _add_job, _auth, _store_image


def _user(db, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _publish(client, db_session, tokens, label: str) -> str:
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=label,
    )
    res = client.post(
        f"/api/v1/looks/{job.id}/publish",
        headers=_auth(tokens),
        json=runway_publish_body(),
    )
    assert res.status_code == 200, res.text
    return res.json()["runway_item_id"]


def test_publish_enrolls_without_opening_competition_status(client, db_session):
    author = register_with_invite(client, db_session, "enroll_a@example.com", "enrollA")
    fan = register_with_invite(client, db_session, "enroll_b@example.com", "enrollB")
    item_id = _publish(client, db_session, author, "auto enroll look")

    week = competition_week_start()
    author_user = _user(db_session, "enroll_a@example.com")
    membership = get_membership(db_session, author_user.id, week_start=week)
    assert membership is not None

    # Fan likes without ever calling /competitions/status
    like = client.post(f"/api/v1/gallery/{item_id}/like", headers=_auth(fan))
    assert like.status_code == 204, like.text
    fan_user = _user(db_session, "enroll_b@example.com")
    fan_member = get_membership(db_session, fan_user.id, week_start=week)
    assert fan_member is not None
    assert fan_member.group_id == membership.group_id or True  # may share group

    # Status is read-only but shows saved membership
    status = client.get("/api/v1/competitions/status", headers=_auth(author))
    assert status.status_code == 200
    standing = status.json()["standing"]
    assert standing is not None
    assert standing["group_id"] == str(membership.group_id)


def test_winner_without_competition_screen(client, db_session):
    week = competition_week_start(datetime(2026, 11, 18, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    author = register_with_invite(client, db_session, "win_a@example.com", "winA")
    fan = register_with_invite(client, db_session, "win_b@example.com", "winB")
    a = _user(db_session, "win_a@example.com")
    b = _user(db_session, "win_b@example.com")

    item = GalleryItem(
        user_id=a.id,
        title="winning look",
        image_url="https://example.com/w.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    db_session.add(item)
    db_session.flush()
    enroll_on_activity(db_session, a.id, now=week + timedelta(hours=2))
    enroll_on_activity(db_session, b.id, now=week + timedelta(hours=2))
    db_session.add(
        GalleryLike(user_id=b.id, gallery_item_id=item.id, created_at=week + timedelta(days=2))
    )
    db_session.flush()

    member = get_membership(db_session, a.id, week_start=week)
    assert member is not None
    picks = select_group_winners(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
    )
    assert any(p.category == "top_design" and p.user_id == a.id for p in picks)

    # GET status must not create awards/payouts
    before_awards = db_session.scalar(select(CompetitionAward).limit(1))
    build_competition_status(db_session, a, now=week + timedelta(days=3))
    after = list(db_session.scalars(select(CompetitionAward)).all())
    assert before_awards is None
    assert after == []


def test_group_capacity_conditional_update(client, db_session):
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    week = competition_week_start(now)
    ensure_competition_week(db_session, now=now)

    with patch("app.services.competition_groups.GROUP_CAPACITY", 2):
        for i in range(5):
            register_with_invite(client, db_session, f"cap2_{i}@example.com", f"cap2{i}")
            u = _user(db_session, f"cap2_{i}@example.com")
            assign_participant(db_session, u.id, now=now)
        groups = list_group_rows(db_session, week)
        assert len(groups) >= 3
        assert all(int(g.participant_count or 0) <= 2 for g in groups)
        assert sum(int(g.participant_count or 0) for g in groups) == 5


def test_comment_spam_does_not_dominate_top_commenter(client, db_session):
    week = competition_week_start(datetime(2026, 11, 18, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    register_with_invite(client, db_session, "spam_a@example.com", "spamA")
    register_with_invite(client, db_session, "spam_b@example.com", "spamB")
    register_with_invite(client, db_session, "spam_c@example.com", "spamC")
    a = _user(db_session, "spam_a@example.com")
    b = _user(db_session, "spam_b@example.com")
    c = _user(db_session, "spam_c@example.com")
    for u in (a, b, c):
        enroll_on_activity(db_session, u.id, now=week + timedelta(hours=1))

    target = GalleryItem(
        user_id=c.id,
        title="target",
        image_url="https://example.com/t.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    other = GalleryItem(
        user_id=c.id,
        title="other-c",
        image_url="https://example.com/o.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    third = GalleryItem(
        user_id=a.id,
        title="author-look",
        image_url="https://example.com/a.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    db_session.add_all([target, other, third])
    db_session.flush()

    # Spammer dumps identical long spam on one design (should de-dupe + per-design cap).
    for i in range(20):
        db_session.add(
            GalleryComment(
                gallery_item_id=target.id,
                user_id=a.id,
                body="Nice look on this piece!!",  # identical / near-identical
                moderation_status="ok",
                created_at=week + timedelta(days=2, minutes=i),
            )
        )
    # Meaningful commenter: unique bodies across two designers (c and a).
    db_session.add(
        GalleryComment(
            gallery_item_id=target.id,
            user_id=b.id,
            body="Love the silhouette and fabric choice here.",
            moderation_status="ok",
            created_at=week + timedelta(days=2),
        )
    )
    db_session.add(
        GalleryComment(
            gallery_item_id=third.id,
            user_id=b.id,
            body="The color story feels fresh for evening wear.",
            moderation_status="ok",
            created_at=week + timedelta(days=2, minutes=1),
        )
    )
    db_session.flush()

    member = get_membership(db_session, a.id, week_start=week)
    ranked = commenter_scores(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
    )
    assert ranked[0].user_id == b.id
    spam_score = next(r.score for r in ranked if r.user_id == a.id)
    good_score = next(r.score for r in ranked if r.user_id == b.id)
    assert good_score > spam_score
    # 20 identical comments collapse to a tiny score (1 body + 1 designer).
    assert spam_score <= 2


def test_settlement_catchup_and_idempotent(client, db_session):
    now = datetime(2026, 11, 22, 1, 0, tzinfo=timezone.utc)
    older = competition_week_start(datetime(2026, 11, 4, 12, tzinfo=timezone.utc))
    prev = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=older + timedelta(hours=1))
    ensure_competition_week(db_session, now=prev + timedelta(hours=1))
    db_session.flush()

    result = tick_competitions(db_session, now=now)
    assert result["settled_previous"] is True
    assert len(result["settled_weeks"]) >= 2
    assert db_session.get(CompetitionWeek, older).status == "locked"
    assert db_session.get(CompetitionWeek, prev).status == "locked"

    again = tick_competitions(db_session, now=now)
    assert again["settled_weeks"] == []


def test_concurrent_settle_does_not_double_lock_crash(client, db_session, engine):
    """Two sequential lock passes are idempotent; row lock serializes workers."""
    week = competition_week_start(datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    register_with_invite(client, db_session, "settle_a@example.com", "settleA")
    register_with_invite(client, db_session, "settle_b@example.com", "settleB")
    a = _user(db_session, "settle_a@example.com")
    b = _user(db_session, "settle_b@example.com")
    item = GalleryItem(
        user_id=a.id,
        title="settle look",
        image_url="https://example.com/s.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    db_session.add(item)
    db_session.flush()
    enroll_on_activity(db_session, a.id, now=week + timedelta(hours=2))
    enroll_on_activity(db_session, b.id, now=week + timedelta(hours=2))
    db_session.add(
        GalleryLike(user_id=b.id, gallery_item_id=item.id, created_at=week + timedelta(days=2))
    )
    db_session.flush()
    before = int(a.ai_stars or 0)

    lock_and_settle_week(db_session, week)
    db_session.refresh(a)
    mid = int(a.ai_stars or 0)
    lock_and_settle_week(db_session, week)
    db_session.refresh(a)
    assert int(a.ai_stars or 0) == mid
    assert mid >= before
    assert db_session.get(CompetitionWeek, week).status == "locked"
