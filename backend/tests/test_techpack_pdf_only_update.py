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


def test_pdf_only_update_honest_zero_assembly_cost(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdfcost@example.com", "pdfcost")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Honest cost")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    paid_cents = int(settled.get("cost_usd_cents") or 0)
    assert paid_cents > 0

    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "roomier hem"}}},
    )
    assert patched.status_code == 200
    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert updated.status_code == 201, updated.text
    meta = updated.json()["metadata"]
    assert meta.get("new_paid_ai_run") is False
    assert meta.get("provider_calls") == 0
    assert meta.get("assembly_cost_usd_cents") == 0
    assert meta.get("actual_cost_usd_cents") == 0
    assert meta.get("budget_recorded_usd_cents") == 0
    assert meta.get("paid_sections") == []
    assert int(meta.get("source_run_cost_usd_cents") or 0) == paid_cents
    assert isinstance(meta.get("source_run_paid_sections"), list)


def test_pdf_only_rejects_front_magic_source_change(client, db_session, monkeypatch):
    from app.models.techpack_draft import TechpackDraft
    from tests.test_techpack_p0_reliability import (
        TUNICS_IDENTITY,
        TUNICS_TROUSERS_SUMMARY,
        _add_job,
        _store_image,
    )

    tokens = register_with_invite(client, db_session, "pdffront@example.com", "pdffront")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Front change")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]

    new_job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert row is not None
    assert str(row.front_job_id) != str(new_job.id)
    row.front_job_id = new_job.id
    db_session.add(row)
    db_session.commit()

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    assert "front" in str(refused.json().get("detail") or "").lower()
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_export_id


def test_pdf_only_rejects_back_magic_source_change(client, db_session, monkeypatch):
    from app.models.techpack_draft import TechpackDraft
    from tests.test_techpack_p0_reliability import (
        TUNICS_IDENTITY,
        TUNICS_TROUSERS_SUMMARY,
        _add_job,
        _store_image,
    )

    tokens = register_with_invite(client, db_session, "pdfback@example.com", "pdfback")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Back change")
    _complete_professional(client, db_session, tokens, draft["id"])

    new_back = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert row is not None
    row.back_job_id = new_back.id
    db_session.add(row)
    db_session.commit()

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "back" in detail


def test_pdf_only_rejects_absent_front_source(client, db_session, monkeypatch):
    from app.models.techpack_draft import TechpackDraft

    tokens = register_with_invite(client, db_session, "pdfabsent@example.com", "pdfabsent")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Absent front")
    _complete_professional(client, db_session, tokens, draft["id"])

    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert row is not None and row.front_job_id is not None
    row.front_job_id = None
    db_session.add(row)
    db_session.commit()

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    assert "front" in str(refused.json().get("detail") or "").lower()


def test_pdf_only_rejects_category_change(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdfcat@example.com", "pdfcat")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Category change")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]

    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = []
    for p in live["spec"]["outfit"]["pieces"]:
        copy = dict(p)
        if p.get("id") == "tunic-1":
            copy["category"] = "dress"
        pieces.append(copy)
    drifted = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": 2, "pieces": pieces}}},
    )
    assert drifted.status_code == 200, drifted.text

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "garment identity" in detail or "category" in detail or "illustrations" in detail
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_export_id


def test_pdf_only_rejects_legacy_unknown_magic_provenance(client, db_session, monkeypatch):
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.techpack_ai_run import TechpackAIRun
    from app.models.techpack_draft import TechpackExport

    tokens = register_with_invite(client, db_session, "pdflegacy@example.com", "pdflegacy")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Legacy provenance")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    run = db_session.get(TechpackAIRun, uuid.UUID(settled["id"]))
    assert run is not None
    # Simulate legacy enqueue: no front/back stamps on request.
    req = dict(run.request or {})
    req.pop("front_job_id", None)
    req.pop("back_job_id", None)
    run.request = req
    flag_modified(run, "request")
    db_session.add(run)

    # Strip Magic ids from all Professional exports for this run.
    exports = (
        db_session.query(TechpackExport)
        .filter(TechpackExport.draft_id == uuid.UUID(draft["id"]))
        .all()
    )
    for exp in exports:
        meta = dict(exp.metadata_ or {})
        meta.pop("front_job_id", None)
        meta.pop("back_job_id", None)
        meta["front_job_id"] = None
        meta["back_job_id"] = None
        exp.metadata_ = meta
        flag_modified(exp, "metadata_")
        db_session.add(exp)
    db_session.commit()

    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "legacy edit"}}},
    )
    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "unknown" in detail or "legacy" in detail or "provenance" in detail


