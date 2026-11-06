"""Professional AI densification — POMs, fabric, body context, empty-page layout."""

from __future__ import annotations

from reportlab.lib.styles import getSampleStyleSheet

from app.services.techpack_ai import (
    _apply_ai_fabric_estimate,
    _apply_ai_pom_estimates,
    _coerce_pom_number,
    _format_body_context,
    _normalize_finished_pom_estimates,
    enrich_spec_heuristic,
)
from app.services.techpack_ai_professional import (
    PROFESSIONAL_ANALYZE_MIN_TOKENS,
    _parse_analysis_json,
)
from app.services.techpack_designer_pdf import _cover_page, _overview_page
from app.services.techpack_garments import empty_finished_measurements


def test_parse_analysis_json_fence_and_min_tokens():
    assert PROFESSIONAL_ANALYZE_MIN_TOKENS >= 4096
    fenced = '```json\n{"silhouette":"mini","confidence":"high"}\n```'
    assert _parse_analysis_json(fenced)["silhouette"] == "mini"
    assert "JSON parse failed" in (_parse_analysis_json("{not json")["assumptions"])


def test_coerce_and_normalize_pom_estimates():
    assert _coerce_pom_number(60) == 60.0
    assert _coerce_pom_number("59–61") == 60.0
    assert _coerce_pom_number("Approx. 145-150 to floor") == 147.5
    norm = _normalize_finished_pom_estimates(
        {
            "sleeve_length_cm": "59–61",
            "center_back_length_cm": "Approx. 145–150",
            "finished_pom_methods": "visual proportion",
        }
    )
    assert norm["sleeve_length"] == 60.0
    assert norm["garment_length"] == 147.5
    assert norm["finished_pom_methods"]["_all"] == "visual proportion"


def test_format_body_context_compact():
    assert _format_body_context({}) == ""
    ctx = _format_body_context(
        {
            "bust": {"value": 88, "unit": "cm"},
            "waist": {"value": 70, "unit": "cm"},
            "height": {"value": 168, "unit": "cm"},
            "hip": {"value": None, "unit": "cm"},
        }
    )
    assert "bust=88cm" in ctx
    assert "waist=70cm" in ctx
    assert "height=168cm" in ctx
    assert "hip" not in ctx


def test_apply_ai_pom_estimates_fills_empty_only():
    piece = {
        "category": "dress",
        "finished_measurements": empty_finished_measurements("dress"),
    }
    piece["finished_measurements"]["chest_bust"] = {
        "value": 92,
        "unit": "cm",
        "source": "designer",
    }
    analysis = {
        "finished_pom_estimates": {
            "garment_length": 91.5,
            "sleeve_length": 58,
            "hem_sweep": 96,
            "neckline_depth": 22,
            "finished_pom_methods": {
                "garment_length": "mini proportion from height",
                "sleeve_length": "long sleeve to wrist",
            },
        }
    }
    _apply_ai_pom_estimates(piece, analysis)
    fm = piece["finished_measurements"]
    assert fm["garment_length"]["value"] == 91.5
    assert fm["garment_length"]["source"] == "ai"
    assert fm["sleeve_length"]["value"] == 58
    assert fm["hem"]["value"] == 96
    assert fm["neckline"]["value"] == 22
    # Designer value preserved
    assert fm["chest_bust"]["value"] == 92
    assert fm["chest_bust"]["source"] == "designer"


def test_apply_ai_fabric_estimate_shell():
    piece = {
        "category": "dress",
        "color_hint": "pink",
        "materials": {"shell": {}},
        "bom": [{"name": "Shell fabric", "component": "shell"}],
    }
    _apply_ai_fabric_estimate(
        piece,
        {
            "fabric_estimate": {
                "likely_fiber": "polyester / elastane jersey",
                "gsm_range": "180–220",
                "hand": "smooth light stretch",
                "drape": "fluid",
                "opacity": "opaque",
                "lining_recommended": True,
                "notes": "Looks like a fine stripe jersey",
            }
        },
    )
    shell = piece["materials"]["shell"]
    assert "polyester" in shell["composition"]
    assert shell["weight_gsm"] == "180–220"
    assert shell["source"] == "ai"
    assert "lining" in piece["materials"]
    assert "polyester" in (piece["bom"][0].get("composition") or "")


