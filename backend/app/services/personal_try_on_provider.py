"""Personal Try On Person — photorealistic images.edit adapter (separate from Magic polish).

Image 1 = original authorized person photograph (identity/pose/background).
Image 2 = isolated transparent garment artwork (design authoritative).

Does NOT reuse the non-photorealistic sketch_polish prompt. Live HTTP is gated
by the same MY_CROQUIS_AI_* fail-closed flags as Create My Croquis.
"""

from __future__ import annotations

import io
import logging
from typing import Any

from app.core.config import get_settings
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    _RATE_IMAGE_IN,
    _RATE_IMAGE_OUT,
    _RATE_TEXT_IN,
    _is_definitive_images_edit_rejection,
    _is_presubmit_sdk_contract_error,
    _safe_api_error_summary,
    extract_edit_png_bytes,
)

logger = logging.getLogger(__name__)

TRY_ON_JOB_TYPE = "personal_try_on"
# V1/V3 kept for historical jobs. Live OpenAI enqueue uses V2.6.
# V3 (swimwear skin-coverage wording) caused 100% OpenAI input moderation_blocked
# category=sexual on ordinary outfits (job 461c9419…). Avoid V3 phrasing.
# V2.1 kept V2 print/identity rules; clarified fashion slits must not become trousers.
# V2.2 adds pale/bridal fabric + open neckline + bilateral sleeve fidelity (#182).
# V2.3 adds drawn footwear from image 2 replacing photo shoes/boots (#184).
# V2.4: continuous one-piece / torso–hip coverage must replace photo jeans/trousers
# under the design (owner one-piece kept street bottoms). Still no V3 "newly uncovered
# skin" language — FASHN remains preferred for coverage-sensitive swimwear.
# V2.5: when image 2 has no drawn footwear and the garment is a one-piece / high-cut
# ending above the ankles, remove photo boots/shoes and show bare feet.
# V2.6: stronger footwear contract — drawn shoes must fully replace photo boots;
# barefoot one-piece must not keep tall boots (owner red swimsuit kept beige boots).
TRY_ON_PROMPT_VERSION = "try-on-person-v2.6"
TRY_ON_CONSENT_VERSION = "try-on-person-preview-v1"

# Product notice — FE and BE must agree on version + hash of this exact text.
TRY_ON_NOTICE_TEXT = (
    "Try On Person sends your original Create My Croquis photo and this garment "
    "sketch to FashionRise’s AI image provider to create a private photorealistic "
    "preview of you wearing the design. This is a concept preview — not a fit or "
    "measurement guarantee. Your original photo and sketch stay private and are "
    "not overwritten. Provider safety rules still apply; refused attempts are not charged."
)

TRY_ON_PROMPT_V1 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, accessories that "
    "are not clothing, and the original background/scene. Do not slim, elongate, or reshape "
    "the person. "
    "Image 2 is an isolated transparent fashion-design artwork of the garment only (no "
    "mannequin, no paper). Replace only the relevant clothing regions with that design: "
    "match its silhouette, colors, materials, neckline, sleeves, hem and coverage as drawn. "
    "Adapt the garment naturally to the body and folds of the pose. "
    "Do not invent extra garments, logos, or text. Do not undress the person or expose body "
    "beyond what image 1 already shows. Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2 — garment print/accessory fidelity (#154). Photo identity rules unchanged from V1.
# V2.1 (#174) — same base; fashion slits/openings from image 2 are design, not undressing;
# do not convert a slit dress into trousers/jumpsuit. Avoids V3 swimwear/coverage wording.
TRY_ON_PROMPT_V2 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, non-design "
    "accessories already on the person, and the original background/scene. Do not slim, "
    "elongate, beautify, or reshape the person. Do not alter the environment. "
    "Image 2 is an isolated transparent fashion-design artwork (no mannequin, no paper). "
    "It is authoritative for garment type, cut, placement, neckline, sleeves, hemline, "
    "coverage, exact chosen colors, and print geometry. Read print topology from image 2 "
    "pixels literally: a checkerboard must stay a checkerboard (not stripes); plaids, dots, "
    "and freehand motifs must keep their structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, hats/caps, belts, scarves — placed on the corresponding body "
    "region. Hats/caps may cover hair while keeping identity recognizable. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Do not undress the person or create nudity. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2.2 (#182) — bridal/pale fill visibility + open neckline + sleeve fidelity.
