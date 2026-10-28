"""Deterministic designer-spec ↔ generated-text fidelity (offline, $0)."""

from __future__ import annotations

from app.services.techpack_ai_professional import OpenAIProfessionalProvider
from app.services.techpack_manufacturing import evaluate_artifact_for_piece
from app.services.techpack_spec_fidelity import (
    closure_prompt_contract,
    color_treatment_prompt_contract,
    detect_closure_caption_mismatch,
    detect_color_treatment_text_mismatch,
    normalize_color_treatment,
    piece_color_treatment,
)


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
