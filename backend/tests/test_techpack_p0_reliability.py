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
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_structure import (
    is_inconclusive_piece,
    list_outfit_pieces,
    plan_professional_image_kinds,
    prepare_professional_outfit,
    professional_input_fingerprint,
    run_matches_authorized_inputs,
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


def test_detect_fallback_is_inconclusive_not_validated():
    detection = detect_pieces_from_evidence(look_summary="an abstract fashion photo", units="cm")
    assert detection["detection_confidence"] == "heuristic_fallback"
    assert len(detection["pieces"]) == 1
    piece = detection["pieces"][0]
    assert piece["category"] == "other"
    assert is_inconclusive_piece(piece) is True


def test_prepare_rejects_empty_draft_without_credible_evidence(db_session, client):
    tokens = register_with_invite(client, db_session, "p0_empty@example.com", "p0_empty")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="soft lighting studio backdrop",
        design_identity={"main_colors": ["#aaa"]},
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Empty evidence"},
    )
    from app.models.techpack_draft import TechpackDraft

    draft = db_session.get(TechpackDraft, uuid.UUID(created.json()["id"]))
    assert draft
    spec = {
        "schema_version": "2.0",
        "look_notes": "soft lighting studio backdrop",
        "look_design_identity": {"main_colors": ["#aaa"]},
        "outfit": {"piece_count": 0, "pieces": []},
    }
    with pytest.raises(ValidationAppError) as ei:
        prepare_professional_outfit(db_session, draft, spec, persist_repair=False)
    msg = str(ei.value).lower()
    assert "confirm" in msg
    assert "categor" in msg


def test_prepare_rejects_generic_other_piece(db_session, client):
    tokens = register_with_invite(client, db_session, "p0_other@example.com", "p0_other")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="unclear silhouette",
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Other garment"},
    )
    from app.models.techpack_draft import TechpackDraft

    draft = db_session.get(TechpackDraft, uuid.UUID(created.json()["id"]))
    assert draft
    spec = {
        "schema_version": "2.0",
        "look_notes": "unclear silhouette",
        "outfit": {
            "piece_count": 1,
            "pieces": [
                {
                    "id": "piece-fallback",
                    "category": "other",
                    "label": "Garment (confirm category)",
                    "detection_source": "heuristic_fallback",
                }
            ],
        },
    }
    with pytest.raises(ValidationAppError) as ei:
        prepare_professional_outfit(db_session, draft, spec, persist_repair=False)
    assert "inconclusive" in str(ei.value).lower() or "confirm" in str(ei.value).lower()


def test_prepare_preserves_designer_confirmed_despite_weak_other_detector(db_session, client):
    tokens = register_with_invite(client, db_session, "p0_keep@example.com", "p0_keep")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    # Magic evidence is deliberately inconclusive (no garment words).
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="studio backdrop soft light",
        design_identity={"main_colors": ["#111"]},
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Designer locked top"},
    )
    from app.models.techpack_draft import TechpackDraft

    draft = db_session.get(TechpackDraft, uuid.UUID(created.json()["id"]))
    assert draft
    spec = {
        "schema_version": "2.0",
        "units": "cm",
        "look_notes": "studio backdrop soft light",
        "look_design_identity": {"main_colors": ["#111"]},
        "outfit": {
            "piece_count": 1,
            "pieces": [
                {
                    "id": "top-confirmed",
                    "category": "top",
                    "label": "Black tunic",
                    "role": "top",
                    "detection_source": "designer",
                    "category_user_confirmed": True,
                    "materials": {
                        "shell": {"name": "silk", "composition": "", "source": "designer"}
                    },
                    "finished_measurements": {
                        "garment_length": {"value": 70, "unit": "cm", "source": "designer"}
                    },
                }
            ],
        },
    }
    out_spec, pieces, meta = prepare_professional_outfit(
        db_session, draft, spec, persist_repair=False
    )
    assert len(pieces) == 1
    assert pieces[0]["id"] == "top-confirmed"
    assert pieces[0]["category"] == "top"
    assert meta["input_fingerprint"]
    assert meta["structure_fingerprint"]
    assert meta["input_fingerprint_version"] == 2
    # Fingerprint stable across harmless bookkeeping
    fp2 = professional_input_fingerprint(out_spec, pieces, draft=draft)
    assert fp2 == meta["input_fingerprint"]


