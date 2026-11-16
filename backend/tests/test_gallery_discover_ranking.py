"""Fair Discovery ranking helpers (Social PR2) — pure unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.services.gallery_discover import (
    DiscoverCandidate,
    diversify_select,
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


def test_seven_day_eligibility_window():
    fresh = _cand(age_hours=24)
    stale = _cand(age_hours=8 * 24)
    assert is_discover_eligible(fresh.created_at, now=NOW)
    assert not is_discover_eligible(stale.created_at, now=NOW)
    assert discover_score(stale, now=NOW) < 0


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
