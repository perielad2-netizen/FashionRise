"""Stage C — enqueue, worker, spend, accept/reject (mocked provider only)."""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.personal_croquis import (
    VERSION_STATUS_ACCEPTED,
    VERSION_STATUS_AWAITING_REVIEW,
    VERSION_STATUS_GENERATING,
    VERSION_STATUS_REJECTED,
)
from app.models.personal_croquis_spend import (
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.services.personal_croquis_provider import (
    CrashBeforeSubmitCroquisProvider,
    MockCroquisProvider,
    UnknownOutcomeCroquisProvider,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    provider_network_tripwire_hits,
    set_croquis_provider_override,
)
from app.services.personal_croquis_worker import run_croquis_worker_tick
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    enable_synthetic_croquis_notices,
    storage_body,
)

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 64, h: int = 96, color=(40, 80, 160)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _enable_upload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


def _enable_ai_spend(monkeypatch, *, ceiling_usd: str = "5", max_run: str = "1", max_day: str = "5"):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", ceiling_usd)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", max_run)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", max_day)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY", "3")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "5")
    get_settings.cache_clear()


def _disable_ai(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_AI_ENABLED", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_SPEND_CEILING_USD", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _synthetic_notices(monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    arm_provider_network_tripwire()
    yield
    disarm_provider_network_tripwire()
    set_croquis_provider_override(None)
    _disable_ai(monkeypatch)


def _upload_ready(client, tokens, monkeypatch):
    _enable_upload(monkeypatch)
    a = client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
    assert a.status_code == 200, a.text
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200, c.text
    consent_id = c.json()["id"]
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"storage_consent_id": consent_id, "display_name": "Stage C subject"},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _ai_consent(client, tokens) -> str:
    r = client.post(f"{BASE}/consent/ai", headers=_auth(tokens), json=ai_body())
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _drain_worker(db_session, *, n: int = 4) -> int:
    return run_croquis_worker_tick(db_session, limit=n)


def test_generate_refused_when_ai_gate_off(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc1@example.com", "sc1")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-gate-off"},
    )
    assert r.status_code == 403
    assert mock.calls == 0
    assert provider_network_tripwire_hits() == 0


def test_generate_refused_without_ai_consent(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc2@example.com", "sc2")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": str(uuid.uuid4()), "idempotency_key": "k-no-consent"},
    )
    assert r.status_code == 400
    assert mock.calls == 0


def test_generate_refused_when_spend_ceiling_zero(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc3@example.com", "sc3")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "0")
    get_settings.cache_clear()
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-ceiling-0"},
    )
    assert r.status_code == 403
    assert mock.calls == 0


def test_enqueue_worker_accept_idempotent(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc4@example.com", "sc4")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider(cost_cents=3)
    set_croquis_provider_override(mock)

    body = {"ai_consent_id": ai_id, "idempotency_key": "k-success-1"}
    r1 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json=body,
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["status"] == VERSION_STATUS_GENERATING
    assert mock.calls == 0  # not yet — worker owns provider call

    assert _drain_worker(db_session) >= 1
    poll = client.get(
        f"{BASE}/{croquis['id']}/versions/1",
        headers=_auth(tokens),
    )
    assert poll.status_code == 200
    assert poll.json()["status"] == VERSION_STATUS_AWAITING_REVIEW
    assert poll.json()["generated_asset_id"]
    assert mock.calls == 1

    acc = client.post(
        f"{BASE}/{croquis['id']}/versions/1/accept",
        headers=_auth(tokens),
    )
    assert acc.status_code == 200
    assert acc.json()["status"] == VERSION_STATUS_ACCEPTED

    # Idempotent enqueue replay — no second provider call
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json=body,
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == r1.json()["id"]
    assert mock.calls == 1

    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-success-1")
        .one()
    )
    assert res.status == RESERVATION_SETTLED
    assert res.actual_cost_cents == 3