def test_pdf_only_uses_export_meta_when_request_lacks_source_ids(
    client, db_session, monkeypatch
):
    """Existing prod runs stamp Magic ids on export metadata, not request — must still gate."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.techpack_ai_run import TechpackAIRun
    from app.models.techpack_draft import TechpackDraft
    from tests.test_techpack_p0_reliability import (
        TUNICS_IDENTITY,
        TUNICS_TROUSERS_SUMMARY,
        _add_job,
        _store_image,
    )

    tokens = register_with_invite(client, db_session, "pdfmeta@example.com", "pdfmeta")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Export meta gate")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    run = db_session.get(TechpackAIRun, uuid.UUID(settled["id"]))
    assert run is not None
    req = dict(run.request or {})
    req.pop("front_job_id", None)
    req.pop("back_job_id", None)
    run.request = req
    flag_modified(run, "request")
    db_session.add(run)
    db_session.commit()

    # Compatible edit → PDF-only should still succeed via export metadata provenance.
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "meta path ok"}}},
    )
    ok = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert ok.status_code == 201, ok.text

    # Front change must still reject using export-meta authorization.
    new_job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert row is not None
    row.front_job_id = new_job.id
    db_session.add(row)
    db_session.commit()
    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    assert "front" in str(refused.json().get("detail") or "").lower()


def test_pdf_only_concurrent_identical_converges_one_export(client, db_session, monkeypatch):
    """Losers of a same-content race adopt the winner export; history stays singular.

    Limitation: this nests two HTTP export calls inside one shared TestClient /
    db_session (overlapping assembly simulation), not two independent PostgreSQL
    transactions. Production serialization relies on ``SELECT FOR UPDATE`` + CAS in
    ``export_pdf_only_update``; see ``test_pdf_only_draft_row_lock_serializes_independent_sessions``.
    """
    from app.models.techpack_draft import TechpackExport
    from app.services import techpack_service

    tokens = register_with_invite(client, db_session, "pdfconc@example.com", "pdfconc")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Concurrent identical")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "concurrent"}}},
    )

    nested = {"done": False, "in_nested": False, "id": None}
    real_build = techpack_service.build_techpack_pdf

    def build_with_racing_winner(*args, **kwargs):
        if nested["in_nested"]:
            return real_build(*args, **kwargs)
        pdf = real_build(*args, **kwargs)
        if not nested["done"]:
            nested["done"] = True
            nested["in_nested"] = True
            try:
                winner = client.post(
                    f"/api/v1/techpacks/{draft['id']}/export",
                    headers=_auth(tokens),
                    json={"mode": "pdf_only_update", "idempotency_key": "winner"},
                )
                assert winner.status_code == 201, winner.text
                nested["id"] = winner.json()["id"]
            finally:
                nested["in_nested"] = False
        return pdf

    monkeypatch.setattr(techpack_service, "build_techpack_pdf", build_with_racing_winner)

    loser = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update", "idempotency_key": "loser"},
    )
    assert loser.status_code == 201, loser.text
    assert nested["id"] is not None
    assert loser.json()["id"] == nested["id"]
    assert nested["id"] != first_export_id

    assert loser.json()["id"] == nested["id"]

    monkeypatch.setattr(techpack_service, "build_techpack_pdf", real_build)
    db_session.expire_all()
    rows = (
        db_session.query(TechpackExport)
        .filter(TechpackExport.draft_id == uuid.UUID(draft["id"]))
        .all()
    )
    pdf_only = [
        r
        for r in rows
        if isinstance(r.metadata_, dict) and r.metadata_.get("pdf_only_update")
    ]
    assert len(pdf_only) == 1
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == nested["id"]
    # Repeat-after-success idempotency is covered in
    # test_pdf_only_update_zero_provider_calls_and_preserves_history.


def test_pdf_only_edit_during_assembly_refuses_stale_bind(client, db_session, monkeypatch):
    from app.services import techpack_service

    tokens = register_with_invite(client, db_session, "pdfedit@example.com", "pdfedit")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Edit during assembly")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "before assembly"}}},
    )
    before = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert before["spec"]["ai"].get("dirty_since_generation") is True

    real_build = techpack_service.build_techpack_pdf

    def _build_and_edit(*args, **kwargs):
        # Intervening designer save changes content fingerprint while PDF bytes assemble.
        edited = client.patch(
            f"/api/v1/techpacks/{draft['id']}",
            headers=_auth(tokens),
            json={"spec": {"preferences": {"notes": "edit during assembly"}}},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["spec"]["preferences"]["notes"] == "edit during assembly"
        return real_build(*args, **kwargs)

    monkeypatch.setattr(techpack_service, "build_techpack_pdf", _build_and_edit)

    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 409, refused.text

    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    # Newer edit must remain; do not bind the stale assembly as current.
    assert after["spec"]["ai"].get("dirty_since_generation") is True
    assert after["spec"]["ai"].get("export_id") == first_export_id
    assert after["spec"]["preferences"]["notes"] == "edit during assembly"


def test_pdf_only_failed_bind_cleans_orphan_file(client, db_session, monkeypatch):
    import pytest

    from app.services import techpack_service
    from app.storage.local import LocalStorageBackend

    tokens = register_with_invite(client, db_session, "pdffail@example.com", "pdffail")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Failed bind")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": "fail bind"}}},
    )

    saved_keys: list[str] = []
    real_save = LocalStorageBackend.save_private_techpack_file

    def _tracking_save(self, *, key, data, content_type=None):
        saved_keys.append(key)
        return real_save(self, key=key, data=data, content_type=content_type)

    monkeypatch.setattr(LocalStorageBackend, "save_private_techpack_file", _tracking_save)

    real_bind = techpack_service._bind_current_professional_export

    def _fail_bind(*args, **kwargs):
        raise RuntimeError("simulated bind failure")

    monkeypatch.setattr(techpack_service, "_bind_current_professional_export", _fail_bind)

    with pytest.raises(RuntimeError, match="simulated bind failure"):
        client.post(
            f"/api/v1/techpacks/{draft['id']}/export",
            headers=_auth(tokens),
            json={"mode": "pdf_only_update"},
        )
    assert saved_keys, "expected a private PDF write before bind failure"
    storage = LocalStorageBackend()
    for key in saved_keys:
        assert storage.resolve_private_techpack_file(key=key) is None

    # Historical paid export file must remain untouched after the failed bind cleanup.
    from app.models.techpack_draft import TechpackExport

    paid = db_session.get(TechpackExport, uuid.UUID(first_export_id))
    assert paid is not None
    assert storage.resolve_private_techpack_file(key=paid.storage_key) is not None
    _ = real_bind  # restored implicitly when monkeypatch fixture tears down


def _dirty_for_pdf_only(client, tokens, draft_id: str) -> None:
    patched = client.patch(
        f"/api/v1/techpacks/{draft_id}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"notes": f"pdf-only-{uuid.uuid4().hex[:8]}"}}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["spec"]["ai"].get("dirty_since_generation") is True


def _piece_arts(draft_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in draft_json["spec"]["outfit"]["pieces"]:
        ill = p.get("illustrations") or {}
        arts = ill.get("artifacts") or {}
        out[str(p.get("id"))] = {k: dict(v) for k, v in arts.items() if isinstance(v, dict)}
    return out


def test_pdf_only_reuses_valid_original_professional_artifacts(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "pdfartok@example.com", "pdfartok")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Valid arts")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    calls_after = CountingMock.provider_calls
    _dirty_for_pdf_only(client, tokens, draft["id"])

    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["id"] != first_export_id
    assert updated.json()["metadata"].get("new_paid_ai_run") is False
    assert CountingMock.provider_calls == calls_after

    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == updated.json()["id"]
    old_pdf = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    new_pdf = client.get(
        f"/api/v1/techpacks/exports/{updated.json()['id']}/pdf", headers=_auth(tokens)
    )
    assert old_pdf.status_code == 200
    assert new_pdf.status_code == 200


def test_pdf_only_rejects_run_from_another_draft_same_user(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdfxdraft@example.com", "pdfxdraft")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft_a = _seed_two_piece_draft(client, db_session, tokens, me, title="Draft A")
    settled_a = _complete_professional(client, db_session, tokens, draft_a["id"])
    draft_b = _seed_two_piece_draft(client, db_session, tokens, me, title="Draft B")
    settled_b = _complete_professional(client, db_session, tokens, draft_b["id"])
    first_b = settled_b["export_id"]

    live = client.get(f"/api/v1/techpacks/{draft_b['id']}", headers=_auth(tokens)).json()
    # Substitute draft B's last_run_id with draft A's completed run (same user).
    forged = client.patch(
        f"/api/v1/techpacks/{draft_b['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "preferences": {"notes": "cross-draft run"},
                "ai": {
                    **(live["spec"].get("ai") or {}),
                    "last_run_id": settled_a["id"],
                    "last_mode": "professional",
                },
            }
        },
    )
    assert forged.status_code == 200, forged.text

    refused = client.post(
        f"/api/v1/techpacks/{draft_b['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "different draft" in detail or "another design" in detail or "not owned" in detail
    after = client.get(f"/api/v1/techpacks/{draft_b['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_b
    hist = client.get(f"/api/v1/techpacks/exports/{first_b}/pdf", headers=_auth(tokens))
    assert hist.status_code == 200


def test_pdf_only_rejects_run_from_another_user(client, db_session, monkeypatch):
    tokens_a = register_with_invite(client, db_session, "pdfuserA@example.com", "pdfuserA")
    me_a = client.get("/api/v1/auth/me", headers=_auth(tokens_a)).json()
    _enable_professional(monkeypatch, me_a["email"])
    draft_a = _seed_two_piece_draft(client, db_session, tokens_a, me_a, title="User A")
    settled_a = _complete_professional(client, db_session, tokens_a, draft_a["id"])

    tokens_b = register_with_invite(client, db_session, "pdfuserB@example.com", "pdfuserB")
    me_b = client.get("/api/v1/auth/me", headers=_auth(tokens_b)).json()
    _enable_professional(monkeypatch, me_b["email"])
    draft_b = _seed_two_piece_draft(client, db_session, tokens_b, me_b, title="User B")
    settled_b = _complete_professional(client, db_session, tokens_b, draft_b["id"])
    first_b = settled_b["export_id"]

    live = client.get(f"/api/v1/techpacks/{draft_b['id']}", headers=_auth(tokens_b)).json()
    forged = client.patch(
        f"/api/v1/techpacks/{draft_b['id']}",
        headers=_auth(tokens_b),
        json={
            "spec": {
                "preferences": {"notes": "cross-user run"},
                "ai": {
                    **(live["spec"].get("ai") or {}),
                    "last_run_id": settled_a["id"],
                    "last_mode": "professional",
                },
            }
        },
    )
    assert forged.status_code == 200, forged.text
    refused = client.post(
        f"/api/v1/techpacks/{draft_b['id']}/export",
        headers=_auth(tokens_b),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "not owned" in detail or "another account" in detail or "authenticated user" in detail
    after = client.get(f"/api/v1/techpacks/{draft_b['id']}", headers=_auth(tokens_b)).json()
    assert after["spec"]["ai"].get("export_id") == first_b


def test_pdf_only_rejects_flat_front_substituted_from_other_garment(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "pdfswap@example.com", "pdfswap")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Swap garment art")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]

    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    arts = _piece_arts(live)
    tunic_front = arts["tunic-1"]["flat_front"]
    trousers_front = arts["tr-1"]["flat_front"]
    assert tunic_front.get("artifact_id") != trousers_front.get("artifact_id")

    pieces = []
    for p in live["spec"]["outfit"]["pieces"]:
        copy = dict(p)
        if p.get("id") == "tr-1":
            ill = dict(copy.get("illustrations") or {})
            art = dict(ill.get("artifacts") or {})
            # Substitute trousers flat_front with the tunic's artifact.
            art["flat_front"] = dict(tunic_front)
            ill["artifacts"] = art
            ill["mode"] = "professional"
            copy["illustrations"] = ill
        pieces.append(copy)

    forged = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "preferences": {"notes": "swap flat_front"},
                "outfit": {"piece_count": 2, "pieces": pieces},
            }
        },
    )
    assert forged.status_code == 200, forged.text
    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "different garment" in detail or "substituted" in detail
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_export_id
    hist = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    assert hist.status_code == 200


def test_pdf_only_rejects_artifact_id_storage_key_mismatch(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "pdfmismatch@example.com", "pdfmismatch")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Key mismatch")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]

    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = []
    for p in live["spec"]["outfit"]["pieces"]:
        copy = dict(p)
        if p.get("id") == "tunic-1":
            ill = dict(copy.get("illustrations") or {})
            art = dict(ill.get("artifacts") or {})
            flat = dict(art.get("flat_front") or {})
            flat["storage_key"] = "forged/not/the/authorized/key.png"
            art["flat_front"] = flat
            ill["artifacts"] = art
            copy["illustrations"] = ill
        pieces.append(copy)

    forged = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "preferences": {"notes": "key mismatch"},
                "outfit": {"piece_count": 2, "pieces": pieces},
            }
        },
    )
    assert forged.status_code == 200, forged.text
    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "storage key" in detail or "path-substituted" in detail or "match" in detail
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_export_id


def test_pdf_only_accepts_legacy_export_with_verifiable_ownership(
    client, db_session, monkeypatch
):
    """Legacy runs without request front/back stamps still work via export-meta + owned arts."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.techpack_ai_run import TechpackAIRun

    tokens = register_with_invite(client, db_session, "pdflegok@example.com", "pdflegok")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Legacy owned")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    run = db_session.get(TechpackAIRun, uuid.UUID(settled["id"]))
    assert run is not None
    req = dict(run.request or {})
    req.pop("front_job_id", None)
    req.pop("back_job_id", None)
    run.request = req
    flag_modified(run, "request")
    db_session.add(run)
    db_session.commit()

    _dirty_for_pdf_only(client, tokens, draft["id"])
    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert updated.status_code == 201, updated.text
    assert updated.json()["id"] != first_export_id
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == updated.json()["id"]
    hist = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    assert hist.status_code == 200


