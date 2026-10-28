"""PDF-only update (No AI) — reuse Professional illustrations, $0 provider calls."""

from __future__ import annotations

import uuid
from typing import Any

from pypdf import PdfReader

from app.models.techpack_ai_run import TechpackAIRun
from app.services.techpack_ai import (
    ensure_professional_pdf_for_run,
    set_professional_provider_override,
)
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import run_techpack_worker_tick
from tests.auth_test_helpers import register_with_invite
from tests.test_techpack_p0_reliability import (
    _auth,
    _counting_mock,
    _enable_professional,
    _seed_two_piece_draft,
)


def _complete_professional(client, db_session, tokens, draft_id: str) -> dict[str, Any]:
    set_professional_provider_override(MockProfessionalProvider())
    gen = client.post(
        f"/api/v1/techpacks/{draft_id}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-pdf-only-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=4) >= 1
    settled = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert settled["status"] == "completed", settled
    assert settled.get("pdf_ready") is True
    assert settled.get("export_id")
    return settled


def test_pdf_only_update_zero_provider_calls_and_preserves_history(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "pdfonly1@example.com", "pdfonly1")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="PDF only update")
    # First paid Professional completion via counting mock path.
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-first-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=4) >= 1
    settled = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert settled["status"] == "completed"
    first_export_id = settled["export_id"]
    provider_calls_after_paid = CountingMock.provider_calls
    assert provider_calls_after_paid > 0

    # Designer edits measurements on the existing tunic only → dirty, pieces preserved.
    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    live_pieces = live["spec"]["outfit"]["pieces"]
    assert len(live_pieces) == 2
    edited_pieces = []
    for p in live_pieces:
        copy = dict(p)
        if p.get("id") == "tunic-1":
            fm = dict(copy.get("finished_measurements") or {})
            fm["garment_length"] = {"value": 74, "unit": "cm", "source": "designer"}
            copy["finished_measurements"] = fm
        edited_pieces.append(copy)
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": 2, "pieces": edited_pieces}}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["spec"]["ai"].get("dirty_since_generation") is True
    assert patched.json()["spec"]["ai"].get("export_id") == first_export_id

    # PDF-only update — no new provider calls.
    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update", "idempotency_key": "pdf-only-1"},
    )
    assert updated.status_code == 201, updated.text
    new_export = updated.json()
    assert new_export["id"] != first_export_id
    assert new_export["metadata"].get("pdf_only_update") is True
    assert new_export["metadata"].get("new_paid_ai_run") is False
    assert new_export["metadata"].get("source_ai_run_id") == run_id
    assert CountingMock.provider_calls == provider_calls_after_paid

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert refreshed["spec"]["ai"].get("dirty_since_generation") is False
    assert refreshed["spec"]["ai"].get("export_id") == new_export["id"]
    assert refreshed["spec"]["ai"].get("outdated_export_id") == first_export_id

    # Historical PDF intact.
    old_pdf = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    assert old_pdf.status_code == 200
    new_pdf = client.get(
        f"/api/v1/techpacks/exports/{new_export['id']}/pdf", headers=_auth(tokens)
    )
    assert new_pdf.status_code == 200
    assert len(PdfReader(__import__("io").BytesIO(new_pdf.content)).pages) >= 1

    # Run count unchanged — no new paid AI run row for the PDF-only update.
    runs = (
        db_session.query(TechpackAIRun)
        .filter(TechpackAIRun.draft_id == uuid.UUID(draft["id"]))
        .all()
    )
    assert len(runs) == 1
    assert str(runs[0].id) == run_id

    # Idempotent repeat returns the same export and still $0 provider.
    again = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update", "idempotency_key": "pdf-only-1"},
    )
    assert again.status_code == 201, again.text
    assert again.json()["id"] == new_export["id"]
    assert CountingMock.provider_calls == provider_calls_after_paid


def test_pdf_only_update_rejects_garment_identity_drift(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdfonly2@example.com", "pdfonly2")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Identity drift")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]

    # Replace piece IDs → incompatible with Professional run structure.
    drifted = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "outfit": {
                    "piece_count": 2,
                    "pieces": [
                        {
                            "id": "brand-new-top",
                            "category": "top",
                            "label": "New top",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                        },
                        {
                            "id": "brand-new-bottom",
                            "category": "trousers",
                            "label": "New trousers",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                        },
                    ],
                }
            }
        },
    )
    assert drifted.status_code == 200, drifted.text

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "garment identity" in detail or "illustrations" in detail

    # Historical export still current pointer / preserved; dirty stays true.
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("dirty_since_generation") is True
    assert after["spec"]["ai"].get("export_id") == first_export_id
    hist = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    assert hist.status_code == 200


def test_ensure_professional_pdf_does_not_clobber_pdf_only_current(
    client, db_session, monkeypatch
):
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "pdfonly3@example.com", "pdfonly3")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="No clobber")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    run_id = settled["id"]
    first_export_id = settled["export_id"]

    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "preferences": {"fit_preference": "relaxed", "notes": "roomier"},
            }
        },
    )
    assert patched.status_code == 200
    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert updated.status_code == 201, updated.text
    new_export_id = updated.json()["id"]
    assert new_export_id != first_export_id

    user = db_session.get(User, uuid.UUID(me["id"]))
    run = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert user is not None and run is not None
    ensure_professional_pdf_for_run(db_session, user, run)

    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    # Current Download must remain the PDF-only export, not the older run export.
    assert after["spec"]["ai"].get("export_id") == new_export_id
    assert after["spec"]["ai"].get("dirty_since_generation") is False
    assert first_export_id != new_export_id
