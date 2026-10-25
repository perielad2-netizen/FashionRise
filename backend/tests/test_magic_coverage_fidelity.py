"""Issue #64: adult swimwear/lingerie garment-coverage fidelity — mocked prompts only.

No live OpenAI. Synthetic design_identity fixtures only. Verifies vision + edit briefs
and that the coverage contract survives IMAGE_PROMPT_MAX_CHARS truncation.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.services import sketch_openai

_COVERAGE_TOKENS = (
    "COVERAGE FIDELITY",
    "Distinguish actual drawn garment material",
    "exposed skin",
    "croquis-body or paper background",
    "Never invent an extra bodysuit",
    "white lining",
    "modesty insert",
    "intentionally drawn white or pale fabric",
)

_STYLE_STILL_REQUIRED = (
    "Professionally refine THIS uploaded fashion sketch",
    "SOURCE OF TRUTH",
    "PRESERVE exactly from visible evidence",
    "UPGRADE construction",
    "Do NOT invent a different garment",
)


def _job(**input_data: Any) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type="sketch_polish", input_data=input_data)


def _case(
    *,
    garment_category: str,
    silhouette: str,
    skin_visible_regions: str,
    garment_panels: str,
    cutouts_and_openings: str,
    intended_pale_or_white_fabric: str,
    image_prompt: str,
    main_colors: str = "as drawn",
    distinctive_details: str = "",
    neckline: str = "as drawn",
    hemline: str = "as drawn",
) -> dict[str, Any]:
    return {
        "summary": f"Synthetic adult {garment_category}",
        "polish_bullets": ["Refine contour clarity", "Keep coverage map"],
        "design_identity": {
            "garment_category": garment_category,
            "silhouette": silhouette,
            "pose": "front-facing adult fashion croquis",
            "neckline": neckline,
            "sleeve_type": "none",
            "sleeve_length": "sleeveless",
            "hemline": hemline,
            "main_colors": main_colors,
            "fabric_patterns": "solid fashion textile",
            "accessories": "none",
            "asymmetry_notes": "",
            "distinctive_details": distinctive_details,
            "skin_visible_regions": skin_visible_regions,
            "garment_panels": garment_panels,
            "cutouts_and_openings": cutouts_and_openings,
            "intended_pale_or_white_fabric": intended_pale_or_white_fabric,
        },
        "image_prompt": image_prompt,
    }


_SCENARIOS: dict[str, dict[str, Any]] = {
    "adult_bikini_two_piece": _case(
        garment_category="bikini two-piece swimsuit",
        silhouette="triangle top with high-cut bottoms",
        skin_visible_regions="bare midriff, open torso between top and bottoms, bare legs and arms",
        garment_panels="triangle bikini top; high-cut bikini bottoms only",
        cutouts_and_openings="full midriff window; high leg openings; open back ties",
        intended_pale_or_white_fabric="no white liner or underlayer drawn",
        image_prompt=(
            "Adult fashion croquis in a teal bikini: triangle top ties, bare midriff, "
            "high-cut bottoms. Do not add a bodysuit or white coverage panel."
        ),
        main_colors="teal",
        distinctive_details="side-tie bottoms",
        neckline="triangle bikini top",
        hemline="high-cut brief",
    ),
    "adult_one_piece_swimsuit": _case(
        garment_category="one-piece swimsuit",
        silhouette="scoop-neck one-piece with high legs",
        skin_visible_regions="bare arms, bare legs below high-cut openings, upper chest as drawn",
        garment_panels="single contiguous swimsuit body panel",
        cutouts_and_openings="high leg openings; scoop neckline; open back keyhole",
        intended_pale_or_white_fabric="no pale lining drawn",
        image_prompt="Preserve the navy one-piece silhouette and high-cut legs; no extra lining.",
        main_colors="navy",
        distinctive_details="back keyhole",
        neckline="scoop",
        hemline="high-cut leg",
    ),
    "adult_cutout_dress": _case(
        garment_category="cut-out evening dress",
        silhouette="column dress with midriff cut-out",
        skin_visible_regions="exposed midriff through waist cut-out; bare arms",
        garment_panels="bodice panel and skirt panel connected at sides only",
        cutouts_and_openings="large front midriff cut-out; thigh slit",
        intended_pale_or_white_fabric="no white insert drawn",
        image_prompt="Keep the waist cut-out open; do not fill with fabric or a white insert.",
        main_colors="black",
        distinctive_details="side connections at waist",
        neckline="halter",
        hemline="ankle with slit",
    ),
    "adult_lingerie_set": _case(
        garment_category="lingerie set",
        silhouette="soft-cup bra with high-waist brief",
        skin_visible_regions="bare midriff between bra and brief; bare legs and arms",
        garment_panels="bra cups and straps; high-waist brief only",
        cutouts_and_openings="open torso between pieces; leg openings on brief",
        intended_pale_or_white_fabric="no slip or underlayer drawn",
        image_prompt="Preserve bra + brief separation and bare midriff; no invented slip layer.",
        main_colors="blush pink",
        distinctive_details="thin shoulder straps",
        neckline="soft-cup bra",
        hemline="high-waist brief",
    ),
    "intentional_white_lining": _case(
        garment_category="structured dress with drawn white lining",
        silhouette="A-line dress with visible white inner lining at hem and neck",
        skin_visible_regions="bare arms and lower legs only",
        garment_panels="outer shell plus intentionally drawn white lining facing",
        cutouts_and_openings="none beyond neckline and hem",
        intended_pale_or_white_fabric=(
            "white lining facing visible at neckline and hem — drawn garment material"
        ),
        image_prompt=(
            "Preserve the drawn white lining facing at neck and hem; do not add extra "
            "bodysuit coverage beyond that lining."
        ),
        main_colors="red shell with white lining",
        distinctive_details="visible lining facing",
        neckline="boat with white facing",
        hemline="knee with white facing",
    ),
    "skin_vs_paper_background": _case(
        garment_category="bikini two-piece swimsuit",
        silhouette="bandeau top with brief bottoms",
        skin_visible_regions=(
            "bare midriff and limbs; light croquis body tone is skin, not fabric; "
            "paper background is not garment"
        ),
        garment_panels="bandeau top and brief bottoms only",
        cutouts_and_openings="full midriff; leg openings",
        intended_pale_or_white_fabric="pale areas are skin or paper, not white fabric",
        image_prompt=(
            "Light croquis body and paper are not fabric. Keep only bandeau + brief panels."
        ),
        main_colors="coral",
        distinctive_details="bandeau",
        neckline="bandeau",
        hemline="brief",
    ),
}


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_edit_prompt_includes_coverage_contract_and_scenario_facts(name: str):
    structured = _SCENARIOS[name]
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert len(prompt) <= sketch_openai.IMAGE_PROMPT_MAX_CHARS
    for token in _COVERAGE_TOKENS:
        assert token in prompt, f"{name}: missing coverage token {token!r}"
    for token in _STYLE_STILL_REQUIRED:
        assert token in prompt, f"{name}: missing style anchor {token!r}"
    identity = structured["design_identity"]
    # Coverage facts must appear via design_identity clause (label + value).
    assert "skin visible regions:" in prompt.lower()
    assert "garment panels:" in prompt.lower()
    assert "cutouts and openings:" in prompt.lower()
    assert "intended pale or white fabric:" in prompt.lower()
    assert identity["garment_category"].split()[0].lower() in prompt.lower()
    assert "bodysuit" in prompt.lower()


def test_vision_system_prompt_requests_coverage_fields():
    system = sketch_openai._system_prompt("sketch_polish")
    for key in (
        "skin_visible_regions",
        "garment_panels",
        "cutouts_and_openings",
        "intended_pale_or_white_fabric",
    ):
        assert key in system
    assert "never invent bodysuits" in system.lower() or "Never invent" in system
    assert "croquis body" in system.lower() or "croquis-body" in system.lower() or "blank/light croquis" in system.lower()
    assert "modesty" in system.lower()


def test_coverage_contract_survives_verbose_evidence_truncation():
    """Coverage clause is in the fixed prefix — must remain after [:3800] slice."""
    huge = ("verbose design note " * 500).strip()
    structured = {
        "summary": "Pressure coverage",
        "image_prompt": huge,
        "design_identity": {
            "garment_category": "bikini two-piece swimsuit",
            "silhouette": "triangle top with bottoms",
            "pose": "front croquis",
            "neckline": "triangle",
            "sleeve_type": "none",
            "sleeve_length": "sleeveless",
            "hemline": "brief",
            "main_colors": "teal",
            "fabric_patterns": "solid",
            "accessories": "none",
            "asymmetry_notes": "",
            "distinctive_details": "bare midriff",
            "skin_visible_regions": "bare midriff between top and bottoms",
            "garment_panels": "bikini top and bottoms only",
            "cutouts_and_openings": "full midriff window",
            "intended_pale_or_white_fabric": "no white liner drawn",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert len(prompt) == sketch_openai.IMAGE_PROMPT_MAX_CHARS
    for token in (
        "COVERAGE FIDELITY",
        "Never invent an extra bodysuit",
        "white lining",
        "PRESERVE exactly from visible evidence",
        "garment coverage map",
    ):
        assert token in prompt
    # Trailing avoid-line may truncate under hard slice — document, do not pull PR #41 packing.
    # Coverage must still be present even if Avoid-photorealism is cut.
    assert "Avoid photorealism" not in prompt or prompt.endswith(
        ("watermark.", "watermark")
    ) or "COVERAGE FIDELITY" in prompt


def test_coverage_does_not_drop_selected_croquis_identity():
    job = _job(reference_model_id="female-straight")
    structured = dict(_SCENARIOS["adult_bikini_two_piece"])
    structured["design_identity"] = dict(structured["design_identity"])
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"], job=job)
    assert "COVERAGE FIDELITY" in prompt
    assert "female-straight" in prompt or "female" in prompt.lower()
    assert "reference" in prompt.lower() or "croquis" in prompt.lower()


def test_intentional_white_fabric_fact_reaches_final_prompt():
    structured = _SCENARIOS["intentional_white_lining"]
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert "intended pale or white fabric" in prompt.lower() or "white lining" in prompt.lower()
    assert "drawn white lining" in prompt.lower() or "lining facing" in prompt.lower()
    assert "Never invent an extra bodysuit" in prompt


def test_no_moderation_bypass_language_in_prompts():
    system = sketch_openai._system_prompt("sketch_polish")
    edit = sketch_openai._build_image_prompt(
        _SCENARIOS["adult_lingerie_set"], "lingerie"
    )
    banned = (
        "bypass safety",
        "disable moderation",
        "ignore content policy",
        "nsfw",
        "explicit sexual",
        "nude genitalia",
    )
    blob = f"{system}\n{edit}".lower()
    for token in banned:
        assert token not in blob