def test_queued_run_rejects_measurement_drift_before_provider(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_drift@example.com", "p0_drift")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()

    class CountingMock(MockProfessionalProvider):
        provider_calls = 0

        def analyze_garment(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().analyze_garment(*args, **kwargs)

        def generate_technical_flat(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().generate_technical_flat(*args, **kwargs)

        def generate_detail_or_pattern(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().generate_detail_or_pattern(*args, **kwargs)

    CountingMock.provider_calls = 0
    set_professional_provider_override(CountingMock())

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
        json={"look_id": str(job.id), "title": "Drift test"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    # Confirm concrete pieces so authorize succeeds with stable IDs.
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "look_notes": TUNICS_TROUSERS_SUMMARY,
                "look_design_identity": TUNICS_IDENTITY,
                "outfit": {
                    "piece_count": 2,
                    "pieces": [
                        {
                            "id": "tunic-1",
                            "category": "top",
                            "label": "Black tunic",
                            "role": "top",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "materials": {
                                "shell": {
                                    "name": "silk",
                                    "composition": "100% silk",
                                    "source": "designer",
                                }
                            },
                            "finished_measurements": {
                                "garment_length": {
                                    "value": 72,
                                    "unit": "cm",
                                    "source": "designer",
                                }
                            },
                        },
                        {
                            "id": "tr-1",
                            "category": "trousers",
                            "label": "Cream trousers",
                            "role": "bottom",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "materials": {
                                "shell": {
                                    "name": "wool",
                                    "composition": "100% wool",
                                    "source": "designer",
                                }
                            },
                            "finished_measurements": {
                                "inseam": {"value": 78, "unit": "cm", "source": "designer"}
                            },
                        },
                    ],
                },
            }
        },
    )
    assert patched.status_code == 200, patched.text

    idem = f"idem-drift-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    assert run_row.status == "queued"
    req = run_row.request if isinstance(run_row.request, dict) else {}
    assert req.get("input_fingerprint")
    assert req.get("input_fingerprint_version") == 2
    assert req.get("structure_fingerprint")

    # Change a measurement while keeping the same piece IDs/categories.
    drift = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "outfit": {
                    "piece_count": 2,
                    "pieces": [
                        {
                            "id": "tunic-1",
                            "category": "top",
                            "label": "Black tunic",
                            "role": "top",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "materials": {
                                "shell": {
                                    "name": "silk",
                                    "composition": "100% silk",
                                    "source": "designer",
                                }
                            },
                            "finished_measurements": {
                                "garment_length": {
                                    "value": 99,
                                    "unit": "cm",
                                    "source": "designer",
                                }
                            },
                        },
                        {
                            "id": "tr-1",
                            "category": "trousers",
                            "label": "Cream trousers",
                            "role": "bottom",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "materials": {
                                "shell": {
                                    "name": "cotton",
                                    "composition": "100% cotton",
                                    "source": "designer",
                                }
                            },
                            "finished_measurements": {
                                "inseam": {"value": 78, "unit": "cm", "source": "designer"}
                            },
                        },
                    ],
                }
            }
        },
    )
    assert drift.status_code == 200, drift.text

    ticks = run_techpack_worker_tick(db_session, limit=2)
    assert ticks == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{run_id}",
        headers=_auth(tokens),
    ).json()
    assert settled["status"] == "failed"
    assert int(settled.get("actual_cost_usd_cents") or settled.get("cost_usd_cents") or 0) == 0
    err = (settled.get("error_message") or "").lower()
    assert "changed" in err or "generate again" in err
    assert CountingMock.provider_calls == 0


