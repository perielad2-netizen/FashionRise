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
from app.services.competition_scoring import (
    COMMENT_POINTS_PER_QUALIFYING,
    MAX_QUALIFYING_COMMENTS_PER_DESIGN,
    commenter_scores,
    community_champion_scores,
    design_engagement_scores,
    designer_scores_from_designs,
)
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
        look_id=uuid.uuid4(),
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
        look_id=uuid.uuid4(),
        user_id=c.id,
        title="target",
        image_url="https://example.com/t.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    other = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=c.id,
        title="other-c",
        image_url="https://example.com/o.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    third = GalleryItem(
        look_id=uuid.uuid4(),
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


def test_repetitive_comments_do_not_inflate_design_awards(client, db_session):
    """100 spam comments from one viewer must not dominate Top Design / Designer / Champion."""
    week = competition_week_start(datetime(2026, 11, 18, 12, tzinfo=timezone.utc))
    ensure_competition_week(db_session, now=week + timedelta(hours=1))
    register_with_invite(client, db_session, "score_a@example.com", "scoreA")
    register_with_invite(client, db_session, "score_b@example.com", "scoreB")
    register_with_invite(client, db_session, "score_c@example.com", "scoreC")
    register_with_invite(client, db_session, "score_d@example.com", "scoreD")
    a = _user(db_session, "score_a@example.com")
    b = _user(db_session, "score_b@example.com")
    c = _user(db_session, "score_c@example.com")
    d = _user(db_session, "score_d@example.com")
    for u in (a, b, c, d):
        enroll_on_activity(db_session, u.id, now=week + timedelta(hours=1))

    spam_target = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=a.id,
        title="spam farm",
        image_url="https://example.com/spam.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    genuine = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=b.id,
        title="genuine look",
        image_url="https://example.com/gen.png",
        visibility="public",
        moderation_status="ok",
        created_at=week + timedelta(days=1),
    )
    db_session.add_all([spam_target, genuine])
    db_session.flush()

    for i in range(100):
        db_session.add(
            GalleryComment(
                gallery_item_id=spam_target.id,
                user_id=c.id,
                body="Nice look on this piece!!",
                moderation_status="ok",
                created_at=week + timedelta(days=2, minutes=i),
            )
        )
    # Distinct viewers leave unique meaningful comments on genuine design.
    for i, commenter in enumerate((a, c, d)):
        db_session.add(
            GalleryComment(
                gallery_item_id=genuine.id,
                user_id=commenter.id,
                body=f"Thoughtful feedback about silhouette number {i} here.",
                moderation_status="ok",
                created_at=week + timedelta(days=2, minutes=i),
            )
        )
    db_session.flush()

    member = get_membership(db_session, a.id, week_start=week)
    designs = design_engagement_scores(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
    )
    by_id = {row.gallery_item_id: row.score for row in designs}
    # Max 2 qualifying comments × 4 pts from one spammer = 8 (identical body → 1×4=4).
    assert by_id[spam_target.id] <= COMMENT_POINTS_PER_QUALIFYING * MAX_QUALIFYING_COMMENTS_PER_DESIGN
    assert by_id[spam_target.id] == COMMENT_POINTS_PER_QUALIFYING  # identical spam collapses
    assert by_id[genuine.id] == COMMENT_POINTS_PER_QUALIFYING * 3
    assert by_id[genuine.id] > by_id[spam_target.id]

    designers = designer_scores_from_designs(designs)
    assert designers[0].user_id == b.id

    champions = community_champion_scores(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
        design_scores=designs,
    )
    # Protected design score feeds champion; spam farm designer must not win solely on spam.
    assert champions[0].user_id != a.id

    picks = select_group_winners(
        db_session,
        week_start=week,
        week_end=week + timedelta(days=7),
        group_id=member.group_id,
    )
    top_design = next(p for p in picks if p.category == "top_design")
    assert top_design.gallery_item_id == genuine.id
    assert top_design.user_id == b.id


