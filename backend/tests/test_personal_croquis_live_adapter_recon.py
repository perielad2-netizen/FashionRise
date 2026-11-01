"""P0: post-submit SDK failures must reconcile (not $0-release) via Stage C worker."""

from __future__ import annotations

import io
import uuid
from types import SimpleNamespace

import httpx
import openai
import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.personal_croquis_spend import (
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    PersonalCroquisSpendReservation,
)
from app.services.personal_croquis_provider import (
    OpenAICroquisImagesEditAdapter,
    ProviderNotAvailableError,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    set_croquis_openai_client_override,
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
from tests.fixtures.croquis.synthetic_adult_model import (
    load_synthetic_clothed_adult_model_png,
)

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 64, h: int = 96) -> bytes:
    img = Image.new("RGB", (w, h), (40, 80, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _enable_ai_spend(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "1.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", "1.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", "1.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "40")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "false")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()


def _enable_upload(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _iso(monkeypatch, db_session):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    set_croquis_openai_client_override(None)
    arm_provider_network_tripwire()
    from app.models.ai_job import AIJob
    from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE

    db_session.query(PersonalCroquisSpendReservation).delete()
    db_session.query(AIJob).filter(AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE).delete()
    db_session.flush()
    yield
    disarm_provider_network_tripwire()
    set_croquis_openai_client_override(None)
    set_croquis_provider_override(None)
    get_settings.cache_clear()


def _upload_ready(client, tokens, monkeypatch):
    _enable_upload(monkeypatch)
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code == 200
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", load_synthetic_clothed_adult_model_png(), "image/png")},
        data={"storage_consent_id": c.json()["id"], "display_name": "Synthetic clothed"},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _ai_consent(client, tokens, croquis_id: str) -> str:
    r = client.post(f"{BASE}/consent/ai", headers=_auth(tokens), json=ai_body(croquis_id=croquis_id))
    assert r.status_code == 200, r.text
    return r.json()["id"]


class _FakeImages:
    def __init__(self, on_edit):
        self._on_edit = on_edit
        self.calls = 0

    def edit(self, **kwargs):
        self.calls += 1
        return self._on_edit(**kwargs)


class _FakeClient:
    def __init__(self, on_edit):
        self.images = _FakeImages(on_edit)

    def with_options(self, **kwargs):
        _ = kwargs
        return self


def _wire_live_adapter(monkeypatch, on_edit) -> OpenAICroquisImagesEditAdapter:
    _enable_ai_spend(monkeypatch)
    set_croquis_openai_client_override(_FakeClient(on_edit))
    adapter = OpenAICroquisImagesEditAdapter()
    set_croquis_provider_override(adapter)
    return adapter


def _enqueue_and_drain(client, tokens, croquis_id, ai_id, db_session, key: str):
    r = client.post(
        f"{BASE}/{croquis_id}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": key},
    )
    assert r.status_code == 201, r.text
    assert run_croquis_worker_tick(db_session, limit=2) >= 1
    return r.json()


def _assert_recon_and_new_key_denied(client, tokens, croquis, ai_id, db_session, key: str):
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == "reconciliation_required"
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_RECONCILIATION
    assert res.provider_called is True
    # Same key denied
    r2 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": key},
    )
    assert r2.status_code == 409
    # New key also denied while recon open
    r3 = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": f"{key}-new"},
    )
    assert r3.status_code == 409


def test_api_timeout_after_submit_reconciles(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, f"to_{uuid.uuid4().hex[:8]}@ex.com", f"to{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        raise openai.APITimeoutError(request=req)

    _wire_live_adapter(monkeypatch, on_edit)
    key = "recon-timeout"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    _assert_recon_and_new_key_denied(client, tokens, croquis, ai_id, db_session, key)


def test_api_connection_error_after_submit_reconciles(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, f"ce_{uuid.uuid4().hex[:8]}@ex.com", f"ce{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        raise openai.APIConnectionError(message="connection reset", request=req)

    _wire_live_adapter(monkeypatch, on_edit)
    key = "recon-conn"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    _assert_recon_and_new_key_denied(client, tokens, croquis, ai_id, db_session, key)


def test_http_5xx_after_submit_reconciles(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, f"xx_{uuid.uuid4().hex[:8]}@ex.com", f"xx{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        resp = httpx.Response(500, request=req)
        raise openai.InternalServerError("upstream 500", response=resp, body=None)

    _wire_live_adapter(monkeypatch, on_edit)
    key = "recon-5xx"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    _assert_recon_and_new_key_denied(client, tokens, croquis, ai_id, db_session, key)


def test_missing_b64_after_200_reconciles(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, f"b64_{uuid.uuid4().hex[:8]}@ex.com", f"b6{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        item = SimpleNamespace(b64_json=None, url="https://example.invalid/img.png")
        return SimpleNamespace(data=[item], id="img_empty")

    _wire_live_adapter(monkeypatch, on_edit)
    key = "recon-nob64"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    _assert_recon_and_new_key_denied(client, tokens, croquis, ai_id, db_session, key)


def test_live_http_disabled_releases_zero(client, monkeypatch, db_session):
    """Definite pre-submit refusal still releases $0."""
    tokens = register_with_invite(client, db_session, f"pre_{uuid.uuid4().hex[:8]}@ex.com", f"pr{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    # No client override — adapter refuses LIVE_HTTP before any edit call.
    set_croquis_provider_override(OpenAICroquisImagesEditAdapter())
    key = "pre-live-off"
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": key},
    )
    assert r.status_code == 201
    assert run_croquis_worker_tick(db_session, limit=2) >= 1
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == "failed"
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.provider_called is False
    assert res.actual_cost_cents == 0


def test_http_400_bad_request_after_submit_releases_zero(client, monkeypatch, db_session):
    """Completed HTTP 400 is a definitive rejection — fail + $0 release, not recon hold."""
    tokens = register_with_invite(client, db_session, f"br_{uuid.uuid4().hex[:8]}@ex.com", f"br{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        resp = httpx.Response(
            400,
            request=req,
            json={"error": {"message": "Invalid image.", "type": "invalid_request_error", "code": "invalid_image"}},
        )
        raise openai.BadRequestError(
            "Invalid image.",
            response=resp,
            body={"error": {"message": "Invalid image.", "type": "invalid_request_error", "code": "invalid_image"}},
        )

    _wire_live_adapter(monkeypatch, on_edit)
    key = "reject-400"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    body = poll.json()
    assert body["status"] == "failed"
    assert body.get("failure_code") == "invalid_image"
    assert body.get("failure_message")
    assert "not charged" in body["failure_message"].lower()
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.provider_called is True
    assert res.actual_cost_cents == 0
    assert res.error_detail and "BadRequestError" in res.error_detail
    # New key allowed after definite failure (unlike reconciliation_required).
    r_new = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": f"{key}-retry"},
    )
    assert r_new.status_code == 201, r_new.text


def test_moderation_blocked_surfaces_owner_safe_message(client, monkeypatch, db_session):
    """OpenAI moderation_blocked must not be bypassed; owner gets explicit explanation."""
    tokens = register_with_invite(client, db_session, f"mb_{uuid.uuid4().hex[:8]}@ex.com", f"mb{uuid.uuid4().hex[:6]}")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        payload = {
            "error": {
                "message": "Your request was rejected by the safety system.",
                "type": "invalid_request_error",
                "code": "moderation_blocked",
            }
        }
        resp = httpx.Response(400, request=req, json=payload)
        err = openai.BadRequestError(
            "Error code: 400 - " + str(payload),
            response=resp,
            body=payload,
        )
        # SDK populates .code from body in real calls; set explicitly for the fake.
        try:
            err.code = "moderation_blocked"
        except Exception:
            pass
        raise err

    _wire_live_adapter(monkeypatch, on_edit)
    key = "reject-moderation"
    _enqueue_and_drain(client, tokens, croquis["id"], ai_id, db_session, key)
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    body = poll.json()
    assert body["status"] == "failed"
    assert body.get("failure_code") == "moderation_blocked"
    assert "safety system" in (body.get("failure_message") or "").lower()
    assert "cannot override" in (body.get("failure_message") or "").lower()
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.actual_cost_cents == 0
    assert "moderation_blocked" in (res.error_detail or "")


def test_adapter_unit_timeout_raises_outcome_unknown(monkeypatch):
    _enable_ai_spend(monkeypatch)

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        raise openai.APITimeoutError(request=req)

    set_croquis_openai_client_override(_FakeClient(on_edit))
    adapter = OpenAICroquisImagesEditAdapter()
    from app.services.personal_croquis_provider import ProviderOutcomeUnknownError

    with pytest.raises(ProviderOutcomeUnknownError, match="outcome unknown"):
        adapter.generate_line_art(_png_bytes())
    with pytest.raises(ProviderNotAvailableError, match="LIVE_HTTP"):
        # Without client override, definite pre-submit.
        set_croquis_openai_client_override(None)
        OpenAICroquisImagesEditAdapter().generate_line_art(_png_bytes())


def test_adapter_unit_bad_request_raises_not_available(monkeypatch):
    _enable_ai_spend(monkeypatch)

    def on_edit(**_kw):
        req = httpx.Request("POST", "https://api.openai.com/v1/images/edits")
        resp = httpx.Response(400, request=req, json={"error": {"message": "bad"}})
        raise openai.BadRequestError("bad", response=resp, body={"error": {"message": "bad"}})

    set_croquis_openai_client_override(_FakeClient(on_edit))
    adapter = OpenAICroquisImagesEditAdapter()
    with pytest.raises(ProviderNotAvailableError, match="rejected by provider"):
        adapter.generate_line_art(_png_bytes())
