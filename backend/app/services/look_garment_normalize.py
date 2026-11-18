"""Social look illustration → photoreal product photo ("materialize" stage).

FashionRise published looks are illustrated design specs. Any try-on model that is
handed the illustration transfers its *rendering* too — painted folds, flat fills,
wrong depth — so the dress looks stuck on. This stage runs one bounded OpenAI
images.edit that re-creates the outfit as a real sewn garment on a white retail
mannequin in a photo studio. The try-on provider then receives an ordinary product
photograph, which is the input it was trained on.

Design decisions (measured on production looks, see docs/00-PROJECT-STATUS.md):

* Mannequin, not "garment alone": a floating garment loses drape, strap geometry
  and sheer layering; a transparent cut-out bakes sheer skirts opaque. On a
  mannequin the model keeps gravity, layering and true translucency.
* Color is never left to the generator: the design palette is measured up front and
  re-imposed deterministically afterwards (``look_color_lock``).
* Output is verified without another paid call; one retry only when the garment is
  missing from the result.
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

from PIL import Image, ImageFilter, ImageStat

from app.core.config import get_settings
from app.services.look_color_lock import (
    lock_plate_to_palette,
    measure_garment_bands,
    palette_prompt_clause,
    palette_summary,
)
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    extract_edit_png_bytes,
)

logger = logging.getLogger(__name__)

LOOK_MATERIALIZE_PROMPT_KIND = "fitting_room_look_materialize_v1"
LOOK_MATERIALIZE_QUALITIES = frozenset({"low", "medium", "high"})

# Wording note: OpenAI input moderation rejects this request when the prompt talks
# about taking clothing off a body (measured: "add or remove garments" → blocked).
# Describe only what to build.
LOOK_MATERIALIZE_PROMPT = (
    "Fashion e-commerce product photography only — a real camera photo of real cloth, never "
    "a sketch, painting, cartoon, CGI render, or digital illustration. Re-create the outfit "
    "from this fashion design illustration as an actual sewn garment on a matte white "
    "full-body retail mannequin with the same body form as the figure in the illustration, "
    "photographed full-length in a photo studio: plain "
    "light-grey seamless backdrop, soft even lighting, natural contact shadow on the floor. "
    "The clothing must look like physical fabric: visible textile weave and fibre "
    "micro-texture, natural gravity drape and soft creases, photographic highlights and "
    "shadows, true optical translucency where layers are sheer. Ban drawing artifacts: no "
    "ink or pencil outlines, no brush or airbrush strokes, no graphic fold lines, no flat "
    "cel fills, no illustrated shading. Keep the design identical to the illustration: same "
    "silhouette, neckline, straps, waist construction, panel layout, number of layers, hem "
    "shape and hem length. Do not invent extra sleeves, linings, underlayers, or "
    "accessories. Reproduce the garment colors exactly as in the illustration, panel by "
    "panel — same hue, same depth, same contrast between panels. Do not brighten, "
    "desaturate, shift hue, or merge different panels into one color. Whole outfit visible "
    "from shoulders to hem, centered, same framing as the illustration."
)

LOOK_MATERIALIZE_RETRY_SUFFIX = (
    " The complete garment must be clearly visible on the mannequin at the same scale as "
    "in the illustration."
)


def look_materialize_prompt(palette: dict[str, Any] | None, *, retry: bool = False) -> str:
    prompt = LOOK_MATERIALIZE_PROMPT + palette_prompt_clause(palette)
    if retry:
        prompt += LOOK_MATERIALIZE_RETRY_SUFFIX
    return prompt


def look_materialize_quality() -> str:
    raw = str(getattr(get_settings(), "fitting_room_look_materialize_quality", "") or "").strip().lower()
    return raw if raw in LOOK_MATERIALIZE_QUALITIES else "high"


def check_materialized_product(
    product_png: bytes, palette: dict[str, Any] | None
) -> dict[str, Any]:
    """Free structural check: is there still a garment of the design's size in frame?"""
    out: dict[str, Any] = {"ok": False}
    try:
        with Image.open(io.BytesIO(product_png)) as im:
            im.load()
            width, height = im.size
    except Exception:  # noqa: BLE001
        out["reason"] = "undecodable"
        return out
    out["size"] = [width, height]
    if width < 256 or height < 256:
        out["reason"] = "too_small"
        return out
    if not isinstance(palette, dict):
        # Achromatic / skin-toned design: nothing measurable — accept the photo.
        out["ok"] = True
        out["reason"] = "no_palette"
        return out
    stats = measure_garment_bands(product_png)
    design_coverage = float(palette.get("coverage") or 0.0)
    coverage = float((stats or {}).get("coverage") or 0.0)
    out["coverage"] = round(coverage, 4)
    out["coverage_ratio"] = round(coverage / design_coverage, 3) if design_coverage else None
    # Sheer / tulle on a white mannequin measures low coverage — 0.4 was rejecting
    # usable plates (ratio ~0.16) and falling back to the illustration.
    if not stats or (design_coverage and coverage < 0.2 * design_coverage):
        out["reason"] = "garment_missing"
        return out
    out["ok"] = True
    out["reason"] = "garment_present"
    return out


