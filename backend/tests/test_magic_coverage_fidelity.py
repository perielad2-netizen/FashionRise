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
    "do not invent bare-skin regions",
    "COLOR FIDELITY",
    "applied garment fill",
    "outline strokes are linework",
)

_STYLE_STILL_REQUIRED = (
    "Professionally refine THIS uploaded fashion sketch",
    "SOURCE OF TRUTH",
    "PRESERVE exactly from visible evidence",
    "UPGRADE construction",
    "Do NOT invent a different garment",
    "Avoid photorealism",
    "non-photorealistic fashion illustration",
)

_PROTECTED_ANCHORS = _COVERAGE_TOKENS + _STYLE_STILL_REQUIRED


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
    "intentional_full_coverage_swimsuit": _case(
        garment_category="full-coverage one-piece swimsuit",
        silhouette="modest tank one-piece with mid-thigh legs",
        skin_visible_regions="bare arms and lower legs only — torso fully covered by swimsuit",
        garment_panels="single full-torso swimsuit panel as drawn",
        cutouts_and_openings="standard neckline and leg openings only; no midriff window",
        intended_pale_or_white_fabric="no extra lining beyond the drawn swimsuit body",
        image_prompt=(
            "Preserve the intentional full-coverage one-piece; do not cut midriff openings "
            "that were not drawn."
        ),
        main_colors="black",
        distinctive_details="tank straps",
        neckline="scoop tank",
        hemline="mid-thigh leg",
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


def test_protected_instructions_survive_verbose_evidence_truncation():
    """Coverage + non-photoreal style stay intact; only lower-priority prose is bounded."""
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
    assert len(prompt) <= sketch_openai.IMAGE_PROMPT_MAX_CHARS
    assert len(prompt) >= sketch_openai.IMAGE_PROMPT_MAX_CHARS - 40
    for token in _PROTECTED_ANCHORS:
        assert token in prompt, f"protected anchor missing under pressure: {token!r}"
    # Known structured coverage facts must win budget over the verbose flood.
    assert "bare midriff between top and bottoms" in prompt
    assert "bikini top and bottoms only" in prompt
    assert "teal" in prompt.lower()


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


def test_missing_coverage_map_does_not_invent_bare_skin_claims():
    structured = {
        "summary": "Teal swim set",
        "image_prompt": "Teal swimsuit panels as drawn on the uploaded sketch.",
        "design_identity": {
            "garment_category": "swimsuit",
            "silhouette": "as drawn",
            "main_colors": "teal",
            # coverage fields omitted entirely
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    for token in _PROTECTED_ANCHORS:
        assert token in prompt
    assert "skin visible regions:" not in prompt.lower()
    # Must not invent a concrete midriff/coverage assertion when vision omitted it.
    assert "bare midriff between" not in prompt.lower()
    assert "rely on the uploaded sketch only" in prompt.lower()


@pytest.mark.parametrize("nullish", [None, "null", "unknown", "n/a", "none", ""])
def test_null_unknown_coverage_fields_are_omitted(nullish):
    structured = {
        "summary": "Ambiguous swim look",
        "image_prompt": "Follow the uploaded sketch coverage exactly.",
        "design_identity": {
            "garment_category": "swimsuit",
            "main_colors": "coral",
            "skin_visible_regions": nullish,
            "garment_panels": nullish,
            "cutouts_and_openings": nullish,
            "intended_pale_or_white_fabric": nullish,
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert "skin visible regions:" not in prompt.lower()
    assert "garment panels:" not in prompt.lower()
    assert "cutouts and openings:" not in prompt.lower()
    assert "intended pale or white fabric:" not in prompt.lower()
    assert "COVERAGE FIDELITY" in prompt
    assert "Avoid photorealism" in prompt
    assert "coral" in prompt.lower()


def test_cutout_misread_as_white_fabric_keeps_open_cutout_evidence():
    structured = {
        "summary": "Cut-out swim dress",
        "image_prompt": (
            "Waist cut-out must stay open skin; do not fill with white fabric even if "
            "the croquis body looks pale."
        ),
        "design_identity": {
            "garment_category": "cut-out swim dress",
            "silhouette": "column with waist cut-out",
            "main_colors": "black",
            "skin_visible_regions": "open waist cut-out showing skin, not fabric",
            "garment_panels": "bodice and skirt only",
            "cutouts_and_openings": "large front waist cut-out",
            "intended_pale_or_white_fabric": "no white fill in the cut-out",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert "open waist cut-out" in prompt.lower()
    assert "no white fill in the cut-out" in prompt.lower()
    assert "Never invent an extra bodysuit" in prompt


def test_genuine_white_swimsuit_panels_are_preserved():
    structured = {
        "summary": "White bandeau bikini",
        "image_prompt": "Opaque white fabric panels for top and bottoms as drawn.",
        "design_identity": {
            "garment_category": "bikini two-piece swimsuit",
            "main_colors": "white",
            "skin_visible_regions": "bare midriff between white top and bottoms",
            "garment_panels": "white bandeau top; white brief bottoms",
            "cutouts_and_openings": "midriff window",
            "intended_pale_or_white_fabric": (
                "white swimsuit fabric panels are intentional drawn garment material"
            ),
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert "white swimsuit fabric panels are intentional" in prompt.lower()
    assert "bare midriff between white top and bottoms" in prompt.lower()
    assert "Never invent an extra bodysuit" in prompt


def test_vision_prose_contradicting_selected_family_is_neutralized():
    job = _job(reference_model_id="male-straight")
    structured = {
        "summary": "female model in teal swim shorts",
        "image_prompt": "A female fashion figure wearing teal swim shorts and a rash top.",
        "design_identity": {
            "garment_category": "swim set",
            "main_colors": "teal and orange",
            "pose": "upright",
            "skin_visible_regions": "bare lower legs",
            "garment_panels": "rash top and swim shorts",
            "cutouts_and_openings": "standard",
            "intended_pale_or_white_fabric": "no white liner drawn",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"], job=job)
    assert "male-straight" in prompt
    assert "SELECTED STUDIO REFERENCE" in prompt or "selected" in prompt.lower()
    # Opposite-family subject claim should be neutralized in summary/evidence path.
    assert "female fashion figure" not in prompt.lower()
    assert "teal" in prompt.lower()
    assert "COVERAGE FIDELITY" in prompt
    assert "Avoid photorealism" in prompt


def test_unusually_long_json_fields_bound_without_dropping_protected_or_key_facts():
    long_detail = ("construction seam note " * 200).strip()
    structured = {
        "summary": "Detailed evening gown",
        "image_prompt": long_detail,
        "design_identity": {
            "garment_category": "evening gown",
            "silhouette": "fitted bodice with train",
            "pose": "three-quarter adult fashion croquis",
            "main_colors": "emerald",
            "fabric_patterns": "satin with tonal jacquard",
            "distinctive_details": long_detail,
            "skin_visible_regions": "bare arms and décolletage as drawn",
            "garment_panels": "bodice and skirt",
            "cutouts_and_openings": "none beyond neckline",
            "intended_pale_or_white_fabric": "no white liner drawn",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    assert len(prompt) <= sketch_openai.IMAGE_PROMPT_MAX_CHARS
    for token in _PROTECTED_ANCHORS:
        assert token in prompt
    assert "emerald" in prompt.lower()
    assert "satin" in prompt.lower()
    assert "bare arms" in prompt.lower()


class _EditTrackingClient:
    def __init__(self, *, on_edit):
        self._on_edit = on_edit
        self.option_calls: list[dict[str, Any]] = []
        self.edit_models: list[str] = []
        self.edit_kwargs: list[dict[str, Any]] = []
        self.generate_calls = 0
        self.images = SimpleNamespace(edit=self.edit, generate=self.generate)

    def with_options(self, **kwargs):
        self.option_calls.append(kwargs)
        return self

    def edit(self, **kwargs):
        self.edit_models.append(str(kwargs.get("model") or ""))
        self.edit_kwargs.append(kwargs)
        return self._on_edit(**kwargs)

    def generate(self, **kwargs):
        self.generate_calls += 1
        raise AssertionError("images.generate must not run")


@pytest.mark.parametrize(
    "model_id,family",
    [
        ("female-straight", "female"),
        ("male-straight", "male"),
    ],
)
def test_two_stage_request_path_coverage_and_identity(monkeypatch, model_id: str, family: str):
    """build_sketch_chat_request → synthetic vision → images.edit prompt handoff."""
    import base64

    _png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
        "x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
    job = _job(
        reference_model_id=model_id,
        image_base64=f"data:image/png;base64,{_png}",
        notes="adult fashion swimwear polish",
    )

    # Stage 1: real vision request construction (no network).
    chat_req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=1400,
    )
    assert chat_req["model"] == "gpt-6-luna"
    system = chat_req["messages"][0]["content"]
    assert "skin_visible_regions" in system
    assert "intended_pale_or_white_fabric" in system
    user = chat_req["messages"][1]["content"]
    assert isinstance(user, list)
    assert any(part.get("type") == "image_url" for part in user if isinstance(part, dict))

    # Stage 2: synthetic vision JSON (incomplete + known midriff for bikini).
    vision = {
        "summary": f"Teal bikini on a fashion croquis",
        "polish_bullets": ["Keep panel edges crisp"],
        "design_identity": {
            "garment_category": "bikini two-piece swimsuit",
            "silhouette": "triangle top with high-cut bottoms",
            "pose": "front-facing adult fashion croquis",
            "main_colors": "teal",
            "skin_visible_regions": "bare midriff between top and bottoms",
            "garment_panels": "triangle top and high-cut bottoms",
            "cutouts_and_openings": "full midriff window",
            "intended_pale_or_white_fabric": "no white liner drawn",
            # Force opposite-family noise for neutralization check.
            "croquis_presentation": (
                "female fashion model" if family == "male" else "male fashion model"
            ),
        },
        "image_prompt": (
            "female model in a teal bikini with bare midriff"
            if family == "male"
            else "male model in a teal bikini with bare midriff"
        ),
        "refine_ok": ["wobbly outlines"],
    }

    captured: dict[str, Any] = {}

    def on_edit(**kwargs):
        captured.update(kwargs)
        item = SimpleNamespace(
            url=None,
            b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"),
        )
        return SimpleNamespace(data=[item])

    client = _EditTrackingClient(on_edit=on_edit)
    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(
            save_file=lambda **kw: "http://127.0.0.1:8001/static/uploads/ai/look.png"
        ),
    )
    monkeypatch.setattr(
        sketch_openai,
        "get_settings",
        lambda: SimpleNamespace(
            openai_image_model="gpt-image-2.5-sunburst",
            openai_image_size="1024x1536",
            openai_image_quality="high",
        ),
    )

    url = sketch_openai._generate_and_store_look_image(
        client, job, vision, vision["summary"]
    )
    assert url.endswith("look.png")
    assert client.generate_calls == 0
    assert client.edit_models == ["gpt-image-2.5-sunburst"]
    assert client.option_calls == [{"max_retries": 0}]
    assert len(client.edit_kwargs) == 1
    prompt = captured.get("prompt") or ""
    assert len(prompt) <= sketch_openai.IMAGE_PROMPT_MAX_CHARS
    for token in _PROTECTED_ANCHORS:
        assert token in prompt
    assert model_id in prompt
    assert family in prompt.lower()
    assert "bare midriff between top and bottoms" in prompt
    assert "teal" in prompt.lower()
    assert captured.get("quality") == "high"
    assert captured.get("size") == "1024x1536"
    # No moderation bypass in the edit payload path.
    assert "bypass" not in prompt.lower()


def test_two_stage_path_with_missing_coverage_fields(monkeypatch):
    import base64

    _png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
        "x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
    job = _job(
        reference_model_id="female-hand-hip",
        image_base64=f"data:image/png;base64,{_png}",
    )
    chat_req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=1400,
    )
    assert "skin_visible_regions" in chat_req["messages"][0]["content"]

    vision = {
        "summary": "Coral swimsuit",
        "image_prompt": "Coral swimsuit as drawn.",
        "design_identity": {
            "garment_category": "one-piece swimsuit",
            "main_colors": "coral",
            "skin_visible_regions": None,
            "garment_panels": "unknown",
            "cutouts_and_openings": "null",
            "intended_pale_or_white_fabric": "n/a",
        },
    }
    captured: dict[str, Any] = {}

    def on_edit(**kwargs):
        captured.update(kwargs)
        item = SimpleNamespace(
            url=None,
            b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"),
        )
        return SimpleNamespace(data=[item])

    client = _EditTrackingClient(on_edit=on_edit)
    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(
            save_file=lambda **kw: "http://127.0.0.1:8001/static/uploads/ai/look.png"
        ),
    )
    monkeypatch.setattr(
        sketch_openai,
        "get_settings",
        lambda: SimpleNamespace(
            openai_image_model="gpt-image-2.5-sunburst",
            openai_image_size="1024x1536",
            openai_image_quality="high",
        ),
    )
    sketch_openai._generate_and_store_look_image(client, job, vision, "Coral swimsuit")
    prompt = captured.get("prompt") or ""
    assert "female-hand-hip" in prompt
    assert "skin visible regions:" not in prompt.lower()
    assert "rely on the uploaded sketch only" in prompt.lower()
    assert "Avoid photorealism" in prompt
    assert "coral" in prompt.lower()
    assert client.generate_calls == 0
    assert len(client.edit_models) == 1
