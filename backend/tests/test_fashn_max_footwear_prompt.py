"""Smart Max prompt footwear appendix (#shoe-span-max)."""

from app.services.fashn_try_on_max_provider import (
    DEFAULT_MAX_PROMPT,
    MAX_BAREFOOT_PROMPT_SUFFIX,
    MAX_DRAWN_FOOTWEAR_PROMPT_SUFFIX,
    build_smart_max_prompt,
)


def test_barefoot_one_piece_hints_append_suffix():
    prompt = build_smart_max_prompt(
        [
            "garment type: continuous one-piece covering torso through hips",
            "footwear: image 2 has no shoes drawn — remove photo boots/shoes; show bare feet matching image 1",
        ]
    )
    assert prompt.startswith(DEFAULT_MAX_PROMPT[:40]) or DEFAULT_MAX_PROMPT.split()[0] in prompt
    assert "bare feet" in prompt.lower() or "remove the model" in prompt.lower()
    assert "tall boots" in prompt.lower()


def test_drawn_footwear_hints_append_replace_suffix():
    prompt = build_smart_max_prompt(
        [
            "footwear: drawn shoes/boots in image 2 — replace the photo shoes/boots entirely; do not keep original boots",
        ]
    )
    assert "replace the model" in prompt.lower() or "footwear matching" in prompt.lower()
    assert MAX_DRAWN_FOOTWEAR_PROMPT_SUFFIX.split()[0].lower() in prompt.lower() or "small dark" in prompt.lower()


def test_one_piece_without_footwear_hint_defaults_barefoot():
    prompt = build_smart_max_prompt(
        ["garment type: continuous one-piece covering torso through hips — not a separate top"]
    )
    assert "bare feet" in prompt.lower() or "boots or shoes" in prompt.lower()
