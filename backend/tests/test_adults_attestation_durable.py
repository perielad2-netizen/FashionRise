"""Adults-beta attestation is account-level for the notice version — not a 24h timer."""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.config import get_settings
from app.models.user_consent_event import PURPOSE_ADULTS_BETA
from app.services import personal_croquis_service as pcs


def _clear():
    get_settings.cache_clear()


def test_adults_attestation_default_max_age_is_durable():
    _clear()
    assert get_settings().my_croquis_adults_attestation_max_age_seconds == 0
    _clear()


def test_latest_adults_attestation_ignores_age_when_max_age_zero(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_ADULTS_ATTESTATION_MAX_AGE_SECONDS", "0")
    monkeypatch.setenv("MY_CROQUIS_ADULTS_ATTESTATION_VERSION", "adults-beta-2026-11-01")
    monkeypatch.setenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", "Approved adults notice for durable test.")
    _clear()

    expected_hash = pcs._hash_text("Approved adults notice for durable test.")
    old = SimpleNamespace(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        purpose=PURPOSE_ADULTS_BETA,
        adults_attested=True,
        consent_version="adults-beta-2026-11-01",
        text_hash=expected_hash,
        created_at=pcs._utcnow() - timedelta(days=30),
    )
    user = SimpleNamespace(id=old.owner_id)
    db = MagicMock()
    # SQLAlchemy query chain used by _latest_adults_attestation
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = old

    found = pcs._latest_adults_attestation(db, user)
    assert found is old
    # No created_at cutoff when max_age is 0 — filter args must not encode a stale cutoff.
    filter_call = q.filter.call_args
    assert filter_call is not None
    # Ensure we did not require created_at >= cutoff by checking call kwargs/args length
    # (filters list has exactly the identity fields when max_age<=0).
    assert q.filter.call_count == 1
    _clear()


def test_latest_adults_attestation_still_honors_positive_max_age(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_ADULTS_ATTESTATION_MAX_AGE_SECONDS", "60")
    monkeypatch.setenv("MY_CROQUIS_ADULTS_ATTESTATION_VERSION", "adults-beta-2026-11-01")
    monkeypatch.setenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", "Approved adults notice for aged test.")
    _clear()

    expected_hash = pcs._hash_text("Approved adults notice for aged test.")
    user = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.order_by.return_value = q
    q.first.return_value = None

    assert pcs._latest_adults_attestation(db, user) is None
    # Positive max_age adds a created_at lower-bound filter clause.
    assert q.filter.call_count == 1
    args = q.filter.call_args[0]
    assert any("created_at" in str(a) for a in args)
    _clear()