# Image 2 may be composited on a dark matte so cream/ivory fabric stays readable.
TRY_ON_PROMPT_V2_2 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, non-design "
    "accessories already on the person, and the original background/scene. Do not slim, "
    "elongate, beautify, or reshape the person. Do not alter the environment. "
    "Image 2 is the authoritative fashion-design artwork for garment type, cut, placement, "
    "neckline depth, sleeve count and length, hemline, coverage, exact chosen colors "
    "(including intentional pale cream, ivory, peach, or white fabric), and print geometry. "
    "Image 2 may sit on a neutral dark matte for readability — the matte is NOT clothing; "
    "only the drawn garment pixels are the design. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, hats/caps, belts, scarves — placed on the corresponding body "
    "region. Hats/caps may cover hair while keeping identity recognizable. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Preserve open / plunging / deep-V necklines exactly — do not fill cleavage or raise "
    "the neckline. If image 2 shows sleeves on both arms, keep both sleeves; do not invent "
    "a one-shoulder or sleeveless redesign. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Do not undress the person or create nudity. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2.3 (#184) — V2.2 + footwear from image 2 replaces photo shoes/boots.
TRY_ON_PROMPT_V2_3 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, and the original "
    "background/scene. Do not slim, elongate, beautify, or reshape the person. Do not "
    "alter the environment. "
    "Image 2 is the authoritative fashion-design artwork for garment type, cut, placement, "
    "neckline depth, sleeve count and length, hemline, footwear/shoes when drawn, coverage, "
    "exact chosen colors (including intentional pale cream, ivory, peach, or white fabric), "
    "and print geometry. "
    "Image 2 may sit on a neutral dark matte for readability — the matte is NOT clothing; "
    "only the drawn garment pixels are the design. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, hats/caps, belts, scarves, shoes/footwear — placed on the "
    "corresponding body region. Hats/caps may cover hair while keeping identity "
    "recognizable. If image 2 draws shoes, boots, flats, heels, or laced footwear, replace "
    "the shoes visible in image 1 with that drawn footwear (color and style); do not keep "
    "the original photo boots when image 2 shows different shoes. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Preserve open / plunging / deep-V necklines exactly — do not fill cleavage or raise "
    "the neckline. If image 2 shows sleeves on both arms, keep both sleeves; do not invent "
    "a one-shoulder or sleeveless redesign. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Do not undress the person or create nudity. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2.4 — V2.3 + replace photo clothing under continuous one-piece / torso–hip coverage.
# Does NOT reuse V3 "skin previously covered by street clothes" wording (moderation).
TRY_ON_PROMPT_V2_4 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, and the original "
    "background/scene. Do not slim, elongate, beautify, or reshape the person. Do not "
    "alter the environment. "
    "Image 2 is the authoritative fashion-design artwork for garment type, cut, placement, "
    "neckline depth, sleeve count and length, hemline, footwear/shoes when drawn, coverage, "
    "exact chosen colors (including intentional pale cream, ivory, peach, or white fabric), "
    "and print geometry. "
    "Image 2 may sit on a neutral dark matte for readability — the matte is NOT clothing; "
    "only the drawn garment pixels are the design. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, one-piece garments, hats/caps, belts, scarves, shoes/footwear "
    "— placed on the corresponding body region. Hats/caps may cover hair while keeping "
    "identity recognizable. If image 2 draws shoes, boots, flats, heels, or laced footwear, "
    "replace the shoes visible in image 1 with that drawn footwear (color and style); do not "
    "keep the original photo boots when image 2 shows different shoes. "
    "Wherever image 2 shows continuous opaque garment coverage on the torso and through "
    "the hips or crotch, replace the person's clothing in those regions with that opaque "
    "design. A one-piece design is not a separate top over trousers — do not leave jeans, "
    "trousers, or shorts from image 1 under a one-piece. Match the designed hem and leg "
    "openings from image 2. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Preserve open / plunging / deep-V necklines exactly — do not fill cleavage or raise "
    "the neckline. If image 2 shows sleeves on both arms, keep both sleeves; do not invent "
    "a one-shoulder or sleeveless redesign. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Keep the look as an opaque fashion catalog presentation. Do not create nudity, sheer "
    "intimate exposure, or suggestive posing. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2.5 — V2.4 + bare feet when image 2 has no footwear and the garment ends above the ankles.