def test_pdf_only_unverifiable_historical_artifact_fails_without_destroying_history(
    client, db_session, monkeypatch
):

    from app.models.techpack_ai_artifact import TechpackAIArtifact

    tokens = register_with_invite(client, db_session, "pdfunv@example.com", "pdfunv")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Unverifiable art")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    first_export_id = settled["export_id"]
    run_id = uuid.UUID(settled["id"])

    arts = (
        db_session.query(TechpackAIArtifact)
        .filter(
            TechpackAIArtifact.run_id == run_id,
            TechpackAIArtifact.kind == "flat_front",
        )
        .all()
    )
    assert arts, "expected flat_front artifacts from Professional completion"
    for row in arts:
        row.piece_id = None  # incomplete historical metadata
        db_session.add(row)
    db_session.commit()

    _dirty_for_pdf_only(client, tokens, draft["id"])
    refused = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert refused.status_code == 422, refused.text
    detail = str(refused.json().get("detail") or "").lower()
    assert "incomplete" in detail or "provenance" in detail or "failing closed" in detail

    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after["spec"]["ai"].get("export_id") == first_export_id
    hist = client.get(
        f"/api/v1/techpacks/exports/{first_export_id}/pdf", headers=_auth(tokens)
    )
    assert hist.status_code == 200
    # Original AI illustrations remain on the draft (not wiped by the refusal).
    live_arts = _piece_arts(after)
    assert live_arts["tunic-1"]["flat_front"].get("artifact_id")


