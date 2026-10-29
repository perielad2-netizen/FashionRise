"""Issue #128 P0 — concurrent designer edits during Professional generation.

Mocked provider only. Asserts DB persist + GET/reopen survival.
"""

from __future__ import annotations

import copy
import io
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from PIL import Image
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackDraft, TechpackExport
from app.services.techpack_ai import set_professional_provider_override
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import run_techpack_worker_tick
from app.services.techpack_garments import FINISHED_POM
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    img = Image.new("RGB", (128, 192), (200, 80, 40))
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
        result_data={
            "summary": "golden-yellow mid-thigh shorts with lavender top",
            "pipeline": "sketch_polish",
            "image_url": image_url,
        },
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


def _designer_cell(value: float | None, *, source: str = "designer", **extra: Any) -> dict[str, Any]:
    cell = {
        "value": value,
        "unit": "cm",
        "source": source if value is not None else "empty",
        "note": extra.pop("note", "owner entered" if value is not None else None),
        "definition": extra.pop("definition", None),
        "confidence": extra.pop("confidence", "high" if value is not None else "unknown"),
        "review_status": extra.pop("review_status", "confirmed" if value is not None else "open"),
        "assumptions": [],
    }
    cell.update(extra)
    return cell


def _seed_shorts_draft(client, db_session, tokens, me) -> dict[str, Any]:
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image())
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "FR-128 Concurrent"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    # Force a shorts piece with all nine POMs filled (outseam/thigh/waistband included).
    live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = live["spec"]["outfit"]["pieces"]
    assert pieces, "expected seeded pieces"
    # Prefer an existing bottom/shorts piece; otherwise retarget first piece.
    target = None
    for p in pieces:
        if str(p.get("category") or "") in ("shorts", "trousers"):
            target = p
            break
    if target is None:
        target = pieces[0]
    target["category"] = "shorts"
    target["label"] = "Shorts"
    values = {
        "waist": 75.0,
        "hip": 110.0,
        "inseam": 18.0,
        "outseam": 42.0,
        "front_rise": 30.0,
        "back_rise": 40.0,
        "thigh": 58.0,
        "leg_opening": 40.0,
        "waistband": 4.0,
    }
    finished = {}
    for key in FINISHED_POM["shorts"]:
        finished[key] = _designer_cell(values[key], definition=key)
    target["finished_measurements"] = finished
    # Keep other pieces but ensure shorts is present.
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": len(pieces), "pieces": pieces}}},
    )
    assert patched.status_code == 200, patched.text
    return patched.json()


class ConcurrentEditProvider(MockProfessionalProvider):
    """Runs a DB edit callback on the first analyze_garment call (mid paid pipeline)."""

    provider_calls = 0

    def __init__(self, on_first_analyze) -> None:
        super().__init__()
        self.on_first_analyze = on_first_analyze
        self._fired = False

    def analyze_garment(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        ConcurrentEditProvider.provider_calls += 1
        if not self._fired:
            self._fired = True
            self.on_first_analyze()
        return super().analyze_garment(*args, **kwargs)


def _find_shorts_piece(spec: dict[str, Any]) -> dict[str, Any]:
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    for piece in outfit.get("pieces") or []:
        if isinstance(piece, dict) and str(piece.get("category") or "") == "shorts":
            return piece
    raise AssertionError("shorts piece missing")


def test_all_nine_shorts_poms_survive_professional_persist_and_reopen(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "meas128a@example.com", "meas128a")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    before = _find_shorts_piece(draft["spec"])["finished_measurements"]

    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"meas-all-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"
    assert status.get("pdf_ready") is True

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    after = _find_shorts_piece(reopened["spec"])["finished_measurements"]
    for key in FINISHED_POM["shorts"]:
        assert after[key]["value"] == before[key]["value"], f"{key} lost"
        assert after[key]["source"] == "designer"
        assert after[key]["review_status"] == before[key]["review_status"]
        assert after[key]["definition"] == before[key]["definition"]


def test_owner_waist_edit_during_ai_run_survives_persist_and_get(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "meas128b@example.com", "meas128b")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    ConcurrentEditProvider.provider_calls = 0

    def _edit_waist() -> None:
        row = db_session.get(TechpackDraft, draft_id)
        assert row is not None
        spec = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
        piece = _find_shorts_piece(spec)
        fm = dict(piece.get("finished_measurements") or {})
        waist = dict(fm.get("waist") or {})
        waist.update(
            {
                "value": 76.5,
                "source": "designer",
                "review_status": "confirmed",
                "note": "edited during AI",
                "definition": "Waist circumference",
                "confidence": "high",
            }
        )
        fm["waist"] = waist
        piece["finished_measurements"] = fm
        for i, p in enumerate(spec["outfit"]["pieces"]):
            if str(p.get("id")) == str(piece.get("id")):
                spec["outfit"]["pieces"][i] = piece
        row.spec = spec
        flag_modified(row, "spec")
        row.revision = int(row.revision or 1) + 1
        row.updated_at = datetime.now(UTC)
        db_session.add(row)
        db_session.commit()

    set_professional_provider_override(ConcurrentEditProvider(_edit_waist))
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"meas-waist-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    calls_before = ConcurrentEditProvider.provider_calls
    assert run_techpack_worker_tick(db_session, limit=2) >= 1
    assert ConcurrentEditProvider.provider_calls > calls_before

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"
    # No second paid enqueue for same completed run.
    again = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"meas-waist-again-{uuid.uuid4().hex}"},
    )
    assert again.status_code == 202
    assert again.json()["run_id"] == run_id
    calls_after_reuse = ConcurrentEditProvider.provider_calls
    assert run_techpack_worker_tick(db_session, limit=2) == 0
    assert ConcurrentEditProvider.provider_calls == calls_after_reuse

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    waist = _find_shorts_piece(reopened["spec"])["finished_measurements"]["waist"]
    assert waist["value"] == 76.5
    assert waist["source"] == "designer"
    assert waist["note"] == "edited during AI"
    assert waist["review_status"] == "confirmed"
    # Sibling POMs still present.
    assert _find_shorts_piece(reopened["spec"])["finished_measurements"]["outseam"]["value"] == 42.0