def _assert_materialize_armed() -> None:
    settings = get_settings()
    if not bool(getattr(settings, "fitting_room_look_materialize_enabled", True)):
        raise ProviderNotAvailableError("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED is false")
    if not settings.my_croquis_ai_enabled:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false")
    if not settings.my_croquis_ai_live_http:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_LIVE_HTTP is false")
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_SPEND_CEILING_USD is 0")
    if not (settings.openai_api_key or "").strip():
        raise ProviderNotAvailableError("OPENAI_API_KEY missing")


def _usage_summary(result: Any) -> dict[str, int] | None:
    usage = getattr(result, "usage", None)
    if usage is None:
        return None
    out: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if isinstance(value, int):
            out[key] = value
    return out or None


def _images_edit_product(*, look_png: bytes, prompt: str, quality: str) -> tuple[bytes, dict[str, Any]]:
    """One OpenAI images.edit call. Raises Provider* errors; never retries on its own."""
    from app.services.sketch_openai import (
        SketchCompletionError,
        assert_image_model_editable,
        build_image_edit_kwargs,
    )

    settings = get_settings()
    model = (settings.openai_image_model or "").strip()
    try:
        assert_image_model_editable(model)
        kwargs = build_image_edit_kwargs(
            model=model,
            prompt=prompt,
            sketch=(look_png, "image/png"),
            size=(settings.openai_image_size or "1024x1536").strip(),
            quality=quality,
            fabric_swatch=None,
        )
    except SketchCompletionError as exc:
        raise ProviderNotAvailableError(str(exc)) from exc
    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    extra = dict(kwargs.get("extra_body") or {})
    extra["moderation"] = "low"
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
        summary = f"{type(exc).__name__}: {str(exc)[:300]}"
        status = getattr(exc, "status_code", None)
        if isinstance(status, int) and 400 <= status < 500:
            # Rejected before generation (moderation / bad request) — not billed.
            raise ProviderNotAvailableError(f"look materialize rejected: {summary}") from exc
        raise ProviderOutcomeUnknownError(f"look materialize images.edit failed: {summary}") from exc
    return extract_edit_png_bytes(result), {
        "model": kwargs.get("model"),
        "quality": kwargs.get("quality"),
        "size": kwargs.get("size"),
        "usage": _usage_summary(result),
    }


def materialize_fashionrise_look(
    *,
    look_png: bytes,
    palette: dict[str, Any] | None,
    color_lock: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    """Look illustration → color-locked studio product photo (PNG, RGB).

    At most two paid images.edit calls (second only when the first lost the garment).
    Raises ``ProviderNotAvailableError`` / ``ProviderOutcomeUnknownError``; callers
    fall back to their direct try-on path.
    """
    _assert_materialize_armed()
    quality = look_materialize_quality()
    product, call_meta = _images_edit_product(
        look_png=look_png, prompt=look_materialize_prompt(palette), quality=quality
    )
    calls = 1
    check = check_materialized_product(product, palette)
    if not check["ok"]:
        logger.info("look materialize first output rejected (%s) — one retry", check.get("reason"))
        product, call_meta = _images_edit_product(
            look_png=look_png,
            prompt=look_materialize_prompt(palette, retry=True),
            quality=quality,
        )
        calls = 2
        check = check_materialized_product(product, palette)
        if not check["ok"]:
            # Prefer a marginal product photo over falling back to the illustration —
            # Max handles fabric better than painted folds pasted onto the person.
            if check.get("reason") == "garment_missing" and product:
                logger.info(
                    "look materialize second output still soft (%s) — keeping product",
                    check.get("reason"),
                )
                check = {**check, "ok": True, "accepted": "soft_keep"}
            else:
                raise ProviderNotAvailableError(
                    f"look materialize produced no usable garment ({check.get('reason')})"
                )

    lock_meta: dict[str, Any] = {"stage": "product", "applied": False, "reason": "disabled"}
    if color_lock:
        try:
            product, lock_meta = lock_plate_to_palette(product, palette)
        except Exception:  # noqa: BLE001
            logger.warning("look product color lock failed — using unlocked product", exc_info=True)
            lock_meta = {"stage": "product", "applied": False, "reason": "error"}

    meta: dict[str, Any] = {
        "provider": "openai_look_materialize",
        "prompt_kind": LOOK_MATERIALIZE_PROMPT_KIND,
        "model": call_meta.get("model"),
        "quality": call_meta.get("quality"),
        "size": call_meta.get("size"),
        "usage": call_meta.get("usage"),
        "openai_calls": calls,
        "check": check,
        "color_lock": lock_meta,
        "palette": palette_summary(palette),
        "source_sha256": hashlib.sha256(look_png).hexdigest(),
        "product_sha256": hashlib.sha256(product).hexdigest(),
    }
    return product, meta


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
