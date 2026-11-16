"""FashionRise Fair Discovery ranking (Social PR2).

Pure helpers — no DB. Every public published look is eligible for the endless
Discover stream. Ranking still prefers cold-start exposure, engagement quality,
and recency — without hard-dropping older designs from the feed.

Liveliness (pilot → scale):
- Soft time rotation + optional viewer salt so the same catalog does not freeze
  into one permanent order for every account / every hour.
- Seen-by-viewer demotion so already-watched looks sink while fresh ones rise.
- Extra boost for brand-new publishes (first hours).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

# Soft recency half-life used by discover_score (not a hard eligibility cut).
RECENCY_HALF_LIFE_HOURS = 36.0
NEW_EXPOSURE_TARGET = 25
MAX_PER_CREATOR_DEFAULT = 2
# Safety only — full eligible set is ranked; this is not a "newest N" cut.
ELIGIBLE_HARD_CAP = 10_000
# Kept for stratified candidate fetch day buckets when the pool is huge.
DISCOVER_STRATIFY_DAYS = 7
# Brand-new publishes get an extra lift so they do not sink behind older likes.
FRESH_BOOST_HOURS = 6.0
FRESH_BOOST_WEIGHT = 1.6
# Looks this viewer already saw sink so the feed feels alive on return visits.
SEEN_BY_VIEWER_FACTOR = 0.42
# Mild explore jitter (±) so near-tied scores reorder by viewer + time bucket.
EXPLORE_JITTER_AMP = 0.55
# Re-roll the explore salt on this cadence (hours).
EXPLORE_ROTATION_HOURS = 3


@dataclass(frozen=True)
class DiscoverCandidate:
    id: UUID
    user_id: UUID
    likes_count: int
    rating_count: int
    unique_impressions_count: int
    created_at: datetime


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_discover_eligible(created_at: datetime, *, now: datetime | None = None) -> bool:
    """All published looks stay eligible; reject only clearly future-dated rows."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    created = ensure_utc(created_at)
    return created <= now_utc + timedelta(seconds=60)


def explore_time_bucket(now: datetime | None = None) -> int:
    """Coarse time key so the feed reshuffles every few hours without thrashing."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    epoch_hours = int(now_utc.timestamp() // 3600)
    return epoch_hours // max(1, int(EXPLORE_ROTATION_HOURS))


def explore_jitter(
    item_id: UUID,
    *,
    viewer_id: UUID | None = None,
    now: datetime | None = None,
    amplitude: float = EXPLORE_JITTER_AMP,
) -> float:
    """Deterministic ±jitter from viewer + time bucket + item (stable within a bucket)."""
    bucket = explore_time_bucket(now)
    viewer_key = str(viewer_id) if viewer_id is not None else "anon"
    material = f"{viewer_key}|{bucket}|{item_id}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    # Map first 8 hex chars → [0, 1)
    unit = int(digest[:8], 16) / float(0xFFFFFFFF)
    return (unit * 2.0 - 1.0) * float(amplitude)


def discover_score(
    candidate: DiscoverCandidate,
    *,
    now: datetime | None = None,
    seen_by_viewer: bool = False,
) -> float:
    """Higher is better. Future-dated items score -1; age never hard-excludes."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    created = ensure_utc(candidate.created_at)
    age = now_utc - created
    if age.total_seconds() < -60:
        return -1.0

    unique = max(0, int(candidate.unique_impressions_count or 0))
    engagement = max(0, int(candidate.likes_count or 0)) + max(
        0, int(candidate.rating_count or 0)
    )

    # Cold start: guarantee initial exposure opportunities for under-seen publishes.
    cold = max(0.0, 1.0 - (unique / float(NEW_EXPOSURE_TARGET)))

    # Engagement quality vs unique impressions (Laplace prior avoids /0 spikes).
    quality = engagement / float(unique + 10)

    # Soft recency (half-life ~36h) — older looks rank lower but remain in the pool.
    age_hours = max(0.0, age.total_seconds() / 3600.0)
    recency = math.exp(-age_hours / RECENCY_HALF_LIFE_HOURS)

    # First hours after publish: keep new designs near the top of Discover.
    if age_hours < FRESH_BOOST_HOURS:
        fresh = FRESH_BOOST_WEIGHT * (1.0 - (age_hours / FRESH_BOOST_HOURS))
    else:
        fresh = 0.0

    score = (2.4 * cold) + (3.2 * quality) + (1.1 * recency) + fresh
    if seen_by_viewer:
        score *= SEEN_BY_VIEWER_FACTOR
    return score


def rank_discover_candidates(
    candidates: Sequence[DiscoverCandidate],
    *,
    now: datetime | None = None,
    viewer_id: UUID | None = None,
    seen_ids: Sequence[UUID] | set[UUID] | None = None,
) -> list[tuple[DiscoverCandidate, float]]:
    seen = set(seen_ids or ())
    scored: list[tuple[DiscoverCandidate, float]] = []
    for row in candidates:
        score = discover_score(row, now=now, seen_by_viewer=row.id in seen)
        if score < 0:
            continue
        # Personalize only for signed-in viewers (viewer + 3h bucket). Anonymous
        # Discover stays pure quality order so ranking unit tests stay stable.
        jitter = (
            explore_jitter(row.id, viewer_id=viewer_id, now=now)
            if viewer_id is not None
            else 0.0
        )
        scored.append((row, score + jitter))
    scored.sort(
        key=lambda pair: (
            -pair[1],
            -ensure_utc(pair[0].created_at).timestamp(),
            str(pair[0].id),
        )
    )
    return scored


def diversify_select_page(
    scored: Sequence[tuple[DiscoverCandidate, float]],
    *,
    limit: int,
    max_per_creator: int = MAX_PER_CREATOR_DEFAULT,
    exclude_ids: Sequence[UUID] | None = None,
) -> list[DiscoverCandidate]:
    """One Discover page: prefer ≤N looks/creator, then fill leftover slots.

    The soft cap stops one creator from dominating a full page when many
    creators are available. If the page is still short (small catalog / few
    creators), keep scoring order and fill remaining slots so looks are not
    stranded behind a load-more that never fires.
    """
    if limit <= 0:
        return []
    skip = set(exclude_ids or ())
    cap = max(1, int(max_per_creator))
    out: list[DiscoverCandidate] = []
    seen_ids: set[UUID] = set()
    per_creator: dict[UUID, int] = {}
    for candidate, _score in scored:
        if candidate.id in skip or candidate.id in seen_ids:
            continue
        used = per_creator.get(candidate.user_id, 0)
        if used >= cap:
            continue
        out.append(candidate)
        seen_ids.add(candidate.id)
        per_creator[candidate.user_id] = used + 1
        if len(out) >= limit:
            return out

    # Fill remaining slots from capped creators (still score-ordered).
    if len(out) < limit:
        for candidate, _score in scored:
            if candidate.id in skip or candidate.id in seen_ids:
                continue
            out.append(candidate)
            seen_ids.add(candidate.id)
            if len(out) >= limit:
                break
    return out


# Back-compat alias for older unit tests / imports.
def diversify_select(
    scored: Sequence[tuple[DiscoverCandidate, float]],
    *,
    limit: int,
    max_per_creator: int = MAX_PER_CREATOR_DEFAULT,
) -> list[DiscoverCandidate]:
    return diversify_select_page(scored, limit=limit, max_per_creator=max_per_creator)


# Back-compat for callers that still import DISCOVER_WINDOW (stratify span).
DISCOVER_WINDOW = timedelta(days=DISCOVER_STRATIFY_DAYS)