TRY_ON_PROMPT_V2_5 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, and the original "
    "background/scene. Do not slim, elongate, beautify, or reshape the person. Do not "
    "alter the environment. "
    "Image 2 is the authoritative fashion-design artwork for garment type, cut, placement, "
    "neckline depth, sleeve count and length, hemline, footwear/shoes when drawn, coverage, "
    "exact chosen colors (including intentional pale cream, ivory, peach, or white fabric), "
    "and print geometry. "
    "Image 2 may sit on a neutral dark matte for readability — the matte is NOT clothing; "
    "only the drawn garment pixels are the design. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, one-piece garments, hats/caps, belts, scarves, shoes/footwear "
    "— placed on the corresponding body region. Hats/caps may cover hair while keeping "
    "identity recognizable. If image 2 draws shoes, boots, flats, heels, or laced footwear, "
    "replace the shoes visible in image 1 with that drawn footwear (color and style); do not "
    "keep the original photo boots when image 2 shows different shoes. "
    "If image 2 does not draw any shoes or boots and the garment is a one-piece or high-cut "
    "design that ends above the ankles, remove the shoes or boots from image 1 and show "
    "bare feet with skin tone matching image 1 — do not keep photo boots under a barefoot "
    "one-piece. Floor-length dresses without drawn footwear may keep image 1 shoes. "
    "Wherever image 2 shows continuous opaque garment coverage on the torso and through "
    "the hips or crotch, replace the person's clothing in those regions with that opaque "
    "design. A one-piece design is not a separate top over trousers — do not leave jeans, "
    "trousers, or shorts from image 1 under a one-piece. Match the designed hem and leg "
    "openings from image 2. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Preserve open / plunging / deep-V necklines exactly — do not fill cleavage or raise "
    "the neckline. If image 2 shows sleeves on both arms, keep both sleeves; do not invent "
    "a one-shoulder or sleeveless redesign. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Keep the look as an opaque fashion catalog presentation. Do not create nudity, sheer "
    "intimate exposure, or suggestive posing. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V2.6 — V2.5 + emphatic footwear replace / barefoot (photo tall boots were surviving).
