"""OpenAI images.edit → photorealistic garment product image for FASHN (#161).

Transforms FashionRise flat-lay sketch plates into e-commerce product photographs
**without** inventing a person/mannequin. Owner must review and accept before any
FASHN credit is spent. Separate spend reservation from the FASHN try-on job.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from typing import Any

from PIL import Image

from app.core.config import get_settings
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    extract_edit_png_bytes,
)

logger = logging.getLogger(__name__)

GARMENT_REALISM_JOB_TYPE = "personal_garment_realism"
GARMENT_REALISM_PROMPT_VERSION = "fashn-garment-realism-v2"
GARMENT_REALISM_PROVIDER_ID = "openai_garment_realism"

GARMENT_REALISM_PROMPT = (
    "Transform this fashion designer's garment sketch into a photorealistic commercial "
    "clothing product photograph. Preserve the exact garment design, silhouette, coverage, "
    "cut, selected colors, gradient placement and visible patterns. Create realistic textile "
    "material, fabric construction, stitching and natural garment structure. Show the clothing "
    "item alone as a clean professional flat-lay or ghost-mannequin-free product image against "
    "a neutral background. No person, body, mannequin, model, face or unrelated accessories. "
    "CRITICAL SILHOUETTE RULES: Do not redesign the garment. Do not turn a swimsuit, bodysuit, "
    "or one-piece into a dress, skirt, romper, or coat. Preserve high-cut leg openings, crotch "
    "coverage, asymmetric straps, necklines, cutouts and hem positions exactly as drawn. "
    "This is a legitimate opaque fashion garment intended for clothing design and virtual try-on."
)


def estimate_garment_realism_cents(*, pieces: int = 1) -> int:
    settings = get_settings()
    per = max(1, int(getattr(settings, "fashn_garment_realism_estimate_cents", None) or settings.my_croquis_ai_estimate_cents or 8))
    return per * max(1, int(pieces))


def garment_realism_prompt(*, category: str | None = None) -> str:
    cat = (category or "auto").strip().lower()
    extra = ""
    if cat == "tops":
        extra = " This plate is the upper garment / swimsuit top only — not a dress."
    elif cat == "bottoms":
        extra = " This plate is the lower garment / swimsuit bottom only — not a skirt."
    elif cat == "one-pieces":
        extra = (
            " This plate is a one-piece swimsuit or bodysuit. Keep high-cut leg openings and "
            "one-piece coverage. It must not become a mini dress, skirt, or gown."
        )
    return GARMENT_REALISM_PROMPT + extra


class OpenAIGarmentRealismAdapter:
    """One images.edit per plate — product photo only, never a person."""

    incomplete = False

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.my_croquis_ai_enabled:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
        if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
            raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed)")
        if not settings.fashn_try_on_enabled:
            raise ProviderNotAvailableError("FASHN_TRY_ON_ENABLED is false")

    def build_edit_kwargs(self, *, plate_png: bytes, category: str | None = None) -> dict[str, Any]:
        from app.services.sketch_openai import (
            SketchCompletionError,
            assert_image_model_editable,
            build_image_edit_kwargs,
        )

        if not plate_png:
            raise ProviderNotAvailableError("Empty garment plate for realism")
        settings = get_settings()
        model = (settings.openai_image_model or "").strip()
        assert_image_model_editable(model)
        size = (settings.openai_image_size or "1024x1536").strip()
        quality = settings.openai_image_quality
        try:
            kwargs = build_image_edit_kwargs(
                model=model,
                prompt=garment_realism_prompt(category=category),
                sketch=(plate_png, "image/png"),
                size=size,
                quality=quality,
            )
        except SketchCompletionError as exc:
            raise ProviderNotAvailableError(str(exc)) from exc
        kwargs["n"] = 1
        kwargs["output_format"] = "png"
        kwargs.pop("background", None)
        extra = dict(kwargs.get("extra_body") or {})
        extra["moderation"] = "low"
        kwargs["extra_body"] = extra
        return kwargs

    def generate_piece(self, *, plate_png: bytes, category: str | None = None) -> tuple[bytes, dict[str, Any]]:
        settings = get_settings()
        if not settings.my_croquis_ai_live_http:
            raise ProviderNotAvailableError(
                "MY_CROQUIS_AI_LIVE_HTTP is false — live garment realism not armed"
            )
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing")

        kwargs = self.build_edit_kwargs(plate_png=plate_png, category=category)
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            timeout=float(settings.openai_timeout_seconds or 180),
        )
        try:
            result = client.with_options(max_retries=0).images.edit(**kwargs)
        except Exception as exc:  # noqa: BLE001
            summary = str(exc)[:400]
            raise ProviderOutcomeUnknownError(
                f"garment realism images.edit failed: {type(exc).__name__}: {summary}"
            ) from exc

        png = extract_edit_png_bytes(result)
        # Force opaque RGB product plate (FASHN prefers non-transparent garment refs).
        with Image.open(io.BytesIO(png)) as im:
            im.load()
            rgb = Image.new("RGB", im.size, (245, 245, 245))
            if im.mode == "RGBA":
                rgb.paste(im, mask=im.split()[-1])
            else:
                rgb.paste(im.convert("RGB"))
            out = io.BytesIO()
            rgb.save(out, format="PNG")
            product = out.getvalue()

        meta: dict[str, Any] = {
            "prompt_version": GARMENT_REALISM_PROMPT_VERSION,
            "provider": GARMENT_REALISM_PROVIDER_ID,
            "model": kwargs.get("model"),
            "category": category or "auto",
            "source_plate_sha256": hashlib.sha256(plate_png).hexdigest(),
            "product_sha256": hashlib.sha256(product).hexdigest(),
        }
        return product, meta


def decode_data_url_png(raw: str) -> bytes:
    text = (raw or "").strip()
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        data = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid garment image encoding") from exc
    if not data:
        raise ValueError("Empty garment image")
    # Prove it's a PNG/JPEG the pipeline can open.
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, format="PNG")
        return buf.getvalue()
