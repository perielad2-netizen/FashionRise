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
TRY_ON_PROMPT_VERSION = "try-on-person-v1"
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

    def build_edit_kwargs(self, *, photo_png: bytes, garment_png: bytes) -> dict[str, Any]:
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

        try:
            # Reuse shared builder: image[0]=photo, image[1]=garment (via fabric_swatch slot).
            kwargs = build_image_edit_kwargs(
                model=model,
                prompt=TRY_ON_PROMPT_V1,
                sketch=(photo_png, "image/png"),
                size=size,
                quality=quality,
                fabric_swatch=(garment_png, "image/png"),
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

    def preflight_report(self, *, photo_png: bytes, garment_png: bytes) -> dict[str, Any]:
        settings = get_settings()
        kwargs = self.build_edit_kwargs(photo_png=photo_png, garment_png=garment_png)
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

    def generate(self, *, photo_png: bytes, garment_png: bytes) -> tuple[bytes, dict[str, Any]]:
        """Run one images.edit. Returns (png_bytes, usage_meta)."""
        settings = get_settings()
        if not settings.my_croquis_ai_live_http:
            raise ProviderNotAvailableError(
                "MY_CROQUIS_AI_LIVE_HTTP is false — live images.edit not armed for try-on"
            )
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing")

        kwargs = self.build_edit_kwargs(photo_png=photo_png, garment_png=garment_png)
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
                raise ProviderNotAvailableError(
                    f"images.edit rejected by provider: {summary}"
                ) from exc
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


def get_try_on_provider() -> Any:
    """Factory — tests inject via ``set_try_on_provider_override``."""
    if _try_on_provider_override is not None:
        return _try_on_provider_override
    return OpenAITryOnImagesEditAdapter()
