"""P0/P1 Professional reliability — offline fixtures + MockProfessionalProvider ($0)."""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from PIL import Image
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.errors import ValidationAppError
from app.models.ai_job import AIJob
from app.models.techpack_ai_run import TechpackAIRun
from app.services.techpack_ai import (
    _persist_professional_result,
    ensure_professional_pdf_for_run,
    set_professional_provider_override,
)
from app.services.techpack_ai_professional import (
    MockProfessionalProvider,
    run_professional_pipeline,
)
from app.services.techpack_ai_worker import run_techpack_worker_tick
from app.services.techpack_compatibility import filter_pattern_inventory
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_structure import (
    plan_professional_image_kinds,
    prepare_professional_outfit,
    validate_professional_pieces,
)
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(color: tuple[int, int, int] = (20, 20, 20)) -> bytes:
    img = Image.new("RGB", (256, 384), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store_image(color: tuple[int, int, int] = (20, 20, 20)) -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(
        key=key, data=io.BytesIO(_png_bytes(color)), content_type="image/png"
    )


def _add_job(
    db_session,
    *,
    user_id: uuid.UUID,
    image_url: str,
    summary: str,
    design_identity: dict[str, Any] | None = None,
) -> AIJob:
    result: dict[str, Any] = {
        "summary": summary,
        "pipeline": "sketch_polish",
        "image_url": image_url,
    }
    if design_identity:
        result["design_identity"] = design_identity
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"studio_side": "front"},
        result_data=result,
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


TUNICS_TROUSERS_SUMMARY = (
    "A crisp black V-slit tunic brings graphic simplicity with cream trousers."
)
TUNICS_IDENTITY = {
    "garment_category": "Long-sleeved tunic top with trousers",
    "neckline": "Shallow V-neck with a narrow, pointed center opening",
    "sleeve_type": "Set-in sleeves",
    "sleeve_length": "Three-quarter length",
    "silhouette": "Relaxed tunic with slim straight trousers",
    "main_colors": ["#111111", "#F5F0E6"],
    "hemline": "Straight tunic hem; full-length trouser hems",
}


@pytest.fixture(autouse=True)
def _clear_provider():
    set_professional_provider_override(None)
    yield
    set_professional_provider_override(None)


def test_validate_rejects_empty_and_duplicate_ids():
    with pytest.raises(ValidationAppError):
        validate_professional_pieces([])
    with pytest.raises(ValidationAppError):
        validate_professional_pieces(
            [
                {"id": "a", "category": "top"},
                {"id": "a", "category": "trousers"},
            ]
        )


def test_image_budget_requires_front_for_each_garment_first():
    pieces = [
        {"id": "top-1", "category": "top", "label": "Top"},
        {"id": "tr-1", "category": "trousers", "label": "Trousers"},
    ]
    plan = plan_professional_image_kinds(
        pieces, propose_back=True, has_back_image=False, max_images=6
    )
    assert plan["required_images"] == 2
    assert "flat_front" in plan["per_piece"]["top-1"]["required"]
    assert "flat_front" in plan["per_piece"]["tr-1"]["required"]
    # Fair optional: both should get proposed backs before second details monopolize budget
    assert "flat_back_proposed" in plan["per_piece"]["top-1"]["all"]
    assert "flat_back_proposed" in plan["per_piece"]["tr-1"]["all"]
    with pytest.raises(ValidationAppError):
        plan_professional_image_kinds(
            pieces, propose_back=True, has_back_image=False, max_images=1
        )


def test_pipeline_fair_budget_two_piece(monkeypatch):
    pieces = [
        {"id": "top-1", "category": "top", "label": "Black tunic"},
        {"id": "tr-1", "category": "trousers", "label": "Cream trousers"},
    ]
    plan = plan_professional_image_kinds(
        pieces, propose_back=True, has_back_image=False, max_images=4
    )
    # 2 fronts + 2 proposed backs; details/patterns skipped
    provider = MockProfessionalProvider()
    result = run_professional_pipeline(
        provider=provider,
        pieces=pieces,
        front_image=(_png_bytes(), "image/png"),
        back_image=None,
        look_notes=TUNICS_TROUSERS_SUMMARY,
        propose_back=True,
        max_images=4,
        image_plan=plan,
    )
    assert len(result["piece_results"]) == 2
    for pr in result["piece_results"]:
        kinds = {a["kind"] for a in pr["artifacts"]}
        assert "flat_front" in kinds
    # Optional skipped honestly
    assert any("budget_optional_skipped" in str(x) for x in result["failed_sections"])