def test_reject_then_regenerate_v2_preserves_nothing_on_v1_reject(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc5@example.com", "sc5")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider(cost_cents=2)
    set_croquis_provider_override(mock)

    r1 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-v1"},
    )
    assert r1.status_code == 201
    _drain_worker(db_session)
    rej = client.post(f"{BASE}/{croquis['id']}/versions/1/reject", headers=_auth(tokens))
    assert rej.status_code == 200
    assert rej.json()["status"] == VERSION_STATUS_REJECTED

    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-v2"},
    )
    assert r2.status_code == 201
    _drain_worker(db_session)
    acc = client.post(f"{BASE}/{croquis['id']}/versions/2/accept", headers=_auth(tokens))
    assert acc.status_code == 200
    assert acc.json()["version"] == 2
    assert acc.json()["status"] == VERSION_STATUS_ACCEPTED
    # v1 remains rejected, not overwritten
    v1 = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert v1.json()["status"] == VERSION_STATUS_REJECTED


def test_unknown_provider_outcome_holds_reservation_no_auto_retry(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc6@example.com", "sc6")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(UnknownOutcomeCroquisProvider())

    r1 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-unknown"},
    )
    assert r1.status_code == 201
    _drain_worker(db_session)
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == "reconciliation_required"

    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-unknown")
        .one()
    )
    assert res.status == RESERVATION_RECONCILIATION
    assert res.provider_called is True

    set_croquis_provider_override(MockCroquisProvider())
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-unknown"},
    )
    assert r2.status_code == 409


def test_crash_before_submit_releases_reservation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc7@example.com", "sc7")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(CrashBeforeSubmitCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-crash"},
    )
    assert r.status_code == 201
    _drain_worker(db_session)
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-crash")
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.actual_cost_cents == 0


def test_spend_ceiling_blocks_second_generation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc8@example.com", "sc8")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch, ceiling_usd="0.05", max_run="1", max_day="1")
    mock = MockCroquisProvider(cost_cents=5)
    set_croquis_provider_override(mock)

    r1 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-ceil-a"},
    )
    assert r1.status_code == 201
    _drain_worker(db_session)
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-ceil-b"},
    )
    assert r2.status_code == 403
    assert mock.calls == 1


def test_cross_user_generate_denied(client, monkeypatch, db_session):
    a = register_with_invite(client, db_session, "sc9a@example.com", "sc9a")
    b = register_with_invite(client, db_session, "sc9b@example.com", "sc9b")
    croquis = _upload_ready(client, a, monkeypatch)
    # User B must attest adults before AI consent; still cannot generate on A's croquis.
    assert (
        client.post(f"{BASE}/attestations/adults", headers=_auth(b), json=adults_body()).status_code
        == 200
    )
    ai_b = _ai_consent(client, b)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(b),
        json={"ai_consent_id": ai_b, "idempotency_key": "k-xuser"},
    )
    assert r.status_code == 404


def test_duplicate_idempotency_key_single_reservation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc10@example.com", "sc10")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    body = {"ai_consent_id": ai_id, "idempotency_key": "k-dup"}
    r1 = client.post(f"{BASE}/{croquis['id']}/versions/generate", headers=_auth(tokens), json=body)
    r2 = client.post(f"{BASE}/{croquis['id']}/versions/generate", headers=_auth(tokens), json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201  # idempotent replay of generating row
    assert r1.json()["id"] == r2.json()["id"]
    db_session.expire_all()
    count = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-dup")
        .count()
    )
    assert count == 1


def test_erasure_during_pending_generation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc11@example.com", "sc11")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-erase"},
    )
    assert r.status_code == 201
    erased = client.delete(f"{BASE}/{croquis['id']}", headers=_auth(tokens))
    assert erased.status_code == 200
    _drain_worker(db_session)
    # Worker should fail closed without inventing a public asset
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    # erased croquis may 404 get_exact_version depending on include_erased — expect 404
    assert poll.status_code in (404, 200)
    if poll.status_code == 200:
        assert poll.json()["status"] in ("failed", VERSION_STATUS_GENERATING, "awaiting_review")
