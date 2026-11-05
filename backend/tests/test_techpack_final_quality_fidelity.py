"""Final Professional Tech Pack quality/fidelity regressions (offline, $0 AI).

PM hardening amendment (#187):
- Historical V1/V2 fingerprints must match approved-main goldens.
- V3 alone carries color_treatment / fabric_pattern.
- Designer-authored construction/BOM survive filtering.
- PDF text reflects confirmed vs UNVERIFIED closures.
- Legacy material cleanup only targets color_hint placeholders.
"""

from __future__ import annotations

import io
from copy import deepcopy
from types import SimpleNamespace

from pypdf import PdfReader

from app.services.techpack_ai import enrich_spec_heuristic
from app.services.techpack_ai_professional import OpenAIProfessionalProvider
from app.services.techpack_compatibility import (
    closure_explicitly_absent,
    closure_hardware_confirmed,
    closure_hardware_named,
    closure_hardware_unverified,
    closure_lacks_hardware_evidence,
    filter_bom_rows,
    filter_construction_steps,
)
from app.services.techpack_flats import default_bom, default_construction_steps
from app.services.techpack_pdf import build_techpack_pdf
from app.services.techpack_spec import default_spec
from app.services.techpack_structure import (
    INPUT_FINGERPRINT_VERSION,
    professional_input_fingerprint,
)

# Golden hashes computed from approved main 1cab0a7b historical snapshot logic
# against GOLDEN_FIXTURE (gradient/color fields present but ignored by V1/V2).
GOLDEN_V1 = "46a8cb1250f6b74171c370c2d66daa3f43d17871106989daa6ddd2fd2568ff06"
GOLDEN_V2 = "1cc025c3241394533e4f7c8d0dccbadd2053ae419f084fc3e249ffd36c445198"

GOLDEN_PIECE = {
    "id": "piece-dress-1",
    "category": "dress",
    "role": "one_piece",
    "label": "Pink Dress",
    "color_hint": "pink",
    "color_treatment": {
        "mode": "gradient",
        "stops": ["#FF0000", "#FFFFFF"],
        "direction": "top-to-bottom",
        "placement": "body",
        "designer_confirmed": True,
        "angle": 90,
    },
    "fabric_pattern": "diagonal stripes",
    "category_user_confirmed": True,
    "detection_source": "heuristic",
    "materials": {
        "shell": {"name": "cotton", "composition": "100% cotton"},
        "lining": {},
    },
    "finished_measurements": {
        "chest_bust": {"value": 90, "unit": "cm", "source": "designer"},
        "garment_length": {"value": 110, "unit": "cm", "source": "designer"},
    },
    "closures": {"type": "pull-on", "notes": "No zipper"},
    "fit": {"silhouette": "fitted"},
    "visible_details": {"neckline": "deep V", "hem_finish": "clean"},
}

GOLDEN_SPEC = {
    "units": "cm",
    "look_notes": "fitted pink dress",
    "designer_notes": "confirm stripe match",
    "size_system": "EU",
    "sample_size": "M",
    "quantity": 1,
    "body": {"bust": {"value": 81, "unit": "cm", "source": "designer"}},
    "preferences": {"fit_preference": "regular", "notes": ""},
    "look_design_identity": {"summary": "pink dress"},
    "outfit": {"pieces": [GOLDEN_PIECE], "piece_count": 1},
}

GOLDEN_DRAFT = SimpleNamespace(
    title="Golden Dress",
    style_code="FR-GOLD",
    look_id="look-gold-1",
    front_job_id="front-job-1",
    back_job_id=None,
)


def _dress_piece(**overrides):
    base = {
        "id": "piece-dress-1",
        "category": "dress",
        "role": "one_piece",
        "label": "Pink Dress",
        "color_hint": "pink",
        "closures": {"type": "pull-on", "notes": "No zipper visible"},
        "fit": {"silhouette": "fitted"},
        "finished_measurements": {},
        "materials": {},
    }
    base.update(overrides)
    return base


