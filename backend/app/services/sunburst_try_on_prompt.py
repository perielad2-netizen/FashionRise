"""Shared Fitting Room Model B / Try On Person sunburst prompt.

Single source of truth so Try On Person and Fitting Room Arm B cannot drift.
Used by ``fitting_room`` (Model B path) and ``personal_try_on_provider`` (OpenAI
Try On Person).
"""

from __future__ import annotations

# Model B — gpt-image-2.6-sunburst raw person+design path (owner A/B/C Arm B).
MODEL_B_SUNBURST_MODEL = "gpt-image-2.6-sunburst"
MODEL_B_SUNBURST_PROMPT_VERSION = "fitting-room-model-b-sunburst-v2"
MODEL_B_SUNBURST_PATH = "openai_model_b_sunburst_raw"
# Compare Arm B prompt + footwear + sex/presentation + garment-type fidelity.
# v2: male/female presentation from image 1 must be preserved; shorts must not
# become skirts/dresses (owner male My Model + shorts → long slit skirt).
MODEL_B_SUNBURST_PROMPT = (
    "Fit the exact garment design from image 2 onto the real person in image 1. "
    "Preserve the person's original face, hair, body, pose, and background. "
    "Preserve the person's apparent sex and gender presentation from image 1 — "
    "do not feminize or masculinize the person or the outfit. "
    "Keep the garment's exact type, colors, silhouette, decorative details, and length "
    "as drawn in image 2. "
    "If image 2 shows shorts, cropped trousers, or any short hem ending above the knee, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit. "
    "If image 2 shows a skirt or dress, keep that type — do not convert it into shorts "
    "or trousers. "
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
    "Preserve the person's apparent sex and gender presentation from image 1 — "
    "do not feminize or masculinize the person or the outfit."
)
MODEL_B_SUNBURST_SHORTS_CLAUSE = (
    "If image 2 shows shorts, cropped trousers, or any short hem ending above the knee, "
    "keep that short length — do not lengthen into a skirt, dress, gown, or high slit."
)
