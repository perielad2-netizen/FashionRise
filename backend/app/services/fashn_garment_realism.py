"""OpenAI images.edit → photorealistic garment product image for FASHN (#161/#167).

Transforms FashionRise flat-lay sketch plates into e-commerce product photographs
**without** inventing a person/mannequin. Owner must review and accept before any
FASHN credit is spent. Separate spend reservation from the FASHN try-on job.

#167 reuses Fashion Magic coverage + color fidelity contracts and optional Studio
croquis context. Does **not** copy Fashion Magic's non-photoreal illustration style.
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
from app.services.sketch_openai import (
    COLOR_FIDELITY_CONTRACT,
    COVERAGE_PRESERVATION_CONTRACT,
)

logger = logging.getLogger(__name__)

GARMENT_REALISM_JOB_TYPE = "personal_garment_realism"
GARMENT_REALISM_PROMPT_VERSION = "fashn-garment-realism-v5"
GARMENT_REALISM_PROVIDER_ID = "openai_garment_realism"
LOCAL_PRODUCT_PROVIDER_ID = "local_filled_plate_v1"

# Plate geometry is authoritative — textile realism only; no wrap/twist redesign.
_AUTHORITATIVE_GEOMETRY_CONTRACT = (
    "AUTHORITATIVE GEOMETRY: Image 1 is the isolated garment plate. Treat its mask, "
    "outlines, color fills, cup/panel separation, neckline depth, waistline, leg openings, "
    "and design geometry as ground truth. Add realistic textile qualities (soft cloth edges, "
    "natural folds, subtle seams, swimwear sheen) WITHOUT changing coverage, joining "
    "intentionally separate panels, inventing straps/twists/wraps/ties, or filling open "
    "necklines / midriff / cut-outs. Do not redesign."
)

_STUDIO_CONTEXT_CONTRACT = (
    "STUDIO CONTEXT: When Image 2 is present, it is the complete Studio croquis showing "
    "how this garment sits on the figure (neckline depth, bikini cut, exposed midriff, "
    "swimwear openings). Use it only to understand coverage openings and construction — "
    "the isolated plate in Image 1 remains the output silhouette and fill authority. "
    "Still output the clothing item alone."
)

_PRODUCT_ONLY_CONTRACT = (
    "OUTPUT: Photorealistic professional product photograph of the clothing item alone "
    "against a neutral studio background. No person, body, mannequin, model, face, hands, "
    "or Fashion Magic illustration style. Remove sketch stroke outlines, paper/canvas "
    "texture, flat vector fills and illustrated line art. Legitimate opaque fashion "
    "garment for clothing design and virtual try-on."
)

GARMENT_REALISM_PROMPT = (
    "Transform this fashion designer's garment sketch plate into a photorealistic commercial "
    "clothing product photograph of the real garment. "
    f"{_AUTHORITATIVE_GEOMETRY_CONTRACT} "
    f"{COVERAGE_PRESERVATION_CONTRACT} "
    f"{COLOR_FIDELITY_CONTRACT} "
    f"{_STUDIO_CONTEXT_CONTRACT} "
    f"{_PRODUCT_ONLY_CONTRACT} "
    "Preserve the exact garment design, silhouette, coverage, cut, selected colors, gradient "
    "placement and visible patterns. Render smooth realistic swimwear fabric. "
    "CRITICAL: Do not invent straps, twists, knots, wraps, ties, ruffles, or asymmetry that "
    "are not drawn. Do not change neckline depth, cup shape, waistline height, or coverage. "
    "Do not turn a swimsuit into a dress or skirt. Keep gradient direction and color "
    "placement identical to the plate."
)


def productize_filled_plate(plate_png: bytes) -> tuple[bytes, dict[str, Any]]:
    """Color-preserving FASHN reference from a filled Studio plate — no generative redesign.

    Owner #164: OpenAI images.edit restyled a deep-V bikini top into a twisted wrap and
    altered bottoms/gradient. Dense filled plates already carry exact cut + colors.
    """
    if not plate_png:
        raise ValueError("Empty plate for local productization")
    with Image.open(io.BytesIO(plate_png)) as im:
        im.load()
        rgb = im.convert("RGB")
        # Soften only near edges slightly without shifting hues of filled regions.
        out = io.BytesIO()
        rgb.save(out, format="PNG", optimize=True)
        product = out.getvalue()
    meta = {
        "prompt_version": LOCAL_PRODUCT_PROVIDER_ID,
        "provider": LOCAL_PRODUCT_PROVIDER_ID,
        "model": None,
        "source_plate_sha256": hashlib.sha256(plate_png).hexdigest(),
        "product_sha256": hashlib.sha256(product).hexdigest(),
        "local_product": True,
    }
    return product, meta


def estimate_garment_realism_cents(*, pieces: int = 1) -> int:
    settings = get_settings()
    per = max(1, int(getattr(settings, "fashn_garment_realism_estimate_cents", None) or settings.my_croquis_ai_estimate_cents or 8))
    return per * max(1, int(pieces))


def dominant_color_hint(plate_png: bytes, *, limit: int = 3) -> str:
    """Sample non-near-white garment colors for prompt injection."""
    with Image.open(io.BytesIO(plate_png)) as im:
        im.load()
        rgb = im.convert("RGB")
        # Downsample for speed
        small = rgb.resize((64, 64), Image.Resampling.BILINEAR)
        counts: dict[tuple[int, int, int], int] = {}
        for px in small.getdata():
            r, g, b = px
            if r >= 230 and g >= 230 and b >= 230:
                continue
            if r < 40 and g < 40 and b < 40:
                continue  # stroke ink
            key = (r // 16 * 16, g // 16 * 16, b // 16 * 16)
            counts[key] = counts.get(key, 0) + 1
        top = sorted(counts.items(), key=lambda t: t[1], reverse=True)[: max(1, limit)]
        if not top:
            return ""
        return ", ".join(f"#{r:02X}{g:02X}{b:02X}" for (r, g, b), _n in top)


def downscale_studio_context(png: bytes, *, max_edge: int = 1024) -> bytes:
    """Persist a bounded Studio croquis context image (full figure + garment)."""
    if not png:
        return b""
    with Image.open(io.BytesIO(png)) as im:
        im.load()
        rgba = im.convert("RGBA")
        w, h = rgba.size
        edge = max(w, h)
        if edge > max_edge:
            scale = max_edge / float(edge)
            rgba = rgba.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        out = io.BytesIO()
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue()


def local_design_identity_bits(*, category: str | None, plate_png: bytes) -> list[str]:
    """Offline structured design facts from plate geometry (no paid vision call).

    Mirrors Fashion Magic design_identity fields that matter for swimwear coverage.
    """
    from app.services.fashn_garment_fidelity import compute_silhouette_features

    feats = compute_silhouette_features(plate_png)
    cat = (category or "auto").strip().lower()
    bits: list[str] = []
    if cat == "tops":
        bits.append("garment_category: bikini / swimsuit top")
        bits.append("silhouette: two-piece top cups / panels as drawn")
    elif cat == "bottoms":
        bits.append("garment_category: bikini / swimsuit bottom")
        bits.append("silhouette: two-piece bottoms coverage as drawn")
    elif cat == "one-pieces":
        bits.append("garment_category: one-piece swimsuit or bodysuit")
    elif feats.swimsuit_like:
        bits.append("garment_category: swimwear as drawn")

    wp = feats.width_profile
    if len(wp) >= 3 and wp[2] > 0:
        top_ratio = wp[0] / float(wp[2])
        if top_ratio <= 0.55:
            bits.append(
                "neckline: deep open / plunging opening — preserve the gap; do not fill, "
                "wrap, or twist fabric across it"
            )
        if top_ratio <= 0.25:
            bits.append(
                "cutouts_and_openings: separated cups or panels with intentional center opening"
            )

    if cat in {"tops", "bottoms"}:
        bits.append("skin_visible_regions: exposed midriff between top and bottom pieces")
    if feats.swimsuit_like:
        bits.append(
            "cutouts_and_openings: swimwear openings, leg openings, and strap placements exactly as drawn"
        )
    colors = dominant_color_hint(plate_png)
    if colors:
        bits.append(f"main_colors: {colors}")
    return bits


def garment_realism_prompt(
    *,
    category: str | None = None,
    color_hint: str | None = None,
    design_bits: list[str] | None = None,
    has_studio_context: bool = False,
) -> str:
    cat = (category or "auto").strip().lower()
    extra = ""
    if cat == "tops":
        extra = (
            " This plate is a bikini / swimsuit top only. Keep the exact deep-V or drawn "
            "neckline and cup geometry, including intentionally separate cups. Do not invent "
            "shoulder straps, twists, wraps, or a connecting bridge that fills the opening."
        )
    elif cat == "bottoms":
        extra = (
            " This plate is a bikini / swimsuit bottom only. Keep the exact waistline height "
            "and coverage. Do not invent side ties or change the cut."
        )
    elif cat == "one-pieces":
        extra = (
            " This plate is a one-piece swimsuit or bodysuit. Keep high-cut leg openings and "
            "one-piece coverage. It must not become a mini dress, skirt, or gown."
        )
    if design_bits:
        extra += " Preserve these design attributes: " + "; ".join(design_bits) + "."
    if color_hint:
        extra += f" Preserve these sketch colors exactly: {color_hint}."
    if has_studio_context:
        extra += (
            " Image 2 is the complete Studio croquis for coverage context only; "
            "Image 1 plate geometry remains authoritative for the product silhouette."
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

    def build_edit_kwargs(
        self,
        *,
        plate_png: bytes,
        category: str | None = None,
        studio_context_png: bytes | None = None,
    ) -> dict[str, Any]:
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
        design_bits = local_design_identity_bits(category=category, plate_png=plate_png)
        # #179 — carry croquis/studio garment geometry (dress slit vs trousers) into
        # realism design_bits. Prefer full Studio context when present; never invent.
        try:
            from app.services.garment_leg_geometry import (
                analyze_lower_garment_geometry,
                openai_trouser_design_hints,
            )

            geo_src = studio_context_png if studio_context_png else plate_png
            geo_bits = openai_trouser_design_hints(analyze_lower_garment_geometry(geo_src))
            for bit in geo_bits:
                if bit not in design_bits:
                    design_bits.append(bit)
        except Exception:
            # Geometry is advisory — never block realism for analyzer errors.
            pass
        context = studio_context_png if studio_context_png else None
        try:
            kwargs = build_image_edit_kwargs(
                model=model,
                prompt=garment_realism_prompt(
                    category=category,
                    color_hint=dominant_color_hint(plate_png) or None,
                    design_bits=design_bits,
                    has_studio_context=bool(context),
                ),
                sketch=(plate_png, "image/png"),
                size=size,
                quality=quality,
                # Reuse second-image slot: Studio croquis context (not a textile swatch).
                fabric_swatch=(context, "image/png") if context else None,
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

    def generate_piece(
        self,
        *,
        plate_png: bytes,
        category: str | None = None,
        studio_context_png: bytes | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        settings = get_settings()
        if not settings.my_croquis_ai_live_http:
            raise ProviderNotAvailableError(
                "MY_CROQUIS_AI_LIVE_HTTP is false — live garment realism not armed"
            )
        if not (settings.openai_api_key or "").strip():
            raise ProviderNotAvailableError("OPENAI_API_KEY missing")

        kwargs = self.build_edit_kwargs(
            plate_png=plate_png,
            category=category,
            studio_context_png=studio_context_png,
        )
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
            "studio_context": bool(studio_context_png),
            "design_bits": local_design_identity_bits(category=category, plate_png=plate_png),
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