def test_pdf_only_draft_row_lock_uses_select_for_update():
    """Document + assert the production lock primitive (independent-session caveat).

    The HTTP concurrent regression nests overlapping exports inside one shared
    TestClient ``db_session`` (connection-bound outer transaction). Independent
    PostgreSQL sessions cannot observe those uncommitted fixture rows, so a true
    two-connection lock-wait assertion is not practical under the current test DB
    harness. Production ``export_pdf_only_update`` still serializes via
    ``SELECT … FOR UPDATE`` on the draft row plus revision/fingerprint CAS.
    """
    import inspect

    from app.services import techpack_service

    src = inspect.getsource(techpack_service._lock_owned_draft)
    assert "with_for_update" in src
    src_export = inspect.getsource(techpack_service.export_pdf_only_update)
    assert "_lock_owned_draft" in src_export
    assert "draft_revision_changed" in src_export or "fingerprint" in src_export


def test_owner_artifact_review_invalidates_pdf_and_excludes_on_rebuild(
    client, db_session, monkeypatch
):
    """P0 production path: clean PDF A → owner reject → dirty CTA → PDF-only B excludes art.

    Also covers: auth-derived reviewer, idempotent repeat, historical A preserved,
    zero provider calls, and other-user isolation.
    """
    import hashlib
    import io

    from app.models.techpack_ai_artifact import TechpackAIArtifact
    from app.storage.local import LocalStorageBackend

    tokens = register_with_invite(client, db_session, "pdfreview@example.com", "pdfreview")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Review gate")
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-review-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=4) >= 1
    settled = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert settled["status"] == "completed", settled
    assert settled.get("pdf_ready") is True
    export_a_id = settled["export_id"]
    calls_after_paid = CountingMock.provider_calls
    assert calls_after_paid > 0

    # Pick shorts/trousers detail if present; else any detail_callouts.
    details = (
        db_session.query(TechpackAIArtifact)
        .filter(
            TechpackAIArtifact.run_id == run_id,
            TechpackAIArtifact.kind == "detail_callouts",
        )
        .all()
    )
    assert details
    detail = next((d for d in details if (d.piece_id or "").endswith("2") or "short" in str(d.piece_id or "").lower()), details[-1])
    artifact_id = str(detail.id)
    storage_key = detail.storage_key
    prior_state = detail.review_state
    prior_revision = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()[
        "revision"
    ]
    storage = LocalStorageBackend()
    art_path = storage.resolve_private_techpack_file(key=storage_key)
    assert art_path is not None and art_path.is_file()
    rejected_sha = hashlib.sha256(art_path.read_bytes()).hexdigest()

    # PDF A is current and clean (not dirty).
    before = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert before["spec"]["ai"].get("dirty_since_generation") is False
    assert before["spec"]["ai"].get("export_id") == export_a_id
    pdf_a = client.get(f"/api/v1/techpacks/exports/{export_a_id}/pdf", headers=_auth(tokens))
    assert pdf_a.status_code == 200
    pages_a = len(PdfReader(io.BytesIO(pdf_a.content)).pages)

    reviewed = client.post(
        f"/api/v1/techpacks/artifacts/{artifact_id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected_category_mismatch",
            "review_message": (
                "Owner QA: detail artwork does not match this garment category. "
                "Original preserved; exclude from PDF-only preview."
            ),
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["review_state"] == "rejected_category_mismatch"
    assert body.get("bytes_preserved") is True
    assert body.get("file_deleted") is False
    assert body.get("pdf_invalidated") is True
    assert body.get("dirty_since_generation") is True
    assert body["operator_decision"]["prior_review_state"] == prior_state
    # Reviewer identity is server-derived from auth — never a client operator string.
    assert body["operator_decision"]["reviewer_user_id"] == me["id"]
    assert body["operator_decision"]["role"] == "owner"
    assert "operator" not in body["operator_decision"]

    db_session.refresh(detail)
    assert detail.review_state == "rejected_category_mismatch"
    assert detail.storage_key == storage_key
    assert detail.metadata_.get("preview_include") is False
    assert art_path.is_file()  # bytes preserved

    # GET draft shows outdated / Update PDF (No AI) gate.
    after_review = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert after_review["spec"]["ai"].get("dirty_since_generation") is True
    assert after_review["spec"]["ai"].get("outdated_export_id") == export_a_id
    assert after_review["spec"]["ai"].get("export_id") == export_a_id
    assert int(after_review["revision"]) == int(prior_revision) + 1

    # Identical repeat is idempotent (no second revision bump).
    repeat = client.post(
        f"/api/v1/techpacks/artifacts/{artifact_id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected_category_mismatch",
            "review_message": (
                "Owner QA: detail artwork does not match this garment category. "
                "Original preserved; exclude from PDF-only preview."
            ),
        },
    )
    assert repeat.status_code == 200, repeat.text
    assert repeat.json().get("idempotent") is True
    again = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert int(again["revision"]) == int(after_review["revision"])

    # Image still downloadable (not deleted).
    img = client.get(
        f"/api/v1/techpacks/artifacts/{artifact_id}/image",
        headers=_auth(tokens),
    )
    assert img.status_code == 200
    assert hashlib.sha256(img.content).hexdigest() == rejected_sha

    # Other user cannot review this artifact.
    tokens_b = register_with_invite(client, db_session, "pdfreviewb@example.com", "pdfreviewb")
    denied = client.post(
        f"/api/v1/techpacks/artifacts/{artifact_id}/review",
        headers=_auth(tokens_b),
        json={
            "review_state": "rejected",
            "review_message": "Should not mutate another user's artifact.",
        },
    )
    assert denied.status_code in (403, 404)

    # PDF-only B — uses latest review state; no provider calls.
    updated = client.post(
        f"/api/v1/techpacks/{draft['id']}/export",
        headers=_auth(tokens),
        json={"mode": "pdf_only_update"},
    )
    assert updated.status_code == 201, updated.text
    export_b = updated.json()
    assert export_b["id"] != export_a_id
    meta = export_b["metadata"]
    assert meta.get("pdf_only_update") is True
    assert meta.get("assembly_cost_usd_cents") == 0
    assert meta.get("new_paid_ai_run") is False
    assert meta.get("generation_mode") == "pdf_only_update"
    assert "PDF-only" in str(meta.get("generation_label") or "")
    assert CountingMock.provider_calls == calls_after_paid

    bound = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert bound["spec"]["ai"].get("export_id") == export_b["id"]
    assert bound["spec"]["ai"].get("dirty_since_generation") is False

    pdf_b = client.get(
        f"/api/v1/techpacks/exports/{export_b['id']}/pdf", headers=_auth(tokens)
    )
    assert pdf_b.status_code == 200
    text_b = "\n".join(
        (p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_b.content)).pages
    )
    flat_b = " ".join(text_b.split())
    assert "EXCLUDED" in flat_b or "MISSING" in flat_b
    assert "does not match this garment category" in flat_b or "Original preserved" in flat_b
    # Rejected source PNG must not be embedded as a full image object with identical sha
    # (ReportLab may re-encode; still require exclusion copy + fewer-or-equal pages).
    pages_b = len(PdfReader(io.BytesIO(pdf_b.content)).pages)
    assert pages_b <= pages_a

    # Historical A remains downloadable and unchanged.
    hist = client.get(f"/api/v1/techpacks/exports/{export_a_id}/pdf", headers=_auth(tokens))
    assert hist.status_code == 200
    assert hist.content == pdf_a.content

    # Reapproval restores inclusion for a subsequent PDF-only rebuild.
    reapprove = client.post(
        f"/api/v1/techpacks/artifacts/{artifact_id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "visual_qa_confirmed",
            "review_message": "Owner visually confirmed this detail matches the garment.",
        },
    )
    assert reapprove.status_code == 200, reapprove.text
    assert reapprove.json().get("pdf_invalidated") is True
    db_session.refresh(detail)
    assert detail.metadata_.get("preview_include") is True
    assert detail.metadata_.get("manufacturing_evidence") is True


