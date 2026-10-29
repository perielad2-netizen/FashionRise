"""AI auto-fill technical specs — mocked $0 regression (black shirt + beige trousers)."""

from __future__ import annotations

import base64
import io
import tempfile
import uuid
from pathlib import Path

from pypdf import PdfReader

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.techpack_draft import TechpackDraft
from app.services.techpack_ai import enrich_spec_heuristic, set_professional_provider_override
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import run_techpack_worker_tick
from app.services.techpack_autofill import (
    apply_visible_analysis_to_piece,
    outfit_needs_structure_repair,
    repair_outfit_from_evidence,
)
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_spec import default_spec
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _store_image() -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")


def _add_job(
    db_session,
    *,
    user_id: uuid.UUID,
    image_url: str,
    summary: str,
    design_identity: dict | None = None,
) -> AIJob:
    result = {"summary": summary, "pipeline": "sketch_polish", "image_url": image_url}
    if design_identity:
        result["design_identity"] = design_identity
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"notes": "polish", "studio_side": "front"},
        result_data=result,
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


SHIRT_TROUSERS_SUMMARY = (
    "black shirt with V-slit neckline and three-quarter sleeves paired with light beige trousers"
)

SHIRT_TROUSERS_IDENTITY = {
    "garment_category": "shirt and trousers set",
    "neckline": "V-slit neckline",
    "sleeve_style": "three-quarter sleeves",
    "main_colors": "black and beige",
    "components": [
        {"category": "shirt", "color": "black", "label": "Black shirt"},
        {"category": "trousers", "color": "beige", "label": "Beige trousers"},
    ],
}


def test_detect_two_piece_not_dress():
    detection = detect_pieces_from_evidence(look_summary=SHIRT_TROUSERS_SUMMARY)
    assert detection["piece_count"] == 2
    cats = {p["category"] for p in detection["pieces"]}
    assert cats == {"shirt", "trousers"}
    assert "dress" not in cats


def test_stale_dress_repaired_from_look_evidence():
    stale = default_spec(look_summary="cream dress look")
    assert stale["outfit"]["piece_count"] == 1
    assert stale["outfit"]["pieces"][0]["category"] == "dress"
    assert outfit_needs_structure_repair(
        stale["outfit"],
        look_summary=SHIRT_TROUSERS_SUMMARY,
        design_identity=SHIRT_TROUSERS_IDENTITY,
    )
    repaired = repair_outfit_from_evidence(
        stale,
        look_summary=SHIRT_TROUSERS_SUMMARY,
        design_identity=SHIRT_TROUSERS_IDENTITY,
    )
    cats = [p["category"] for p in repaired["outfit"]["pieces"]]
    assert sorted(cats) == ["shirt", "trousers"]
    shirt = next(p for p in repaired["outfit"]["pieces"] if p["category"] == "shirt")
    assert "V-slit" in str(shirt.get("visible_details", {}).get("neckline") or "")
    assert "three-quarter" in str(shirt.get("visible_details", {}).get("sleeves") or "").lower()
    trousers = next(p for p in repaired["outfit"]["pieces"] if p["category"] == "trousers")
    assert not (trousers.get("visible_details") or {}).get("neckline")


def test_enrich_does_not_fabricate_empty_body_measurements():
    spec = enrich_spec_heuristic(default_spec(look_summary=SHIRT_TROUSERS_SUMMARY))
    shirt = next(p for p in spec["outfit"]["pieces"] if p["category"] == "shirt")
    sleeve = shirt["finished_measurements"]["sleeve_length"]
    assert sleeve.get("value") in (None, "")
    assert sleeve.get("source") in ("unknown", "empty")
    trousers = next(p for p in spec["outfit"]["pieces"] if p["category"] == "trousers")
    inseam = trousers["finished_measurements"]["inseam"]
    assert inseam.get("value") in (None, "")


def test_conflict_flagged_when_user_confirmed_category_differs():
    piece = {
        "id": "p1",
        "category": "dress",
        "category_user_confirmed": True,
        "detection_source": "designer",
        "label": "My dress",
        "fit": {},
        "materials": {},
        "closures": {},
        "finished_measurements": {},
    }
    filled = apply_visible_analysis_to_piece(
        piece,
        {"category": "shirt", "neckline": "V-slit", "sleeves": "three-quarter sleeves"},
        only_empty=True,
    )
    assert filled["category"] == "dress"
    assert filled.get("ai_conflicts")
    assert filled["ai_conflicts"][0]["field"] == "category"


