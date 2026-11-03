"""OpenAI images.edit → photorealistic garment product image for FASHN (#161/#167/#180).

Transforms FashionRise flat-lay sketch plates into e-commerce product photographs
**without** inventing a person/mannequin. Owner must review and accept before any
FASHN credit is spent. Separate spend reservation from the FASHN try-on job.

#167 reuses Fashion Magic coverage + color fidelity contracts and optional Studio
croquis context. Does **not** copy Fashion Magic's non-photoreal illustration style.

#180 croquis-conditioned realism: composite the accepted personal croquis under the
garment sketch so OpenAI can see exposed legs through slits (dress vs trousers).
Image 1 = on-figure Studio layer; Image 2 = isolated plate (colors). OUTPUT removes
the croquis/figure — clothing alone for FASHN.
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
GARMENT_REALISM_PROMPT_VERSION = "fashn-garment-realism-v6"
GARMENT_REALISM_PROVIDER_ID = "openai_garment_realism"
LOCAL_PRODUCT_PROVIDER_ID = "local_filled_plate_v1"
# #180 — silhouette lock for open-leg / high-slit dresses: never let generative
# realism invent trousers. Local plate productization preserves Studio geometry.
STRUCTURE_PRESERVING_LOCAL_REASON = "source_high_slit_dress_lock_silhouette"

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

# #180 — croquis underlay is a removable reference layer for outfit type.
_CROQUIS_CONDITIONED_CONTRACT = (
    "CROQUIS-CONDITIONED READING: Image 1 is the Studio croquis figure WITH the garment "
    "sketch layered on top (figure underlay + garment artwork). Use Image 1 to read "
    "garment TYPE and openings: if the figure's legs or skin show through a center or "
    "side gap, that gap is a fashion slit on a dress/skirt/gown — NOT separate trouser "
    "legs, pants, or a jumpsuit. Do not invent a crotch seam or two pant legs. "
    "Image 2 is the isolated transparent garment plate — authoritative for colors, "
    "prints, gradients, and panel fills. "
    "OUTPUT: remove the croquis figure, body, face, hands, paper, and underlay entirely. "
    "Emit only the clothing product on a neutral studio background, preserving the dress "
    "or skirt as one continuous garment with the slit kept as open negative space."
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

GARMENT_REALISM_PROMPT_CROQUIS_CONDITIONED = (
    "Transform this Studio fashion design into a photorealistic commercial clothing "
    "product photograph of the real garment. "
    f"{_CROQUIS_CONDITIONED_CONTRACT} "
    f"{COVERAGE_PRESERVATION_CONTRACT} "
    f"{COLOR_FIDELITY_CONTRACT} "
    f"{_PRODUCT_ONLY_CONTRACT} "
    "Preserve the exact garment design, silhouette, coverage, cut, selected colors, gradient "
    "placement and visible patterns from the plate. "
    "CRITICAL: Do not invent straps, twists, knots, wraps, ties, or asymmetry that are not "
    "drawn. Do not convert an open-leg / high-slit dress into trousers or a jumpsuit. "
    "Keep slit openings as fashion cutaways where the figure's legs were visible."
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
        rgba = im.convert("RGBA")
        # Opaque studio product plate (FASHN prefers non-transparent refs) while
        # keeping the exact alpha silhouette — critical for open-leg / slit dresses.
        rgb = Image.new("RGB", rgba.size, (245, 245, 245))
        rgb.paste(rgba, mask=rgba.split()[-1])
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


def should_lock_silhouette_to_plate(plate_png: bytes) -> bool:
    """True when Studio geometry is a confident open-leg / high-slit dress.

    Generative realism has repeatedly reinvented these as trousers/jumpsuits (#180).
    Locking to the filled plate preserves the designer's silhouette for FASHN.
    """
    if not plate_png:
        return False
    try:
        from app.services.garment_leg_geometry import analyze_lower_garment_geometry

        geo = analyze_lower_garment_geometry(plate_png)
    except Exception:
        return False
    return bool(geo.looks_like_high_slit_dress and not geo.looks_like_trousers)


def _fit_contain(
    src_w: int, src_h: int, box_w: int, box_h: int
) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) placing src inside box with contain + center (Studio export)."""
    if src_w <= 0 or src_h <= 0 or box_w <= 0 or box_h <= 0:
        return 0, 0, max(1, box_w), max(1, box_h)
    scale = min(box_w / float(src_w), box_h / float(src_h))
    w = max(1, int(round(src_w * scale)))
    h = max(1, int(round(src_h * scale)))
    x = (box_w - w) // 2
    y = (box_h - h) // 2
    return x, y, w, h


def compose_studio_on_figure(
    *,
    croquis_png: bytes,
    garment_png: bytes,
    max_edge: int = 1536,
) -> bytes:
    """Layer accepted personal croquis under the transparent garment capture.

    Matches Studio export alignment: croquis fit-contained on the design plane,
    garment artwork composited on top. OpenAI sees exposed legs through slits;
    the figure is a removable reference layer (output still clothing-only).
    """
    if not croquis_png or not garment_png:
        raise ValueError("croquis_png and garment_png are required")
    with Image.open(io.BytesIO(garment_png)) as g_im:
        g_im.load()
        garment = g_im.convert("RGBA")
    with Image.open(io.BytesIO(croquis_png)) as c_im:
        c_im.load()
        croquis = c_im.convert("RGBA")

    width, height = garment.size
    # Soft paper so the figure reads clearly (not a transparent void).
    canvas = Image.new("RGBA", (width, height), (245, 240, 230, 255))
    x, y, w, h = _fit_contain(croquis.width, croquis.height, width, height)
    fitted = croquis.resize((w, h), Image.Resampling.LANCZOS)
    canvas.paste(fitted, (x, y), fitted)
    canvas.alpha_composite(garment)
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return downscale_studio_context(out.getvalue(), max_edge=max_edge)


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
    croquis_conditioned: bool = False,
) -> str:
    cat = (category or "auto").strip().lower()
    extra = ""
    if croquis_conditioned:
        # Outfit type comes from on-figure Image 1 — avoid swimwear one-piece wording
        # that fights open-leg dresses.
        if cat == "tops":
            extra = (
                " Image 2 is a top / upper plate — preserve neckline and cup geometry; "
                "do not invent straps or wraps."
            )
        elif cat == "bottoms":
            extra = (
                " Image 2 is a bottoms plate — preserve waistline and coverage; "
                "do not invent side ties."
            )
        elif cat == "one-pieces":
            extra = (
                " Image 2 may be a one-piece plate OR an open-leg dress drawn as one fill. "
                "If Image 1 shows figure legs through a center opening, keep a dress/skirt "
                "with slit — do not emit trousers, a jumpsuit, or a closed swimsuit crotch."
            )
    elif cat == "tops":
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
    if croquis_conditioned:
        extra += (
            " Remember: remove the croquis figure from the output; clothing item alone."
        )
        return GARMENT_REALISM_PROMPT_CROQUIS_CONDITIONED + extra
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
        croquis_conditioned: bool = False,
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
        # #179/#180 — dress/slit vs trousers hints from the isolated plate (never the
        # on-figure composite: figure legs would false-trigger trousers).
        try:
            from app.services.garment_leg_geometry import (
                analyze_lower_garment_geometry,
                openai_trouser_design_hints,
            )

            geo_bits = openai_trouser_design_hints(analyze_lower_garment_geometry(plate_png))
            for bit in geo_bits:
                if bit not in design_bits:
                    design_bits.append(bit)
        except Exception:
            # Geometry is advisory — never block realism for analyzer errors.
            pass
        if croquis_conditioned and studio_context_png:
            if (
                "garment type: dress or gown with a high fashion slit — not trousers or a jumpsuit"
                not in design_bits
            ):
                design_bits.append(
                    "Studio on-figure layer: exposed legs through openings mean dress/slit, "
                    "not trousers — remove the croquis figure from the product output"
                )
            try:
                kwargs = build_image_edit_kwargs(
                    model=model,
                    prompt=garment_realism_prompt(
                        category=category,
                        color_hint=dominant_color_hint(plate_png) or None,
                        design_bits=design_bits,
                        has_studio_context=True,
                        croquis_conditioned=True,
                    ),
                    # Image 1 = croquis+garment (outfit type); Image 2 = plate (colors).
                    sketch=(studio_context_png, "image/png"),
                    size=size,
                    quality=quality,
                    fabric_swatch=(plate_png, "image/png"),
                )
            except SketchCompletionError as exc:
                raise ProviderNotAvailableError(str(exc)) from exc
        else:
            context = studio_context_png if studio_context_png else None
            try:
                kwargs = build_image_edit_kwargs(
                    model=model,
                    prompt=garment_realism_prompt(
                        category=category,
                        color_hint=dominant_color_hint(plate_png) or None,
                        design_bits=design_bits,
                        has_studio_context=bool(context),
                        croquis_conditioned=False,
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
        croquis_conditioned: bool = False,
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
            croquis_conditioned=croquis_conditioned,
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
            "croquis_conditioned": bool(croquis_conditioned and studio_context_png),
            "design_bits": local_design_identity_bits(category=category, plate_png=plate_png),
        }
        return product, meta


def decode_data_url_png(raw: str) -> bytes:
    """Decode a data-URL / bare base64 image and return stable PNG bytes.

    PNG payloads are returned as-is after PIL validation. Re-encoding every
    image as RGBA used to undo ``productize_filled_plate`` (RGB round-trip
    restored the source plate SHA), so Max enqueue treated silhouette-locked
    local products as sketch-like and 422'd (#180).
    """
    text = (raw or "").strip()
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        data = base64.b64decode(text, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid garment image encoding") from exc
    if not data:
        raise ValueError("Empty garment image")
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        fmt = (im.format or "").upper()
        # Preserve original PNG bytes so productize SHA / source_plate SHA stay stable.
        if fmt == "PNG" or data[:8] == b"\x89PNG\r\n\x1a\n":
            return data
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, format="PNG")
        return buf.getvalue()
