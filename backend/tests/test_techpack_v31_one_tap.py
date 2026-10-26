"""V3.1 one-tap Professional generate + compatibility helpers (mocked provider, $0 real spend)."""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from PIL import Image
from pypdf import PdfReader

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.services.techpack_ai import set_professional_provider_override
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_compatibility import (
    collect_compatibility_warnings,
    filter_construction_steps,
    filter_pattern_inventory,
    material_contradiction,
)
from app.services.techpack_flats import default_construction_steps, pattern_inventory_for_category
from app.services.techpack_pdf import build_techpack_pdf
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    img = Image.new("RGB", (256, 384), (120, 20, 40))
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

SLEEVELESS_ANALYSIS = {
    "schema_version": "techpack_analysis_v3",
    "category": "dress",
    "silhouette": "fitted slip",
    "length": "midi",
    "neckline": "cowl",
    "sleeves": "sleeveless spaghetti straps",
    "fit": "fitted",
    "fabric_pattern": "solid burgundy",
    "stripe_direction": "n/a",
    "colors": ["burgundy"],
    "construction_notes": ["Finish armholes cleanly", "Set sleeves and press"],
    "pattern_pieces_suggested": [
        {"id": "DR-NF", "name": "Neckline facing", "cut_qty": 1, "notes": "AI proposed"}
    ],
    "confidence": "high",
    "assumptions": [],
}


@pytest.fixture(autouse=True)
def _clear_provider():
    set_professional_provider_override(None)
    yield
    set_professional_provider_override(None)


def test_material_contradiction_silk_vs_cotton():
    msg = material_contradiction("silk", "100% cotton")
    assert msg is not None
    assert "inconsistent" in msg.lower()


def test_sleeve_construction_filtered_for_sleeveless():
    steps = default_construction_steps("dress")
    filtered = filter_construction_steps(
        steps, analysis={"sleeves": "sleeveless spaghetti straps"}
    )
    joined = " ".join(str(s) for s in filtered).lower()
    assert "do not set sleeves" in joined or "finish armholes for sleeveless" in joined


def test_pattern_inventory_marks_sleeve_unresolved():
    rows = filter_pattern_inventory(
        pattern_inventory_for_category("dress"),
        analysis={"sleeves": "sleeveless"},
        ai_suggested=[{"id": "X", "name": "Neckline facing"}],
    )
    sleeve = next(r for r in rows if "sleeve" in str(r.get("name") or "").lower())
    assert sleeve.get("cut_qty") is None
    assert sleeve.get("review_state") == "proposed_unverified"
    assert any("facing" in str(r.get("name") or "").lower() for r in rows)


def test_compatibility_warnings_preserve_owner_sleeve_value():
    spec = {
        "outfit": {
            "pieces": [
                {
                    "id": "p1",
                    "category": "dress",
                    "materials": {"shell": {"name": "silk", "composition": "100% cotton"}},
                    "finished_measurements": {
                        "sleeve_length": {"value": 60, "unit": "cm", "source": "designer"}
                    },
                    "illustrations": {"analysis": {"sleeves": "sleeveless spaghetti straps"}},
                }
            ]
        }
    }
    warns = collect_compatibility_warnings(spec)
    codes = {w["code"] for w in warns}
    assert "material_composition_mismatch" in codes
    assert "measurement_garment_mismatch" in codes
    assert spec["outfit"]["pieces"][0]["finished_measurements"]["sleeve_length"]["value"] == 60


def test_one_tap_professional_idempotent_and_progress(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "v31_tap@example.com", "v31_tap")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    monkeypatch.setenv("TECHPACK_AI_ENABLED", "true")
    monkeypatch.setenv("TECHPACK_AI_SPEND_CEILING_USD", "20")
    monkeypatch.setenv("TECHPACK_AI_MAX_USD_PER_RUN", "8")
    monkeypatch.setenv("TECHPACK_AI_OWNER_ALLOWLIST", me["email"])
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    get_settings.cache_clear()

    set_professional_provider_override(MockProfessionalProvider(analysis_override=SLEEVELESS_ANALYSIS))
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="burgundy sleeveless slip dress cowl neckline",
    )
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Burgundy slip V31"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    pieces = draft["spec"]["outfit"]["pieces"]
    pieces[0]["category"] = "dress"
    pieces[0]["label"] = "Burgundy slip"
    pieces[0]["materials"] = {"shell": {"name": "silk", "composition": "100% cotton"}}
    pieces[0]["finished_measurements"] = {
        **(pieces[0].get("finished_measurements") or {}),
        "sleeve_length": {"value": 60, "unit": "cm", "source": "designer"},
    }
    client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": 1, "pieces": pieces}}},
    )

    idem = f"idem-v31-{uuid.uuid4().hex}"
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": True},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["mode"] == "professional"
    assert body["status"] == "completed"
    assert body["idempotent_replay"] is False
    assert body["artifacts"]

    replay = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": idem, "propose_back": True},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["run_id"] == body["run_id"]

    latest = client.get(
        f"/api/v1/techpacks/{draft['id']}/ai/latest-run",
        headers=_auth(tokens),
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == body["run_id"]
    assert latest.json().get("progress", {}).get("phase") == "ready"

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    warns = refreshed["spec"].get("warnings") or []
    codes = {w.get("code") for w in warns if isinstance(w, dict)}
    assert "material_composition_mismatch" in codes or "measurement_garment_mismatch" in codes

    exported = client.post(f"/api/v1/techpacks/{draft['id']}/export", headers=_auth(tokens))
    assert exported.status_code == 201
    pdf = client.get(
        f"/api/v1/techpacks/exports/{exported.json()['id']}/pdf",
        headers=_auth(tokens),
    )
    assert pdf.status_code == 200
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Create Real Design V3.1" in text
    assert "Create Real Design V2" not in text
    assert "PROPOSED BACK" in text or "AI FLAT" in text
    get_settings.cache_clear()


def test_pdf_v31_branding_offline_fixture():
    spec = {
        "schema_version": "2.0",
        "units": "cm",
        "ai": {"last_mode": "professional", "last_run_id": str(uuid.uuid4())},
        "outfit": {
            "piece_count": 1,
            "pieces": [
                {
                    "id": "p1",
                    "category": "dress",
                    "role": "ONE_PIECE",
                    "label": "Slip dress",
                    "materials": {"shell": {"name": "silk", "composition": "100% cotton"}},
                    "finished_measurements": {
                        "sleeve_length": {"value": 60, "unit": "cm", "source": "designer"}
                    },
                    "illustrations": {
                        "mode": "professional",
                        "analysis": {"sleeves": "sleeveless", "neckline": "cowl"},
                        "artifacts": {},
                    },
                    "construction_steps": [
                        {"step": i + 1, "instruction": s, "source": "estimate"}
                        for i, s in enumerate(default_construction_steps("dress"))
                    ],
                }
            ],
        },
        "warnings": [],
    }
    pdf_bytes, pages = build_techpack_pdf(
        title="FR-TEST",
        style_code="FR-TEST",
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="look-test",
        front_image=None,
        back_image=None,
        spec=spec,
    )
    assert pages >= 1
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    assert "Create Real Design V3.1" in text
    assert "Create Real Design V2" not in text
    assert "REVIEW" in text or "inconsistent" in text.lower() or "silk" in text.lower()
