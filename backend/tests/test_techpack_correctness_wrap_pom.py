"""Technical correctness: full-circ POM labeling + wrap closure consistency."""

from __future__ import annotations

from app.services.techpack_designer_spec import (
    DRESS_POM_HOW_TO,
    detect_closure_family,
    enrich_piece_for_designer_pdf,
    formal_dress_bom,
    finished_pom_rows,
    qc_for_piece,
    scrub_conflicting_closure_bom,
)


def test_dress_pom_howto_is_full_circumference_not_half():
    for key in ("chest_bust", "waist", "hip", "hem"):
        text = DRESS_POM_HOW_TO[key].lower()
        assert "full" in text
        assert "1/2" not in text
        assert "half" not in text or "flat half" in text or "×2" in text or "x2" in text


def test_detect_wrap_when_no_visible_closure():
    piece = {
        "category": "dress",
        "label": "Long-sleeve deep-V wrap dress",
        "illustrations": {
            "analysis": {
                "silhouette": "fitted wrap",
                "closure_visible": "No closure hardware visible; waist sash",
                "distinctive_features": ["wrap front", "thigh slit", "asymmetric drape"],
            }
        },
    }
    assert detect_closure_family(piece) == "wrap"


def test_wrap_bom_has_no_invisible_zipper():
    bom = formal_dress_bom(color_hint="beige", closure_family="wrap")
    blob = " ".join(str(r.get("item") or "") for r in bom).lower()
    assert "invisible zipper" not in blob
    assert "sash" in blob or "tie" in blob
    assert any("proposed" in str(r.get("notes") or "").lower() for r in bom)


def test_scrub_removes_zip_from_legacy_bom():
    legacy = [
        {"item": "Invisible zipper", "qty": "1", "placement": "CB"},
        {"item": "Hook and eye", "qty": "1", "placement": "Top of zipper"},
        {"item": "Shell fabric", "qty": "2", "unit": "m"},
    ]
    cleaned = scrub_conflicting_closure_bom(legacy, closure_family="wrap")
    items = " ".join(str(r.get("item") or "").lower() for r in cleaned)
    assert "zip" not in items
    assert "shell" in items


def test_enrich_wrap_piece_qc_and_missing_design_poms():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "color_hint": "beige",
        "bom": [
            {"item": "Invisible zipper", "qty": "1", "unit": "pcs", "placement": "CB"},
            {"item": "Shell", "qty": "2", "unit": "m"},
        ],
        "finished_measurements": {
            "chest_bust": {"value": 89, "unit": "cm", "source": "calculated"},
            "waist": {"value": 79, "unit": "cm", "source": "calculated"},
            "hip": {"value": 99, "unit": "cm", "source": "calculated"},
        },
        "illustrations": {
            "analysis": {
                "closure_visible": "No closure hardware visible; narrow waist tie",
                "silhouette": "wrap bodice",
                "distinctive_features": ["deep V wrap", "thigh slit"],
            }
        },
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    assert enriched["_closure_family"] == "wrap"
    bom_blob = " ".join(str(r.get("item") or "") for r in enriched["bom"]).lower()
    assert "invisible zipper" not in bom_blob
    qc = " ".join(qc_for_piece(enriched)).lower()
    assert "wrap overlap" in qc
    assert "no zipper qc" in qc or "unless a zip" in qc
    assert "invisible zip smooth" not in qc
    finished = enriched["finished_measurements"]
    assert finished["wrap_overlap"]["value"] is None
    assert "missing" in str(finished["slit_start"].get("note") or "").lower()
    rows = finished_pom_rows(enriched)
    bust = next(r for r in rows if r["key"] == "chest_bust")
    assert "full" in bust["how_to"].lower()
    assert "1/2 bust" not in bust["how_to"].lower()


def test_enrich_wrap_redacts_invented_back_zip():
    piece = {
        "category": "dress",
        "label": "Wrap dress",
        "illustrations": {
            "analysis": {
                "closure_visible": "No zipper; waist sash wrap",
                "silhouette": "wrap",
                "distinctive_features": ["wrap front"],
                "back_construction_proposal": (
                    "Propose modest back neckline with center-back seam, "
                    "concealed short invisible zip from upper back to waist, "
                    "and center-back skirt seam."
                ),
            }
        },
        "construction_steps": [
            {"operation": "Install invisible zipper", "notes": "CB"},
            {"operation": "Finish wrap neckline", "notes": "stay tape"},
        ],
    }
    enriched = enrich_piece_for_designer_pdf(piece)
    prop = str(enriched["illustrations"]["analysis"]["back_construction_proposal"]).lower()
    assert "invisible zip" not in prop
    assert "wrap closure" in prop
    steps = " ".join(
        str(s.get("operation") or "") for s in enriched["construction_steps"] if isinstance(s, dict)
    ).lower()
    assert "zip" not in steps
    assert "wrap neckline" in steps
