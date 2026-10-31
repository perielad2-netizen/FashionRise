"""Stage C — generate, consent, spend reservation, idempotency (mocked provider only)."""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.personal_croquis import VERSION_STATUS_ACCEPTED, PersonalCroquisVersion
from app.models.personal_croquis_spend import (
    RESERVATION_RECONCILIATION,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.services.personal_croquis_provider import (
    MockCroquisProvider,
    UnknownOutcomeCroquisProvider,
    set_croquis_provider_override,
)
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
    yield
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
    assert "ceiling" in r.json()["detail"].lower()
    assert mock.calls == 0


def test_generate_success_with_mock_provider_idempotent(client, monkeypatch, db_session):
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
    payload = r1.json()
    assert payload["version"] == 1
    assert payload["status"] == VERSION_STATUS_ACCEPTED
    assert payload["generated_asset_id"]
    assert payload["geometry_profile"] == "fit_contain_768x1024_v1"
    assert mock.calls == 1

    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json=body,
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == payload["id"]
    assert mock.calls == 1  # no second paid/mock call

    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-success-1")
        .one()
    )
    assert res.status == RESERVATION_SETTLED
    assert res.actual_cost_cents == 3


def test_regenerate_allocates_v2_new_asset(client, monkeypatch, db_session):
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
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-v2"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["version"] == 2
    assert r2.json()["generated_asset_id"] != r1.json()["generated_asset_id"]
    assert mock.calls == 2


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
    assert r1.status_code == 409
    assert "reconcil" in r1.json()["detail"].lower()

    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "k-unknown")
        .one()
    )
    assert res.status == RESERVATION_RECONCILIATION
    assert res.provider_called is True

    # Same key refuses automatic retry
    set_croquis_provider_override(MockCroquisProvider())
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-unknown"},
    )
    assert r2.status_code == 409
    assert "reconcil" in r2.json()["detail"].lower()


def test_spend_ceiling_blocks_second_generation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "sc7@example.com", "sc7")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens)
    # Ceiling just enough for one estimate (5¢) then blocks.
    _enable_ai_spend(monkeypatch, ceiling_usd="0.05", max_run="1", max_day="1")
    mock = MockCroquisProvider(cost_cents=5)
    set_croquis_provider_override(mock)

    r1 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-ceil-a"},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "k-ceil-b"},
    )
    assert r2.status_code == 403
    assert mock.calls == 1
