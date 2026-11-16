"""FashionRise Fair Discovery ranking (Social PR2).

Pure helpers — no DB. Eligibility is a rolling 7-day window. New designs get
cold-start exposure; engagement relative to unique impressions raises rank;
diversify_select caps per-creator slots so established accounts cannot monopolize.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence
from uuid import UUID

DISCOVER_WINDOW = timedelta(days=7)
NEW_EXPOSURE_TARGET = 25
MAX_PER_CREATOR_DEFAULT = 2
CANDIDATE_POOL_CAP = 500


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
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    created = ensure_utc(created_at)
    return created >= now_utc - DISCOVER_WINDOW


def discover_score(candidate: DiscoverCandidate, *, now: datetime | None = None) -> float:
    """Higher is better. Ineligible items score -1."""
    now_utc = ensure_utc(now or datetime.now(timezone.utc))
    created = ensure_utc(candidate.created_at)
    age = now_utc - created
    if age > DISCOVER_WINDOW or age.total_seconds() < -60:
        return -1.0

    unique = max(0, int(candidate.unique_impressions_count or 0))
    engagement = max(0, int(candidate.likes_count or 0)) + max(
        0, int(candidate.rating_count or 0)
    )

    # Cold start: guarantee initial exposure opportunities for new publishes.
    cold = max(0.0, 1.0 - (unique / float(NEW_EXPOSURE_TARGET)))

    # Engagement quality vs unique impressions (Laplace prior avoids /0 spikes).
    quality = engagement / float(unique + 10)

    # Recency within the 7-day window (half-life ~36h).
    age_hours = max(0.0, age.total_seconds() / 3600.0)
    recency = math.exp(-age_hours / 36.0)

    return (2.4 * cold) + (3.2 * quality) + (1.1 * recency)


def rank_discover_candidates(
    candidates: Sequence[DiscoverCandidate],
    *,
    now: datetime | None = None,
) -> list[tuple[DiscoverCandidate, float]]:
    scored: list[tuple[DiscoverCandidate, float]] = []
    for row in candidates:
        score = discover_score(row, now=now)
        if score < 0:
            continue
        scored.append((row, score))
    scored.sort(key=lambda pair: (-pair[1], -ensure_utc(pair[0].created_at).timestamp(), str(pair[0].id)))
    return scored


def diversify_select(
    scored: Sequence[tuple[DiscoverCandidate, float]],
    *,
    limit: int,
    max_per_creator: int = MAX_PER_CREATOR_DEFAULT,
) -> list[DiscoverCandidate]:
    """Pick a page that spreads creators and never repeats the same design id."""
    if limit <= 0:
        return []
    cap = max(1, int(max_per_creator))
    out: list[DiscoverCandidate] = []
    seen_ids: set[UUID] = set()
    per_creator: dict[UUID, int] = {}
    for candidate, _score in scored:
        if candidate.id in seen_ids:
            continue
        used = per_creator.get(candidate.user_id, 0)
        if used >= cap:
            continue
        out.append(candidate)
        seen_ids.add(candidate.id)
        per_creator[candidate.user_id] = used + 1
        if len(out) >= limit:
            break
    return out