TRY_ON_PROMPT_V2_6 = (
    "Create a photorealistic photograph of the person from image 1 wearing the garment "
    "design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, visible skin, and the original "
    "background/scene. Do not slim, elongate, beautify, or reshape the person. Do not "
    "alter the environment. "
    "Image 2 is the authoritative fashion-design artwork for garment type, cut, placement, "
    "neckline depth, sleeve count and length, hemline, footwear/shoes when drawn, coverage, "
    "exact chosen colors (including intentional pale cream, ivory, peach, or white fabric), "
    "and print geometry. "
    "Image 2 may sit on a neutral dark matte for readability — the matte is NOT clothing; "
    "only the drawn garment pixels are the design. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, dresses, one-piece garments, hats/caps, belts, scarves, shoes/footwear "
    "— placed on the corresponding body region. Hats/caps may cover hair while keeping "
    "identity recognizable. "
    "Footwear is mandatory to resolve from image 2: if image 2 draws any shoes, boots, "
    "flats, heels, or laced footwear on the feet, you MUST fully replace image 1's shoes "
    "or boots with that drawn footwear (match color and style). Never leave image 1's tall "
    "boots, combat boots, or heels when image 2 shows different shoes or bare feet. "
    "If image 2 shows bare feet or no footwear at all and the garment is a one-piece or "
    "high-cut design ending above the ankles, remove image 1's shoes and boots completely "
    "and render bare feet with skin tone matching image 1. Floor-length dresses without "
    "drawn footwear may keep image 1 shoes. "
    "Wherever image 2 shows continuous opaque garment coverage on the torso and through "
    "the hips or crotch, replace the person's clothing in those regions with that opaque "
    "design. A one-piece design is not a separate top over trousers — do not leave jeans, "
    "trousers, or shorts from image 1 under a one-piece. Match the designed hem and leg "
    "openings from image 2. "
    "Adapt garments naturally to pose and folds as an approximate drape only. "
    "Preserve open / plunging / deep-V necklines exactly — do not fill cleavage or raise "
    "the neckline. If image 2 shows sleeves on both arms, keep both sleeves; do not invent "
    "a one-shoulder or sleeveless redesign. "
    "Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Keep the look as an opaque fashion catalog presentation. Do not create nudity, sheer "
    "intimate exposure, or suggestive posing. Fashion necklines, hems, cutouts, and "
    "slits drawn in image 2 are opaque garment styling — keep that cut; do not convert a "
    "dress or skirt with a slit into trousers or a jumpsuit. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

# V3 — legitimate opaque fashion/swimwear coverage (#156).
# Removes V2's contradiction that forbade showing skin newly uncovered by a swimsuit
# when image 1 is street clothes. Still forbids nudity / sexual framing.
TRY_ON_PROMPT_V3 = (
    "Create a photorealistic fashion photograph of the person from image 1 wearing the "
    "opaque garment design shown in image 2. "
    "Image 1 is the authoritative full-body photograph — preserve the person's exact face, "
    "hairstyle, skin tone, body proportions, pose, stance, non-design accessories already "
    "on the person, and the original background/scene. Do not slim, elongate, beautify, "
    "or reshape the person. Do not alter the environment. "
    "Image 2 is an isolated transparent fashion-design artwork (no mannequin, no paper). "
    "It is authoritative for garment type, cut, placement, neckline, straps, sleeves, "
    "hemline, coverage, exact chosen colors, and print geometry — including ordinary "
    "two-piece swimwear, one-piece swimsuits, dresses, tops, and bottoms when drawn. "
    "Replace the person's current clothing with that opaque design as a clothed fashion "
    "lookbook / catalog visualization. The designed coverage in image 2 is authoritative: "
    "skin previously covered by street clothes may appear only where the opaque swimsuit "
    "or garment leaves it uncovered in a normal fashion presentation. "
    "Read print topology from image 2 pixels literally: a checkerboard must stay a "
    "checkerboard (not stripes); plaids, dots, and freehand motifs must keep their "
    "structure; do not invent a different graphic. "
    "Include every deliberately drawn garment piece and design accessory in image 2 — "
    "tops, bottoms, swimwear pieces, dresses, hats/caps, belts, scarves — placed on the "
    "corresponding body region. Hats/caps may cover hair while keeping identity "
    "recognizable. Adapt garments naturally to pose and folds as an approximate drape only. "
    "All garments must remain fully opaque fabric. Do not create nudity, sheer or "
    "transparent intimate exposure, lingerie presentation, sexual posing, or sexualized "
    "framing. Do not invent extra garments, logos, text, or accessories absent from image 2. "
    "Do not copy mannequin outlines into the photo. "
    "Output a single realistic photograph."
)

TRY_ON_USER_MODERATION_MESSAGE = (
    "This design could not be rendered by our image provider. Your sketch is saved. "
    "You can continue editing or choose Fashion Magic."
)
# #176 — clearer copy when the provider blocked the generated OUTPUT (not the input sketch).
TRY_ON_USER_OUTPUT_MODERATION_MESSAGE = (
    "Our image provider blocked the generated preview after creating it "
    "(output safety filter). Your sketch and photo are unchanged and were not rejected "
    "as uploads. Try Fashion Magic / FASHN Try On for this silhouette, or adjust coverage "
    "if you want to retry OpenAI Try On."
)
TRY_ON_USER_PROVIDER_REJECT_MESSAGE = (
    "Try On Person could not finish this preview. Your sketch and photo are unchanged. "
    "You can continue editing or choose Fashion Magic."
)


def build_try_on_prompt(design_hints: list[str] | None = None) -> str:
    """Active OpenAI try-on prompt (V2.6) plus optional Studio-derived design hints.

    V3 remains in-module for audit only — do not activate for live OpenAI Try On.
    Coverage-sensitive swimwear still prefers the separate FASHN provider path;
    V2.6 strengthens footwear replace / barefoot so photo boots do not survive.
    """
    prompt = TRY_ON_PROMPT_V2_6
    cleaned: list[str] = []
    for raw in design_hints or []:
        if not isinstance(raw, str):
            continue
        text = " ".join(raw.split())
        if not text:
            continue
        cleaned.append(text[:120])
        if len(cleaned) >= 8:
            break
    if cleaned:
        prompt += " Studio design evidence (do not invent beyond this or image 2): " + "; ".join(
            cleaned
        ) + "."
    return prompt


def try_on_notice_text_hash() -> str:
    import hashlib

    return hashlib.sha256(TRY_ON_NOTICE_TEXT.encode("utf-8")).hexdigest()


def estimate_try_on_cost_cents() -> int:
    """Conservative estimate for UI / reservation soft field (not the hard cap)."""
    settings = get_settings()
    configured = int(settings.my_croquis_ai_estimate_cents or 0)
    # Try-on uses a full photo + garment edit; allow estimate at least croquis estimate.
    return max(configured, 3)


class OpenAITryOnImagesEditAdapter:
    """images.edit adapter for personal_try_on (photo + garment artwork)."""

    incomplete = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")

    def build_edit_kwargs(
        self,
        *,
        photo_png: bytes,
        garment_png: bytes,
        design_hints: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.services.sketch_openai import (
            SketchCompletionError,
            assert_image_model_editable,
            build_image_edit_kwargs,
        )

        if not photo_png:
            raise ProviderNotAvailableError("Empty source photograph for try-on")
        if not garment_png:
            raise ProviderNotAvailableError("Empty garment artwork for try-on")

        settings = get_settings()
        model = (settings.openai_image_model or "").strip()
        assert_image_model_editable(model)
        size = (settings.openai_image_size or "1024x1536").strip()
        quality = settings.openai_image_quality

        # #182 — pale bridal fills vanish on white flatten; matte for OpenAI only.
        from app.services.garment_upper_geometry import prepare_openai_try_on_garment_visibility

        garment_for_edit, _vis_meta = prepare_openai_try_on_garment_visibility(garment_png)

        try:
            # Reuse shared builder: image[0]=photo, image[1]=garment (via fabric_swatch slot).
            kwargs = build_image_edit_kwargs(
                model=model,
                prompt=build_try_on_prompt(design_hints),
                sketch=(photo_png, "image/png"),
                size=size,
                quality=quality,
                fabric_swatch=(garment_for_edit, "image/png"),
            )
        except SketchCompletionError as exc:
            raise ProviderNotAvailableError(str(exc)) from exc

        kwargs["n"] = 1
        kwargs["output_format"] = "png"
        # Opaque photograph output (not transparent croquis).
        kwargs.pop("background", None)
        extra = dict(kwargs.get("extra_body") or {})
        extra["moderation"] = "low"
        kwargs["extra_body"] = extra
        if "moderation" in kwargs:
            raise ProviderNotAvailableError(
                "Try-on edit must not pass top-level moderation= (SDK TypeError)"
            )
        image = kwargs.get("image")
        if not isinstance(image, list) or len(image) != 2:
            raise ProviderNotAvailableError("Try-on edit requires exactly photo + garment inputs")
        return kwargs

    def preflight_report(
        self,
        *,
        photo_png: bytes,
        garment_png: bytes,
        design_hints: list[str] | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        kwargs = self.build_edit_kwargs(
            photo_png=photo_png, garment_png=garment_png, design_hints=design_hints
        )
        return {
            "prompt_version": TRY_ON_PROMPT_VERSION,
            "consent_version": TRY_ON_CONSENT_VERSION,
            "model": kwargs.get("model"),
            "size": kwargs.get("size"),
            "quality": kwargs.get("quality"),
            "image_inputs": 2,
            "estimate_cents": estimate_try_on_cost_cents(),
            "max_exposure_cents": int(settings.my_croquis_ai_max_exposure_cents or 0),
            "live_http": bool(settings.my_croquis_ai_live_http),
        }

    def generate(
        self,
        *,
        photo_png: bytes,
        garment_png: bytes,
        design_hints: list[str] | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Run one images.edit. Returns (png_bytes, usage_meta)."""
        settings = get_settings()
        if not settings.my_croquis_ai_live_http:
            raise ProviderNotAvailableError(
                "MY_CROQUIS_AI_LIVE_HTTP is false — live images.edit not armed for try-on"
            )
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing")

        kwargs = self.build_edit_kwargs(
            photo_png=photo_png, garment_png=garment_png, design_hints=design_hints
        )
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=float(settings.openai_timeout_seconds or 180),
        )
        try:
            result = client.with_options(max_retries=0).images.edit(**kwargs)
        except Exception as exc:  # noqa: BLE001 — classify below
            summary = _safe_api_error_summary(exc)
            if _is_presubmit_sdk_contract_error(exc):
                raise ProviderNotAvailableError(
                    f"images.edit refused before HTTP (SDK contract): {summary}"
                ) from exc
            if _is_definitive_images_edit_rejection(exc):
                from app.services.personal_croquis_provider import (
                    _api_error_code,
                    _api_status_code,
                    _moderation_details_sanitized,
                    _safe_request_id_from_exc,
                )

                code = _api_error_code(exc)
                mod = _moderation_details_sanitized(exc) or {}
                safe_meta = {
                    "error_code": (
                        "PROVIDER_MODERATION_BLOCKED"
                        if (code == "moderation_blocked" or "moderation_blocked" in summary)
                        else "PROVIDER_REJECTED"
                    ),
                    "provider_code": code,
                    "http_status": _api_status_code(exc),
                    "moderation_stage": mod.get("moderation_stage"),
                    "categories": mod.get("categories"),
                    "request_id": _safe_request_id_from_exc(exc),
                    "operator_summary": summary[:400],
                }
                err = ProviderNotAvailableError(
                    f"images.edit rejected by provider: {summary}"
                )
                err.safe_meta = safe_meta  # type: ignore[attr-defined]
                raise err from exc
            raise ProviderOutcomeUnknownError(
                f"images.edit outcome unknown after submit: {type(exc).__name__}"
            ) from exc

        png = extract_edit_png_bytes(result)
        usage = getattr(result, "usage", None)
        meta: dict[str, Any] = {
            "prompt_version": TRY_ON_PROMPT_VERSION,
            "provider": "openai_images_edit",
            "model": kwargs.get("model"),
        }
        # Best-effort cost from token usage when present.
        try:
            if usage is not None:
                tin = int(getattr(usage, "input_tokens_details", None).text_tokens or 0) if getattr(usage, "input_tokens_details", None) else 0
                iin = int(getattr(usage, "input_tokens_details", None).image_tokens or 0) if getattr(usage, "input_tokens_details", None) else 0
                iout = int(getattr(usage, "output_tokens", 0) or 0)
                usd = (tin * _RATE_TEXT_IN + iin * _RATE_IMAGE_IN + iout * _RATE_IMAGE_OUT) / 1_000_000.0
                meta["actual_cost_cents"] = max(1, int(round(usd * 100))) if usd > 0 else None
        except Exception:  # noqa: BLE001
            meta["actual_cost_cents"] = None
        return png, meta


_try_on_provider_override: Any | None = None


def set_try_on_provider_override(provider: Any | None) -> None:
    """Test-only injection — never used in production paths."""
    global _try_on_provider_override
    _try_on_provider_override = provider


def get_try_on_provider(provider: str | None = None) -> Any:
    """Factory — tests inject via ``set_try_on_provider_override``.

    ``provider`` is frozen on the job at enqueue (``openai`` default, or ``fashn``).
    Never auto-switch after a refusal.
    """
    if _try_on_provider_override is not None:
        return _try_on_provider_override
    name = (provider or "openai").strip().lower()
    if name in {"fashn_max", "fashn_tryon_max", "tryon-max"}:
        from app.services.fashn_try_on_max_provider import FashnTryOnMaxAdapter

        return FashnTryOnMaxAdapter()
    if name in {"fashn", "fashn_tryon_v1_6", "tryon-v1.6"}:
        from app.services.fashn_try_on_provider import FashnTryOnV16Adapter

        return FashnTryOnV16Adapter()
    return OpenAITryOnImagesEditAdapter()
