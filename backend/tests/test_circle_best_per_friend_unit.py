"""Unit tests for Friends-circle one-best-per-friend selection (no DB)."""

from __future__ import annotations

import types
import uuid

from app.services.gallery_service import pick_first_look_per_user


def _row(user: uuid.UUID, likes: int) -> types.SimpleNamespace:
    return types.SimpleNamespace(user_id=user, likes_count=likes, id=uuid.uuid4())


def test_pick_first_look_per_user_keeps_quality_order():
    a = uuid.uuid4()
    b = uuid.uuid4()
    # Pretend caller already sorted by likes desc.
    rows = [
        _row(a, 10),
        _row(a, 2),
        _row(b, 8),
        _row(b, 1),
        _row(a, 0),
    ]
    best = pick_first_look_per_user(rows)  # type: ignore[arg-type]
    assert [r.user_id for r in best] == [a, b]
    assert best[0].likes_count == 10
    assert best[1].likes_count == 8


def test_pick_first_look_per_user_empty():
    assert pick_first_look_per_user([]) == []