def _pdf_text(spec: dict, *, style_code: str = "QA") -> str:
    pdf, _pages = build_techpack_pdf(
        title=style_code,
        style_code=style_code,
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id="offline-qa",
        front_image=None,
        back_image=None,
        spec=spec,
    )
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)


def test_input_fingerprint_version_is_v3():
    assert INPUT_FINGERPRINT_VERSION == 3


def test_golden_v1_fingerprint_matches_approved_main():
    fp = professional_input_fingerprint(
        GOLDEN_SPEC, [GOLDEN_PIECE], version=1, draft=GOLDEN_DRAFT
    )
    assert fp == GOLDEN_V1


def test_golden_v2_fingerprint_matches_approved_main():
    fp = professional_input_fingerprint(
        GOLDEN_SPEC, [GOLDEN_PIECE], version=2, draft=GOLDEN_DRAFT
    )
    assert fp == GOLDEN_V2


def test_v1_v2_ignore_color_treatment_and_fabric_pattern_drift():
    solid = deepcopy(GOLDEN_PIECE)
    solid["color_treatment"] = {
        "mode": "solid",
        "stops": ["#FF0000"],
        "direction": "",
        "placement": "body",
        "designer_confirmed": True,
    }
    solid["fabric_pattern"] = "solid"
    spec_s = deepcopy(GOLDEN_SPEC)
    spec_s["outfit"] = {"pieces": [solid], "piece_count": 1}
    assert professional_input_fingerprint(
        GOLDEN_SPEC, [GOLDEN_PIECE], version=1, draft=GOLDEN_DRAFT
    ) == professional_input_fingerprint(spec_s, [solid], version=1, draft=GOLDEN_DRAFT)
    assert professional_input_fingerprint(
        GOLDEN_SPEC, [GOLDEN_PIECE], version=2, draft=GOLDEN_DRAFT
    ) == professional_input_fingerprint(spec_s, [solid], version=2, draft=GOLDEN_DRAFT)


def test_color_treatment_change_same_hint_changes_v3_fingerprint_only():
    gradient = _dress_piece(
        color_treatment={
            "mode": "gradient",
            "stops": ["#FF0000", "#FFFFFF"],
            "direction": "top-to-bottom",
            "placement": "body",
            "designer_confirmed": True,
            "angle": 90,
        }
    )
    solid = deepcopy(gradient)
    solid["color_treatment"] = {
        "mode": "solid",
        "stops": ["#FF0000"],
        "direction": "",
        "placement": "body",
        "designer_confirmed": True,
    }
    spec_g = default_spec(look_summary="gradient dress")
    spec_g["outfit"] = {"pieces": [gradient], "piece_count": 1}
    spec_s = default_spec(look_summary="gradient dress")
    spec_s["outfit"] = {"pieces": [solid], "piece_count": 1}

    assert professional_input_fingerprint(spec_g, [gradient], version=3) != (
        professional_input_fingerprint(spec_s, [solid], version=3)
    )
    assert professional_input_fingerprint(spec_g, [gradient], version=2) == (
        professional_input_fingerprint(spec_s, [solid], version=2)
    )


def test_fabric_pattern_change_changes_v3_fingerprint():
    striped = _dress_piece(fabric_pattern="diagonal stripes")
    solid = _dress_piece(fabric_pattern="solid")
    spec_a = default_spec(look_summary="striped")
    spec_a["outfit"] = {"pieces": [striped], "piece_count": 1}
    spec_b = default_spec(look_summary="striped")
    spec_b["outfit"] = {"pieces": [solid], "piece_count": 1}
    assert professional_input_fingerprint(spec_a, [striped], version=3) != (
        professional_input_fingerprint(spec_b, [solid], version=3)
    )


