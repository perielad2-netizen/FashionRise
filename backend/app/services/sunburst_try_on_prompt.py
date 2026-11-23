"""Shared Fitting Room Model B / Try On Person sunburst prompt.

Single source of truth so Try On Person and Fitting Room Arm B cannot drift.
Used by ``fitting_room`` (Model B path) and ``personal_try_on_provider`` (OpenAI
Try On Person).
"""

from __future__ import annotations

# Model B — gpt-image-2.6-sunburst raw person+design path (owner A/B/C Arm B).
MODEL_B_SUNBURST_MODEL = "gpt-image-2.6-sunburst"
MODEL_B_SUNBURST_PROMPT_VERSION = "fitting-room-model-b-sunburst-v5"
MODEL_B_SUNBURST_PATH = "openai_model_b_sunburst_raw"
# v4: owner sex flag outranks geometry. Job 2a646dc6 froze male + shorts but the
# worker then injected "dress with high fashion slit" + "plunging V cleavage" from
# false-positive plate geometry and those hints filled the 8-slot budget.
# v5: colored lower-leg / foot regions are garments or footwear — never skin-tone edits.
MODEL_B_SUNBURST_PROMPT = (
    "Fit the exact garment design from image 2 onto the real person in image 1. "
    "Preserve the person's original face, hair, body, pose, skin tone, and background. "
    "PRIORITY: when Studio design evidence names a person sex flag (male or female), "
    "that flag outranks silhouette guesses — never override it with dress/skirt/cleavage "
    "stereotypes. "
    "If the person sex flag is male: render masculine presentation; treat short or baggy "
    "lower garments as shorts or pants — never a skirt, dress, gown, or fashion slit; "
    "keep the drawn neckline — do not invent a plunging V or cleavage. "
    "If the person sex flag is female: keep feminine presentation and follow image 2 "
    "garment type (skirt/dress stays skirt/dress; shorts stay shorts). "
    "Keep the garment's exact type, colors, silhouette, decorative details, neckline, "
    "sleeve asymmetry, fabric texture/pattern, layer placement, and length as drawn in image 2. "
    "If image 2 shows separate top and bottom, keep both pieces — do not merge into one dress. "
    "If image 2 shows shorts, cropped trousers, or any short hem ending above mid-calf, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit. "
    "Colored regions on the lower legs or feet in image 2 are stockings, boots, shoes, or "
    "other garments — never reinterpret them as changes to the person's skin color. "
    "Make the clothing naturally photorealistic. Do not change anything else. "
    "If the fashion design shows shoes, heels, boots, or other footwear, replace "
    "the person's existing footwear with the matching design footwear, preserving "
    "its style, color, and proportions. If no footwear is shown in the design, "
    "preserve the original shoes."
)
MODEL_B_SUNBURST_SKIN_TONE_CLAUSE = (
    "Colored regions on the lower legs or feet in image 2 are stockings, boots, shoes, or "
    "other garments — never reinterpret them as changes to the person's skin color."
)
MODEL_B_SUNBURST_FOOTWEAR_CLAUSE = (
    "If the fashion design shows shoes, heels, boots, or other footwear, replace "
    "the person's existing footwear with the matching design footwear, preserving "
    "its style, color, and proportions. If no footwear is shown in the design, "
    "preserve the original shoes."
)
MODEL_B_SUNBURST_SEX_CLAUSE = (
    "PRIORITY: when Studio design evidence names a person sex flag (male or female), "
    "that flag outranks silhouette guesses — never override it with dress/skirt/cleavage "
    "stereotypes."
)
MODEL_B_SUNBURST_SHORTS_CLAUSE = (
    "If image 2 shows shorts, cropped trousers, or any short hem ending above mid-calf, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit."
)
MODEL_B_SUNBURST_MALE_PANTS_CLAUSE = (
    "If the person sex flag is male: render masculine presentation; treat short or baggy "
    "lower garments as shorts or pants — never a skirt, dress, gown, or fashion slit; "
    "keep the drawn neckline — do not invent a plunging V or cleavage."
)


def sex_flag_design_hints(sex: str | None) -> list[str]:
    """Priority Try On hints from the owner-declared My Model sex flag."""
    flag = (sex or "").strip().lower()
    if flag == "male":
        return [
            "person sex flag: male — PRIORITY over geometry; keep masculine presentation",
            "lower garment: male shorts or baggy pants — NEVER a skirt, dress, gown, or slit",
            "neckline: keep drawn closed/crew neck — do not invent plunging V or cleavage",
        ]
    if flag == "female":
        return [
            "person sex flag: female — PRIORITY over geometry; keep feminine presentation",
            "lower garment: follow image 2 — skirt/dress stays skirt/dress; shorts stay shorts",
        ]
    return []
