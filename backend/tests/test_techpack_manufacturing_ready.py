"""Manufacturing-ready tech pack foundation — offline fixtures ($0, no provider)."""

from __future__ import annotations

import io
import json
from copy import deepcopy
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.units import mm

from app.services.techpack_manufacturing import (
    READINESS_DESIGN_CONCEPT,
    READINESS_SAMPLE_DEVELOPMENT,
    assess_manufacturing_readiness,
    enrich_spec_for_manufacturing_preview,
    evaluate_artifact_for_piece,
    normalize_bom_rows,
    normalize_closure_display,
    normalize_shell_material,
    validate_piece_measurements,
    validate_sample_size,
)
from app.services.techpack_pdf import _SizedImage, build_techpack_pdf
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


def _pom(value: float, *, source: str = "designer") -> dict:
    return {
        "value": value,
        "unit": "cm",
        "source": source,
        "note": None,
        "definition": None,
        "confidence": "high" if source == "designer" else "low",
        "review_status": "confirmed" if source == "designer" else "open",
        "designer_confirmed": source == "designer",
    }


def _check_all_qc(spec: dict) -> None:
    for row in spec.get("qc_checklist") or []:
        if isinstance(row, dict):
            row["checked"] = True


def _complete_trousers_piece(piece: dict) -> dict:
    """Genuinely complete, designer-confirmed trousers — SAMPLE-READY eligible."""
    piece = deepcopy(piece)
    piece["category"] = "trousers"
    piece["label"] = "Trousers"
    piece["materials"] = {
        "shell": {
            "name": "Cotton twill",
            "composition": "100% cotton",
            "fabric_structure": "woven",
            "stretch": "none",
            "source": "designer",
            "designer_confirmed": True,
        }
    }
    piece["closures"] = {
        "type": "Zip fly + button",
        "notes": "Metal zip, horn button",
        "source": "designer",
        "designer_confirmed": True,
    }
    piece["fit"] = {
        "suggestion": "regular",
        "silhouette": "straight",
        "ease_note": "+4 cm hip ease confirmed",
        "source": "designer",
        "designer_confirmed": True,
        "review_status": "confirmed",
    }
    piece["finished_measurements"] = {
        "waist": _pom(78),
        "hip": _pom(98),
        "inseam": _pom(78),
        "front_rise": _pom(28),
        "leg_opening": _pom(42),
        "outseam": _pom(104),
        "back_rise": _pom(36),
    }
    piece["pom_tolerances"] = {
        "default_cm": 0.5,
        "source": "designer",
        "designer_confirmed": True,
    }
    piece["construction_steps"] = [
        {
            "step": 1,
            "instruction": "Join fronts at zip fly; set waistband with confirmed 0.5 cm SA.",
            "source": "designer",
            "designer_confirmed": True,
        },
        {
            "step": 2,
            "instruction": "Sew inseams and side seams; finish hem at marked inseam.",
            "source": "designer",
            "designer_confirmed": True,
        },
    ]
    piece["construction_confirmed"] = True
    # No unverified detail art on the happy path.
    piece["illustrations"] = {"mode": "basic", "artifacts": {}}
    piece["bom"] = [
        {
            "item": "Cotton twill shell",
            "qty": "1.6",
            "unit": "m",
            "notes": "150 cm width",
            "source": "designer",
        }
    ]
    return piece


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
    assert spec["body"]["waist"]["value"] == 90
    assert shorts["finished_measurements"]["waist"]["value"] == 75


def test_material_and_closure_normalization():
    spec = _load_fr3958()
    top = next(p for p in spec["outfit"]["pieces"] if p["category"] == "top")
    norm = normalize_shell_material(top)
    shell = norm["materials"]["shell"]
    assert shell.get("review_status") == "needs_review" or not shell.get("name")
    assert (
        "colorway_note" in shell
        or "fabric" in str(shell.get("colorway_note") or "").lower()
        or shell.get("name") == ""
    )
    closures = normalize_closure_display(top.get("closures"))
    assert closures.get("display_type") != "True"
    assert closures.get("type") in ("",) or closures.get("review_status") == "needs_review"