def test_create_draft_seeds_two_piece_and_professional_pdf(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "autofill@example.com", "autofill")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "15")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_USER_DAY", "20")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()

    set_professional_provider_override(MockProfessionalProvider())
    try:
        url = _store_image()
        job = _add_job(
            db_session,
            user_id=uuid.UUID(me["id"]),
            image_url=url,
            summary=SHIRT_TROUSERS_SUMMARY,
            design_identity=SHIRT_TROUSERS_IDENTITY,
        )
        created = client.post(
            "/api/v1/techpacks",
            headers=_auth(tokens),
            json={"look_id": str(job.id), "title": "Black shirt set"},
        )
        assert created.status_code == 201, created.text
        draft = created.json()
        pieces = draft["spec"]["outfit"]["pieces"]
        assert draft["spec"]["outfit"]["piece_count"] == 2
        cats = {p["category"] for p in pieces}
        assert cats == {"shirt", "trousers"}
        assert "dress" not in cats
        shirt = next(p for p in pieces if p["category"] == "shirt")
        assert "V-slit" in str((shirt.get("visible_details") or {}).get("neckline") or "")
        assert "three-quarter" in str((shirt.get("visible_details") or {}).get("sleeves") or "").lower()

        # Stale dress draft is repaired on GET without paid AI.
        row = db_session.get(TechpackDraft, uuid.UUID(draft["id"]))
        assert row is not None
        row.spec = default_spec(look_summary="migrated cream dress")
        db_session.add(row)
        db_session.commit()
        refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens))
        assert refreshed.status_code == 200
        repaired_pieces = refreshed.json()["spec"]["outfit"]["pieces"]
        assert {p["category"] for p in repaired_pieces} == {"shirt", "trousers"}

        idem = f"autofill-{uuid.uuid4().hex}"
        gen = client.post(
            f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
            headers=_auth(tokens),
            json={"idempotency_key": idem, "propose_back": False},
        )
        assert gen.status_code == 202, gen.text
        assert gen.json()["mode"] == "professional"
        assert run_techpack_worker_tick(db_session, limit=2) == 1
        settled = client.get(
            f"/api/v1/techpacks/ai/runs/{gen.json()['run_id']}",
            headers=_auth(tokens),
        )
        assert settled.status_code == 200
        assert settled.json()["status"] == "completed"
        assert int(settled.json().get("cost_usd_cents") or 0) > 0  # mock cents only

        final = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
        final_pieces = final["spec"]["outfit"]["pieces"]
        assert {p["category"] for p in final_pieces} == {"shirt", "trousers"}
        shirt = next(p for p in final_pieces if p["category"] == "shirt")
        trousers = next(p for p in final_pieces if p["category"] == "trousers")
        analysis = (shirt.get("illustrations") or {}).get("analysis") or {}
        neck = str(
            analysis.get("neckline") or (shirt.get("visible_details") or {}).get("neckline") or ""
        )
        sleeves = str(
            analysis.get("sleeves") or (shirt.get("visible_details") or {}).get("sleeves") or ""
        )
        assert "V-slit" in neck
        assert "three-quarter" in sleeves.lower()
        t_analysis = (trousers.get("illustrations") or {}).get("analysis") or {}
        assert str(t_analysis.get("category") or trousers.get("category")) == "trousers"
        ga = final["spec"].get("garment_analysis") or {}
        assert ga.get("schema_version") == "garment_analysis_v1"
        assert len(ga.get("pieces") or []) == 2
        for pom in ("sleeve_length", "garment_length"):
            cell = (shirt.get("finished_measurements") or {}).get(pom) or {}
            assert cell.get("value") in (None, "")
        inseam = (trousers.get("finished_measurements") or {}).get("inseam") or {}
        assert inseam.get("value") in (None, "")

        with tempfile.TemporaryDirectory() as tmp:
            front = Path(tmp) / "front.png"
            front.write_bytes(_png_bytes())
            pdf_bytes, pages = build_techpack_pdf(
                title=final["title"],
                style_code=final["style_code"],
                revision=final["revision"],
                verification=final["verification"],
                status=final["status"],
                look_id=final["look_id"],
                front_image=front,
                back_image=None,
                spec=final["spec"],
            )
            reader = PdfReader(io.BytesIO(pdf_bytes))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            assert "shirt" in text.lower()
            assert "trouser" in text.lower()
            # Outfit must not be titled as a dress.
            assert "FRONT — DRESS" not in text.upper()
            assert "BACK — DRESS" not in text.upper()
            assert "DRAFT" in text.upper()
            assert "UNVERIFIED" in text.upper()
            assert pages >= 2
    finally:
        set_professional_provider_override(None)
        get_settings.cache_clear()
