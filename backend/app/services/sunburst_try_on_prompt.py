"""Shared Fitting Room Model B / Try On Person sunburst prompt.

Single source of truth so Try On Person and Fitting Room Arm B cannot drift.
Used by ``fitting_room`` (Model B path) and ``personal_try_on_provider`` (OpenAI
Try On Person).
"""

from __future__ import annotations

# Model B — gpt-image-2.6-sunburst raw person+design path (owner A/B/C Arm B).
MODEL_B_SUNBURST_MODEL = "gpt-image-2.6-sunburst"
MODEL_B_SUNBURST_PROMPT_VERSION = "fitting-room-model-b-sunburst-v3"
MODEL_B_SUNBURST_PATH = "openai_model_b_sunburst_raw"
# Compare Arm B prompt + footwear + sex flag + garment-type fidelity.
# v3: owner-declared male/female on My Model drives pants-vs-skirt disambiguation
# (male shorts were still becoming slit skirts under v2 inference-only).
MODEL_B_SUNBURST_PROMPT = (
    "Fit the exact garment design from image 2 onto the real person in image 1. "
    "Preserve the person's original face, hair, body, pose, and background. "
    "When Studio design evidence names a person sex flag (male or female), treat that "
    "flag as authoritative for presentation and for pants-versus-skirt decisions — "
    "do not override it from clothing stereotypes. "
    "Preserve the person's apparent sex and gender presentation from image 1 — "
    "do not feminize or masculinize the person or the outfit. "
    "Keep the garment's exact type, colors, silhouette, decorative details, and length "
    "as drawn in image 2. "
    "If image 2 shows shorts, cropped trousers, or any short hem ending above the knee, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit. "
    "If the person sex flag is male and the lower garment is ambiguous, render shorts or "
    "pants — never a skirt, dress, gown, or fashion slit. "
    "If image 2 shows a skirt or dress and the person sex flag is female, keep that type. "
    "Make the clothing naturally photorealistic. Do not change anything else. "
    "If the fashion design shows shoes, heels, boots, or other footwear, replace "
    "the person's existing footwear with the matching design footwear, preserving "
    "its style, color, and proportions. If no footwear is shown in the design, "
    "preserve the original shoes."
)
MODEL_B_SUNBURST_FOOTWEAR_CLAUSE = (
    "If the fashion design shows shoes, heels, boots, or other footwear, replace "
    "the person's existing footwear with the matching design footwear, preserving "
    "its style, color, and proportions. If no footwear is shown in the design, "
    "preserve the original shoes."
)
MODEL_B_SUNBURST_SEX_CLAUSE = (
    "When Studio design evidence names a person sex flag (male or female), treat that "
    "flag as authoritative for presentation and for pants-versus-skirt decisions — "
    "do not override it from clothing stereotypes."
)
MODEL_B_SUNBURST_SHORTS_CLAUSE = (
    "If image 2 shows shorts, cropped trousers, or any short hem ending above the knee, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit."
)
MODEL_B_SUNBURST_MALE_PANTS_CLAUSE = (
    "If the person sex flag is male and the lower garment is ambiguous, render shorts or "
    "pants — never a skirt, dress, gown, or fashion slit."
)


def sex_flag_design_hints(sex: str | None) -> list[str]:
    """Priority Try On hints from the owner-declared My Model sex flag."""
    flag = (sex or "").strip().lower()
    if flag == "male":
        return [
            "person sex flag: male — keep masculine presentation from image 1",
            "lower garment: for this male model treat short or ambiguous bottoms as "
            "shorts or pants — never a skirt, dress, gown, or high slit",
        ]
    if flag == "female":
        return [
            "person sex flag: female — keep feminine presentation from image 1",
            "lower garment: follow image 2 type — skirt or dress stays skirt/dress; "
            "shorts stay shorts",
        ]
    return []
