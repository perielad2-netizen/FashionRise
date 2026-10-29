"""Issue #128 — designer finished measurements must survive Professional enrichment."""

from __future__ import annotations

from copy import deepcopy

from app.services.techpack_ai import enrich_spec_heuristic
from app.services.techpack_garments import FINISHED_POM, default_piece
from app.services.techpack_spec import ensure_v2


def _designer_cell(value: float, *, definition: str, unit: str = "cm", **extra):
    cell = {
        "value": value,
        "unit": unit,
        "source": "designer",
        "note": "owner entered",
        "definition": definition,
        "confidence": "high",
        "review_status": "confirmed",
        "assumptions": [],
    }
    cell.update(extra)
    return cell


def _shorts_piece_with_all_poms() -> dict:
    """Every shorts POM filled by the designer, including outseam/thigh/waistband."""
    piece = default_piece(
        piece_id="piece-shorts-128",
        category="shorts",
        label="Shorts",
        role="bottom",
        color_hint="navy",
    )
    values = {
        "waist": 74.0,
        "hip": 98.5,
        "inseam": 18.0,
        "outseam": 42.0,
        "front_rise": 28.0,
        "back_rise": 36.0,
        "thigh": 58.0,
        "leg_opening": 52.0,
        "waistband": 4.0,
    }
    definitions = {
        "waist": "Waist circumference",
        "hip": "Hip circumference",
        "inseam": "Inseam",
        "outseam": "Outseam",
        "front_rise": "Front rise",
        "back_rise": "Back rise",
        "thigh": "Thigh circumference",
        "leg_opening": "Leg opening",
        "waistband": "Waistband height",
    }
    finished = {}
    for key in FINISHED_POM["shorts"]:
        finished[key] = _designer_cell(values[key], definition=definitions[key])
    piece["finished_measurements"] = finished
    return piece


def _spec_with_shorts(piece: dict) -> dict:
    return ensure_v2(
        {
            "schema_version": "2.0",
            "units": "cm",
            "body": {
                "waist": {"value": 70, "unit": "cm", "source": "designer"},
                "hip": {"value": 94, "unit": "cm", "source": "designer"},
                "inseam": {"value": 76, "unit": "cm", "source": "designer"},
            },
            "preferences": {"fit_preference": "regular"},
            "outfit": {"piece_count": 1, "pieces": [piece]},
        }
    )


def test_shorts_all_designer_poms_survive_enrich_and_reopen():
    """Regression #128: outseam/thigh/waistband must not vanish after enrich."""
    original = _shorts_piece_with_all_poms()
    before = deepcopy(original["finished_measurements"])
    assert set(before) == set(FINISHED_POM["shorts"])
    for key in ("outseam", "thigh", "waistband"):
        assert before[key]["value"] is not None
        assert before[key]["source"] == "designer"

    enriched = enrich_spec_heuristic(_spec_with_shorts(original))
    after = enriched["outfit"]["pieces"][0]["finished_measurements"]

    for key, cell in before.items():
        got = after[key]
        assert got["value"] == cell["value"], f"{key} value lost/changed"
        assert got["unit"] == cell["unit"], f"{key} unit lost"
        assert got["source"] == "designer", f"{key} source overwritten"
        assert got["note"] == cell["note"], f"{key} note lost"
        assert got["definition"] == cell["definition"], f"{key} definition lost"
        assert got["review_status"] == cell["review_status"], f"{key} review_status lost"
        assert got["confidence"] == cell["confidence"], f"{key} confidence lost"

    # Simulate reopen: enrich again on the persisted enriched spec.
    reopened = enrich_spec_heuristic(deepcopy(enriched))
    again = reopened["outfit"]["pieces"][0]["finished_measurements"]
    for key, cell in before.items():
        assert again[key]["value"] == cell["value"]
        assert again[key]["source"] == "designer"
        assert again[key]["definition"] == cell["definition"]


def test_enrich_proposes_only_genuinely_empty_fields():
    piece = default_piece(
        piece_id="piece-shorts-empty",
        category="shorts",
        label="Shorts",
    )
    # Designer filled only waist; leave outseam empty for a proposal path that
    # does not invent outseam (no body→outseam calc exists).
    piece["finished_measurements"]["waist"] = _designer_cell(72.0, definition="Waist")
    # Leave thigh explicitly empty with designer note metadata still present.
    piece["finished_measurements"]["thigh"] = {
        "value": None,
        "unit": "cm",
        "source": "empty",
        "note": "will measure later",
        "definition": "Thigh circumference",
        "confidence": "unknown",
        "review_status": "open",
        "assumptions": [],
    }

    enriched = enrich_spec_heuristic(_spec_with_shorts(piece))
    finished = enriched["outfit"]["pieces"][0]["finished_measurements"]

    assert finished["waist"]["value"] == 72.0
    assert finished["waist"]["source"] == "designer"
    # Empty thigh stays empty / not fabricated from thin air.
    assert finished["thigh"]["value"] in (None, "")
    assert finished["thigh"]["definition"] == "Thigh circumference"
    # Calculated waist proposal must not replace designer waist even when body exists.
    # Hip may be proposed from body when empty.
    assert finished["hip"]["source"] in ("calculated", "unknown", "empty")
    if finished["hip"].get("value") is not None:
        assert finished["hip"]["source"] == "calculated"


def test_non_designer_nonempty_also_preserved():
    """Calculated/confirmed nonempty cells must not be wiped on re-enrich."""
    piece = default_piece(
        piece_id="piece-shorts-calc",
        category="shorts",
        label="Shorts",
    )
    piece["finished_measurements"]["outseam"] = {
        "value": 41.5,
        "unit": "cm",
        "source": "calculated",
        "note": "prior proposal kept",
        "definition": "Outseam",
        "confidence": "medium",
        "review_status": "proposed",
        "assumptions": ["prior"],
    }
    enriched = enrich_spec_heuristic(_spec_with_shorts(piece))
    cell = enriched["outfit"]["pieces"][0]["finished_measurements"]["outseam"]
    assert cell["value"] == 41.5
    assert cell["source"] == "calculated"
    assert cell["note"] == "prior proposal kept"


def test_autofill_category_swap_preserves_nonempty_poms():
    from app.services.techpack_autofill import apply_visible_analysis_to_piece

    piece = default_piece(
        piece_id="piece-bot",
        category="trousers",
        label="Bottom",
        detection_source="heuristic_summary",
    )
    piece["finished_measurements"]["outseam"] = _designer_cell(55.0, definition="Outseam")
    piece["finished_measurements"]["thigh"] = _designer_cell(60.0, definition="Thigh")
    piece["finished_measurements"]["waistband"] = _designer_cell(3.5, definition="Waistband")

    out = apply_visible_analysis_to_piece(
        piece,
        {"category": "shorts", "confidence": "high"},
        only_empty=True,
    )
    assert out["category"] == "shorts"
    assert out["finished_measurements"]["outseam"]["value"] == 55.0
    assert out["finished_measurements"]["thigh"]["value"] == 60.0
    assert out["finished_measurements"]["waistband"]["value"] == 3.5
    assert out["finished_measurements"]["outseam"]["source"] == "designer"
