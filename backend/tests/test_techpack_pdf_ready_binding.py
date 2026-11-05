"""Professional Ready requires a PDF bound to the exact AI run — not draft.latest_export."""

from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackExport
from app.services.techpack_ai import (
    execute_professional_run,
    set_professional_provider_override,
)
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import run_techpack_worker_tick
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    img = Image.new("RGB", (128, 192), (220, 40, 120))
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
        result_data={"summary": "pink striped dress", "pipeline": "sketch_polish", "image_url": image_url},
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


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
        json={"look_id": str(job.id), "title": "Pink stripe"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_completed_run_ready_only_with_bound_professional_pdf(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdf_ready@example.com", "pdf_ready")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _draft(client, db_session, tokens, me)

    # Seed an older Basic export that must NOT be treated as the Professional PDF.
    basic = TechpackExport(
        id=uuid.uuid4(),
        draft_id=uuid.UUID(draft["id"]),
        user_id=uuid.UUID(me["id"]),
        filename="FR_basic.pdf",
        storage_key=f"{me['id'].replace('-', '')}/{draft['id'].replace('-', '')}/basic.pdf",
        byte_size=100,
        page_count=1,
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        metadata_={"generation_mode": "none", "is_professional": False, "paid_sections": []},
    )
    storage = LocalStorageBackend()
    storage.save_private_techpack_file(
        key=basic.storage_key, data=io.BytesIO(b"%PDF-1.4 basic"), content_type="application/pdf"
    )
    db_session.add(basic)
    db_session.commit()

    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"pdf-ready-{uuid.uuid4().hex}", "propose_back": True},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) == 1

    row = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert row["status"] == "completed"
    assert row["pdf_ready"] is True
    assert row["export_id"]
    assert row["export_id"] != str(basic.id)
    assert row["download_path"] == f"/api/v1/techpacks/exports/{row['export_id']}/pdf"
    assert row["progress"]["phase"] == "ready"

    exported = db_session.get(TechpackExport, uuid.UUID(row["export_id"]))
    assert exported is not None
    meta = exported.metadata_ if isinstance(exported.metadata_, dict) else {}
    assert meta.get("is_professional") is True
    assert str(meta.get("ai_run_id")) == run_id

    pdf = client.get(f"/api/v1/techpacks/exports/{row['export_id']}/pdf", headers=_auth(tokens))
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    assert b"basic" not in pdf.content

    # Reuse completed matching run — no second paid job.
    again = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"pdf-ready-again-{uuid.uuid4().hex}", "propose_back": True},
    )
    assert again.status_code == 202
    body = again.json()
    assert body["run_id"] == run_id
    assert body.get("reused_completed") is True or body.get("idempotent_replay") is True
    assert body["pdf_ready"] is True


def test_stale_basic_latest_export_not_ready_substitute(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdf_basic@example.com", "pdf_basic")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _draft(client, db_session, tokens, me)

    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"bind-{uuid.uuid4().hex}"},
    )
    run_id = uuid.UUID(gen.json()["run_id"])
    run_techpack_worker_tick(db_session, limit=1)
    run = db_session.get(TechpackAIRun, run_id)
    assert run is not None and run.status == "completed"
    result = dict(run.result or {})
    pro_export_id = result.get("export_id")
    assert pro_export_id

    # Insert a newer Basic export after Professional — draft.latest_export preference must
    # still resolve to the Professional bound to last_run_id.
    newer_basic = TechpackExport(
        id=uuid.uuid4(),
        draft_id=uuid.UUID(draft["id"]),
        user_id=uuid.UUID(me["id"]),
        filename="newer_basic.pdf",
        storage_key=f"{me['id'].replace('-', '')}/{draft['id'].replace('-', '')}/newer_basic.pdf",
        byte_size=50,
        page_count=1,
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        metadata_={"generation_mode": "none", "is_professional": False},
    )
    LocalStorageBackend().save_private_techpack_file(
        key=newer_basic.storage_key,
        data=io.BytesIO(b"%PDF-1.4 newer-basic"),
        content_type="application/pdf",
    )
    db_session.add(newer_basic)
    db_session.commit()

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert refreshed["latest_export"]["id"] == pro_export_id
    assert refreshed["latest_export"]["metadata"].get("is_professional") is True

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["export_id"] == pro_export_id
    assert status["pdf_ready"] is True


def test_ensure_pdf_recovers_completed_run_without_export(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdf_rec@example.com", "pdf_rec")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _draft(client, db_session, tokens, me)
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"rec-{uuid.uuid4().hex}"},
    )
    run_id = uuid.UUID(gen.json()["run_id"])
    run_techpack_worker_tick(db_session, limit=1)

    run = db_session.get(TechpackAIRun, run_id)
    assert run is not None
    # Simulate historical bug: completed with illustrations but no bound PDF in result.
    result = dict(run.result or {})
    export_id = result.pop("export_id", None)
    result["pdf_ready"] = False
    result.pop("download_path", None)
    run.result = result
    db_session.add(run)
    db_session.commit()

    # GET run recovers PDF from existing illustrations (zero OpenAI).
    recovered = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert recovered["pdf_ready"] is True
    assert recovered["export_id"]
    if export_id:
        # Prefer reusing the previously assembled Professional export when still on disk.
        assert recovered["export_id"]


def test_execute_does_not_mark_ready_before_pdf(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdf_ord@example.com", "pdf_ord")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _draft(client, db_session, tokens, me)
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"ord-{uuid.uuid4().hex}"},
    )
    run_id = uuid.UUID(gen.json()["run_id"])
    out = execute_professional_run(db_session, run_id)
    assert out["status"] == "completed"
    assert out["pdf_ready"] is True
    assert out["export_id"]
    assert out["progress"]["phase"] == "ready"