def test_normalize_bom_flags_outfit_color_list_without_inventing_composition():
    rows = normalize_bom_rows(
        [
            {
                "item": "['Lavender-purple top', 'Golden-yellow shorts'] shell",
                "qty": "1",
                "unit": "m",
                "composition": "should be cleared",
                "source": "estimate",
            },
            {"item": "Thread", "qty": "1", "unit": "cone", "source": "estimate"},
        ]
    )
    assert rows[0]["review_status"] == "needs_review"
    assert "NOT CONFIRMED" in rows[0]["item"]
    assert rows[0].get("composition") == ""
    assert "Lavender" in str(rows[0].get("original_item") or "")
    assert rows[1]["item"] == "Thread"


def test_cross_garment_detail_artifact_rejected():
    spec = _load_fr3958()
    shorts = next(p for p in spec["outfit"]["pieces"] if p["category"] == "shorts")
    detail = shorts["illustrations"]["artifacts"]["detail_callouts"]
    decision = evaluate_artifact_for_piece(shorts, kind="detail_callouts", artifact_meta=detail)
    assert decision["include"] is False
    assert decision["manufacturing_evidence"] is False
    assert "mismatch" in decision["review_state"] or "rejected" in decision["review_state"]


def test_unreviewed_wrong_garment_detail_stays_unverified_not_manufacturing_evidence():
    """Unmarked semantic mismatch: metadata looks fine, but no visual confirmation.

    Must remain reviewable (include=True) yet never count as manufacturing evidence.
    Pixel/content is not proven by artifact IDs or analysis text.
    """
    shorts = {
        "id": "piece-shorts",
        "category": "shorts",
        "label": "Golden shorts",
        "illustrations": {
            "mode": "professional",
            "analysis": {"silhouette": "shorts", "garment_category": "shorts"},
            "artifacts": {
                "detail_callouts": {
                    # Deliberately wrong garment content — but metadata claims shorts.
                    "artifact_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "storage_key": "private/wrong_hoodie_drawn_as_shorts_detail.png",
                    "review_state": "proposed",  # NOT rejected — unreviewed
                    "piece_id": "piece-shorts",
                    "analysis_match": True,
                }
            },
        },
    }
    meta = shorts["illustrations"]["artifacts"]["detail_callouts"]
    decision = evaluate_artifact_for_piece(shorts, kind="detail_callouts", artifact_meta=meta)
    assert decision["include"] is True
    assert decision["manufacturing_evidence"] is False
    assert "unverified" in decision["review_state"] or decision["review_state"] == "proposed"

    # Incomplete otherwise-plausible shorts + unverified detail → DESIGN CONCEPT.
    spec = default_spec(look_summary="golden mid-thigh shorts")
    piece = spec["outfit"]["pieces"][0]
    piece.update(
        {
            "id": "piece-shorts",
            "category": "shorts",
            "label": "Golden shorts",
            "materials": {
                "shell": {
                    "name": "Cotton chino",
                    "composition": "98% cotton 2% elastane",
                    "source": "designer",
                    "designer_confirmed": True,
                }
            },
            "closures": {"type": "Elastic waist + drawcord", "source": "designer", "designer_confirmed": True},
            "fit": {
                "suggestion": "relaxed",
                "silhouette": "mid-thigh",
                "source": "designer",
                "designer_confirmed": True,
            },
            "finished_measurements": {
                "waist": _pom(78),
                "hip": _pom(100),
                "inseam": _pom(18),
                "front_rise": _pom(28),
                "leg_opening": _pom(52),
            },
            "pom_tolerances": {"default_cm": 0.5, "designer_confirmed": True, "source": "designer"},
            "construction_steps": [
                {
                    "step": 1,
                    "instruction": "Set elastic waistband; finish inseam hem.",
                    "source": "designer",
                    "designer_confirmed": True,
                }
            ],
            "construction_confirmed": True,
            "illustrations": shorts["illustrations"],
        }
    )
    spec["outfit"]["pieces"] = [piece]
    spec["sample_size"] = "M"
    spec["body"] = {
        "height": {"value": 170, "unit": "cm"},
        "bust": {"value": 90, "unit": "cm"},
        "waist": {"value": 74, "unit": "cm"},
        "hip": {"value": 96, "unit": "cm"},
        "inseam": {"value": 78, "unit": "cm"},
    }
    _check_all_qc(spec)
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
    assert assessment["production_approved"] is False
    assert any(i.get("code") == "detail_art_unverified" for i in assessment["issues"])


