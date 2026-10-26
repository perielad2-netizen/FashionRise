"""Create Real Design V3 — professional image-aware AI (mocked provider, $0 real spend)."""

from __future__ import annotations

import base64
import io
import uuid

import pytest
from pypdf import PdfReader

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.services.techpack_ai import set_professional_provider_override
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (256, 384), (255, 105, 180))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store_image() -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")


def _add_job(db_session, *, user_id: uuid.UUID, image_url: str, summary: str) -> AIJob:
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"studio_side": "front"},
        result_data={"summary": summary, "pipeline": "sketch_polish", "image_url": image_url},
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


def test_professional_fail_closed_without_allowlist(client, db_session, monkeypatch):
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "15")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", "")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "v3_deny@example.com", "v3_deny")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="pink striped dress",
    )
    draft = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id)},
    ).json()
    status = client.get("/api/v1/techpacks/ai/status", headers=_auth(tokens)).json()
    assert status["professional_available"] is False
    confirm = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(tokens),
        json={"stage": "generate", "mode": "professional"},
    ).json()
    assert confirm["ai_enabled"] is False
    paid = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": confirm["confirm_token"],
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
            "mode": "professional",
        },
    )
    assert paid.status_code == 403
    get_settings.cache_clear()


def test_professional_mock_pipeline_fr7182_features(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "v3_pro@example.com", "v3_pro")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    get_settings.cache_clear()

    mock = MockProfessionalProvider()
    set_professional_provider_override(mock)

    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="bright pink and white diagonal striped fitted mini dress deep V long sleeves",
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Pink Dress FR-7182"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    # Correct detection to dress
    pieces = draft["spec"]["outfit"]["pieces"]
    pieces[0]["category"] = "dress"
    pieces[0]["label"] = "Pink striped dress"
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": 1, "pieces": pieces}}},
    )

    status = client.get("/api/v1/techpacks/ai/status", headers=_auth(tokens)).json()
    assert status["professional_available"] is True
    assert status["owner_allowlisted"] is True
    assert status["estimate_professional_cents_max"] >= status["estimate_professional_cents_min"]

    confirm = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(tokens),
        json={"stage": "generate", "mode": "professional"},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["ai_enabled"] is True
    assert confirm.json()["estimated_cost_usd_cents"] > 0

    idem = f"idem-pro-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": confirm.json()["confirm_token"],
            "idempotency_key": idem,
            "mode": "professional",
            "propose_back": False,
        },
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["mode"] == "professional"
    assert body["actual_cost_usd_cents"] > 0
    assert body["artifacts"]
    kinds = {a["kind"] for a in body["artifacts"]}
    assert "flat_front" in kinds
    assert "pattern_sheet" in kinds
    assert any("analyze:" in c for c in mock.calls)
    assert any(c.startswith("flat:front:") for c in mock.calls)
    # Vision must have received real image bytes (>0)
    analyze_call = next(c for c in mock.calls if c.startswith("analyze:"))
    assert int(analyze_call.split(":")[1]) > 0

    # Artifact image download
    art_id = body["artifacts"][0]["id"]
    img = client.get(f"/api/v1/techpacks/artifacts/{art_id}/image", headers=_auth(tokens))
    assert img.status_code == 200
    assert img.content[:4] == b"\x89PNG"

    # Idempotent replay — no duplicate charge path
    replay = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": confirm.json()["confirm_token"],
            "idempotency_key": idem,
            "mode": "professional",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    analysis = refreshed["spec"]["outfit"]["pieces"][0]["illustrations"]["analysis"]
    assert "deep plunging" in (analysis.get("neckline") or "").lower() or "V" in (analysis.get("neckline") or "")
    assert "long" in (analysis.get("sleeves") or "").lower()
    assert "diagonal" in (analysis.get("stripe_direction") or "").lower() or "stripe" in (
        analysis.get("fabric_pattern") or ""
    ).lower()
    assert analysis.get("silhouette")

    exported = client.post(f"/api/v1/techpacks/{draft['id']}/export", headers=_auth(tokens))
    assert exported.status_code == 201
    pdf = client.get(
        f"/api/v1/techpacks/exports/{exported.json()['id']}/pdf",
        headers=_auth(tokens),
    )
    assert pdf.status_code == 200
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "AI PROFESSIONAL" in text or "AI FLAT" in text
    assert "deep plunging" in text.lower() or "neckline" in text.lower()
    assert "NOT TO SCALE" in text
    # Must not claim generation mode none
    assert "Paid sections: none" not in text

    # Preview/export must not create new paid runs
    runs_before = body["run_id"]
    client.post(f"/api/v1/techpacks/{draft['id']}/export", headers=_auth(tokens))
    # heuristic still works
    confirm_h = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(tokens),
        json={"stage": "generate", "mode": "heuristic"},
    ).json()
    heur = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": confirm_h["confirm_token"],
            "idempotency_key": f"idem-h-{uuid.uuid4().hex}",
            "mode": "heuristic",
        },
    )
    assert heur.status_code == 200
    assert heur.json()["cost_usd_cents"] == 0
    _ = runs_before
    get_settings.cache_clear()


def test_owner_isolation_on_artifacts(client, db_session, monkeypatch):
    a = register_with_invite(client, db_session, "v3_a@example.com", "v3_a")
    b = register_with_invite(client, db_session, "v3_b@example.com", "v3_b")
    me = client.get("/api/v1/auth/me", headers=_auth(a)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    get_settings.cache_clear()
    set_professional_provider_override(MockProfessionalProvider())
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="dress",
    )
    draft = client.post(
        "/api/v1/techpacks", headers=_auth(a), json={"look_id": str(job.id)}
    ).json()
    confirm = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(a),
        json={"stage": "generate", "mode": "professional"},
    ).json()
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(a),
        json={
            "confirm_token": confirm["confirm_token"],
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
            "mode": "professional",
        },
    ).json()
    art_id = gen["artifacts"][0]["id"]
    denied = client.get(f"/api/v1/techpacks/artifacts/{art_id}/image", headers=_auth(b))
    assert denied.status_code == 404
    get_settings.cache_clear()