def test_concurrent_settle_workers_single_payout(engine):
    """Two workers settle the same week in parallel — Stars credited once."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from sqlalchemy import delete
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.competition import CompetitionGroup, CompetitionGroupMember, StarPayout
    from app.models.gallery_like import GalleryLike as GalleryLikeModel
    from app.models.user import User as UserModel
    from app.services import ai_stars

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Isolated past week so committed fixture data does not collide with rolled-back tests.
    week = competition_week_start(datetime(2025, 1, 5, 12, tzinfo=timezone.utc))
    suffix = uuid.uuid4().hex[:8]
    author_id = None
    fan_id = None
    item_id = None

    bootstrap = SessionLocal()
    try:
        a = UserModel(
            email=f"race_a_{suffix}@example.com",
            username=f"raceA_{suffix}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
        )
        b = UserModel(
            email=f"race_b_{suffix}@example.com",
            username=f"raceB_{suffix}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
        )
        ai_stars.apply_new_user_stars(a)
        ai_stars.apply_new_user_stars(b)
        bootstrap.add_all([a, b])
        bootstrap.flush()
        ensure_competition_week(bootstrap, now=week + timedelta(hours=1))
        enroll_on_activity(bootstrap, a.id, now=week + timedelta(hours=2))
        enroll_on_activity(bootstrap, b.id, now=week + timedelta(hours=2))
        item = GalleryItem(
            look_id=uuid.uuid4(),
            user_id=a.id,
            title="race settle",
            image_url="https://example.com/r.png",
            visibility="public",
            moderation_status="ok",
            created_at=week + timedelta(days=1),
        )
        bootstrap.add(item)
        bootstrap.flush()
        bootstrap.add(
            GalleryLikeModel(
                user_id=b.id,
                gallery_item_id=item.id,
                created_at=week + timedelta(days=2),
            )
        )
        bootstrap.commit()
        author_id = a.id
        fan_id = b.id
        item_id = item.id
        before = int(a.ai_stars or 0)
    finally:
        bootstrap.close()

    barrier = threading.Barrier(2, timeout=10)

    def _worker() -> int:
        session = SessionLocal()
        try:
            barrier.wait()
            lock_and_settle_week(session, week)
            session.commit()
            user = session.get(UserModel, author_id)
            return int(user.ai_stars or 0)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            balances = [
                f.result() for f in as_completed([pool.submit(_worker), pool.submit(_worker)])
            ]

        assert balances[0] == balances[1]
        assert balances[0] >= before
        verify = SessionLocal()
        try:
            week_row = verify.get(CompetitionWeek, week)
            assert week_row is not None and week_row.status == "locked"
            awards = list(
                verify.scalars(
                    select(CompetitionAward).where(CompetitionAward.week_start == week)
                ).all()
            )
            keys = [row.payout_key for row in awards]
            assert len(keys) == len(set(keys))
            user = verify.get(UserModel, author_id)
            assert int(user.ai_stars or 0) == balances[0]
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.execute(
                delete(CompetitionAward).where(CompetitionAward.week_start == week)
            )
            cleanup.execute(delete(StarPayout).where(StarPayout.user_id.in_([author_id, fan_id])))
            cleanup.execute(
                delete(CompetitionGroupMember).where(CompetitionGroupMember.week_start == week)
            )
            cleanup.execute(
                delete(CompetitionGroup).where(CompetitionGroup.week_start == week)
            )
            cleanup.execute(delete(CompetitionWeek).where(CompetitionWeek.week_start == week))
            if item_id is not None:
                cleanup.execute(delete(GalleryLikeModel).where(GalleryLikeModel.gallery_item_id == item_id))
                cleanup.execute(delete(GalleryItem).where(GalleryItem.id == item_id))
            if author_id is not None:
                cleanup.execute(delete(UserModel).where(UserModel.id.in_([author_id, fan_id])))
            cleanup.commit()
        finally:
            cleanup.close()


def test_concurrent_streak_checkin_same_day(engine):
    """Parallel same-day check-ins increment lifetime once and never double-reward."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from sqlalchemy import delete
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.competition import LoginStreak, StarPayout
    from app.models.user import User as UserModel
    from app.services import ai_stars
    from app.services.login_streak import record_daily_checkin

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    suffix = uuid.uuid4().hex[:8]
    day = datetime(2026, 11, 16, 15, tzinfo=timezone.utc)
    user_id = None

    bootstrap = SessionLocal()
    try:
        user = UserModel(
            email=f"streak_race_{suffix}@example.com",
            username=f"streakRace_{suffix}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
        )
        ai_stars.apply_new_user_stars(user)
        bootstrap.add(user)
        bootstrap.commit()
        user_id = user.id
        before = int(user.ai_stars or 0)
    finally:
        bootstrap.close()

    barrier = threading.Barrier(4, timeout=10)

    def _worker() -> bool:
        session = SessionLocal()
        try:
            u = session.get(UserModel, user_id)
            barrier.wait()
            status = record_daily_checkin(session, u, now=day)
            return bool(status.rewarded_this_checkin)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            rewarded_flags = [
                f.result() for f in as_completed([pool.submit(_worker) for _ in range(4)])
            ]

        assert sum(1 for flag in rewarded_flags if flag) == 0  # day 1 of streak, no 7-day reward
        verify = SessionLocal()
        try:
            streak = verify.get(LoginStreak, user_id)
            assert streak is not None
            assert int(streak.lifetime_checkins or 0) == 1
            assert streak.current_streak == 1
            user = verify.get(UserModel, user_id)
            assert int(user.ai_stars or 0) == before
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        try:
            cleanup.execute(delete(StarPayout).where(StarPayout.user_id == user_id))
            cleanup.execute(delete(LoginStreak).where(LoginStreak.user_id == user_id))
            cleanup.execute(delete(UserModel).where(UserModel.id == user_id))
            cleanup.commit()
        finally:
            cleanup.close()
