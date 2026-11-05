"""Final Professional Tech Pack quality/fidelity regressions (offline, $0 AI).

Covers demonstrated remaining defects from the FR-* audit matrix:
- color_treatment drift must change professional input fingerprint (PDF dirty / auth)
- heuristic enrich must not invent shell fabric from color_hint alone
- construction/BOM must not invent zipper/buttons when closure is unverified
- flat/detail prompts must carry gradient/stripe + closure honesty
"""

from __future__ import annotations

from copy import deepcopy

from app.services.techpack_ai import enrich_spec_heuristic
from app.services.techpack_ai_professional import OpenAIProfessionalProvider
from app.services.techpack_compatibility import (
    closure_hardware_unverified,
    filter_bom_rows,
    filter_construction_steps,
)
from app.services.techpack_flats import default_bom, default_construction_steps
from app.services.techpack_spec import default_spec
from app.services.techpack_structure import (
    INPUT_FINGERPRINT_VERSION,
    professional_input_fingerprint,
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


def test_input_fingerprint_version_includes_color_treatment():
    assert INPUT_FINGERPRINT_VERSION >= 3


def test_color_treatment_change_same_hint_changes_professional_fingerprint():
    """Gradient→solid with identical color_hint must invalidate Professional inputs."""
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

    fp_g = professional_input_fingerprint(spec_g, [gradient])
    fp_s = professional_input_fingerprint(spec_s, [solid])
    assert fp_g != fp_s


def test_fabric_pattern_change_changes_professional_fingerprint():
    striped = _dress_piece(fabric_pattern="diagonal stripes")
    solid = _dress_piece(fabric_pattern="solid")
    spec_a = default_spec(look_summary="striped")
    spec_a["outfit"] = {"pieces": [striped], "piece_count": 1}
    spec_b = default_spec(look_summary="striped")
    spec_b["outfit"] = {"pieces": [solid], "piece_count": 1}
    assert professional_input_fingerprint(spec_a, [striped]) != professional_input_fingerprint(
        spec_b, [solid]
    )


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
    assert shell.get("suggestion") != "cotton" or shell.get("source") != "estimate"


def test_enrich_clears_legacy_color_hint_fabric_invention():
    spec = default_spec(look_summary="fitted pink dress")
    piece = _dress_piece(
        materials={
            "shell": {
                "name": "pink fabric",
                "suggestion": "cotton",
                "source": "estimate",
            }
        }
    )
    spec["outfit"] = {"pieces": [piece], "piece_count": 1}
    enriched = enrich_spec_heuristic(spec)
    out = enriched["outfit"]["pieces"][0]
    mats = out.get("materials") if isinstance(out.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    assert "pink fabric" not in str(shell.get("name") or "").lower()


def test_default_construction_and_bom_do_not_assert_invented_hardware():
    steps = default_construction_steps("shirt")
    joined = " ".join(str(s.get("instruction")) for s in steps).lower()
    assert "install closure (buttons/placket/zipper)" not in joined
    assert "do not invent" in joined or "if designed" in joined

    bom = default_bom("shirt", color_hint="red")
    items = " ".join(str(r.get("item")) for r in bom).lower()
    assert "buttons or zipper" not in items
    assert any("if designed" in str(r.get("item") or "").lower() for r in bom)
    # color hint stays in notes — not fabric identity
    assert all(str(r.get("item") or "").lower() != "red shell" for r in bom)


def test_filter_strips_invented_closure_when_pull_on():
    piece = _dress_piece(closures={"type": "pull-on", "notes": "No zipper visible"})
    analysis = {"closure_visible": "none visible — pull-on", "sleeves": "long sleeves"}
    assert closure_hardware_unverified(analysis=analysis, piece=piece) is True

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
    assert "zipper" in text  # mentioned as forbidden, not as install target of hardware line

    bom = filter_bom_rows(
        [
            {
                "item": "Buttons or zipper",
                "qty": "TBD",
                "unit": "pcs",
                "source": "estimate",
                "notes": "Confirm closure choice",
            }
        ],
        analysis=analysis,
        piece=piece,
    )
    assert bom[0]["qty"] == "UNVERIFIED"
    assert "if designed" in str(bom[0]["item"]).lower()


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
        assert "do not invent zipper" in prompt.lower() or "only show zipper" in prompt.lower()
        assert "closure_visible" in prompt
