"""Social look illustration → photoreal garment reference (alpha-preserving).

FashionRise published looks are illustrated design specs. Direct try-on pastes that
art style onto a real person. This module runs one bounded OpenAI images.edit to
produce an isolated photoreal garment reference, then post-processes alpha so
sheer/cutaway regions from the source look are not baked opaque (the failure mode
of the earlier productize→Max path that flattened RGBA onto gray RGB).
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

from PIL import Image, ImageFilter, ImageStat

from app.core.config import get_settings
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    extract_edit_png_bytes,
)

logger = logging.getLogger(__name__)

LOOK_NORMALIZE_PROMPT_KIND = "fitting_room_look_normalize_v1"
LOOK_STUDIO_BG_RGB = (242, 242, 242)

# Structural design-spec prompt — describes WHAT to build, not "be photorealistic".
LOOK_NORMALIZE_PROMPT = (
    "Task: rebuild this FashionRise look as a catalog PRODUCT PHOTO of a real sewn garment. "
    "Treat the input as a DESIGN SPECIFICATION only (silhouette, neckline, straps, wrap "
    "waist, panel colors, hem asymmetry, sheer layering, openings). "
    "Do NOT copy illustration style: no ink outlines, no graphic fold strokes, no flat "
    "digital painting, no airbrushed concept-art shading, no ghost mannequin sketch. "
    "OUTPUT: clothing alone on a clean light studio backdrop (or transparent). "
    "No person, face, hair, hands, or drawn body silhouette. "
    "MATERIAL: real chiffon/tulle/woven cloth with photographic micro-texture, soft "
    "contact shadows, gravity folds, and natural specular highlights from studio light. "
    "MULTI-TONE: keep upper vs lower panel hues distinct — never unify. "
    "SHEER/CUTAWAY: keep translucent layers and high-low openings as open space or true "
    "sheer cloth — never bake an opaque filled skirt. "
    "No boots, leggings, or invented underlayers."
)


def extract_look_design_spec(
    garment_png: bytes,
    *,
    look_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Offline design facts from a published look plate (no paid vision call)."""
    from app.services.fitting_room import (
        analyze_fashionrise_look_plate,
        analyze_look_plate_sheer_legs,
        sample_look_garment_panel_colors,
    )

    analysis = look_analysis if isinstance(look_analysis, dict) else analyze_fashionrise_look_plate(
        garment_png
    )
    lock = analysis.get("look_color_lock")
    if not isinstance(lock, dict):
        lock = sample_look_garment_panel_colors(garment_png)
    sheer = analysis.get("sheer") if isinstance(analysis.get("sheer"), dict) else {}
    if not sheer:
        sheer = analyze_look_plate_sheer_legs(garment_png)

    bits: list[str] = [
        "source_type: fashion_illustration_look_plate",
        "ignore_drawn_model_body_face_hair",
        "output_clothing_item_alone",
    ]
    if isinstance(lock, dict):
        bits.append(
            "panel_colors: bodice "
            f"{lock.get('bodice_hex')} / skirt {lock.get('skirt_hex')} "
            f"({lock.get('relation')})"
        )
        bits.append("keep_multi_tone_panels_distinct")
    if sheer.get("sheer_legs"):
        bits.append("coverage: sheer_or_cutaway_lower — keep legs/openings visible")
        if sheer.get("signals", {}).get("asymmetric") or float(sheer.get("side_open_delta") or 0) >= 0.08:
            bits.append("hem: asymmetrical_high_low")
        bits.append("fabric_hint: layered_chiffon_or_tulle_where_translucent")
    else:
        bits.append("coverage: treat_lower_as_drawn — do_not_invent_extra_opacity")

    return {
        "bits": bits,
        "look_color_lock": lock,
        "sheer_legs": bool(sheer.get("sheer_legs")),
        "sheer": sheer,
        "preferred_path": "normalize_then_max",
    }


