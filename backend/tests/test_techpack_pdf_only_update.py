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
    """Losers of a same-content race adopt the winner export; history stays singular."""
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
