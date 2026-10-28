"""Manufacturing-ready tech pack foundation — offline fixtures ($0, no provider)."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from pypdf import PdfReader

from app.services.techpack_manufacturing import (
    READINESS_DESIGN_CONCEPT,
    READINESS_SAMPLE_DEVELOPMENT,
    assess_manufacturing_readiness,
    enrich_spec_for_manufacturing_preview,
    evaluate_artifact_for_piece,
    normalize_closure_display,
    normalize_shell_material,
    validate_piece_measurements,
    validate_sample_size,
)
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_spec import default_spec

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FR3958 = FIXTURES / "fr_3958_manufacturing_spec.json"


def _tiny_png(path: Path) -> None:
    import base64

    path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSjAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
    )


def _load_fr3958() -> dict:
    return json.loads(FR3958.read_text())


def test_fr3958_sample_size_missing_and_pom_contradictions():
    spec = _load_fr3958()
    issues = validate_sample_size(spec)
    assert any(i["code"] == "sample_size_missing" for i in issues)

    body = spec["body"]
    prefs = spec.get("preferences") or {}
    all_issues = []
    for piece in spec["outfit"]["pieces"]:
        all_issues.extend(validate_piece_measurements(piece, body=body, preferences=prefs))

    codes = {i["code"] for i in all_issues}
    assert "shorts_inseam_vs_silhouette" in codes or "pom_outside_category_band" in codes
    assert "length_vs_visual_silhouette" in codes or "pom_outside_category_band" in codes
    assert "finished_waist_smaller_than_body" in codes
    assert "zero_ease_hip_with_relaxed_fit" in codes
    assert "zero_ease_chest_with_relaxed_fit" in codes

    # Designer values must remain intact (no silent correction).
    shorts = next(p for p in spec["outfit"]["pieces"] if p["category"] == "shorts")
    assert shorts["finished_measurements"]["inseam"]["value"] == 80
    top = next(p for p in spec["outfit"]["pieces"] if p["category"] == "top")
    assert top["finished_measurements"]["garment_length"]["value"] == 110


def test_body_and_finished_remain_separate_entities():
    spec = _load_fr3958()
    assert "bust" in spec["body"] and "waist" in spec["body"]
    top = next(p for p in spec["outfit"]["pieces"] if p["category"] == "top")
    assert "chest_bust" in top["finished_measurements"]
    assert "bust" not in top["finished_measurements"]
    shorts = next(p for p in spec["outfit"]["pieces"] if p["category"] == "shorts")
    assert "waist" in shorts["finished_measurements"]
    # Body waist stays on outfit body, not overwritten by finished waist.
    assert spec["body"]["waist"]["value"] == 90
    assert shorts["finished_measurements"]["waist"]["value"] == 75


def test_material_and_closure_normalization():
    spec = _load_fr3958()
    top = next(p for p in spec["outfit"]["pieces"] if p["category"] == "top")
    norm = normalize_shell_material(top)
    shell = norm["materials"]["shell"]
    assert shell.get("review_status") == "needs_review" or not shell.get("name")
    assert "colorway_note" in shell or "fabric" in str(shell.get("colorway_note") or "").lower() or shell.get("name") == ""
    closures = normalize_closure_display(top.get("closures"))
    assert closures.get("display_type") != "True"
    assert closures.get("type") in ("",) or closures.get("review_status") == "needs_review"


def test_cross_garment_detail_artifact_rejected():
    spec = _load_fr3958()
    shorts = next(p for p in spec["outfit"]["pieces"] if p["category"] == "shorts")
    detail = shorts["illustrations"]["artifacts"]["detail_callouts"]
    decision = evaluate_artifact_for_piece(shorts, kind="detail_callouts", artifact_meta=detail)
    assert decision["include"] is False
    assert "mismatch" in decision["review_state"] or "rejected" in decision["review_state"]


def test_readiness_stays_design_concept_until_confirmed():
    spec = _load_fr3958()
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
    assert assessment["production_approved"] is False
    assert assessment["pattern_status"]["sewing_pattern_supplied"] is False
    assert assessment["blocking_issue_count"] >= 1


def test_sample_ready_requires_confirmation_and_clean_inputs():
    """Happy-path: confirmed checklist + clean POMs can reach SAMPLE-DEVELOPMENT READY."""
    spec = default_spec(look_summary="navy cotton trousers")
    # Force a simple trousers piece with plausible POMs and materials.
    piece = spec["outfit"]["pieces"][0]
    piece["category"] = "trousers"
    piece["label"] = "Trousers"
    piece["materials"]["shell"] = {
        "name": "Cotton twill",
        "composition": "100% cotton",
        "fabric_structure": "woven",
        "stretch": "none",
        "source": "designer",
    }
    piece["closures"] = {"type": "Zip fly + button", "notes": "Confirmed", "source": "designer"}
    piece["finished_measurements"]["waist"]["value"] = 78
    piece["finished_measurements"]["hip"]["value"] = 98
    piece["finished_measurements"]["inseam"]["value"] = 78
    piece["pom_tolerances"] = {"default_cm": 0.5}
    piece["fit"] = {"suggestion": "regular", "silhouette": "straight"}
    spec["sample_size"] = "M"
    spec["body"] = {
        "height": {"value": 170, "unit": "cm"},
        "bust": {"value": 90, "unit": "cm"},
        "waist": {"value": 74, "unit": "cm"},
        "hip": {"value": 96, "unit": "cm"},
        "inseam": {"value": 78, "unit": "cm"},
    }
    for row in spec.get("qc_checklist") or []:
        if isinstance(row, dict):
            row["checked"] = True
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_SAMPLE_DEVELOPMENT
    assert assessment["production_approved"] is False


def test_corrected_fr3958_pdf_preview_offline(tmp_path: Path):
    """New offline FR-3958 preview — does not overwrite any production export."""
    spec = enrich_spec_for_manufacturing_preview(_load_fr3958())
    front = tmp_path / "front.png"
    _tiny_png(front)
    pdf, pages = build_techpack_pdf(
        title="FR-3958 manufacturing preview",
        style_code="FR-3958",
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="00000000-0000-0000-0000-000000000395",
        front_image=front,
        back_image=None,
        spec=spec,
    )
    out = tmp_path / "FR-3958_manufacturing_preview.pdf"
    out.write_bytes(pdf)
    # Also write under repo artifacts for human review (not a production export).
    preview_dir = Path(__file__).resolve().parents[2] / "artifacts" / "manufacturing_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "FR-3958_manufacturing_preview.pdf").write_bytes(pdf)

    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    assert pages >= 6
    assert "DESIGN CONCEPT" in text or "DRAFT" in text
    assert "SAMPLE-DEVELOPMENT READY" not in text.split("Current readiness")[1][:80] or "DESIGN CONCEPT" in text
    assert "sample size" in text.lower() or "Sample size" in text
    assert "NEEDS REVIEW" in text or "REVIEW" in text
    assert "NOT TO SCALE" in text
    assert "sewing pattern is not supplied" in text.lower() or "sewing pattern is <b>not</b> supplied" in text.lower() or "No production sewing pattern" in text or "patternmaker must develop" in text.lower()
    assert "Piece A" not in text  # generic A/B/C cutting rectangles removed
    assert "Garment color" in text
    assert "Shell material" in text
    assert "boolean" in text.lower() or "Closure" in text
    # Cross-garment exclusion messaging
    assert "EXCLUDED" in text or "MISSING" in text or "mismatch" in text.lower()
    # Historical export not touched — we only wrote a new preview file.
    assert out.exists() and out.stat().st_size > 1000


def test_d47d_two_piece_still_renders_with_readiness(tmp_path: Path):
    """FR-D47D-shaped top+trousers fixture remains printable offline."""
    from app.services.techpack_ai import enrich_spec_heuristic

    front = tmp_path / "front.png"
    _tiny_png(front)
    spec = enrich_spec_heuristic(
        default_spec(look_summary="black V-slit tunic with cream trousers")
    )
    spec["sample_size"] = ""
    pdf, pages = build_techpack_pdf(
        title="FR-D47D readiness check",
        style_code="FR-D47D",
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="00000000-0000-0000-0000-00000000d47d",
        front_image=front,
        back_image=None,
        spec=spec,
    )
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
    assert pages >= 6
    assert "Manufacturing readiness" in text or "readiness" in text.lower()
    assert "Body measurements" in text
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
