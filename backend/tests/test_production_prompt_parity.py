"""P1 #54 offline production-prompt parity / quality-preservation gates.

No live OpenAI. Reconstructs full edit briefs from mocked vision JSON for
representative FashionRise designs and asserts professional illustration
instructions survive assembly (including under evidence pressure).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import sketch_openai

# Style anchors present on production WEB-V4E (2cbc1ad0) and retained on migration.
_STYLE_ANCHORS = (
    "Professionally refine THIS uploaded fashion sketch",
    "SOURCE OF TRUTH",
    "PRESERVE exactly from visible evidence",
    "fabric/textile patterns",
    "UPGRADE construction",
    "fabric folds",
    "crisp repeating textile patterns",
    "Do NOT invent a different garment",
    "faint watercolor",
    "Avoid photorealism, photography, CGI",
)

_SCENARIOS: dict[str, dict[str, Any]] = {
    "detailed_dress_textile": {
        "summary": "Long printed evening dress with structured bodice",
        "image_prompt": (
            "Preserve the floral foulard print scale on the skirt and the bias drape at the hem; "
            "keep the sweetheart neckline and slim straps exactly as drawn."
        ),
        "design_identity": {
            "garment_category": "evening dress",
            "silhouette": "fitted bodice with flowing midi skirt",
            "pose": "three-quarter fashion croquis with weight on the back leg",
            "neckline": "sweetheart",
            "sleeve_type": "thin strap",
            "sleeve_length": "sleeveless",
            "hemline": "midi",
            "main_colors": "ivory and coral",
            "fabric_patterns": "repeating coral floral foulard print",
            "accessories": "thin gold chain belt",
            "asymmetry_notes": "hem slightly longer at the trailing side",
            "distinctive_details": "structured bodice seams, bias-cut skirt panels",
        },
        "must_include": ("floral foulard", "sweetheart", "coral"),
    },
    "asymmetric_croquis_pose": {
        "summary": "Asymmetric jumpsuit on a dynamic croquis",
        "image_prompt": "Keep the lifted bent knee and hand-on-hip exactly; do not square the pose.",
        "design_identity": {
            "garment_category": "jumpsuit",
            "silhouette": "wide-leg jumpsuit",
            "pose": (
                "asymmetric fashion stance with one bent leg angled away from the "
                "supporting leg and one hand on the hip"
            ),
            "neckline": "deep V neckline",
            "sleeve_type": "flowing",
            "sleeve_length": "long",
            "hemline": "full length",
            "main_colors": "hot pink",
            "fabric_patterns": "solid with subtle tonal weave",
            "accessories": "wide-brimmed hat",
            "asymmetry_notes": "asymmetric leg stance",
            "distinctive_details": "wide-brim hat, deep V, flowing sleeves",
            "pose_lock": {
                "torso_orientation": "slight three-quarter fashion tilt",
                "supporting_leg": "one leg planted as the standing support",
                "free_leg": "opposite leg bent with knee lifted and foot angled",
                "arm_positions": "one hand on hip; other arm relaxed",
            },
        },
        "must_include": ("hand on the hip", "wide-brim", "hot pink"),
    },
    "swimwear_two_piece": {
        "summary": "Coordinated bikini two-piece swimsuit",
        "image_prompt": "Preserve triangle top ties and high-cut bottoms; keep teal color blocking.",
        "design_identity": {
            "garment_category": "bikini two-piece swimsuit",
            "silhouette": "triangle top with high-cut bottoms",
            "pose": "front-facing fashion croquis, relaxed arms",
            "neckline": "triangle bikini top",
            "sleeve_type": "none",
            "sleeve_length": "sleeveless",
            "hemline": "high-cut brief",
            "main_colors": "teal and white",
            "fabric_patterns": "solid teal with white edge binding",
            "accessories": "none",
            "asymmetry_notes": "",
            "distinctive_details": "side-tie bottoms, thin shoulder strings",
        },
        "must_include": ("bikini", "teal", "high-cut"),
    },
    "swim_shorts_coordinated_top": {
        "summary": "Orange long-sleeve rash top with blue swim shorts",
        "image_prompt": "Keep the orange rashguard and navy board-short length; preserve side pocket flaps.",
        "design_identity": {
            "garment_category": "swim set",
            "silhouette": "fitted long-sleeve top with mid-thigh shorts",
            "pose": "upright croquis, feet slightly apart",
            "neckline": "crew",
            "sleeve_type": "set-in",
            "sleeve_length": "long",
            "hemline": "mid-thigh shorts",
            "main_colors": "orange top, navy shorts",
            "fabric_patterns": "matte stretch jersey top; quick-dry shorts",
            "accessories": "drawstring waist",
            "asymmetry_notes": "",
            "distinctive_details": "contrasting white waistband stripe on shorts",
        },
        "must_include": ("orange", "navy", "shorts"),
    },
    "accessories_texture_shading": {
        "summary": "Wool coat with scarf and textured weave",
        "image_prompt": (
            "Show brushed wool texture and soft scarf folds; keep tortoise buttons and herringbone pattern."
        ),
        "design_identity": {
            "garment_category": "coat",
            "silhouette": "double-breasted knee-length coat",
            "pose": "walking fashion pose with slight forward step",
            "neckline": "notched lapel",
            "sleeve_type": "set-in",
            "sleeve_length": "long",
            "hemline": "knee",
            "main_colors": "camel and charcoal",
            "fabric_patterns": "camel herringbone wool",
            "accessories": "fringed scarf, tortoise buttons",
            "asymmetry_notes": "scarf draped longer on the left",
            "distinctive_details": "visible fabric folds at elbow and scarf drape",
        },
        "must_include": ("herringbone", "scarf", "tortoise"),
    },
}


def _structured(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": scenario["summary"],
        "image_prompt": scenario["image_prompt"],
        "polish_bullets": ["Refine seam clarity", "Keep textile scale"],
        "design_identity": scenario["design_identity"],
    }


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_representative_prompts_retain_professional_illustration_style(name: str):
    scenario = _SCENARIOS[name]
    prompt = sketch_openai._build_image_prompt(_structured(scenario), scenario["summary"])
    assert isinstance(prompt, str) and prompt
    assert len(prompt) <= sketch_openai.IMAGE_PROMPT_MAX_CHARS + 50  # packing budget guard
    for anchor in _STYLE_ANCHORS:
        assert anchor in prompt, f"{name}: missing style anchor {anchor!r}"
    # Garment-first / croquis language
    assert "fashion" in prompt.lower()
    assert "illustration" in prompt.lower()
    for token in scenario["must_include"]:
        assert token.lower() in prompt.lower(), f"{name}: missing design token {token!r}"


def test_style_instructions_survive_verbose_evidence_pressure():
    """Photorealism ban and PRESERVE/UPGRADE frame must not be crowded out."""
    huge = ("verbose design note " * 400).strip()
    structured = {
        "summary": "Pressure-test packing",
        "image_prompt": huge,
        "design_identity": {
            "garment_category": "dress",
            "silhouette": "A-line",
            "pose": "front croquis",
            "neckline": "round",
            "sleeve_type": "cap",
            "sleeve_length": "short",
            "hemline": "knee",
            "main_colors": "red",
            "fabric_patterns": "polka dots",
            "accessories": "belt",
            "asymmetry_notes": "",
            "distinctive_details": "contrast stitching",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    for anchor in (
        "PRESERVE exactly from visible evidence",
        "UPGRADE construction",
        "Avoid photorealism, photography, CGI",
        "Do NOT invent a different garment",
    ):
        assert anchor in prompt
    # Must not be a hard mid-string chop that drops the reserved avoid-line.
    assert prompt.rstrip().endswith("watermark.") or "Avoid photorealism" in prompt


def test_no_prompt_regression_to_photoreal_or_editorial_language():
    prompt = sketch_openai._build_image_prompt(
        _structured(_SCENARIOS["detailed_dress_textile"]),
        _SCENARIOS["detailed_dress_textile"]["summary"],
    )
    banned = (
        "photorealistic render",
        "dslr photograph",
        "lookbook photography",
        "cgi character",
    )
    # The avoid-line mentions photorealism; ensure we are not instructing TO use it.
    assert "Avoid photorealism" in prompt
    for phrase in banned:
        assert phrase not in prompt.lower()