def _insert_orphan_artifact(
    db_session,
    *,
    user_id,
    draft_id,
    run_id,
    piece_id: str,
    kind: str = "detail_callouts",
):
    """Persist a TechpackAIArtifact row that may or may not be outfit-referenced."""
    from app.models.techpack_ai_artifact import TechpackAIArtifact
    from app.storage.local import LocalStorageBackend

    storage = LocalStorageBackend()
    key = f"{user_id.hex}/{draft_id.hex}/{uuid.uuid4().hex}.png"
    storage.save_private_techpack_file(
        key=key,
        data=__import__("io").BytesIO(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
            b"\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        ),
        content_type="image/png",
    )
    row = TechpackAIArtifact(
        id=uuid.uuid4(),
        run_id=run_id,
        draft_id=draft_id,
        user_id=user_id,
        piece_id=piece_id,
        kind=kind,
        storage_key=key,
        mime_type="image/png",
        byte_size=68,
        review_state="proposed",
        metadata_={"synthetic": True},
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_artifact_review_rejects_non_professional_run(client, db_session, monkeypatch):
    """Same-user/same-draft non-Professional stage must fail closed (no silent continue)."""
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "revbasic@example.com", "revbasic")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Non-pro review")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    user = db_session.get(User, uuid.UUID(me["id"]))
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert user and row

    basic_run = TechpackAIRun(
        id=uuid.uuid4(),
        draft_id=row.id,
        user_id=user.id,
        stage="basic",
        status="completed",
        confirm_token=f"tok-{uuid.uuid4().hex}",
        idempotency_key=f"basic-{uuid.uuid4().hex}",
        cost_usd_cents=0,
        request={"mode": "basic"},
        result={"note": "non-professional"},
    )
    db_session.add(basic_run)
    db_session.commit()

    piece_id = row.spec["outfit"]["pieces"][0]["id"]
    orphan = _insert_orphan_artifact(
        db_session,
        user_id=user.id,
        draft_id=row.id,
        run_id=basic_run.id,
        piece_id=piece_id,
    )
    # Even if we forge an outfit reference, non-Professional stage must fail.
    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = live["spec"]["outfit"]["pieces"]
    for p in pieces:
        if p.get("id") != piece_id:
            continue
        ill = dict(p.get("illustrations") or {})
        arts = dict(ill.get("artifacts") or {})
        arts["detail_callouts"] = {
            "artifact_id": str(orphan.id),
            "storage_key": orphan.storage_key,
        }
        ill["artifacts"] = arts
        p["illustrations"] = ill
    # Keep last_run_id on the real Professional run so the pack stays valid;
    # the basic-run artifact still fails the stage gate.
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": len(pieces), "pieces": pieces}}},
    )
    assert patched.status_code == 200, patched.text
    prior_rev = patched.json()["revision"]

    denied = client.post(
        f"/api/v1/techpacks/artifacts/{orphan.id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected",
            "review_message": "Must not invalidate from a basic/non-Professional run.",
        },
    )
    assert denied.status_code == 422, denied.text
    msg = str((denied.json().get("detail") or {}).get("message") or "")
    assert "Professional" in msg or "Disallowed" in msg
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert int(after["revision"]) == int(prior_rev)
    assert after["spec"]["ai"].get("export_id") == settled["export_id"]
    _ = settled  # paid pack preserved


