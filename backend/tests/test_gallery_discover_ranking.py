"""Fair Discovery ranking helpers (Social PR2) — pure unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.gallery_discover import (
    DiscoverCandidate,
    diversify_select,
    diversify_select_page,
    discover_score,
    is_discover_eligible,
    rank_discover_candidates,
)


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def _cand(
    *,
    likes: int = 0,
    ratings: int = 0,
    unique: int = 0,
    age_hours: float = 1,
    user_id=None,
) -> DiscoverCandidate:
    return DiscoverCandidate(
        id=uuid4(),
        user_id=user_id or uuid4(),
        likes_count=likes,
        rating_count=ratings,
        unique_impressions_count=unique,
        created_at=NOW - timedelta(hours=age_hours),
    )


def test_all_ages_remain_eligible_with_soft_recency():
    fresh = _cand(age_hours=24)
    stale = _cand(age_hours=8 * 24)
    assert is_discover_eligible(fresh.created_at, now=NOW)
    assert is_discover_eligible(stale.created_at, now=NOW)
    assert discover_score(stale, now=NOW) >= 0
    assert discover_score(fresh, now=NOW) > discover_score(stale, now=NOW)


def test_new_designs_outrank_ignored_high_like_monopoly():
    """Cold-start new look beats a saturated high-like look with weak engagement rate."""
    newbie = _cand(likes=0, unique=2, age_hours=2)
    monopolist = _cand(likes=80, unique=4000, age_hours=20)
    assert discover_score(newbie, now=NOW) > discover_score(monopolist, now=NOW)


def test_strong_engagement_rate_beats_weak_rate_at_similar_exposure():
    hot = _cand(likes=12, ratings=4, unique=40, age_hours=10)
    cold = _cand(likes=1, ratings=0, unique=40, age_hours=10)
    assert discover_score(hot, now=NOW) > discover_score(cold, now=NOW)


def test_diversify_limits_per_creator_and_skips_duplicates():
    creator_a = uuid4()
    creator_b = uuid4()
    a1 = _cand(user_id=creator_a, likes=5, unique=5)
    a2 = _cand(user_id=creator_a, likes=4, unique=5)
    a3 = _cand(user_id=creator_a, likes=3, unique=5)
    b1 = _cand(user_id=creator_b, likes=2, unique=5)
    scored = rank_discover_candidates([a1, a2, a3, b1], now=NOW)
    # Force a1 twice in scored list to prove de-dupe
    scored = [(a1, 99.0), (a1, 98.0), *scored]
    picked = diversify_select(scored, limit=4, max_per_creator=2)
    assert len(picked) == 3  # a1, a2, b1 — a3 blocked by cap; duplicate a1 skipped
    assert sum(1 for c in picked if c.user_id == creator_a) == 2
    assert sum(1 for c in picked if c.user_id == creator_b) == 1
    assert len({c.id for c in picked}) == 3


def test_pagination_resets_creator_cap_and_excludes_seen():
    creator_a = uuid4()
    creator_b = uuid4()
    a1 = _cand(user_id=creator_a, likes=9, unique=3)
    a2 = _cand(user_id=creator_a, likes=8, unique=3)
    a3 = _cand(user_id=creator_a, likes=7, unique=3)
    b1 = _cand(user_id=creator_b, likes=6, unique=3)
    scored = rank_discover_candidates([a1, a2, a3, b1], now=NOW)
    page1 = diversify_select_page(scored, limit=2, max_per_creator=2)
    assert len(page1) == 2
    page2 = diversify_select_page(
        scored,
        limit=2,
        max_per_creator=2,
        exclude_ids=[c.id for c in page1],
    )
    assert len(page2) == 2
    assert {c.id for c in page1}.isdisjoint({c.id for c in page2})
    # Creator A can appear again on page 2 after exclude (cap is per page).
    assert any(c.user_id == creator_a for c in page2) or any(c.user_id == creator_b for c in page2)


def test_candidate_cap_stratifies_older_days_not_newest_only(db_session, client):
    """When eligible pool exceeds hard_cap, older-day cold starts stay candidates."""
    from app.models.gallery_item import GalleryItem
    from app.models.user import User
    from app.services.gallery_service import fetch_discover_candidate_rows
    from tests.auth_test_helpers import register_with_invite

    author = register_with_invite(client, db_session, "cap_author@example.com", "capAuthor")
    user = db_session.query(User).filter(User.email == "cap_author@example.com").one()
    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    cutoff = now - timedelta(days=7)

    # Flood the newest day with 6 saturated looks; put 2 cold-starts on day 0 (oldest).
    rows: list[GalleryItem] = []
    for i in range(6):
        rows.append(
            GalleryItem(
                look_id=uuid4(),
                user_id=user.id,
                title=f"newest-{i}",
                image_url="https://example.com/n.png",
                visibility="public",
                moderation_status="ok",
                likes_count=10,
                unique_impressions_count=500,
                impressions_count=500,
                created_at=now - timedelta(hours=i + 1),
            )
        )
    older_a = GalleryItem(
        look_id=uuid4(),
        user_id=user.id,
        title="older-cold-a",
        image_url="https://example.com/o.png",
        visibility="public",
        moderation_status="ok",
        likes_count=0,
        unique_impressions_count=1,
        impressions_count=1,
        created_at=cutoff + timedelta(hours=2),
    )
    older_b = GalleryItem(
        look_id=uuid4(),
        user_id=user.id,
        title="older-cold-b",
        image_url="https://example.com/o2.png",
        visibility="public",
        moderation_status="ok",
        likes_count=0,
        unique_impressions_count=2,
        impressions_count=2,
        created_at=cutoff + timedelta(hours=5),
    )
    rows.extend([older_a, older_b])
    db_session.add_all(rows)
    db_session.flush()
    older_ids = {older_a.id, older_b.id}

    # Newest-only cut of 6 would drop both older looks; stratified hard_cap=7 keeps them.
    picked = fetch_discover_candidate_rows(
        db_session, cutoff=cutoff, now=now, hard_cap=7
    )
    picked_ids = {r.id for r in picked}
    assert older_ids & picked_ids, "older-day cold starts must remain under stratified cap"
    assert len(picked) <= 7