def test_enrich_then_ai_poms_fill_lengths():
    spec = {
        "units": "cm",
        "preferences": {"fit_preference": "fitted"},
        "body": {
            "bust": {"value": 90, "unit": "cm"},
            "waist": {"value": 72, "unit": "cm"},
            "hip": {"value": 96, "unit": "cm"},
            "height": {"value": 170, "unit": "cm"},
        },
        "outfit": {
            "piece_count": 1,
            "pieces": [
                {
                    "id": "p1",
                    "category": "dress",
                    "label": "Mini dress",
                    "color_hint": "pink",
                }
            ],
        },
    }
    enriched = enrich_spec_heuristic(spec)
    piece = enriched["outfit"]["pieces"][0]
    assert piece["finished_measurements"]["garment_length"].get("value") in (None, "")
    _apply_ai_pom_estimates(
        piece,
        {"finished_pom_estimates": {"garment_length": 88, "sleeve_length": 60}},
    )
    assert piece["finished_measurements"]["garment_length"]["value"] == 88
    assert piece["finished_measurements"]["sleeve_length"]["value"] == 60


def test_cover_skips_tryon_boilerplate_notes():
    styles = {
        "title": getSampleStyleSheet()["Title"],
        "h2": getSampleStyleSheet()["Heading2"],
        "h3": getSampleStyleSheet()["Heading3"],
        "body": getSampleStyleSheet()["BodyText"],
        "muted": getSampleStyleSheet()["BodyText"],
        "warn": getSampleStyleSheet()["BodyText"],
        "small": getSampleStyleSheet()["BodyText"],
    }
    v2 = {
        "look_notes": "Try On Person preview — stockings on",
        "ai": {},
        "disclaimer": "Sample development pack.",
        "preferences": {"fit_preference": "fitted"},
        "body": {"bust": {"value": 88, "unit": "cm"}},
        "warnings": [],
    }
    pieces = [
        {
            "id": "p1",
            "category": "dress",
            "label": "Dress",
            "color_hint": "beige",
            "illustrations": {
                "analysis": {
                    "silhouette": "fitted mini",
                    "neckline": "deep V",
                    "sleeves": "long",
                    "length": "mini",
                    "fabric_estimate": {"likely_fiber": "poly jersey", "gsm_range": "200"},
                }
            },
        }
    ]
    story = _cover_page(
        title="Test",
        style_code="FR-TEST",
        revision=1,
        status_label="DRAFT",
        look_id="look-1",
        front_image=None,
        back_image=None,
        v2=v2,
        pieces=pieces,
        styles=styles,
    )
    texts = [getattr(f, "text", "") for f in story if hasattr(f, "text")]
    blob = " ".join(str(t) for t in texts)
    assert "Try On Person" not in blob
    assert "GARMENT TECH SHEET" in blob or "fitted mini" in blob or "Key garment" in blob
    assert "No Magic back" in blob or "AI proposes" in blob or "Proposed" in blob


def test_overview_notes_proposed_back_when_missing():
    styles = {
        "h2": getSampleStyleSheet()["Heading2"],
        "h3": getSampleStyleSheet()["Heading3"],
        "body": getSampleStyleSheet()["BodyText"],
        "muted": getSampleStyleSheet()["BodyText"],
        "warn": getSampleStyleSheet()["BodyText"],
        "small": getSampleStyleSheet()["BodyText"],
    }
    story = _overview_page(
        front_image=None,
        back_image=None,
        v2={
            "preferences": {},
            "body": {},
            "warnings": [{"message": "POM tolerances not confirmed"}],
        },
        styles=styles,
    )
    texts = [getattr(f, "text", "") for f in story if hasattr(f, "text")]
    blob = " ".join(str(t) for t in texts)
    assert "Proposed back" in blob
    assert "No Magic back" in blob
    # Warnings stay off overview (pointer only) so they cannot orphan a near-empty page.
    assert "Measurement review warnings" not in blob
    assert "Manufacturing readiness" in blob