def test_persist_rejects_unknown_piece_id(db_session, client):
    tokens = register_with_invite(client, db_session, "p0_mismatch@example.com", "p0_mis")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Two piece"},
    )
    assert created.status_code == 201, created.text
    draft_id = uuid.UUID(created.json()["id"])
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User

    user = db_session.get(User, uuid.UUID(me["id"]))
    draft = db_session.get(TechpackDraft, draft_id)
    assert user and draft
    run = TechpackAIRun(
        id=uuid.uuid4(),
        draft_id=draft.id,
        user_id=user.id,
        stage="professional",
        status="running",
        confirm_token="confirm-token-xx",
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        request={"mode": "professional"},
    )
    db_session.add(run)
    db_session.commit()

    pipeline = {
        "piece_results": [
            {
                "piece_id": "totally-unknown",
                "analysis": {"silhouette": "x", "sleeves": "long"},
                "artifacts": [{"kind": "flat_front", "bytes": _png_bytes(), "mime": "image/png"}],
            }
        ],
        "usage": {"cost_usd_cents": 10},
        "analysis_summary": "bad",
        "failed_sections": [],
    }
    with pytest.raises(ValidationAppError):
        _persist_professional_result(
            db_session,
            user=user,
            draft=draft,
            run=run,
            pipeline=pipeline,
            base_spec=draft.spec if isinstance(draft.spec, dict) else {},
        )


def test_two_piece_one_tap_preserves_both_garments(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_two@example.com", "p0_two")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    monkeypatch.setenv("TECHPACK_AI_MAX_IMAGES_PER_RUN", "8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()

    set_professional_provider_override(MockProfessionalProvider())
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Tunic trousers"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    # Intentionally wrong one-piece dress — Magic evidence should repair before paid call.
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "look_notes": TUNICS_TROUSERS_SUMMARY,
                "look_design_identity": TUNICS_IDENTITY,
                "outfit": {
                    "piece_count": 1,
                    "pieces": [
                        {
                            "id": "stale-dress",
                            "category": "dress",
                            "label": "Dress",
                            "role": "one_piece",
                            "detection_source": "heuristic",
                        }
                    ],
                },
            }
        },
    )

    idem = f"idem-two-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": True},
    )
    assert gen.status_code == 202, gen.text
    body = gen.json()
    assert body["status"] == "queued"
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{body['run_id']}",
        headers=_auth(tokens),
    )
    assert settled.status_code == 200
    settled_body = settled.json()
    assert settled_body["status"] == "completed"
    assert settled_body.get("pdf_ready") is True

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    pieces = refreshed["spec"]["outfit"]["pieces"]
    assert refreshed["spec"]["outfit"]["piece_count"] == 2
    assert len(pieces) == 2
    cats = sorted(str(p.get("category")) for p in pieces)
    assert cats == ["shirt", "trousers"] or "trousers" in cats
    # Each piece has its own professional flat_front artifact binding
    for p in pieces:
        arts = ((p.get("illustrations") or {}).get("artifacts") or {})
        assert "flat_front" in arts, p.get("id")
        assert arts["flat_front"].get("artifact_id")


def test_structure_repair_marks_historical_pdf_dirty(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_dirty@example.com", "p0_dirty")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()
    set_professional_provider_override(MockProfessionalProvider())

    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image((200, 40, 80)),
        summary="hot-pink mini dress diagonal stripes plunging neckline",
        design_identity={"garment_category": "Long-sleeved mini dress", "main_colors": ["pink"]},
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Pink dress then repair"},
    )
    draft = created.json()
    idem = f"idem-dirty-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    done = client.get(
        f"/api/v1/techpacks/ai/runs/{gen.json()['run_id']}", headers=_auth(tokens)
    ).json()
    assert done["status"] == "completed"
    export_id = done.get("export_id") or (done.get("result") or {}).get("export_id")

    # Simulate post-hoc Magic evidence of separates + stale one-piece PDF lineage.
    from app.models.techpack_draft import TechpackDraft
    from app.models.user import User

    user = db_session.get(User, uuid.UUID(me["id"]))
    row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert user and row
    spec = dict(row.spec or {})
    spec["look_notes"] = TUNICS_TROUSERS_SUMMARY
    spec["look_design_identity"] = TUNICS_IDENTITY
    # Force stale dress structure matching old PDF
    spec["outfit"] = {
        "piece_count": 1,
        "pieces": [
            {
                "id": "stale-dress",
                "category": "dress",
                "label": "Dress",
                "role": "one_piece",
                "detection_source": "heuristic",
                "illustrations": {"mode": "professional", "artifacts": {"flat_front": {}}},
            }
        ],
    }
    ai = dict(spec.get("ai") or {})
    ai.update(
        {
            "last_mode": "professional",
            "last_run_id": done["run_id"],
            "export_id": export_id,
            "dirty_since_generation": False,
        }
    )
    spec["ai"] = ai
    row.spec = spec
    db_session.add(row)
    db_session.commit()

    # GET draft triggers repair → dirty_since_generation
    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert refreshed["spec"]["outfit"]["piece_count"] >= 2
    assert refreshed["spec"]["ai"].get("dirty_since_generation") is True
    # Historical export id preserved for history
    assert refreshed["spec"]["ai"].get("export_id") or refreshed["spec"]["ai"].get(
        "outdated_export_id"
    )

    # Recovery must not clear dirty / revalidate obsolete pack
    run_row = db_session.get(TechpackAIRun, uuid.UUID(done["run_id"]))
    assert run_row is not None
    ensure_professional_pdf_for_run(db_session, user, run_row)
    again = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert again["spec"]["ai"].get("dirty_since_generation") is True

    # Idempotent GET without further structure change does not bump revision
    rev = again["revision"]
    again2 = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert again2["revision"] == rev