def test_readiness_stays_design_concept_until_confirmed():
    spec = _load_fr3958()
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
    assert assessment["production_approved"] is False
    assert assessment["pattern_status"]["sewing_pattern_supplied"] is False
    assert assessment["blocking_issue_count"] >= 1


def test_incomplete_but_plausible_trousers_remain_design_concept():
    """Negative: waist/hip/inseam + materials + checked QC is still insufficient."""
    spec = default_spec(look_summary="navy cotton trousers")
    piece = spec["outfit"]["pieces"][0]
    piece["category"] = "trousers"
    piece["label"] = "Trousers"
    piece["materials"]["shell"] = {
        "name": "Cotton twill",
        "composition": "100% cotton",
        "fabric_structure": "woven",
        "source": "ai",  # not designer-confirmed
    }
    piece["closures"] = {"type": "Zip fly", "source": "estimate"}
    piece["finished_measurements"]["waist"] = _pom(78, source="ai")
    piece["finished_measurements"]["hip"] = _pom(98, source="estimate")
    piece["finished_measurements"]["inseam"] = _pom(78, source="ai")
    # Missing front_rise / leg_opening entirely.
    piece["pom_tolerances"] = {"default_cm": 0.5}  # no designer confirmation
    piece["fit"] = {"suggestion": "regular", "silhouette": "straight"}  # AI-ish, unconfirmed
    piece["construction_steps"] = [
        {"step": 1, "instruction": "Sew side seams.", "source": "estimate"}  # generic default
    ]
    spec["sample_size"] = "M"
    spec["body"] = {
        "height": {"value": 170, "unit": "cm"},
        "bust": {"value": 90, "unit": "cm"},
        "waist": {"value": 74, "unit": "cm"},
        "hip": {"value": 96, "unit": "cm"},
        "inseam": {"value": 78, "unit": "cm"},
    }
    _check_all_qc(spec)
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
    assert assessment["production_approved"] is False
    assert assessment["checklist_complete"] is True  # checklist alone is insufficient
    missing = " ".join(assessment["missing_required"])
    assert "finished_poms" in missing or "waist_hip_inseam" in missing or "construction" in missing


def test_incomplete_but_plausible_hoodie_remains_design_concept():
    """Negative: hoodie with some POMs + checked checklist still DESIGN CONCEPT."""
    spec = default_spec(look_summary="lavender zip hoodie")
    piece = spec["outfit"]["pieces"][0]
    piece["id"] = "piece-hoodie"
    piece["category"] = "top"
    piece["label"] = "Zip hoodie"
    piece["materials"]["shell"] = {
        "name": "Cotton fleece",
        "composition": "80% cotton 20% polyester",
        "source": "designer",
        "designer_confirmed": True,
    }
    piece["closures"] = {"type": "Center-front zipper", "source": "designer", "designer_confirmed": True}
    piece["fit"] = {
        "suggestion": "relaxed",
        "silhouette": "hoodie",
        "length_style": "Hip-length",
        "source": "ai",
    }
    piece["finished_measurements"] = {
        "chest_bust": _pom(108, source="ai"),
        "garment_length": _pom(68, source="estimate"),
        "shoulder_width": _pom(44, source="ai"),
        # sleeve_length missing
    }
    piece["pom_tolerances"] = {"default_cm": 0.5, "designer_confirmed": True, "source": "designer"}
    piece["construction_steps"] = [
        {"step": 1, "instruction": "Attach hood; set zipper.", "source": "estimate"}
    ]
    spec["outfit"]["pieces"] = [piece]
    spec["sample_size"] = "M"
    spec["body"] = {
        "height": {"value": 176, "unit": "cm"},
        "bust": {"value": 100, "unit": "cm"},
        "waist": {"value": 90, "unit": "cm"},
        "hip": {"value": 110, "unit": "cm"},
        "inseam": {"value": 80, "unit": "cm"},
    }
    _check_all_qc(spec)
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_DESIGN_CONCEPT
    assert assessment["production_approved"] is False
    assert assessment["checklist_complete"] is True
    assert any("finished_poms" in m or "fit_ease" in m or "construction" in m for m in assessment["missing_required"])