def test_artifact_review_rejects_historical_non_current_run(client, db_session, monkeypatch):
    """Artifact from an older Professional run not bound as last_run_id must fail closed."""
    from app.models.techpack_ai_artifact import TechpackAIArtifact
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "revhist@example.com", "revhist")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Historical review")
    first = _complete_professional(client, db_session, tokens, draft["id"])
    first_run_id = first["run_id"]
    first_details = (
        db_session.query(TechpackAIArtifact)
        .filter(
            TechpackAIArtifact.run_id == first_run_id,
            TechpackAIArtifact.kind == "detail_callouts",
        )
        .all()
    )
    assert first_details
    historical = first_details[0]

    # Dirty + regenerate so last_run_id points at a newer Professional run.
    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = live["spec"]["outfit"]["pieces"]
    edited = []
    for p in pieces:
        copy = dict(p)
        fm = dict(copy.get("finished_measurements") or {})
        fm["garment_length"] = {"value": 88, "unit": "cm", "source": "designer"}
        copy["finished_measurements"] = fm
        edited.append(copy)
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": len(edited), "pieces": edited}}},
    )
    assert patched.status_code == 200
    second = _complete_professional(client, db_session, tokens, draft["id"])
    assert second["run_id"] != first_run_id
    bound = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert bound["spec"]["ai"].get("last_run_id") == second["run_id"]
    prior_rev = bound["revision"]

    denied = client.post(
        f"/api/v1/techpacks/artifacts/{historical.id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected_category_mismatch",
            "review_message": "Historical artifact must not dirty the current pack.",
        },
    )
    assert denied.status_code == 422, denied.text
    detail = str((denied.json().get("detail") or {}).get("message") or "")
    assert "historical" in detail.lower() or "unbound" in detail.lower() or "current" in detail.lower()
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert int(after["revision"]) == int(prior_rev)
    assert after["spec"]["ai"].get("last_run_id") == second["run_id"]
    user = db_session.get(User, uuid.UUID(me["id"]))
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert user and row