def test_v3_payload_carries_explicit_version():
    from app.services.techpack_structure import _fingerprint_payload_v3

    payload = _fingerprint_payload_v3(GOLDEN_SPEC, [GOLDEN_PIECE], draft=GOLDEN_DRAFT)
    assert payload["v"] == 3
    assert "color_treatment" in payload["pieces"][0]
    assert "fabric_pattern" in payload["pieces"][0]


def test_enrich_does_not_invent_shell_from_color_hint():
    spec = default_spec(look_summary="fitted pink striped dress")
    piece = _dress_piece()
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    out = enriched["outfit"]["pieces"][0]
    mats = out.get("materials") if isinstance(out.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    name = str(shell.get("name") or "")
    assert "pink fabric" not in name.lower()


def test_enrich_clears_only_legacy_color_hint_fabric_placeholder():
    spec = default_spec(look_summary="fitted pink dress")
    piece = _dress_piece(
        color_hint="pink",
        materials={
            "shell": {
                "name": "pink fabric",
                "suggestion": "cotton",
                "source": "estimate",
            }
        },
    )
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    out = enriched["outfit"]["pieces"][0]
    mats = out.get("materials") if isinstance(out.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    assert "pink fabric" not in str(shell.get("name") or "").lower()


def test_enrich_preserves_legitimate_fabric_description_ending_in_fabric():
    spec = default_spec(look_summary="silk dress")
    piece = _dress_piece(
        color_hint="burgundy",
        materials={
            "shell": {
                "name": "Italian silk fabric",
                "composition": "100% silk",
                "source": "estimate",
            }
        },
    )
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    shell = enriched["outfit"]["pieces"][0]["materials"]["shell"]
    assert shell["name"] == "Italian silk fabric"
    assert shell["composition"] == "100% silk"


def test_enrich_preserves_designer_confirmed_shell():
    spec = default_spec(look_summary="cotton dress")
    piece = _dress_piece(
        color_hint="pink",
        materials={
            "shell": {
                "name": "pink fabric",
                "source": "estimate",
                "designer_confirmed": True,
                "composition": "100% cotton",
            }
        },
    )
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    shell = enriched["outfit"]["pieces"][0]["materials"]["shell"]
    assert shell["name"] == "pink fabric"
    assert shell.get("designer_confirmed") is True


def test_enrich_preserves_unknown_shell_material():
    spec = default_spec(look_summary="dress")
    piece = _dress_piece(
        color_hint="",
        materials={"shell": {"name": "Unknown shell material", "source": "designer"}},
    )
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    shell = enriched["outfit"]["pieces"][0]["materials"]["shell"]
    assert shell["name"] == "Unknown shell material"


def test_default_construction_and_bom_do_not_assert_invented_hardware():
    steps = default_construction_steps("shirt")
    joined = " ".join(str(s.get("instruction")) for s in steps).lower()
    assert "install closure (buttons/placket/zipper)" not in joined

    bom = default_bom("shirt", color_hint="red")
    items = " ".join(str(r.get("item")) for r in bom).lower()
    assert "buttons or zipper" not in items
    assert all(str(r.get("item") or "").lower() != "red shell" for r in bom)


def test_filter_preserves_designer_authored_zipper_step_with_warning():
    piece = _dress_piece(closures={"type": "pull-on", "notes": "No zipper visible"})
    analysis = {"closure_visible": "none visible — pull-on", "sleeves": "long sleeves"}
    warnings: list[dict] = []
    original = "Install center-back invisible zipper; understitch and press."
    steps = filter_construction_steps(
        [
            {
                "step": 4,
                "instruction": original,
                "source": "designer",
                "id": "step-zip",
            }
        ],
        analysis=analysis,
        piece=piece,
        warnings_out=warnings,
    )
    assert steps[0]["instruction"] == original
    assert steps[0]["id"] == "step-zip"
    assert steps[0]["step"] == 4
    assert steps[0]["source"] == "designer"
    assert warnings
    assert warnings[0]["code"] == "construction_closure_conflict"
    # Idempotent
    again = filter_construction_steps(steps, analysis=analysis, piece=piece, warnings_out=[])
    assert again[0]["instruction"] == original


def test_filter_preserves_explicitly_confirmed_step_even_with_source_designer_only_provenance_rules():
    piece = _dress_piece(
        closures={
            "type": "invisible zipper",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    steps = filter_construction_steps(
        [
            {
                "step": 1,
                "instruction": "Install invisible zipper at CB.",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        analysis=None,  # missing analysis
        piece=piece,
    )
    assert steps[0]["instruction"] == "Install invisible zipper at CB."
    assert steps[0]["review_status"] == "confirmed"


def test_filter_rewrites_estimate_zipper_when_pull_on():
    piece = _dress_piece(closures={"type": "pull-on", "notes": "No zipper visible"})
    analysis = {"closure_visible": "none visible — pull-on"}
    assert closure_lacks_hardware_evidence(analysis=analysis, piece=piece) is True
    steps = filter_construction_steps(
        [
            {
                "step": 1,
                "instruction": "Install closure (buttons/placket/zipper) and press.",
                "source": "estimate",
            }
        ],
        analysis=analysis,
        piece=piece,
    )
    text = str(steps[0]["instruction"]).lower()
    assert "do not invent" in text
    # Idempotent
    again = filter_construction_steps(steps, analysis=analysis, piece=piece)
    assert again[0]["instruction"] == steps[0]["instruction"]


def test_filter_marks_estimate_named_zipper_unverified_not_destroyed():
    piece = _dress_piece(
        closures={"type": "zipper", "source": "estimate", "notes": "AI guess"}
    )
    assert closure_hardware_unverified(piece=piece) is True
    assert closure_hardware_confirmed(piece=piece) is False
    original = "Install CF zipper and topstitch."
    steps = filter_construction_steps(
        [{"step": 2, "instruction": original, "source": "estimate"}],
        analysis={"closure_visible": "center-front zipper"},
        piece=piece,
    )
    assert steps[0]["instruction"] == original
    assert steps[0]["review_status"] == "proposed_unverified"


def test_filter_bom_preserves_confirmed_hardware_quantity():
    piece = _dress_piece(
        closures={
            "type": "buttons",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    rows = filter_bom_rows(
        [
            {
                "item": "Buttons",
                "qty": "8",
                "unit": "pcs",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        piece=piece,
    )
    assert rows[0]["qty"] == "8"
    assert rows[0]["item"] == "Buttons"


def test_filter_bom_marks_unverified_generic_hardware():
    piece = _dress_piece(closures={"type": "pull-on"})
    rows = filter_bom_rows(
        [
            {
                "item": "Buttons or zipper",
                "qty": "TBD",
                "unit": "pcs",
                "source": "estimate",
            }
        ],
        piece=piece,
    )
    assert rows[0]["qty"] == "UNVERIFIED"
    assert "unverified" in str(rows[0].get("review_state") or "").lower()


def test_pdf_retains_designer_confirmed_zipper_instruction():
    piece = _dress_piece(
        closures={
            "type": "invisible zipper",
            "designer_confirmed": True,
            "review_status": "confirmed",
        },
        construction_steps=[
            {
                "step": 1,
                "instruction": "Install invisible CB zipper; understitch placket.",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        bom=[
            {
                "item": "Invisible zipper",
                "qty": "1",
                "unit": "pcs",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        illustrations={},  # missing analysis
    )
    spec = default_spec(look_summary="zip dress")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-ZIP")
    assert "Install invisible CB zipper" in text
    assert "Invisible zipper" in text
    assert "1" in text


def test_pdf_retains_designer_confirmed_buttons():
    piece = _dress_piece(
        category="shirt",
        label="QA Shirt",
        closures={
            "type": "buttons",
            "designer_confirmed": True,
            "review_status": "confirmed",
        },
        construction_steps=[
            {
                "step": 1,
                "instruction": "Sew buttonholes and attach buttons.",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        bom=[
            {
                "item": "Buttons",
                "qty": "7",
                "unit": "pcs",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        ],
        illustrations={},
    )
    spec = default_spec(look_summary="button shirt")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-BTN")
    assert "Sew buttonholes and attach buttons" in text
    assert "Buttons" in text


def test_pdf_pull_on_has_no_invented_install_instruction():
    piece = _dress_piece(
        closures={"type": "pull-on", "notes": "No zipper"},
        construction_steps=default_construction_steps("dress"),
        bom=default_bom("dress", color_hint="pink"),
        illustrations={"analysis": {"closure_visible": "none", "sleeves": "long"}},
    )
    # Force an estimate install line as older drafts might have.
    piece["construction_steps"] = piece["construction_steps"] + [
        {
            "step": 99,
            "instruction": "Install closure (buttons/placket/zipper) and press.",
            "source": "estimate",
        }
    ]
    spec = default_spec(look_summary="pull-on dress")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-PULL").lower()
    assert "install closure (buttons/placket/zipper)" not in text
    assert "do not invent" in text or "if designed" in text


def test_pdf_ai_estimated_zipper_marked_unverified():
    piece = _dress_piece(
        closures={"type": "zipper", "source": "estimate"},
        construction_steps=[
            {
                "step": 1,
                "instruction": "Install CF zipper and press.",
                "source": "estimate",
            }
        ],
        bom=[
            {
                "item": "Zipper",
                "qty": "1",
                "unit": "pcs",
                "source": "estimate",
            }
        ],
        illustrations={"analysis": {"closure_visible": "zipper at CF"}},
    )
    spec = default_spec(look_summary="est zip")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-ESTZIP")
    assert "Install CF zipper" in text
    assert "UNVERIFIED" in text


def test_flat_and_detail_prompts_include_color_treatment_and_closure_honesty():
    piece = _dress_piece(
        color_treatment={
            "mode": "gradient",
            "stops": ["#AA00FF", "#FFFFFF"],
            "direction": "top-to-bottom",
            "placement": "body",
        }
    )
    analysis = {
        "silhouette": "fitted",
        "length": "mini",
        "neckline": "deep plunging V",
        "sleeves": "long sleeves",
        "fit": "fitted",
        "fabric_pattern": "gradient",
        "stripe_direction": None,
        "colors": ["purple", "white"],
        "closure_visible": "none visible",
        "color_treatment": {"mode": "gradient", "direction": "top-to-bottom"},
        "distinctive_features": ["deep V", "gradient"],
    }
    flat = OpenAIProfessionalProvider._flat_prompt(analysis, view="front", piece=piece)
    detail = OpenAIProfessionalProvider._detail_prompt(analysis, piece=piece)
    for prompt in (flat, detail):
        assert "color_treatment_mode=gradient" in prompt
        assert "closure_visible" in prompt


# --- Final P0: closure negation before positive hardware matching -----------------


def test_confirmed_no_zipper_is_absent_not_named_hardware():
    piece = _dress_piece(
        closures={
            "type": "no zipper",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    assert closure_explicitly_absent(piece=piece) is True
    assert closure_hardware_named(piece=piece) is False
    assert closure_hardware_confirmed(piece=piece) is False
    assert closure_lacks_hardware_evidence(piece=piece) is True


def test_confirmed_no_buttons_is_absent_not_named_hardware():
    piece = _dress_piece(
        category="shirt",
        closures={
            "type": "no buttons",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    assert closure_explicitly_absent(piece=piece) is True
    assert closure_hardware_named(piece=piece) is False
    assert closure_hardware_confirmed(piece=piece) is False


def test_confirmed_buttonless_and_without_zipper_phrases():
    for phrase in (
        "buttonless",
        "without zipper",
        "without buttons",
        "pull-on",
        "none",
        "not visible",
    ):
        piece = _dress_piece(
            closures={
                "type": phrase,
                "designer_confirmed": True,
                "review_status": "confirmed",
            }
        )
        assert closure_explicitly_absent(piece=piece) is True, phrase
        assert closure_hardware_named(piece=piece) is False, phrase
        assert closure_hardware_confirmed(piece=piece) is False, phrase


def test_bare_dash_or_na_not_treated_as_explicit_absence():
    for phrase in ("-", "—", "na"):
        piece = _dress_piece(closures={"type": phrase})
        assert closure_explicitly_absent(piece=piece) is False, phrase


def test_confirmed_invisible_zipper_and_button_front_retained():
    zip_piece = _dress_piece(
        closures={
            "type": "invisible zipper",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    btn_piece = _dress_piece(
        category="shirt",
        closures={
            "type": "button-front placket",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    assert closure_hardware_named(piece=zip_piece) is True
    assert closure_hardware_confirmed(piece=zip_piece) is True
    assert closure_hardware_named(piece=btn_piece) is True
    assert closure_hardware_confirmed(piece=btn_piece) is True


def test_ai_analysis_zipper_alone_never_confirms_hardware():
    piece = _dress_piece(
        closures={"type": "", "source": "estimate"},
    )
    analysis = {"closure_visible": "center-front zipper visible"}
    # May be named via analysis for anti-invention filtering…
    assert closure_hardware_named(analysis=analysis, piece=piece) is True
    # …but never manufacturing-confirmed from analysis alone.
    assert closure_hardware_confirmed(analysis=analysis, piece=piece) is False
    assert closure_hardware_unverified(analysis=analysis, piece=piece) is True


def test_pdf_confirmed_no_zipper_does_not_assert_install():
    piece = _dress_piece(
        closures={
            "type": "no zipper",
            "designer_confirmed": True,
            "review_status": "confirmed",
            "notes": "Pull-on neckline finish only",
        },
        construction_steps=[
            {
                "step": 1,
                "instruction": "Install closure (buttons/placket/zipper) and press.",
                "source": "estimate",
            },
            {
                "step": 2,
                "instruction": "Finish neckline clean; no zipper.",
                "source": "designer",
                "designer_confirmed": True,
                "review_status": "confirmed",
            },
        ],
        bom=[
            {
                "item": "Buttons or zipper",
                "qty": "TBD",
                "unit": "pcs",
                "source": "estimate",
            }
        ],
        illustrations={},
    )
    spec = default_spec(look_summary="no zip dress")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-NOZIP")
    assert "Install closure (buttons/placket/zipper)" not in text
    assert "Finish neckline clean; no zipper." in text
    assert "do not invent" in text.lower() or "UNVERIFIED" in text
    # Confirmed absence must not surface as confirmed zipper hardware.
    assert closure_hardware_confirmed(piece=piece) is False


def test_pdf_confirmed_no_buttons_does_not_assert_buttons():
    piece = _dress_piece(
        category="shirt",
        label="QA No Buttons",
        closures={
            "type": "no buttons",
            "designer_confirmed": True,
            "review_status": "confirmed",
        },
        construction_steps=[
            {
                "step": 1,
                "instruction": "Sew buttonholes and attach buttons.",
                "source": "estimate",
            }
        ],
        bom=[
            {
                "item": "Buttons",
                "qty": "8",
                "unit": "pcs",
                "source": "estimate",
            }
        ],
        illustrations={},
    )
    spec = default_spec(look_summary="no buttons top")
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    text = _pdf_text(spec, style_code="QA-NOBTN").lower()
    # Estimate button install rewritten / not asserted as confirmed fact.
    assert "sew buttonholes and attach buttons" not in text or "unverified" in text
    assert closure_hardware_confirmed(piece=piece) is False


def test_seven_buttons_positive_phrase_confirmed():
    piece = _dress_piece(
        category="shirt",
        closures={
            "type": "seven buttons",
            "designer_confirmed": True,
            "review_status": "confirmed",
        }
    )
    assert closure_hardware_named(piece=piece) is True
    assert closure_hardware_confirmed(piece=piece) is True