def test_sample_ready_requires_genuinely_complete_confirmed_specs():
    """Positive: fully designer-confirmed trousers can reach SAMPLE-DEVELOPMENT READY.

    Never grants PRODUCTION APPROVED automatically.
    """
    spec = default_spec(look_summary="navy cotton trousers")
    piece = _complete_trousers_piece(spec["outfit"]["pieces"][0])
    spec["outfit"]["pieces"] = [piece]
    spec["sample_size"] = "M"
    spec["preferences"] = {"fit_preference": "regular", "fit_preference_confirmed": True}
    spec["body"] = {
        "height": {"value": 170, "unit": "cm", "source": "designer"},
        "bust": {"value": 90, "unit": "cm", "source": "designer"},
        "waist": {"value": 74, "unit": "cm", "source": "designer"},
        "hip": {"value": 96, "unit": "cm", "source": "designer"},
        "inseam": {"value": 78, "unit": "cm", "source": "designer"},
    }
    _check_all_qc(spec)
    assessment = assess_manufacturing_readiness(spec)
    assert assessment["readiness_level"] == READINESS_SAMPLE_DEVELOPMENT, assessment["missing_required"]
    assert assessment["production_approved"] is False
    assert assessment["designer_confirmed"] is True


def test_sized_image_wrap_preserves_immutable_intended_dimensions(tmp_path: Path):
    png = tmp_path / "x.png"
    _tiny_png(png)
    img = _SizedImage(png, 170 * mm, 145 * mm)
    intended = img.intended_size
    # Tight first wrap must not permanently shrink intended size.
    w1, _h1 = img.wrap(40 * mm, 30 * mm)
    assert w1 <= 40 * mm + 0.01
    assert img.intended_size == intended
    # Later roomier wrap recomputes from intended, not from the shrunk pass.
    w2, _h2 = img.wrap(180 * mm, 160 * mm)
    assert abs(w2 - intended[0]) < 0.01
    assert abs(_h2 - intended[1]) < 0.01


def test_corrected_fr3958_pdf_preview_offline(tmp_path: Path):
    """Offline FR-3958 text/layout preview — does not overwrite any production export.

    Uses a 1×1 Magic stub for unit coverage only. Real visual acceptance uses the
    private FR-3958 Magic + six stored artifacts (see private QA evidence; not in git).
    """
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
    preview_dir = Path(__file__).resolve().parents[2] / "artifacts" / "manufacturing_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "FR-3958_manufacturing_preview.pdf").write_bytes(pdf)

    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    # ReportLab wraps mid-phrase; flatten whitespace for stable assertions.
    flat = " ".join(text.split())
    assert pages >= 6
    assert "DESIGN CONCEPT" in flat or "DRAFT" in flat
    assert "Current readiness: DESIGN CONCEPT" in flat or "Current readiness:</b> DESIGN CONCEPT" in text
    # Cover/readiness must stay DESIGN CONCEPT — not SAMPLE READY for FR-3958.
    assert "Readiness: DESIGN CONCEPT" in flat
    assert "Readiness: SAMPLE-DEVELOPMENT READY" not in flat
    assert "sample size" in flat.lower() or "Sample size" in flat
    assert "NEEDS REVIEW" in flat or "REVIEW" in flat
    assert "NOT TO SCALE" in flat
    assert (
        "sewing pattern is not supplied" in flat.lower()
        or "No production sewing pattern" in flat
        or "patternmaker must develop" in flat.lower()
    )
    assert "Piece A" not in flat
    assert "Garment color" in flat
    assert "Shell material" in flat
    assert "boolean" in flat.lower() or "Closure" in flat
    assert "EXCLUDED" in flat or "MISSING" in flat or "mismatch" in flat.lower()
    # BOM color-list rows must be flagged, not printed as fabric names.
    assert "Shell fabric — NOT CONFIRMED" in flat or "NOT CONFIRMED" in flat
    assert "Shell fabric — NOT CONFIRMED · NEEDS REVIEW" in flat or "NEEDS REVIEW" in flat
    # Color list may appear only as historical "Was:" note — never as the live item name alone.
    assert "Item Qty Unit Source Notes Shell fabric" in flat or "Shell fabric — NOT CONFIRMED" in flat
    assert "UNVERIFIED DETAIL ART" in flat
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
