"""V10 MTM — garment-aware templates (no dress leakage onto shirt/jeans)."""

from __future__ import annotations

from app.services.techpack_designer_spec import (
    callouts_for_piece,
    detect_closure_family,
    enrich_piece_for_designer_pdf,
    mtm_checklist_rows_for_piece,
    mtm_consultation_decisions,
    mtm_design_dim_keys,
    mtm_detail_focus,
    mtm_worksheet_rows,
)


def _shirt() -> dict:
    return {
        "id": "piece-shirt",
        "category": "shirt",
        "label": "Burgundy shirt",
        "role": "top",
        "closures": {"type": "button-front", "display_type": "buttons"},
        "illustrations": {
            "analysis": {
                "closure_visible": "front button placket",
                "neckline": "standing collar",
                "silhouette": "fitted shirt",
                "distinctive_features": ["rolled sleeves", "curved hem"],
            }
        },
        "finished_measurements": {
            "chest_bust": {"value": 104, "unit": "cm", "source": "ai"},
            "garment_length": {"value": 72, "unit": "cm", "source": "ai"},
            "wrap_overlap": {"value": 12, "unit": "cm", "source": "ai"},
            "sash_width": {"value": 4, "unit": "cm", "source": "ai"},
            "slit_start": {"value": 40, "unit": "cm", "source": "ai"},
        },
    }


def _trousers() -> dict:
    return {
        "id": "piece-jeans",
        "category": "trousers",
        "label": "Blue jeans",
        "role": "bottom",
        "closures": {"type": "zip fly", "display_type": "fly"},
        "illustrations": {
            "analysis": {
                "closure_visible": "concealed center-front fly",
                "silhouette": "tapered jeans",
                "distinctive_features": ["diagonal stripe denim", "belt loops", "back pockets"],
            }
        },
        "finished_measurements": {
            "waist": {"value": 82, "unit": "cm", "source": "ai"},
            "inseam": {"value": 78, "unit": "cm", "source": "ai"},
            "sash_length": {"value": 190, "unit": "cm", "source": "ai"},
            "wrap_overlap": {"value": 10, "unit": "cm", "source": "ai"},
        },
    }


def test_shirt_closure_is_button_not_wrap():
    assert detect_closure_family(_shirt()) == "button"


def test_trousers_closure_is_fly():
    assert detect_closure_family(_trousers()) == "fly"


def test_shirt_design_dims_exclude_dress_keys():
    keys = mtm_design_dim_keys("shirt")
    assert "chest_bust" in keys or "garment_length" in keys
    for banned in ("wrap_overlap", "sash_width", "sash_length", "slit_start", "overlay_length"):
        assert banned not in keys


def test_trousers_design_dims_are_leg_fit():
    keys = mtm_design_dim_keys("trousers")
    assert "waist" in keys
    assert "inseam" in keys
    assert "wrap_overlap" not in keys
    assert "sash_width" not in keys


def test_enrich_strips_dress_poms_from_shirt():
    out = enrich_piece_for_designer_pdf(_shirt())
    fm = out.get("finished_measurements") or {}
    assert "wrap_overlap" not in fm
    assert "sash_width" not in fm
    assert "slit_start" not in fm
    assert "chest_bust" in fm


def test_shirt_consultation_has_no_sash_or_wrap():
    blob = " ".join(f"{a} {b}" for a, b in mtm_consultation_decisions(_shirt())).lower()
    assert "collar" in blob
    assert "button" in blob
    assert "sash" not in blob
    assert "wrap/tie" not in blob
    assert "slit" not in blob


def test_jeans_consultation_mentions_fly_and_stripe():
    blob = " ".join(f"{a} {b}" for a, b in mtm_consultation_decisions(_trousers())).lower()
    assert "fly" in blob or "waistband" in blob
    assert "stripe" in blob or "denim" in blob or "grain" in blob
    assert "sash" not in blob
    assert "v-neck" not in blob and "v neck" not in blob


def test_detail_focus_matches_category():
    shirt_blob = " ".join(f"{a} {b}" for a, b in mtm_detail_focus(_shirt())).lower()
    jeans_blob = " ".join(f"{a} {b}" for a, b in mtm_detail_focus(_trousers())).lower()
    assert "placket" in shirt_blob or "collar" in shirt_blob
    assert "sash" not in shirt_blob
    assert "fly" in jeans_blob or "waistband" in jeans_blob
    assert "asymmetric" not in jeans_blob


def test_callouts_are_not_dress_defaults_for_shirt():
    labels = " ".join(lab for _n, lab in callouts_for_piece(_shirt())).lower()
    assert "placket" in labels or "collar" in labels
    assert "invisible zipper" not in labels
    assert "thigh slit" not in labels
    assert "sash" not in labels


def test_worksheet_rows_category_specific():
    shirt_ws = " ".join(lab for lab, _u in mtm_worksheet_rows(_shirt())).lower()
    jeans_ws = " ".join(lab for lab, _u in mtm_worksheet_rows(_trousers())).lower()
    assert "collar" in shirt_ws or "shirt" in shirt_ws
    assert "inseam" in jeans_ws
    assert "sash" not in shirt_ws
    assert "wrap" not in jeans_ws


def test_checklist_per_garment_and_no_dress_fastening_on_shirt():
    rows = mtm_checklist_rows_for_piece(_shirt())
    blob = " ".join(f"{a} {b}" for a, b in rows).lower()
    assert "shirt" in blob or "top" in blob
    assert "button" in blob
    assert "wrap/tie" not in blob
    jeans_rows = mtm_checklist_rows_for_piece(_trousers())
    jblob = " ".join(f"{a} {b}" for a, b in jeans_rows).lower()
    assert "fly" in jblob or "waist" in jblob
    assert "dress fastening" not in jblob
