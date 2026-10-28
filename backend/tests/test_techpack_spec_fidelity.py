"""Deterministic designer-spec ↔ generated-text fidelity (offline, $0)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.techpack_ai_professional import OpenAIProfessionalProvider
from app.services.techpack_manufacturing import evaluate_artifact_for_piece
from app.services.techpack_spec_fidelity import (
    apply_fidelity_gates_to_artifact_meta,
    apply_studio_fills_to_spec,
    closure_prompt_contract,
    color_treatment_from_studio_fills,
    color_treatment_prompt_contract,
    detect_closure_caption_mismatch,
    detect_color_treatment_text_mismatch,
    normalize_color_treatment,
    piece_color_treatment,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_buttons_vs_fly_zipper_caption_mismatch_marks_unverified():
    jeans = {
        "id": "jeans-1",
        "category": "trousers",
        "label": "Jeans",
        "closures": {"type": "buttons", "source": "designer", "review_status": "confirmed"},
    }
    hit = detect_closure_caption_mismatch(
        jeans,
        caption_text="FLY (ZIPPER) — center front fly with metal zipper",
    )
    assert hit is not None
    assert hit["designer_requirement"] == "buttons"
    assert hit["generated_implies"] == "zipper_fly"
    assert hit["manufacturing_evidence"] is False

    decision = evaluate_artifact_for_piece(
        jeans,
        kind="detail_callouts",
        artifact_meta={
            "review_state": "proposed",
            "caption": "FLY (ZIPPER)",
            "analysis": {"closure_visible": "fly zipper"},
        },
    )
    assert decision["include"] is True
    assert decision["manufacturing_evidence"] is False
    assert decision["review_state"] == "proposed_unverified"
    assert "buttons" in decision["reason"].lower()


def test_matching_buttons_caption_does_not_false_positive():
    jeans = {
        "id": "jeans-1",
        "category": "trousers",
        "closures": {"type": "buttons", "source": "designer"},
    }
    assert (
        detect_closure_caption_mismatch(
            jeans, caption_text="Center-front button placket with buttonholes"
        )
        is None
    )


def test_detail_prompt_includes_designer_buttons_contract():
    jeans = {
        "category": "trousers",
        "label": "Jeans",
        "closures": {"type": "buttons", "source": "designer"},
    }
    prompt = OpenAIProfessionalProvider._detail_prompt(
        {"neckline": None, "sleeves": None, "fabric_pattern": "denim", "stripe_direction": None},
        piece=jeans,
    )
    assert "BUTTONS" in prompt.upper()
    assert "FLY (ZIPPER)" in prompt.upper() or "zipper fly" in prompt.lower()
    assert "FORBIDDEN" in prompt.upper() or "Do NOT" in prompt
    flat = OpenAIProfessionalProvider._flat_prompt(
        {"silhouette": "straight", "distinctive_features": []},
        view="front",
        piece=jeans,
    )
    assert "BUTTONS" in flat.upper()


def test_color_treatment_gradient_preserved_and_simplification_flagged():
    shirt = {
        "id": "shirt-1",
        "category": "shirt",
        "color_treatment": {
            "mode": "gradient",
            "stops": ["near-black", "burgundy"],
            "direction": "top-to-bottom",
            "designer_confirmed": True,
            "source": "designer",
        },
        "color_hint": "dark-to-burgundy gradient",
    }
    ct = piece_color_treatment(shirt)
    assert ct is not None
    assert ct["mode"] == "gradient"
    assert "burgundy" in " ".join(str(x) for x in ct["stops"]).lower()

    contract = color_treatment_prompt_contract(shirt)
    assert "gradient" in contract.lower()
    assert "two-tone" in contract.lower() or "color-block" in contract.lower()

    hit = detect_color_treatment_text_mismatch(shirt, rendered_color_text="red")
    assert hit is not None
    assert hit["code"] == "color_treatment_simplified"
    assert hit["manufacturing_evidence"] is False

    # Gradient language in rendered text → no false positive.
    assert (
        detect_color_treatment_text_mismatch(
            shirt, rendered_color_text="dark-to-burgundy gradient"
        )
        is None
    )


def test_normalize_color_treatment_and_closure_contract_helpers():
    assert normalize_color_treatment({}) is None
    assert normalize_color_treatment({"mode": "color_block", "named_colors": ["black", "burgundy"]})[
        "mode"
    ] == "color_block"
    piece = {"closures": {"type": "buttons"}}
    assert "BUTTONS" in closure_prompt_contract(piece).upper()


def test_closure_bom_prefers_designer_buttons_over_generic_zipper():
    from app.services.techpack_flats import default_bom
    from app.services.techpack_spec_fidelity import closure_bom_row, format_color_treatment_for_pdf

    jeans = {
        "category": "trousers",
        "closures": {
            "type": "buttons",
            "source": "designer",
            "designer_confirmed": True,
        },
    }
    row = closure_bom_row(jeans)
    assert "button" in row["item"].lower()
    assert "zipper" not in row["item"].lower()
    bom = default_bom("trousers", piece=jeans)
    items = " ".join(str(r.get("item") or "") for r in bom).lower()
    assert "button" in items
    assert "zipper / elastic / closure" not in items

    shirt = {
        "color_treatment": {
            "mode": "gradient",
            "named_colors": ["near-black", "burgundy"],
            "direction": "top-to-bottom",
            "designer_confirmed": True,
            "source": "designer",
        }
    }
    pdf_line = format_color_treatment_for_pdf(shirt)
    assert "gradient" in pdf_line.lower()
    assert "burgundy" in pdf_line.lower()
    assert "designer-confirmed" in pdf_line.lower()


def test_autofill_does_not_overwrite_designer_buttons():
    from app.services.techpack_autofill import apply_visible_analysis_to_piece

    piece = {
        "id": "jeans-1",
        "category": "trousers",
        "closures": {
            "type": "buttons",
            "source": "designer",
            "designer_confirmed": True,
        },
        "color_treatment": {
            "mode": "gradient",
            "stops": ["near-black", "burgundy"],
            "designer_confirmed": True,
            "source": "designer",
        },
    }
    analysis = {
        "closure_visible": "FLY (ZIPPER)",
        "colors": ["red"],
        "fabric_pattern": "solid",
        "color_treatment": "solid",
    }
    out = apply_visible_analysis_to_piece(piece, analysis, only_empty=True)
    assert out["closures"]["type"] == "buttons"
    assert out["closures"].get("ai_observed_closure_visible")
    assert out["color_treatment"]["mode"] == "gradient"
    assert out["color_treatment"]["designer_confirmed"] is True


def test_mixed_button_and_zipper_captions_flag_when_designer_requires_buttons():
    """FR-B9F9 page 11: WAISTBAND & BUTTON + FLY (ZIPPER) must not false-negative."""
    jeans = {
        "id": "jeans-1",
        "category": "trousers",
        "closures": {
            "type": "buttons",
            "source": "designer",
            "designer_confirmed": True,
        },
    }
    mixed = "WAISTBAND & BUTTON · FLY (ZIPPER) — center front"
    hit = detect_closure_caption_mismatch(jeans, caption_text=mixed)
    assert hit is not None
    assert hit["designer_requirement"] == "buttons"
    assert hit["generated_implies"] == "zipper_fly"

    decision = evaluate_artifact_for_piece(
        jeans,
        kind="detail_callouts",
        artifact_meta={
            "review_state": "proposed",
            "captions": ["WAISTBAND & BUTTON", "FLY (ZIPPER)"],
            "annotations": ["button waistband", "fly (zipper)"],
        },
    )
    assert decision["manufacturing_evidence"] is False
    assert decision["review_state"] == "proposed_unverified"


def test_zipper_required_flags_button_only_caption():
    piece = {
        "closures": {"type": "zipper", "source": "designer", "designer_confirmed": True}
    }
    hit = detect_closure_caption_mismatch(
        piece, caption_text="Center-front button placket with buttons"
    )
    assert hit is not None
    assert hit["designer_requirement"] == "zipper"
    assert hit["generated_implies"] == "buttons"
    # Both zipper + buttons present → not button-only; no mismatch.
    assert (
        detect_closure_caption_mismatch(
            piece, caption_text="FLY (ZIPPER) with optional button tab"
        )
        is None
    )


def test_studio_gradient_fill_maps_to_piece_color_treatment_with_provenance():
    design_data = json.loads(
        (_FIXTURES / "studio_gradient_fill_upstream.json").read_text(encoding="utf-8")
    )
    derived = color_treatment_from_studio_fills(design_data["fills"])
    assert derived is not None
    assert derived["mode"] == "gradient"
    assert derived["provenance"] == "confirmed"
    assert derived["designer_confirmed"] is True
    assert derived["source"] == "studio_fill"
    assert derived["direction"] == "top-to-bottom"
    assert derived["gradient_id"] == "near-black-burgundy"
    assert len(derived["stops"]) == 2

    spec = {
        "schema_version": "2.0",
        "outfit": {
            "pieces": [
                {
                    "id": "shirt-1",
                    "category": "shirt",
                    "color_hint": "red",
                    "color_treatment": {"mode": "", "source": "empty"},
                }
            ]
        },
    }
    out = apply_studio_fills_to_spec(spec, design_data)
    piece = out["outfit"]["pieces"][0]
    ct = piece_color_treatment(piece)
    assert ct is not None
    assert ct["mode"] == "gradient"
    assert ct["provenance"] == "confirmed"
    assert piece["color_hint"] == "red"  # hint may stay; treatment must not flatten
    assert out["studio_color_treatment_source"]["fill_count"] == 1
    assert out["studio_color_treatment_source"]["mode"] == "gradient"

    # Professional input snapshot must carry structured treatment (not invent).
    from app.services.techpack_structure import _piece_input_snapshot

    snap = _piece_input_snapshot(piece)
    assert isinstance(snap.get("color_treatment"), dict)
    assert snap["color_treatment"]["mode"] == "gradient"


def test_red_only_hint_plus_upstream_gradient_does_not_flatten():
    piece = {
        "id": "shirt-1",
        "color_hint": "red",
        "studio_fills": [
            {
                "id": "f1",
                "style": {
                    "kind": "gradient",
                    "gradientId": "near-black-burgundy",
                    "colors": ["#1a0a0a", "#6b1c2a"],
                    "angle": 90,
                },
            }
        ],
    }
    ct = piece_color_treatment(piece)
    assert ct is not None
    assert ct["mode"] == "gradient"
    hit = detect_color_treatment_text_mismatch(piece, rendered_color_text="red")
    assert hit is not None
    assert hit["code"] == "color_treatment_simplified"


def test_two_tone_text_does_not_evade_structured_gradient_mismatch():
    shirt = {
        "color_treatment": {
            "mode": "gradient",
            "stops": ["#1a0a0a", "#6b1c2a"],
            "designer_confirmed": True,
            "source": "studio_fill",
            "provenance": "confirmed",
        }
    }
    hit = detect_color_treatment_text_mismatch(
        shirt, rendered_color_text="two-tone black and burgundy hard split"
    )
    assert hit is not None
    assert hit["code"] == "color_treatment_simplified"


def test_missing_studio_source_exposes_unconfirmed_not_invented():
    empty = apply_studio_fills_to_spec(
        {"outfit": {"pieces": [{"id": "p1", "color_hint": "red"}]}},
        {"fills": []},
    )
    assert empty["studio_color_treatment_source"]["fill_count"] == 0
    assert empty["studio_color_treatment_source"]["provenance"] == "unconfirmed"
    # No invented gradient on the piece.
    assert piece_color_treatment(empty["outfit"]["pieces"][0]) is None


def test_fidelity_gates_preserve_rejected_preview_exclude():
    piece = {
        "closures": {"type": "buttons", "source": "designer"},
        "color_treatment": {
            "mode": "gradient",
            "stops": ["a", "b"],
            "designer_confirmed": True,
            "source": "designer",
        },
    }
    gated = apply_fidelity_gates_to_artifact_meta(
        piece,
        kind="detail_callouts",
        artifact_meta={
            "review_state": "rejected_category_mismatch",
            "preview_include": False,
            "caption": "FLY (ZIPPER)",
            "garment_color": "red",
        },
    )
    assert gated["preview_include"] is False
    assert gated["manufacturing_evidence"] is False
    assert gated["review_state"] == "rejected_category_mismatch"
    assert gated.get("fidelity_mismatches")

    decision = evaluate_artifact_for_piece(
        piece,
        kind="detail_callouts",
        artifact_meta={
            "review_state": "rejected",
            "preview_include": False,
            "caption": "FLY (ZIPPER)",
        },
    )
    assert decision["include"] is False
    assert decision["review_state"] == "rejected"