def test_queued_run_unchanged_inputs_complete_with_mock(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_stable@example.com", "p0_stable")
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
        image_url=_store_image((30, 30, 120)),
        summary=TUNICS_TROUSERS_SUMMARY,
        design_identity=TUNICS_IDENTITY,
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Stable inputs"},
    )
    draft = created.json()
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "look_notes": TUNICS_TROUSERS_SUMMARY,
                "look_design_identity": TUNICS_IDENTITY,
                "outfit": {
                    "piece_count": 2,
                    "pieces": [
                        {
                            "id": "tunic-1",
                            "category": "top",
                            "label": "Black tunic",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                        },
                        {
                            "id": "tr-1",
                            "category": "trousers",
                            "label": "Cream trousers",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                        },
                    ],
                },
            }
        },
    )
    idem = f"idem-stable-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_row = db_session.get(TechpackAIRun, uuid.UUID(gen.json()["run_id"]))
    assert run_row is not None
    req = run_row.request if isinstance(run_row.request, dict) else {}
    assert req.get("input_fingerprint")
    assert req.get("input_fingerprint_version") == 2
    # Harmless server bookkeeping alone must not drift the fingerprint.
    from app.models.techpack_draft import TechpackDraft

    draft_row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert draft_row
    spec = dict(draft_row.spec or {})
    ai = dict(spec.get("ai") or {})
    ai["touch_marker"] = "bookkeeping-only"
    spec["ai"] = ai
    draft_row.spec = spec
    db_session.add(draft_row)
    db_session.commit()
    db_session.refresh(draft_row)
    pieces = (spec.get("outfit") or {}).get("pieces") or []
    assert (
        run_matches_authorized_inputs(req, spec=spec, pieces=pieces, draft=draft_row)
        is True
    )

    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{gen.json()['run_id']}",
        headers=_auth(tokens),
    ).json()
    assert settled["status"] == "completed"
    assert settled.get("pdf_ready") is True


def _enable_professional(monkeypatch, email: str) -> None:
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", email)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()


def _counting_mock() -> type:
    class CountingMock(MockProfessionalProvider):
        provider_calls = 0

        def analyze_garment(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().analyze_garment(*args, **kwargs)

        def generate_technical_flat(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().generate_technical_flat(*args, **kwargs)

        def generate_detail_or_pattern(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).provider_calls += 1
            return super().generate_detail_or_pattern(*args, **kwargs)

    CountingMock.provider_calls = 0
    return CountingMock


def _seed_two_piece_draft(client, db_session, tokens, me, *, title: str) -> dict[str, Any]:
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
        json={"look_id": str(job.id), "title": title},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "look_notes": TUNICS_TROUSERS_SUMMARY,
                "look_design_identity": TUNICS_IDENTITY,
                "size_system": "EU",
                "sample_size": "M",
                "body": {
                    "waist": {"value": 70, "unit": "cm", "source": "designer"},
                    "bust": {"value": 88, "unit": "cm", "source": "designer"},
                    "hip": {"value": 94, "unit": "cm", "source": "designer"},
                },
                "preferences": {"fit_preference": "regular", "notes": ""},
                "outfit": {
                    "piece_count": 2,
                    "pieces": [
                        {
                            "id": "tunic-1",
                            "category": "top",
                            "label": "Black tunic",
                            "role": "top",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "finished_measurements": {
                                "garment_length": {
                                    "value": 72,
                                    "unit": "cm",
                                    "source": "designer",
                                }
                            },
                        },
                        {
                            "id": "tr-1",
                            "category": "trousers",
                            "label": "Cream trousers",
                            "role": "bottom",
                            "detection_source": "designer",
                            "category_user_confirmed": True,
                            "finished_measurements": {
                                "inseam": {"value": 78, "unit": "cm", "source": "designer"}
                            },
                        },
                    ],
                },
            }
        },
    )
    assert patched.status_code == 200, patched.text
    return patched.json()


def test_queued_run_rejects_shared_body_waist_drift(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_body@example.com", "p0_body")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(
        client, db_session, tokens, me, title="Body waist drift"
    )
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-body-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    # Change shared body waist only — garment IDs / finished POMs unchanged.
    drift = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"body": {"waist": {"value": 75, "unit": "cm", "source": "designer"}}}},
    )
    assert drift.status_code == 200, drift.text
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)
    ).json()
    assert settled["status"] == "failed"
    assert int(settled.get("actual_cost_usd_cents") or settled.get("cost_usd_cents") or 0) == 0
    assert CountingMock.provider_calls == 0
    assert "generate again" in (settled.get("error_message") or "").lower()


