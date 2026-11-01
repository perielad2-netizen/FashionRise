"""Zero-network: one-call executor must bind the exact authorized job, not oldest-queue."""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import (
    CROQUIS_GENERATE_JOB_TYPE,
    PersonalCroquisVersion,
)
from app.models.personal_croquis_spend import PersonalCroquisSpendReservation
from app.services.personal_croquis_one_call import (
    OneCallGuardError,
    assert_only_target_croquis_job_queued,
)
from app.services.personal_croquis_provider import (
    MockCroquisProvider,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    set_croquis_provider_override,
)
from app.services.personal_croquis_worker import (
    run_croquis_worker_tick,
    run_specific_croquis_job,
)
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


def _other_png() -> bytes:
    """Different bytes from the approved synthetic fixture."""
    img = Image.new("RGB", (40, 60), (200, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _enable_ai(monkeypatch) -> None:
    """Raise operator ceiling so two competing reservations can coexist in-test."""
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", "1.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", "5.00")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "40")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "false")
    get_settings.cache_clear()


def _enable_upload(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _iso(monkeypatch, db_session):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    arm_provider_network_tripwire()
    db_session.query(PersonalCroquisSpendReservation).delete()
    db_session.query(AIJob).filter(AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE).delete()
    db_session.flush()
    yield
    disarm_provider_network_tripwire()
    set_croquis_provider_override(None)
    get_settings.cache_clear()


def _upload(client, tokens, monkeypatch, *, png: bytes, name: str):
    _enable_upload(monkeypatch)
    assert (
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code
        == 200
    )
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", png, "image/png")},
        data={"storage_consent_id": c.json()["id"], "display_name": name},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _enqueue(client, tokens, croquis_id: str, ai_id: str, key: str, db_session) -> tuple[dict, uuid.UUID]:
    r = client.post(
        f"{BASE}/{croquis_id}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": key},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    ver = db_session.get(PersonalCroquisVersion, uuid.UUID(body["id"]))
    assert ver is not None and ver.provider_job_id
    return body, uuid.UUID(ver.provider_job_id)


def test_oldest_queue_tick_would_prefer_earlier_job(client, monkeypatch, db_session):
    """Document the hazard: tick claims oldest first — executor must not use it."""
    tokens_a = register_with_invite(
        client, db_session, f"old_{uuid.uuid4().hex[:8]}@ex.com", f"o{uuid.uuid4().hex[:6]}"
    )
    tokens_b = register_with_invite(
        client, db_session, f"new_{uuid.uuid4().hex[:8]}@ex.com", f"n{uuid.uuid4().hex[:6]}"
    )
    croquis_old = _upload(client, tokens_a, monkeypatch, png=_other_png(), name="other")
    croquis_new = _upload(
        client, tokens_b, monkeypatch, png=load_synthetic_clothed_adult_model_png(), name="approved"
    )
    _enable_ai(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=3))

    ai_old = client.post(
        f"{BASE}/consent/ai", headers=_auth(tokens_a), json=ai_body(croquis_id=croquis_old["id"])
    ).json()["id"]
    ai_new = client.post(
        f"{BASE}/consent/ai", headers=_auth(tokens_b), json=ai_body(croquis_id=croquis_new["id"])
    ).json()["id"]

    _ver_old, old_id = _enqueue(client, tokens_a, croquis_old["id"], ai_old, "key-old", db_session)
    _ver_new, new_id = _enqueue(client, tokens_b, croquis_new["id"], ai_new, "key-new", db_session)

    old_job = db_session.get(AIJob, old_id)
    new_job = db_session.get(AIJob, new_id)
    assert old_job is not None and new_job is not None
    assert old_job.created_at <= new_job.created_at

    # Fresh-DB / only-target guards must refuse this multi-queued state.
    with pytest.raises(OneCallGuardError, match="exactly 1 queued"):
        assert_only_target_croquis_job_queued(db_session, new_id)

    # Oldest-queue tick processes the unapproved earlier job first.
    assert run_croquis_worker_tick(db_session, limit=1) == 1
    db_session.refresh(old_job)
    db_session.refresh(new_job)
    assert old_job.status == "completed"
    assert new_job.status == "queued"


def test_specific_job_bind_processes_only_authorized(client, monkeypatch, db_session):
    tokens_a = register_with_invite(
        client, db_session, f"oa_{uuid.uuid4().hex[:8]}@ex.com", f"a{uuid.uuid4().hex[:6]}"
    )
    tokens_b = register_with_invite(
        client, db_session, f"ob_{uuid.uuid4().hex[:8]}@ex.com", f"b{uuid.uuid4().hex[:6]}"
    )
    croquis_old = _upload(client, tokens_a, monkeypatch, png=_other_png(), name="other")
    croquis_new = _upload(
        client, tokens_b, monkeypatch, png=load_synthetic_clothed_adult_model_png(), name="approved"
    )
    _enable_ai(monkeypatch)
    mock = MockCroquisProvider(cost_cents=3)
    set_croquis_provider_override(mock)

    ai_old = client.post(
        f"{BASE}/consent/ai", headers=_auth(tokens_a), json=ai_body(croquis_id=croquis_old["id"])
    ).json()["id"]
    ai_new = client.post(
        f"{BASE}/consent/ai", headers=_auth(tokens_b), json=ai_body(croquis_id=croquis_new["id"])
    ).json()["id"]
    _ver_old, old_id = _enqueue(client, tokens_a, croquis_old["id"], ai_old, "bind-old", db_session)
    _ver_new, new_id = _enqueue(client, tokens_b, croquis_new["id"], ai_new, "bind-new", db_session)

    run_specific_croquis_job(db_session, new_id)

    old_job = db_session.get(AIJob, old_id)
    new_job = db_session.get(AIJob, new_id)
    assert new_job is not None and old_job is not None
    assert new_job.status == "completed"
    assert old_job.status == "queued"  # competing job untouched
    assert mock.calls == 1

    poll_new = client.get(f"{BASE}/{croquis_new['id']}/versions/1", headers=_auth(tokens_b))
    assert poll_new.json()["status"] == "awaiting_review"
    poll_old = client.get(f"{BASE}/{croquis_old['id']}/versions/1", headers=_auth(tokens_a))
    assert poll_old.json()["status"] == "generating"
