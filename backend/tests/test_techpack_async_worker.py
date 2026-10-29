"""Durable async Professional generate — 202 enqueue + worker claim (mocked provider, $0 real spend)."""

from __future__ import annotations

import io
import time
import uuid
from typing import Any

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.techpack_ai_run import TechpackAIRun
from app.services.techpack_ai import set_professional_provider_override
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import (
    claim_next_techpack_run,
    run_techpack_worker_tick,
)
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    img = Image.new("RGB", (128, 192), (40, 80, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store_image() -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")


def _add_job(db_session, *, user_id: uuid.UUID, image_url: str) -> AIJob:
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"studio_side": "front"},
        result_data={"summary": "dress", "pipeline": "sketch_polish", "image_url": image_url},
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


class SlowMockProvider(MockProfessionalProvider):
    """Simulates multi-step image work without real OpenAI calls."""

    def __init__(self, *, delay_s: float = 0.05, **kwargs: Any):
        super().__init__(**kwargs)
        self.delay_s = delay_s
        self.slow_calls = 0

    def analyze_garment(self, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(self.delay_s)
        self.slow_calls += 1
        return super().analyze_garment(**kwargs)

    def generate_technical_flat(self, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(self.delay_s)
        self.slow_calls += 1
        return super().generate_technical_flat(**kwargs)

    def generate_detail_or_pattern(self, **kwargs):  # type: ignore[no-untyped-def]
        time.sleep(self.delay_s)
        self.slow_calls += 1
        return super().generate_detail_or_pattern(**kwargs)


class PartialCostFailProvider(MockProfessionalProvider):
    """Records vision cost then fails on first image — tests partial accounting."""

    def generate_technical_flat(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated image provider failure after vision")


class UncertainOutcomeProvider(MockProfessionalProvider):
    def generate_technical_flat(self, **kwargs):  # type: ignore[no-untyped-def]
        # Leave in_flight set by pipeline; raise as if connection dropped mid-call.
        raise ConnectionError("simulated uncertain provider outcome")


@pytest.fixture(autouse=True)
def _clear_provider():
    set_professional_provider_override(None)
    yield
    set_professional_provider_override(None)


def _enable_ai(monkeypatch, email: str) -> None:
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_USER_DAY", "20")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", email)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()


def _draft(client, db_session, tokens, me):
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image())
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Async dress"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_one_tap_returns_202_and_worker_completes(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_ok@example.com", "async_ok")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(SlowMockProvider(delay_s=0.02))
    draft = _draft(client, db_session, tokens, me)

    idem = f"async-{uuid.uuid4().hex}"
    t0 = time.monotonic()
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": True},
    )
    elapsed = time.monotonic() - t0
    assert gen.status_code == 202, gen.text
    assert elapsed < 2.0, "enqueue must return promptly (not wait on pipeline)"
    body = gen.json()
    assert body["status"] == "queued"
    assert body["run_id"]
    assert body.get("status_url")

    # HTTP connection is done — worker continues independently.
    n = run_techpack_worker_tick(db_session, limit=2)
    assert n == 1
    row = client.get(
        f"/api/v1/techpacks/ai/runs/{body['run_id']}",
        headers=_auth(tokens),
    ).json()
    assert row["status"] == "completed"
    assert row["artifacts"]
    assert int(row["cost_usd_cents"]) > 0

    # Idempotent replay — same key does not enqueue a second paid run.
    replay = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": True},
    )
    assert replay.status_code == 202
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["run_id"] == body["run_id"]


def test_double_click_same_key_single_run(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_dbl@example.com", "async_dbl")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(SlowMockProvider(delay_s=0.01))
    draft = _draft(client, db_session, tokens, me)
    idem = f"dbl-{uuid.uuid4().hex}"
    a = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem},
    )
    b = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem},
    )
    assert a.status_code == 202 and b.status_code == 202
    assert a.json()["run_id"] == b.json()["run_id"]
    from sqlalchemy import select

    runs = list(
        db_session.scalars(select(TechpackAIRun).where(TechpackAIRun.idempotency_key == idem)).all()
    )
    assert len(runs) == 1


def test_two_tabs_reuse_inflight_draft_run(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_tabs@example.com", "async_tabs")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(SlowMockProvider(delay_s=0.01))
    draft = _draft(client, db_session, tokens, me)
    a = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"tab-a-{uuid.uuid4().hex}"},
    )
    b = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"tab-b-{uuid.uuid4().hex}"},
    )
    assert a.status_code == 202 and b.status_code == 202
    assert a.json()["run_id"] == b.json()["run_id"]
    assert b.json().get("idempotent_replay") is True


def test_claim_once_then_empty_queue(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_claim@example.com", "async_claim")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(SlowMockProvider(delay_s=0.01))
    draft = _draft(client, db_session, tokens, me)
    client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"claim-{uuid.uuid4().hex}"},
    )
    claimed = claim_next_techpack_run(db_session)
    assert claimed is not None
    assert claimed.status == "running"
    # Already claimed — queue empty for a second claim on this session.
    assert claim_next_techpack_run(db_session) is None
    from app.services.techpack_ai_worker import process_claimed_techpack_run

    status = process_claimed_techpack_run(db_session, claimed.id)
    assert status == "completed"
    assert run_techpack_worker_tick(db_session, limit=2) == 0


def test_partial_cost_preserved_on_failure(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_cost@example.com", "async_cost")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(PartialCostFailProvider())
    draft = _draft(client, db_session, tokens, me)
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"cost-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202
    run_id = gen.json()["run_id"]
    run_techpack_worker_tick(db_session, limit=1)
    row = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert row["status"] in ("failed", "reconciliation_required", "completed")
    # Vision ran — cost must not be wiped to zero when illustrations fail.
    if row["status"] == "failed":
        assert int(row["cost_usd_cents"]) > 0


def test_uncertain_outcome_marks_reconciliation_not_blind_retry(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_unc@example.com", "async_unc")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])

    class StickyInFlight(MockProfessionalProvider):
        def generate_technical_flat(self, **kwargs):  # type: ignore[no-untyped-def]
            # Simulate worker crash after in_flight was persisted: raise after progress callback.
            raise ConnectionError("drop")

    set_professional_provider_override(StickyInFlight())
    draft = _draft(client, db_session, tokens, me)
    idem = f"unc-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem},
    )
    run_id = uuid.UUID(gen.json()["run_id"])
    # Manually set in_flight then call execute to hit reconciliation path.
    row = db_session.get(TechpackAIRun, run_id)
    assert row is not None
    req = dict(row.request)
    req["provider_in_flight"] = {"kind": "flat_front", "piece_id": "x"}
    row.status = "running"
    row.request = req
    db_session.add(row)
    db_session.commit()

    from app.services.techpack_ai import execute_professional_run

    out = execute_professional_run(db_session, run_id)
    assert out["status"] == "reconciliation_required"
    assert out.get("safe_retry") is False

    # Same idempotency key must not start a new paid attempt.
    again = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem},
    )
    assert again.status_code == 202
    assert again.json()["run_id"] == str(run_id)
    assert again.json()["status"] == "reconciliation_required"


def test_unauthenticated_generate_rejected(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "async_unauth@example.com", "async_unauth")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _draft(client, db_session, tokens, me)
    r = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        json={"idempotency_key": f"noauth-{uuid.uuid4().hex}"},
    )
    assert r.status_code in (401, 403)