def test_artifact_review_rejects_unreferenced_illustration(client, db_session, monkeypatch):
    """Same current Professional run, but artifact not in outfit illustrations → fail closed."""
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User

    tokens = register_with_invite(client, db_session, "revunref@example.com", "revunref")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Unreferenced review")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    user = db_session.get(User, uuid.UUID(me["id"]))
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert user and row
    piece_id = row.spec["outfit"]["pieces"][0]["id"]
    orphan = _insert_orphan_artifact(
        db_session,
        user_id=user.id,
        draft_id=row.id,
        run_id=uuid.UUID(settled["run_id"]),
        piece_id=piece_id,
        kind="detail_callouts",
    )
    prior = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    prior_rev = prior["revision"]

    denied = client.post(
        f"/api/v1/techpacks/artifacts/{orphan.id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected",
            "review_message": "Unreferenced illustration must not invalidate current PDF.",
        },
    )
    assert denied.status_code == 422, denied.text
    assert "not referenced" in str((denied.json().get("detail") or {}).get("message") or "").lower()
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert int(after["revision"]) == int(prior_rev)
    assert after["spec"]["ai"].get("export_id") == settled["export_id"]


def test_artifact_review_allows_legacy_blank_stage_with_professional_evidence(
    client, db_session, monkeypatch
):
    """Blank stage is allowed only when draft last_mode/last_run_id prove Professional."""
    from app.models.techpack_ai_artifact import TechpackAIArtifact
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    tokens = register_with_invite(client, db_session, "revlegacy@example.com", "revlegacy")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Legacy blank stage")
    settled = _complete_professional(client, db_session, tokens, draft["id"])
    user = db_session.get(User, uuid.UUID(me["id"]))
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert user and row
    run = db_session.get(TechpackAIRun, uuid.UUID(settled["run_id"]))
    assert run is not None
    # Simulate legacy blank stage while request.mode is also blank — draft AI evidence
    # (last_mode + last_run_id) is the only Professional authorization.
    run.stage = ""
    run.request = dict(run.request or {})
    run.request.pop("mode", None)
    db_session.add(run)
    db_session.commit()

    detail = (
        db_session.query(TechpackAIArtifact)
        .filter(
            TechpackAIArtifact.run_id == run.id,
            TechpackAIArtifact.kind == "detail_callouts",
        )
        .first()
    )
    assert detail is not None
    prior_rev = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()[
        "revision"
    ]
    ok = client.post(
        f"/api/v1/techpacks/artifacts/{detail.id}/review",
        headers=_auth(tokens),
        json={
            "review_state": "rejected_category_mismatch",
            "review_message": "Legacy blank-stage Professional evidence still authorizes review.",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json().get("pdf_invalidated") is True
    after = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert int(after["revision"]) == int(prior_rev) + 1
    assert after["spec"]["ai"].get("dirty_since_generation") is True
    flag_modified(row, "spec")