def test_owner_adds_outseam_during_ai_run_survives(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "meas128c@example.com", "meas128c")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])

    # Clear outseam before generation so the mid-run add is meaningful.
    row = db_session.get(TechpackDraft, draft_id)
    assert row is not None
    spec0 = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
    piece0 = _find_shorts_piece(spec0)
    fm0 = dict(piece0.get("finished_measurements") or {})
    fm0["outseam"] = _designer_cell(None, definition="Outseam")
    piece0["finished_measurements"] = fm0
    for i, p in enumerate(spec0["outfit"]["pieces"]):
        if str(p.get("id")) == str(piece0.get("id")):
            spec0["outfit"]["pieces"][i] = piece0
    row.spec = spec0
    flag_modified(row, "spec")
    db_session.add(row)
    db_session.commit()

    ConcurrentEditProvider.provider_calls = 0

    def _add_outseam() -> None:
        live = db_session.get(TechpackDraft, draft_id)
        assert live is not None
        spec = copy.deepcopy(live.spec if isinstance(live.spec, dict) else {})
        piece = _find_shorts_piece(spec)
        fm = dict(piece.get("finished_measurements") or {})
        fm["outseam"] = _designer_cell(
            43.5,
            definition="Outseam",
            note="added during AI",
            review_status="confirmed",
        )
        piece["finished_measurements"] = fm
        for i, p in enumerate(spec["outfit"]["pieces"]):
            if str(p.get("id")) == str(piece.get("id")):
                spec["outfit"]["pieces"][i] = piece
        live.spec = spec
        flag_modified(live, "spec")
        live.updated_at = datetime.now(UTC)
        live.revision = int(live.revision or 1) + 1
        db_session.add(live)
        db_session.commit()

    set_professional_provider_override(ConcurrentEditProvider(_add_outseam))
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"meas-outseam-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1
    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    outseam = _find_shorts_piece(reopened["spec"])["finished_measurements"]["outseam"]
    assert outseam["value"] == 43.5
    assert outseam["source"] == "designer"
    assert outseam["note"] == "added during AI"


def test_stale_completion_does_not_overwrite_newer_pdf_only_pack(
    client, db_session, monkeypatch
):
    """If draft already owns a newer Professional/PDF pack, stale persist must not clobber it."""
    tokens = register_with_invite(client, db_session, "meas128d@example.com", "meas128d")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    ConcurrentEditProvider.provider_calls = 0

    def _install_newer_pack() -> None:
        live = db_session.get(TechpackDraft, draft_id)
        assert live is not None
        newer_run_id = uuid.uuid4()
        export_id = uuid.uuid4()
        export = TechpackExport(
            id=export_id,
            draft_id=draft_id,
            user_id=uuid.UUID(me["id"]),
            filename="newer_pdf_only.pdf",
            storage_key=(
                f"{me['id'].replace('-', '')}/{draft['id'].replace('-', '')}/newer.pdf"
            ),
            byte_size=40,
            page_count=1,
            revision=int(live.revision or 1) + 1,
            status="DRAFT",
            verification="UNVERIFIED",
            metadata_={
                "generation_mode": "pdf_only_update",
                "is_professional": True,
                "ai_run_id": str(newer_run_id),
            },
        )
        LocalStorageBackend().save_private_techpack_file(
            key=export.storage_key,
            data=io.BytesIO(b"%PDF-1.4 newer-pack"),
            content_type="application/pdf",
        )
        db_session.add(export)
        spec = copy.deepcopy(live.spec if isinstance(live.spec, dict) else {})
        ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
        ai.update(
            {
                "last_mode": "professional",
                "last_run_id": str(newer_run_id),
                "export_id": str(export_id),
                "dirty_since_generation": False,
            }
        )
        # Distinct measurement proving the newer pack's designer state.
        piece = _find_shorts_piece(spec)
        fm = dict(piece.get("finished_measurements") or {})
        fm["waist"] = _designer_cell(77.0, definition="Waist", note="pdf-only pack")
        piece["finished_measurements"] = fm
        for i, p in enumerate(spec["outfit"]["pieces"]):
            if str(p.get("id")) == str(piece.get("id")):
                spec["outfit"]["pieces"][i] = piece
        spec["ai"] = ai
        live.spec = spec
        flag_modified(live, "spec")
        live.revision = int(live.revision or 1) + 1
        live.updated_at = datetime.now(UTC)
        db_session.add(live)
        db_session.commit()

    set_professional_provider_override(ConcurrentEditProvider(_install_newer_pack))
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"meas-pdf-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    assert int(run_row.cost_usd_cents or 0) > 0  # paid usage retained
    result = run_row.result if isinstance(run_row.result, dict) else {}
    assert result.get("skipped_stale_spec_write") is True

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    waist = _find_shorts_piece(reopened["spec"])["finished_measurements"]["waist"]
    assert waist["value"] == 77.0
    assert waist["note"] == "pdf-only pack"
    ai = reopened["spec"]["ai"]
    assert ai.get("export_id") != run_id
    assert str(ai.get("last_run_id")) != run_id