def test_queued_run_rejects_fit_preference_drift(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_fit@example.com", "p0_fit")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Fit drift")
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-fit-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    drift = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"preferences": {"fit_preference": "relaxed", "notes": ""}}},
    )
    assert drift.status_code == 200, drift.text
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)
    ).json()
    assert settled["status"] == "failed"
    assert CountingMock.provider_calls == 0
    assert int(settled.get("cost_usd_cents") or 0) == 0


def test_queued_run_rejects_sample_size_drift(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "p0_size@example.com", "p0_size")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Sample size drift")
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-size-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    drift = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"sample_size": "L"}},
    )
    assert drift.status_code == 200, drift.text
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)
    ).json()
    assert settled["status"] == "failed"
    assert CountingMock.provider_calls == 0
    assert int(settled.get("cost_usd_cents") or 0) == 0


def test_v1_fingerprint_algorithm_unchanged_and_stale_queue_rejected(
    client, db_session, monkeypatch
):
    """v1 hash meaning stays frozen; queued v1 runs cannot start a paid call."""
    tokens = register_with_invite(client, db_session, "p0_v1@example.com", "p0_v1")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    CountingMock = _counting_mock()
    set_professional_provider_override(CountingMock())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="V1 stale")
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-v1-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    from app.models.techpack_draft import TechpackDraft

    draft_row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
    assert draft_row
    pieces = list_outfit_pieces(draft_row.spec if isinstance(draft_row.spec, dict) else {})
    # Prove v1 algorithm remains deterministic for historical hashes.
    v1_a = professional_input_fingerprint(
        draft_row.spec, pieces, version=1, draft=draft_row
    )
    v1_b = professional_input_fingerprint(
        draft_row.spec, pieces, version=1, draft=draft_row
    )
    assert v1_a == v1_b
    v2 = professional_input_fingerprint(
        draft_row.spec, pieces, version=2, draft=draft_row
    )
    assert v1_a != v2

    # Downgrade the queued stamp to v1 → worker must fail closed ($0).
    req = dict(run_row.request or {})
    req["input_fingerprint"] = v1_a
    req["input_fingerprint_version"] = 1
    run_row.request = req
    db_session.add(run_row)
    db_session.commit()

    assert run_techpack_worker_tick(db_session, limit=2) == 1
    settled = client.get(
        f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)
    ).json()
    assert settled["status"] == "failed"
    assert CountingMock.provider_calls == 0
    assert int(settled.get("cost_usd_cents") or 0) == 0
    err = (settled.get("error_message") or "").lower()
    assert "older input snapshot" in err or "generate again" in err


def test_completed_historical_run_accessible_without_paid_retry(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "p0_hist@example.com", "p0_hist")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_professional(monkeypatch, me["email"])
    set_professional_provider_override(MockProfessionalProvider())
    draft = _seed_two_piece_draft(client, db_session, tokens, me, title="Historical")
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"idem-hist-{uuid.uuid4().hex}", "propose_back": False},
    )
    assert gen.status_code == 202, gen.text
    assert run_techpack_worker_tick(db_session, limit=2) == 1
    done = client.get(
        f"/api/v1/techpacks/ai/runs/{gen.json()['run_id']}", headers=_auth(tokens)
    ).json()
    assert done["status"] == "completed"
    assert done.get("pdf_ready") is True
    export_id = done.get("export_id")
    assert export_id

    from app.models.user import User

    user = db_session.get(User, uuid.UUID(me["id"]))
    run_row = db_session.get(TechpackAIRun, uuid.UUID(done["run_id"]))
    assert user and run_row
    # Recovery / accessibility must not start another paid provider call.
    class Guard(MockProfessionalProvider):
        def analyze_garment(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("paid provider must not run for historical recovery")

    set_professional_provider_override(Guard())
    recovered = ensure_professional_pdf_for_run(db_session, user, run_row)
    assert recovered.status == "completed"
    again = client.get(
        f"/api/v1/techpacks/ai/runs/{done['run_id']}", headers=_auth(tokens)
    ).json()
    assert again["status"] == "completed"
    assert again.get("pdf_ready") is True
    assert again.get("export_id") == export_id