def test_pattern_review_default_proposed_unverified():
    rows = filter_pattern_inventory(
        [
            {"id": "F1", "name": "Front", "source": "ai", "cut_qty": 1},
            {
                "id": "T1",
                "name": "Template sleeve",
                "source": "template",
                "cut_qty": 2,
                "review_state": "approved_template",
            },
        ],
        analysis={"sleeves": "long sleeves"},
    )
    ai_row = next(r for r in rows if r["id"] == "F1")
    assert ai_row["review_state"] == "proposed_unverified"
    tmpl = next(r for r in rows if r["id"] == "T1")
    assert tmpl["review_state"] == "approved_template"


def test_pdf_material_and_sleeveless_review_offline():
    piece = {
        "id": "p1",
        "category": "dress",
        "label": "Slip",
        "role": "one_piece",
        "materials": {"shell": {"name": "silk", "composition": "100% cotton", "source": "designer"}},
        "finished_measurements": {
            "sleeve_length": {"value": 60, "unit": "cm", "source": "designer"},
            "chest_bust": {"value": 90, "unit": "cm", "source": "designer"},
        },
        "illustrations": {
            "mode": "basic",
            "analysis": {"sleeves": "sleeveless spaghetti straps", "silhouette": "slip"},
        },
        "pattern_pieces": [
            {"id": "F1", "name": "Front", "source": "ai", "cut_qty": 1},
        ],
        "construction_steps": [{"step": 1, "instruction": "Set sleeves and press.", "source": "estimate"}],
    }
    pdf, _pages = build_techpack_pdf(
        title="Slip",
        style_code="FR-TEST",
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="look",
        front_image=None,
        back_image=None,
        spec={
            "schema_version": "2.0",
            "units": "cm",
            "outfit": {"piece_count": 1, "pieces": [piece]},
            "body": {},
            "disclaimer": "DRAFT / UNVERIFIED. NOT TO SCALE.",
        },
    )
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert "REVIEW" in text
    assert "silk" in text.lower()
    assert "cotton" in text.lower()
    assert "DRAFT" in text.upper() or "UNVERIFIED" in text.upper()
    assert "NOT TO SCALE" in text.upper()
    assert "sleeve length" in text.lower()
    # Construction should not instruct setting sleeves for sleeveless
    assert "do not set sleeves" in text.lower() or "finish armholes" in text.lower()
    assert "proposed_unverified" in text.lower() or "proposed" in text.lower()


def test_prepare_blocks_designer_conflict(db_session, client):
    tokens = register_with_invite(client, db_session, "p0_lock@example.com", "p0_lock")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Locked"},
    )
    from app.models.techpack_draft import TechpackDraft

    draft = db_session.get(TechpackDraft, uuid.UUID(created.json()["id"]))
    assert draft
    spec = {
        "schema_version": "2.0",
        "look_notes": TUNICS_TROUSERS_SUMMARY,
        "look_design_identity": TUNICS_IDENTITY,
        "outfit": {
            "piece_count": 1,
            "pieces": [
                {
                    "id": "only-dress",
                    "category": "dress",
                    "label": "My dress",
                    "detection_source": "designer",
                    "category_user_confirmed": True,
                }
            ],
        },
    }
    with pytest.raises(ValidationAppError) as ei:
        prepare_professional_outfit(db_session, draft, spec, persist_repair=False)
    assert "conflict" in str(ei.value).lower() or "confirm" in str(ei.value).lower()