def build_look_openness_mask(garment_png: bytes) -> Image.Image | None:
    """Per-pixel openness map (0=solid garment, 255=fully open) from the look plate.

    Uses skin-like + pale-through-sheer heuristics in the lower garment band so
    post-normalize alpha can re-open regions the generator filled opaque.
    """
    from app.services.fitting_room import _is_garment_chrominance_pixel, _is_skin_like_rgb

    if not garment_png:
        return None
    try:
        with Image.open(io.BytesIO(garment_png)) as im:
            im.load()
            rgb = im.convert("RGB")
    except Exception:  # noqa: BLE001
        return None

    w, h = rgb.size
    if w < 8 or h < 16:
        return None
    mask = Image.new("L", (w, h), 0)
    px = rgb.load()
    out = mask.load()
    # Full body: mild openness on skin; strong in lower band.
    for y in range(h):
        lower = y >= int(h * 0.52)
        for x in range(w):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            if mx < 28:
                continue
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            mn = min(r, g, b)
            sat = (mx - mn) / float(mx or 1)
            open_v = 0
            if _is_skin_like_rgb(r, g, b):
                open_v = 255 if lower else 200
            elif lower and luma >= 125 and sat <= 0.40 and not (
                _is_garment_chrominance_pixel(r, g, b) and sat > 0.28 and luma < 110
            ):
                # Pale / translucent overlay over legs in illustrations.
                open_v = 170
            elif lower and _is_garment_chrominance_pixel(r, g, b) and sat < 0.22 and luma > 140:
                open_v = 110
            if open_v:
                out[x, y] = open_v
    # Soften so alpha re-open does not look cut-out jagged.
    return mask.filter(ImageFilter.GaussianBlur(radius=max(1, min(w, h) // 180)))


def apply_openness_mask_to_product(
    product_png: bytes,
    openness: Image.Image | None,
    *,
    sheer_expected: bool,
) -> tuple[bytes, dict[str, Any]]:
    """Re-apply source openness onto a generated product so sheer is not baked opaque.

    Does NOT flatten to opaque RGB. Returns PNG (RGBA when sheer/openings exist).
    """
    meta: dict[str, Any] = {
        "alpha_preserved": False,
        "openness_applied": False,
        "sheer_expected": sheer_expected,
    }
    if not product_png:
        return product_png, meta
    try:
        with Image.open(io.BytesIO(product_png)) as im:
            im.load()
            rgba = im.convert("RGBA")
    except Exception:  # noqa: BLE001
        return product_png, meta

    if openness is not None:
        if openness.size != rgba.size:
            openness = openness.resize(rgba.size, Image.Resampling.BILINEAR)
        px = rgba.load()
        op = openness.load()
        w, h = rgba.size
        touched = 0
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                open_v = int(op[x, y])
                if open_v < 24:
                    continue
                # Reduce alpha where the look showed openings / sheer.
                # Keep some fabric presence for soft tulle (not full wipe).
                factor = 1.0 - (open_v / 255.0) * (0.92 if sheer_expected else 0.75)
                new_a = int(round(a * max(0.0, min(1.0, factor))))
                if new_a < a:
                    touched += 1
                px[x, y] = (r, g, b, new_a)
        meta["openness_applied"] = touched > 0
        meta["openness_pixels_adjusted"] = touched

    # Detect remaining alpha.
    alpha = rgba.split()[-1]
    extrema = alpha.getextrema()
    has_transparency = bool(extrema and extrema[0] < 250)
    meta["alpha_preserved"] = has_transparency

    out = io.BytesIO()
    if has_transparency or sheer_expected:
        rgba.save(out, format="PNG", optimize=True)
    else:
        # Solid garments: light studio RGB is fine for try-on / FASHN.
        bg = Image.new("RGB", rgba.size, LOOK_STUDIO_BG_RGB)
        bg.paste(rgba, mask=alpha)
        bg.save(out, format="PNG", optimize=True)
        meta["alpha_preserved"] = False
    return out.getvalue(), meta


def composite_look_garment_for_try_on(product_png: bytes) -> bytes:
    """Light-studio composite for OpenAI try-on input (avoids charcoal matte holes).

    Openings stay light-gray (readable as non-clothing). Opaque fabric unchanged.
    """
    if not product_png:
        return product_png
    try:
        with Image.open(io.BytesIO(product_png)) as im:
            im.load()
            rgba = im.convert("RGBA")
    except Exception:  # noqa: BLE001
        return product_png
    bg = Image.new("RGBA", rgba.size, (*LOOK_STUDIO_BG_RGB, 255))
    composed = Image.alpha_composite(bg, rgba).convert("RGB")
    out = io.BytesIO()
    composed.save(out, format="PNG", optimize=True)
    return out.getvalue()


def look_normalize_prompt(spec: dict[str, Any]) -> str:
    bits = spec.get("bits") if isinstance(spec, dict) else None
    prompt = LOOK_NORMALIZE_PROMPT
    if isinstance(bits, list) and bits:
        prompt += " Design attributes: " + "; ".join(str(b) for b in bits[:12]) + "."
    lock = spec.get("look_color_lock") if isinstance(spec, dict) else None
    if isinstance(lock, dict):
        bh = str(lock.get("bodice_hex") or "")
        sh = str(lock.get("skirt_hex") or "")
        if bh.startswith("#") and sh.startswith("#"):
            prompt += (
                f" COLOR LOCK: bodice {bh}, skirt {sh}. "
                "Keep the measured value difference; never average into one mid-tone."
            )
    return prompt


def normalize_fashionrise_look_garment(
    *,
    garment_png: bytes,
    data: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    """OpenAI images.edit: look illustration → isolated photoreal garment (alpha-aware)."""
    from app.services.sketch_openai import (
        SketchCompletionError,
        assert_image_model_editable,
        build_image_edit_kwargs,
    )

    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
    if not settings.my_croquis_ai_live_http:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_LIVE_HTTP is false")
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0")
    if not (settings.openai_api_key or "").strip():
        raise ProviderNotAvailableError("OPENAI_API_KEY missing")

    analysis = data.get("look_analysis") if isinstance(data.get("look_analysis"), dict) else None
    spec = extract_look_design_spec(garment_png, look_analysis=analysis)
    data["look_design_spec"] = spec
    if spec.get("look_color_lock") and not data.get("look_color_lock"):
        data["look_color_lock"] = spec["look_color_lock"]
    data["look_sheer_legs"] = bool(spec.get("sheer_legs"))

    model = (settings.openai_image_model or "").strip()
    assert_image_model_editable(model)
    size = (settings.openai_image_size or "1024x1536").strip()
    quality = settings.openai_image_quality

    try:
        kwargs = build_image_edit_kwargs(
            model=model,
            prompt=look_normalize_prompt(spec),
            sketch=(garment_png, "image/png"),
            size=size,
            quality=quality,
            fabric_swatch=None,
        )
    except SketchCompletionError as exc:
        raise ProviderNotAvailableError(str(exc)) from exc

    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    # Prefer transparent product when the API accepts it (gpt-image family).
    kwargs["background"] = "transparent"
    # High input_fidelity preserves illustration strokes — drop it so the model can
    # rebuild photographic fabric instead of tracing the sketch.
    kwargs.pop("input_fidelity", None)
    extra = dict(kwargs.get("extra_body") or {})
    extra["moderation"] = "low"
    if "input_fidelity" in extra:
        extra.pop("input_fidelity", None)
    kwargs["extra_body"] = extra

    from openai import OpenAI

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=float(settings.openai_timeout_seconds or 180),
    )
    try:
        result = client.with_options(max_retries=0).images.edit(**kwargs)
    except Exception as exc:  # noqa: BLE001
        # Retry once without background= if the model rejects the parameter.
        summary = str(exc)[:400]
        if "background" in summary.lower():
            kwargs.pop("background", None)
            try:
                result = client.with_options(max_retries=0).images.edit(**kwargs)
            except Exception as exc2:  # noqa: BLE001
                raise ProviderOutcomeUnknownError(
                    f"look normalize images.edit failed: {type(exc2).__name__}: {str(exc2)[:400]}"
                ) from exc2
        else:
            raise ProviderOutcomeUnknownError(
                f"look normalize images.edit failed: {type(exc).__name__}: {summary}"
            ) from exc

    raw_png = extract_edit_png_bytes(result)
    # One bounded style retry if the first product still reads as illustration.
    style = estimate_sketch_texture_score(raw_png)
    style_retry = False
    if style.get("illustrated_texture_suspected"):
        style_retry = True
        retry_prompt = (
            look_normalize_prompt(spec)
            + " CRITICAL RETRY: previous output still looked like a digital fashion "
            "illustration. Emit a real-camera product photo of physical cloth only."
        )
        kwargs["prompt"] = retry_prompt
        kwargs.pop("input_fidelity", None)
        try:
            result = client.with_options(max_retries=0).images.edit(**kwargs)
            raw_png = extract_edit_png_bytes(result)
            style = estimate_sketch_texture_score(raw_png)
        except Exception:  # noqa: BLE001
            logger.info("look normalize style retry failed — keeping first product", exc_info=True)

    openness = build_look_openness_mask(garment_png) if spec.get("sheer_legs") else None
    product, alpha_meta = apply_openness_mask_to_product(
        raw_png,
        openness,
        sheer_expected=bool(spec.get("sheer_legs")),
    )
    # Mild color lock only on remaining opaque pixels (skip_skin already).
    if data.get("look_color_lock") and not spec.get("sheer_legs"):
        from app.services.fitting_room import reinforce_look_plate_panel_colors

        product = reinforce_look_plate_panel_colors(
            product, data.get("look_color_lock"), strength=0.28
        )

    try_on_plate = composite_look_garment_for_try_on(product)
    meta = {
        "provider": "openai_look_normalize",
        "model": kwargs.get("model"),
        "prompt_kind": LOOK_NORMALIZE_PROMPT_KIND,
        "source_sha256": hashlib.sha256(garment_png).hexdigest(),
        "product_sha256": hashlib.sha256(product).hexdigest(),
        "try_on_plate_sha256": hashlib.sha256(try_on_plate).hexdigest(),
        "look_color_lock": data.get("look_color_lock"),
        "look_design_spec": {"bits": spec.get("bits"), "sheer_legs": spec.get("sheer_legs")},
        "alpha": alpha_meta,
        "background_param": kwargs.get("background"),
        "input_fidelity": kwargs.get("input_fidelity", "omit"),
        "style_retry": style_retry,
        "product_texture": style,
    }
    # Stash try-on plate on data for the caller.
    data["look_normalized_product_png"] = product
    data["look_normalized_tryon_png"] = try_on_plate
    data["look_normalized"] = True
    return try_on_plate, meta


def estimate_sketch_texture_score(png: bytes) -> dict[str, Any]:
    """Deterministic sketch/illustration texture signals on a try-on result.

    High edge density + low local chroma variance in the garment band often means
    pasted illustration folds rather than photographed cloth.
    """
    empty = {
        "edge_density": 0.0,
        "chroma_flatness": 0.0,
        "illustrated_texture_suspected": False,
    }
    if not png:
        return empty
    try:
        with Image.open(io.BytesIO(png)) as im:
            im.load()
            rgb = im.convert("RGB")
    except Exception:  # noqa: BLE001
        return empty

    w, h = rgb.size
    if w < 16 or h < 32:
        return empty

    def _edge_mean(box: tuple[float, float, float, float]) -> float:
        crop = rgb.crop(
            (int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3]))
        )
        gray = crop.convert("L").resize((64, 96), Image.Resampling.BILINEAR)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        return float(ImageStat.Stat(edges).mean[0]) / 255.0

    # Garment band (torso→hem) vs face band — illustrated folds often spike edges
    # relative to photographic skin/hair detail.
    garment_edge = _edge_mean((0.20, 0.34, 0.80, 0.94))
    face_edge = _edge_mean((0.30, 0.04, 0.70, 0.28))
    edge_density = garment_edge
    edge_ratio = garment_edge / max(face_edge, 1e-3)

    crop = rgb.crop((int(w * 0.22), int(h * 0.34), int(w * 0.78), int(h * 0.92)))
    small_c = crop.resize((64, 96), Image.Resampling.BILINEAR)
    sats: list[float] = []
    for r, g, b in small_c.getdata():
        mx, mn = max(r, g, b), min(r, g, b)
        if mx < 30:
            continue
        sats.append((mx - mn) / float(mx))
    if len(sats) < 20:
        return empty
    mean_s = sum(sats) / len(sats)
    var_s = sum((s - mean_s) ** 2 for s in sats) / len(sats)
    chroma_flatness = 1.0 / (1.0 + var_s * 80.0)
    # Tuned against the green-dress illustrated failure (garment edges >> face).
    illustrated = (garment_edge >= 0.12 and chroma_flatness >= 0.45 and var_s < 0.03) or (
        edge_ratio >= 1.25 and garment_edge >= 0.12 and var_s < 0.035
    )
    return {
        "edge_density": round(edge_density, 3),
        "face_edge_density": round(face_edge, 3),
        "garment_face_edge_ratio": round(edge_ratio, 3),
        "chroma_flatness": round(chroma_flatness, 3),
        "sat_variance": round(var_s, 5),
        "illustrated_texture_suspected": illustrated,
    }
