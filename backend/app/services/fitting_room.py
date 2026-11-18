"""AI Fitting Room — person photo + clothing image(s) → try-on preview (F1–F5).

Reuses the OpenAI Try On Person images.edit adapter. Fail-closed behind
``fitting_room_enabled`` / ``fitting_room_live_http``. No wardrobe, stylist,
shopping, or new billing.

Stars: flat ``ai_stars_fitting_room_cost`` (default 20) per successful try-on,
regardless of how many garments appear in the clothing image / outfit collage.
Debit only after success.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import uuid
from typing import Any

from fastapi import HTTPException, status
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.user import User
from app.services.ai_stars import assert_can_spend_fitting_room, fitting_room_cost
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_PROMPT_VERSION,
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    get_try_on_provider,
)
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

FITTING_ROOM_JOB_TYPE = "fitting_room_try_on"
FITTING_ROOM_MODE = "fitting_room"
FITTING_ROOM_CONSENT_VERSION = "fitting-room-preview-v1"
FITTING_ROOM_NOTICE = (
    "AI Fitting Room creates a visual concept preview only — not an accurate size "
    "or fit guarantee. Your photo and clothing image stay private."
)

_DATA_URL_RE = re.compile(r"^data:([^;,]+)?(;base64)?,(.+)$", re.DOTALL | re.IGNORECASE)

# Categories the OpenAI path can soft-hint; unsupported combos stay honest in FE.
SUPPORTED_GARMENT_CATEGORIES = frozenset(
    {"auto", "tops", "bottoms", "one-pieces", "dresses", "outerwear", "shoes"}
)

# Combinations that conflict for a single try-on plate (honest UX — still allowed
# only when the client sends a single composite; we surface warnings in preflight).
CONFLICTING_CATEGORY_SETS: tuple[frozenset[str], ...] = (
    frozenset({"one-pieces", "tops"}),
    frozenset({"one-pieces", "bottoms"}),
    frozenset({"dresses", "tops"}),
    frozenset({"dresses", "bottoms"}),
    frozenset({"one-pieces", "dresses"}),
)

MAX_OUTFIT_PIECES = 4


def fitting_room_enabled() -> bool:
    return bool(get_settings().fitting_room_enabled)


def fitting_room_live_armed() -> bool:
    settings = get_settings()
    return bool(settings.fitting_room_enabled and settings.fitting_room_live_http)


def combo_warning_for_categories(categories: list[str]) -> str | None:
    cats = {c for c in categories if c and c != "auto"}
    for conflict in CONFLICTING_CATEGORY_SETS:
        if conflict.issubset(cats):
            labels = " + ".join(sorted(conflict))
            return (
                f"Selected categories ({labels}) usually conflict on one body. "
                "The AI will still attempt a single preview collage, but results "
                "may look inconsistent — prefer replacing one piece."
            )
    return None


def preflight_public(*, user: User) -> dict[str, Any]:
    """No billable work — UI gate + consent copy + categories + flat Stars cost."""
    _ = user
    settings = get_settings()
    enabled = fitting_room_enabled()
    cost = fitting_room_cost()
    return {
        "enabled": enabled,
        "live_http": fitting_room_live_armed(),
        "consent_version": FITTING_ROOM_CONSENT_VERSION,
        "notice_text": FITTING_ROOM_NOTICE,
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "supported_categories": sorted(SUPPORTED_GARMENT_CATEGORIES),
        "preview_disclaimer": (
            "Concept preview only — not a fit guarantee. Results may differ from real garments."
        ),
        "ai_gate": bool(settings.my_croquis_ai_enabled),
        "stars_cost": cost,
        "stars_cost_note": (
            f"{cost} Stars per successful Fitting Room preview — flat rate whether the "
            "clothing image shows one garment or several."
        ),
        "max_outfit_pieces": MAX_OUTFIT_PIECES,
        "conflicting_category_sets": [sorted(s) for s in CONFLICTING_CATEGORY_SETS],
    }


def _orient_upload_to_png(decoded: bytes, *, field: str) -> bytes:
    """Bake EXIF orientation into pixel data and strip metadata (PNG).

    Phone portrait JPEGs often store landscape pixels + Orientation=6. Browsers
    show them upright in <img>, but providers receive sideways bytes unless we
    transpose here — which produced Fitting Room results rotated 90°.
    """
    try:
        opened = Image.open(io.BytesIO(decoded))
        oriented = ImageOps.exif_transpose(opened) or opened
        oriented.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} is not a readable image.",
        ) from exc
    if oriented.mode in ("RGBA", "LA") or (
        oriented.mode == "P" and "transparency" in oriented.info
    ):
        converted = oriented.convert("RGBA")
    else:
        converted = oriented.convert("RGB")
    buf = io.BytesIO()
    converted.save(buf, format="PNG", optimize=True)
    out = buf.getvalue()
    settings = get_settings()
    if len(out) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is too large.")
    return out


def _decode_png(raw: str, *, field: str) -> bytes:
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required.")
    text = raw.strip()
    match = _DATA_URL_RE.match(text)
    b64 = match.group(3) if match else text
    try:
        decoded = base64.b64decode(b64, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is not valid base64."
        ) from exc
    if len(decoded) < 32:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is empty.")
    settings = get_settings()
    if len(decoded) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is too large.")
    if decoded[:8] != b"\x89PNG\r\n\x1a\n":
        if decoded[:2] != b"\xff\xd8":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} must be a PNG or JPEG image.",
            )
    return _orient_upload_to_png(decoded, field=field)


def _normalize_category(raw: str | None) -> str:
    cat = (raw or "auto").strip().lower() or "auto"
    if cat not in SUPPORTED_GARMENT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported garment category '{cat}'.",
        )
    return cat


def _bytes_to_rgba(png_or_jpeg: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png_or_jpeg))
    img = ImageOps.exif_transpose(img) or img
    return img.convert("RGBA")


def compose_outfit_collage(piece_pngs: list[bytes]) -> bytes:
    """Side-by-side collage of outfit pieces for a single images.edit garment plate.

    Flat Stars cost still applies once — piece count does not multiply the charge.
    """
    if not piece_pngs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="At least one clothing image is required."
        )
    if len(piece_pngs) == 1:
        # Normalize to PNG.
        buf = io.BytesIO()
        _bytes_to_rgba(piece_pngs[0]).save(buf, format="PNG")
        return buf.getvalue()

    images = [_bytes_to_rgba(p) for p in piece_pngs[:MAX_OUTFIT_PIECES]]
    target_h = 768
    resized: list[Image.Image] = []
    for im in images:
        w, h = im.size
        scale = target_h / max(h, 1)
        nw = max(1, int(round(w * scale)))
        resized.append(im.resize((nw, target_h), Image.Resampling.LANCZOS))
    gap = 12
    total_w = sum(im.width for im in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGBA", (total_w, target_h), (255, 255, 255, 0))
    x = 0
    for im in resized:
        canvas.paste(im, (x, 0), im)
        x += im.width + gap
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def enqueue_fitting_room_try_on(
    db: Session,
    user: User,
    *,
    person_image_base64: str,
    garment_image_base64: str | None = None,
    garment_pieces: list[dict[str, Any]] | None = None,
    idempotency_key: str,
    consent_acknowledged: bool,
    consent_version: str,
    garment_category: str | None = None,
) -> AIJob:
    if not fitting_room_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI Fitting Room is not enabled on this server.",
        )
    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fitting Room requires explicit preview consent.",
        )
    if (consent_version or "").strip() != FITTING_ROOM_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fitting Room consent version is outdated.",
        )

    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key is required."
        )
    if not key.startswith("fitting_room:"):
        key = f"fitting_room:{key}"

    existing = (
        db.query(AIJob)
        .filter(
            AIJob.user_id == user.id,
            AIJob.job_type == FITTING_ROOM_JOB_TYPE,
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .order_by(AIJob.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing

    person_png = _decode_png(person_image_base64, field="person_image_base64")

    piece_bytes: list[bytes] = []
    piece_cats: list[str] = []
    piece_sources: list[str] = []
    if isinstance(garment_pieces, list) and garment_pieces:
        if len(garment_pieces) > MAX_OUTFIT_PIECES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Outfit supports at most {MAX_OUTFIT_PIECES} clothing pieces.",
            )
        for i, piece in enumerate(garment_pieces):
            if not isinstance(piece, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"garment_pieces[{i}] invalid."
                )
            raw = piece.get("image_base64") or piece.get("imageBase64")
            piece_bytes.append(_decode_png(str(raw or ""), field=f"garment_pieces[{i}]"))
            piece_cats.append(_normalize_category(piece.get("category") or piece.get("garment_category")))
            piece_sources.append(str(piece.get("source") or "").strip().lower())
    elif garment_image_base64:
        piece_bytes.append(_decode_png(garment_image_base64, field="garment_image_base64"))
        piece_cats.append(_normalize_category(garment_category))
        piece_sources.append("")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide garment_image_base64 or garment_pieces.",
        )

    category = piece_cats[0] if len(piece_cats) == 1 else "auto"
    combo_warning = combo_warning_for_categories(piece_cats)
    look_plate = any(src == "fashionrise_look" for src in piece_sources)

    # Flat Stars check before enqueue — debit only after success (worker).
    assert_can_spend_fitting_room(db, user)

    garment_png = compose_outfit_collage(piece_bytes)
    person_fp = hashlib.sha256(person_png).hexdigest()
    garment_fp = hashlib.sha256(garment_png).hexdigest()
    person_b64 = base64.b64encode(person_png).decode("ascii")
    garment_b64 = base64.b64encode(garment_png).decode("ascii")

    hints: list[str] = [
        "fitting_room_flat_stars",
        f"outfit_piece_count:{len(piece_bytes)}",
    ]
    for cat in piece_cats:
        if cat != "auto":
            hints.append(f"garment_category:{cat}")
    look_color_lock: dict[str, Any] | None = None
    if look_plate:
        look_color_lock = sample_look_garment_panel_colors(garment_png)
        hints.extend(
            [
                "fashionrise_look_plate",
                "Ignore illustrated model body/skin; clothing design only.",
                "Render real fabric photo matching image-1 lighting; no sketch overlay.",
                "1:1 look design; photoreal cloth not illustration paste.",
                "Keep exact multi-tone colors (bodice vs skirt); do not unify panels.",
            ]
        )
        if look_color_lock:
            hints.append(
                "COLOR LOCK: bodice "
                f"{look_color_lock.get('bodice_hex')} vs skirt "
                f"{look_color_lock.get('skirt_hex')} "
                f"({look_color_lock.get('relation')}); never average into one green."
            )
    if len(piece_bytes) > 1:
        hints.append(
            "Apply all clothing pieces from the garment collage onto the person photo "
            "as one coordinated outfit without dropping earlier pieces."
        )

    job = AIJob(
        user_id=user.id,
        job_type=FITTING_ROOM_JOB_TYPE,
        status="queued",
        input_data={
            "mode": FITTING_ROOM_MODE,
            "idempotency_key": key,
            "person_image_base64": f"data:image/png;base64,{person_b64}",
            "garment_image_base64": f"data:image/png;base64,{garment_b64}",
            "person_fingerprint": person_fp,
            "garment_fingerprint": garment_fp,
            "garment_category": category,
            "outfit_categories": piece_cats,
            "outfit_piece_count": len(piece_bytes),
            "garment_sources": piece_sources,
            "garment_source": "fashionrise_look" if look_plate else None,
            "look_color_lock": look_color_lock,
            "combo_warning": combo_warning,
            "stars_cost": fitting_room_cost(),
            "design_hints": hints,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
            "prompt_version": TRY_ON_PROMPT_VERSION,
            "provider": "openai",
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _openai_exc_is_moderation(exc: BaseException) -> bool:
    """True when OpenAI refused the Fitting Room request for moderation/sexual."""
    safe_meta = getattr(exc, "safe_meta", None)
    meta = safe_meta if isinstance(safe_meta, dict) else {}
    code = str(meta.get("error_code") or "").strip().upper()
    if code == "PROVIDER_MODERATION_BLOCKED":
        return True
    detail = str(exc).lower()
    if "moderation_blocked" in detail or "moderation_stage" in detail:
        return True
    try:
        from app.services.personal_croquis_provider import provider_rejection_code_from_text

        return provider_rejection_code_from_text(str(exc)) == "moderation_blocked"
    except Exception:  # noqa: BLE001
        return False


def _fashn_fallback_armed() -> bool:
    """Live FASHN Max or v1.6 (or test override) may finish swimwear/lingerie Fitting Room."""
    from app.services.fashn_try_on_max_provider import fashn_max_configured, fashn_max_live_armed
    from app.services.fashn_try_on_provider import fashn_configured, fashn_live_armed
    from app.services.personal_try_on_provider import _try_on_provider_override

    if _try_on_provider_override is not None:
        return True
    if fashn_max_configured() and fashn_max_live_armed():
        return True
    return bool(fashn_configured() and fashn_live_armed())


def _fashn_max_fallback_armed() -> bool:
    from app.services.fashn_try_on_max_provider import fashn_max_configured, fashn_max_live_armed
    from app.services.personal_try_on_provider import _try_on_provider_override

    if _try_on_provider_override is not None:
        return True
    return bool(fashn_max_configured() and fashn_max_live_armed())


def _fashn_category_for_fitting_room(data: dict[str, Any]) -> str:
    """Map Fitting Room categories → FASHN v1.6 category (swimwear → one-pieces)."""
    raw = data.get("outfit_categories")
    cats = [str(c).strip().lower() for c in raw] if isinstance(raw, list) else []
    primary = str(data.get("garment_category") or "").strip().lower()
    if primary and primary not in cats:
        cats = [primary, *cats]
    if any(c in {"one-pieces", "dresses"} for c in cats):
        return "one-pieces"
    if "tops" in cats and "bottoms" not in cats:
        return "tops"
    if "bottoms" in cats and "tops" not in cats:
        return "bottoms"
    # Collage / ambiguous / swimwear product plate — one-pieces is the lingerie/swim default.
    return "one-pieces"


# Max prompt: garment-only transfer — no props, no skin recolor (Fitting Room product photos).
FITTING_ROOM_MAX_PROMPT = (
    "Fit only the clothing, swimwear, or lingerie from the product image onto the person. "
    "Ignore handheld props, bottles, bags, phones, and background objects in the product "
    "photo — never transfer them onto the person. Preserve the garment's exact color, "
    "fabric, straps, trim, cut, and coverage with clean edges. Keep the person's identity, "
    "face, hair, pose, proportions, lighting, background, and exact natural skin tone "
    "unchanged — do not darken, bronze, tint, or recolor any skin."
)

# Social Try on me plants a full look illustration (model + outfit), not a flat product plate.
# Keep short: FASHN Max truncates prompts at 1000 chars (color lock appends below).
FITTING_ROOM_LOOK_PLATE_PROMPT = (
    "FashionRise look illustration — ignore drawn body/face/hair; transfer garments as "
    "REAL photographed clothing (not a sketch overlay). 1:1 design + exact panel hues "
    "(bodice vs skirt). Keep sheer tulle/chiffon translucent — legs must stay visible "
    "where the look shows them through the skirt; never make the skirt opaque. Match "
    "person-photo lighting. Keep identity, face, hair, pose, background, skin unchanged."
)

# OpenAI Fitting Room path for Social looks — full photoreal + 1:1 contract (not Max-truncated).
# Used when productize→Max is unavailable (fallback only).
FITTING_ROOM_LOOK_OPENAI_PROMPT = (
    "Create a single photorealistic photograph of the person from image 1 wearing real "
    "clothing that matches the FashionRise look illustration in image 2 one-to-one. "
    "Image 2 includes a drawn model — ignore that illustrated body, face, hair, skin, and "
    "pose; use only the garment design. Keep cut, silhouette, neckline, straps, coverage, "
    "and every panel color exact (including two-tone bodice vs skirt — do not unify hues). "
    "SHEER LAYERS: if image 2 shows legs through a sheer/tulle/chiffon skirt, the person's "
    "legs MUST remain visible through those sheer layers — never fill an opaque skirt over "
    "the legs. "
    "CRITICAL REALISM: render real fabric — weave, folds, photographic sheerness matching "
    "image 1 lighting with soft contact shadows. Do NOT paste sketch strokes, flat "
    "illustrated fills, airbrushed concept-art shading, or a sketched overlay. "
    "Preserve identity, face, hair, pose, proportions, background, and natural skin tone. "
    "Output one realistic photograph."
)

# Step 1 for Social looks: illustration → photoreal product plate (no person), then Max try-on.
FITTING_ROOM_LOOK_PRODUCTIZE_PROMPT = (
    "Transform this FashionRise look illustration into a photorealistic commercial clothing "
    "product photograph of the REAL garment alone on a neutral light studio background. "
    "Ignore the drawn model body, face, hair, skin, and pose — clothing only. Keep 1:1 "
    "design: silhouette, wrap bodice, straps, multi-tone panel colors (bodice vs skirt — "
    "never unify). CRITICAL SHEER: keep tulle/chiffon layers translucent with open "
    "negative space where legs showed through the look — do not bake an opaque filled skirt. "
    "Real fabric texture and weave — not sketch strokes or illustration style. No person."
)

# Step 2 Max prompt when the garment ref is already a photoreal product from the look.
FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT = (
    "Fit only the clothing from the product photograph onto the person as real fabric. "
    "Preserve multi-tone hues (bodice vs skirt), cut, and straps. Keep sheer tulle/chiffon "
    "translucent — the person's legs must stay visible through sheer layers when the "
    "product/look shows that; never cover legs with an opaque skirt. Do not unify colors "
    "or paste sketch shading. Match person-photo lighting. Keep identity, face, hair, "
    "pose, background, and natural skin tone unchanged."
)


def _is_fashionrise_look_plate(data: dict[str, Any]) -> bool:
    sources = data.get("garment_sources")
    if isinstance(sources, list) and any(
        str(s).strip().lower() == "fashionrise_look" for s in sources
    ):
        return True
    return str(data.get("garment_source") or "").strip().lower() == "fashionrise_look"


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"


def sample_look_garment_panel_colors(garment_png: bytes) -> dict[str, Any] | None:
    """Sample upper vs lower greenish garment hues from a FashionRise look plate.

    Used to lock multi-tone dresses (e.g. lighter olive bodice + darker forest skirt)
    so try-on providers do not wash both panels into one mid-green.
    """
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
    px = rgb.load()

    def _region_mean(y0: float, y1: float, x0: float = 0.22, x1: float = 0.78) -> tuple[int, int, int] | None:
        yy0, yy1 = int(h * y0), max(int(h * y0) + 1, int(h * y1))
        xx0, xx1 = int(w * x0), max(int(w * x0) + 1, int(w * x1))
        rs: list[float] = []
        gs: list[float] = []
        bs: list[float] = []
        for y in range(yy0, yy1):
            for x in range(xx0, xx1):
                r, g, b = px[x, y]
                mx = max(r, g, b)
                mn = min(r, g, b)
                if mx < 36:
                    continue
                sat = (mx - mn) / float(mx or 1)
                # Prefer saturated garment greens; skip near-gray background / skin.
                if sat < 0.12:
                    continue
                if g + 6 < r and g + 6 < b:
                    continue
                rs.append(float(r))
                gs.append(float(g))
                bs.append(float(b))
        if len(rs) < 40:
            return None
        return (
            int(round(sum(rs) / len(rs))),
            int(round(sum(gs) / len(gs))),
            int(round(sum(bs) / len(bs))),
        )

    # Upper torso / bodice vs mid–lower skirt band on a full-body look plate.
    bodice = _region_mean(0.28, 0.46)
    skirt = _region_mean(0.52, 0.74)
    if bodice is None or skirt is None:
        return None

    bodice_l = 0.299 * bodice[0] + 0.587 * bodice[1] + 0.114 * bodice[2]
    skirt_l = 0.299 * skirt[0] + 0.587 * skirt[1] + 0.114 * skirt[2]
    delta = bodice_l - skirt_l
    if abs(delta) < 6:
        # No meaningful two-tone split — skip lock (solid garment).
        return None
    relation = "lighter_bodice" if delta > 0 else "darker_bodice"
    return {
        "bodice_rgb": list(bodice),
        "skirt_rgb": list(skirt),
        "bodice_hex": _rgb_to_hex(bodice),
        "skirt_hex": _rgb_to_hex(skirt),
        "luma_delta": round(delta, 1),
        "relation": relation,
    }


def reinforce_look_plate_panel_colors(
    garment_png: bytes,
    lock: dict[str, Any] | None,
    *,
    strength: float = 0.42,
) -> bytes:
    """Mildly pull upper/lower green pixels toward measured panel means.

    Helps FASHN Max see the bodice/skirt split instead of averaging to one olive.
    No-op when lock is missing or the plate cannot be decoded.
    """
    if not garment_png or not isinstance(lock, dict):
        return garment_png
    bodice_raw = lock.get("bodice_rgb")
    skirt_raw = lock.get("skirt_rgb")
    if not (isinstance(bodice_raw, (list, tuple)) and isinstance(skirt_raw, (list, tuple))):
        return garment_png
    if len(bodice_raw) < 3 or len(skirt_raw) < 3:
        return garment_png
    try:
        bt = (int(bodice_raw[0]), int(bodice_raw[1]), int(bodice_raw[2]))
        st = (int(skirt_raw[0]), int(skirt_raw[1]), int(skirt_raw[2]))
    except (TypeError, ValueError):
        return garment_png

    try:
        with Image.open(io.BytesIO(garment_png)) as im:
            im.load()
            rgba = im.convert("RGBA")
    except Exception:  # noqa: BLE001
        return garment_png

    w, h = rgba.size
    if w < 8 or h < 16:
        return garment_png
    px = rgba.load()
    t = max(0.0, min(0.75, float(strength)))
    mid_y = int(h * 0.48)

    for y in range(h):
        target = bt if y < mid_y else st
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 24:
                continue
            mx = max(r, g, b)
            mn = min(r, g, b)
            if mx < 36:
                continue
            sat = (mx - mn) / float(mx or 1)
            if sat < 0.10:
                continue
            # Skip non-garment (skin/hair-ish warm neutrals).
            if g + 8 < r and b + 8 < r:
                continue
            if g < r - 4 and g < b - 4:
                continue
            nr = int(round(r * (1.0 - t) + target[0] * t))
            ng = int(round(g * (1.0 - t) + target[1] * t))
            nb = int(round(b * (1.0 - t) + target[2] * t))
            px[x, y] = (
                max(0, min(255, nr)),
                max(0, min(255, ng)),
                max(0, min(255, nb)),
                a,
            )

    out = io.BytesIO()
    rgba.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _look_color_lock_prompt_clause(lock: dict[str, Any] | None) -> str:
    if not isinstance(lock, dict):
        return ""
    bodice_hex = str(lock.get("bodice_hex") or "").strip()
    skirt_hex = str(lock.get("skirt_hex") or "").strip()
    if not (bodice_hex.startswith("#") and skirt_hex.startswith("#")):
        return ""
    relation = str(lock.get("relation") or "")
    if relation == "lighter_bodice":
        rel = "Bodice must stay lighter than the skirt."
    elif relation == "darker_bodice":
        rel = "Bodice must stay darker than the skirt."
    else:
        rel = "Keep the measured value difference between panels."
    return (
        f" COLOR LOCK: bodice {bodice_hex}, skirt {skirt_hex}. {rel} "
        "Never average panels into one green."
    )


def _fitting_room_max_prompt(data: dict[str, Any]) -> str:
    if not _is_fashionrise_look_plate(data):
        return FITTING_ROOM_MAX_PROMPT
    lock = data.get("look_color_lock")
    clause = _look_color_lock_prompt_clause(lock if isinstance(lock, dict) else None)
    # Already productized look → shorter product-fit prompt; else illustration prompt.
    base = (
        FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT
        if data.get("look_productized")
        else FITTING_ROOM_LOOK_PLATE_PROMPT
    )
    # normalize_max_prompt truncates at 1000 — keep color lock near the front.
    return (base[:720] + clause) if clause else base


def _look_productize_prompt(data: dict[str, Any]) -> str:
    lock = data.get("look_color_lock")
    clause = _look_color_lock_prompt_clause(lock if isinstance(lock, dict) else None)
    return FITTING_ROOM_LOOK_PRODUCTIZE_PROMPT + clause


def productize_fashionrise_look_plate(
    *,
    garment_png: bytes,
    data: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    """OpenAI images.edit: look illustration → photoreal product plate for FASHN Max.

    Separates realism (productize) from person try-on (Max) so Social looks get both
    photographed fabric and COLOR LOCK panel hues — OpenAI one-shot try-on traded one off.
    """
    from app.services.personal_croquis_provider import extract_edit_png_bytes
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

    _ensure_look_color_lock(garment_png, data)
    plate = _garment_png_for_look_plate(garment_png, data)
    model = (settings.openai_image_model or "").strip()
    assert_image_model_editable(model)
    size = (settings.openai_image_size or "1024x1536").strip()
    quality = settings.openai_image_quality

    try:
        kwargs = build_image_edit_kwargs(
            model=model,
            prompt=_look_productize_prompt(data),
            sketch=(plate, "image/png"),
            size=size,
            quality=quality,
            fabric_swatch=None,
        )
    except SketchCompletionError as exc:
        raise ProviderNotAvailableError(str(exc)) from exc

    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    kwargs.pop("background", None)
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
        summary = str(exc)[:400]
        raise ProviderOutcomeUnknownError(
            f"look productize images.edit failed: {type(exc).__name__}: {summary}"
        ) from exc

    png = extract_edit_png_bytes(result)
    # Opaque RGB product plate — FASHN prefers non-transparent garment refs.
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

    # Re-apply color lock pull on the product so Max sees the measured split.
    product = reinforce_look_plate_panel_colors(product, data.get("look_color_lock"))
    return product, {
        "provider": "openai_look_productize",
        "model": kwargs.get("model"),
        "prompt_kind": "fitting_room_look_productize",
        "source_sha256": hashlib.sha256(garment_png).hexdigest(),
        "product_sha256": hashlib.sha256(product).hexdigest(),
        "look_color_lock": data.get("look_color_lock"),
    }


def _fitting_room_openai_prompt(data: dict[str, Any], hints: list[str]) -> str | None:
    """Look-plate OpenAI prompt override; None → provider default try-on prompt."""
    if not _is_fashionrise_look_plate(data):
        return None
    lock = data.get("look_color_lock")
    clause = _look_color_lock_prompt_clause(lock if isinstance(lock, dict) else None)
    # Append compact design evidence (COLOR LOCK + realism) without the full Studio prefix.
    evidence: list[str] = []
    for raw in hints:
        text = " ".join(str(raw).split())
        if not text:
            continue
        evidence.append(text[:120])
        if len(evidence) >= 6:
            break
    prompt = FITTING_ROOM_LOOK_OPENAI_PROMPT + clause
    if evidence:
        prompt += " Design evidence: " + "; ".join(evidence) + "."
    return prompt


def _ensure_look_color_lock(
    garment_png: bytes, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Return look_color_lock from job data, sampling the plate when missing."""
    if not _is_fashionrise_look_plate(data):
        return None
    lock = data.get("look_color_lock")
    if (
        isinstance(lock, dict)
        and str(lock.get("bodice_hex") or "").startswith("#")
        and str(lock.get("skirt_hex") or "").startswith("#")
    ):
        return lock
    sampled = sample_look_garment_panel_colors(garment_png)
    if sampled:
        data["look_color_lock"] = sampled
    return sampled


def _garment_png_for_look_plate(garment_png: bytes, data: dict[str, Any]) -> bytes:
    """Return garment bytes for providers; reinforce multi-tone look plates when locked."""
    lock = _ensure_look_color_lock(garment_png, data)
    if not lock:
        return garment_png
    return reinforce_look_plate_panel_colors(garment_png, lock)


def _fitting_room_garment_prep(
    *,
    garment_png: bytes,
    data: dict[str, Any],
):
    from app.services.fashn_garment_prep import prep_from_approved_product_pieces

    category = _fashn_category_for_fitting_room(data)
    piece_cat = (
        category if category in {"tops", "bottoms", "one-pieces", "auto"} else "one-pieces"
    )
    return (
        piece_cat,
        prep_from_approved_product_pieces(
            pieces=[(piece_cat, garment_png)],
            source_fingerprint=str(data.get("garment_fingerprint") or "fitting-room"),
        ),
    )


def _generate_fitting_room_via_fashn(
    *,
    person_png: bytes,
    garment_png: bytes,
    data: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    """Product-photo FASHN try-on after OpenAI moderation.

    Prefers **Try-On Max** (``quality`` · ``2k``) when armed — better swimwear/lingerie
    fidelity than v1.6. Falls back to v1.6 only if Max is unavailable.
    """
    plate = _garment_png_for_look_plate(garment_png, data)
    category, prep = _fitting_room_garment_prep(garment_png=plate, data=data)

    if _fashn_max_fallback_armed():
        try:
            max_provider = get_try_on_provider("fashn_max")
            png, meta = max_provider.generate(
                photo_png=person_png,
                garment_png=plate,
                prep=prep,
                generation_mode="quality",
                resolution="2k",
                prompt=_fitting_room_max_prompt(data),
            )
            if not isinstance(meta, dict):
                meta = {}
            meta.setdefault("provider", "fashn_tryon_max")
            meta["fitting_room_fashn_path"] = "max_quality_2k"
            if _is_fashionrise_look_plate(data):
                meta["look_color_lock"] = data.get("look_color_lock")
            return png, meta
        except ProviderNotAvailableError:
            logger.info("Fitting Room Max unavailable — trying FASHN v1.6")
        except ProviderOutcomeUnknownError:
            raise

    provider = get_try_on_provider("fashn")
    png, meta = provider.generate(
        photo_png=person_png,
        garment_png=plate,
        prep=prep,
        v16_experiment={"category": category, "mode": "quality"},
    )
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("provider", "fashn")
    meta["fitting_room_fashn_path"] = "v16_quality"
    return png, meta


def complete_fitting_room_job(db: Session, job: AIJob) -> dict[str, Any]:
    """Worker entry — OpenAI try-on with silent FASHN fallback; Stars debit elsewhere."""
    data = job.input_data if isinstance(job.input_data, dict) else {}

    def _fail(msg: str, *, code: str = "FITTING_ROOM_FAILED") -> dict[str, Any]:
        # Never leak raw OpenAI moderation / BadRequest text to the client.
        job.status = "failed"
        job.error_message = msg[:240]
        result = {
            "status": "failed",
            "summary": job.error_message,
            "mode": FITTING_ROOM_MODE,
            "error_code": code,
        }
        job.result_data = result
        return result

    if not fitting_room_enabled():
        return _fail("AI Fitting Room is disabled.", code="GATE_OFF")

    try:
        person_png = _decode_png(str(data.get("person_image_base64") or ""), field="person")
        garment_png = _decode_png(str(data.get("garment_image_base64") or ""), field="garment")
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Invalid Fitting Room images."
        return _fail(detail, code="BAD_INPUT")

    hints_raw = data.get("design_hints")
    hints = [str(h) for h in hints_raw if isinstance(h, str)] if isinstance(hints_raw, list) else []

    used_provider = "openai"
    fallback_from: str | None = None
    openai_operator_detail: str | None = None
    png: bytes | None = None
    meta: dict[str, Any] = {}

    from app.services.personal_try_on_provider import _try_on_provider_override

    if _try_on_provider_override is None and not fitting_room_live_armed():
        return _fail(
            "Fitting Room live AI is not armed on this server.",
            code="LIVE_HTTP_OFF",
        )

    look_plate = _is_fashionrise_look_plate(data)
    # Social look plates: productize illustration → FASHN Max (photoreal + COLOR LOCK).
    # One-shot OpenAI try-on traded realism vs multi-tone; Max needs a product plate.
    if (
        look_plate
        and _fashn_max_fallback_armed()
        and _try_on_provider_override is None
    ):
        try:
            product_png, product_meta = productize_fashionrise_look_plate(
                garment_png=garment_png, data=data
            )
            data_for_max = dict(data)
            data_for_max["look_productized"] = True
            png, meta = _generate_fitting_room_via_fashn(
                person_png=person_png, garment_png=product_png, data=data_for_max
            )
            if not isinstance(meta, dict):
                meta = {}
            meta["look_productize"] = product_meta
            meta["fitting_room_look_path"] = "productize_then_max"
            used_provider = str(meta.get("provider") or "fashn_tryon_max")
            fallback_from = None
            openai_operator_detail = None
        except Exception:  # noqa: BLE001
            logger.info(
                "Fitting Room job %s look productize→Max failed — OpenAI try-on fallback",
                job.id,
                exc_info=True,
            )
            png = None

    # Swimwear / lingerie / product dresses: prefer Try-On Max quality first (skip
    # OpenAI moderation landmines). Look plates handled above.
    prefer_max_first = (
        _fashn_max_fallback_armed()
        and _fashn_category_for_fitting_room(data) == "one-pieces"
        and _try_on_provider_override is None
        and not look_plate
    )
    if prefer_max_first and png is None:
        try:
            png, meta = _generate_fitting_room_via_fashn(
                person_png=person_png, garment_png=garment_png, data=data
            )
            if not isinstance(meta, dict):
                meta = {}
            used_provider = str(meta.get("provider") or "fashn_tryon_max")
            fallback_from = None
            # Jump straight to success persist below (skip OpenAI).
            openai_operator_detail = None
        except Exception:  # noqa: BLE001
            logger.info(
                "Fitting Room job %s Max-first path failed — trying OpenAI then fallback",
                job.id,
            )
            png = None

    if png is None:
        try:
            provider = get_try_on_provider("openai")
            garment_for_openai = _garment_png_for_look_plate(garment_png, data)
            openai_prompt = _fitting_room_openai_prompt(data, hints)
            generate_kwargs: dict[str, Any] = {
                "photo_png": person_png,
                "garment_png": garment_for_openai,
                "design_hints": hints,
            }
            if openai_prompt:
                generate_kwargs["prompt_override"] = openai_prompt
            png, meta = provider.generate(**generate_kwargs)
            if not isinstance(meta, dict):
                meta = {}
            used_provider = "openai"
        except ProviderNotAvailableError as exc:
            openai_operator_detail = str(exc)[:400]
            if _openai_exc_is_moderation(exc) and _fashn_fallback_armed():
                logger.info(
                    "Fitting Room job %s OpenAI moderation — falling back to FASHN Max",
                    job.id,
                )
                try:
                    png, meta = _generate_fitting_room_via_fashn(
                        person_png=person_png, garment_png=garment_png, data=data
                    )
                    if not isinstance(meta, dict):
                        meta = {}
                    used_provider = str(meta.get("provider") or "fashn_tryon_max")
                    fallback_from = "openai"
                except ProviderOutcomeUnknownError as fashn_exc:
                    job.status = "failed"
                    job.error_message = (
                        "Fitting Room could not finish this preview. No Stars were charged."
                    )[:240]
                    job.result_data = {
                        "status": "failed",
                        "summary": job.error_message,
                        "mode": FITTING_ROOM_MODE,
                        "error_code": "PROVIDER_OUTCOME_UNKNOWN",
                        "reconciliation_required": True,
                        "fallback_attempted": "fashn_max",
                        "operator_summary": (
                            f"openai={openai_operator_detail}; fashn={str(fashn_exc)[:200]}"
                        )[:400],
                    }
                    return job.result_data
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Fitting Room job %s FASHN fallback failed after OpenAI moderation",
                        job.id,
                    )
                    return _fail(
                        "Fitting Room could not finish this swimwear/lingerie preview. "
                        "No Stars were charged.",
                        code="PROVIDER_FALLBACK_FAILED",
                    )
            else:
                # Non-moderation OpenAI failure — keep copy owner-safe (no raw API dump).
                if _openai_exc_is_moderation(exc):
                    return _fail(
                        "Fitting Room could not finish this preview with the current clothing "
                        "photo. Try a different angle or garment shot. No Stars were charged.",
                        code="PROVIDER_MODERATION_BLOCKED",
                    )
                return _fail(
                    "Fitting Room could not finish this preview. No Stars were charged.",
                    code="PROVIDER_UNAVAILABLE",
                )
        except ProviderOutcomeUnknownError as exc:
            job.status = "failed"
            job.error_message = (
                "Fitting Room provider outcome is uncertain. No automatic retry — "
                "check your balance if a charge appears."
            )[:240]
            result = {
                "status": "failed",
                "summary": job.error_message,
                "mode": FITTING_ROOM_MODE,
                "error_code": "PROVIDER_OUTCOME_UNKNOWN",
                "reconciliation_required": True,
                "detail": str(exc)[:200],
            }
            job.result_data = result
            return result
        except Exception:  # noqa: BLE001
            logger.exception("Fitting Room job %s provider failure", job.id)
            return _fail("Fitting Room could not finish this preview.", code="PROVIDER_ERROR")

    if not png:
        return _fail("Fitting Room returned an empty image.", code="EMPTY_RESULT")

    key = f"ai/{job.id.hex}_fitting_{uuid.uuid4().hex[:10]}.png"
    url = LocalStorageBackend().save_file(key=key, data=io.BytesIO(png), content_type="image/png")

    cost = int(data.get("stars_cost") or fitting_room_cost())
    result = {
        "status": "completed",
        "summary": "Fitting Room preview ready (concept preview — not a fit guarantee).",
        "bullets": [
            "Person photo and clothing image were not overwritten.",
            FITTING_ROOM_NOTICE,
            f"Flat Stars charge on success: {cost} (not per garment in the image).",
            f"Prompt {TRY_ON_PROMPT_VERSION}",
        ],
        "image_url": url,
        "mode": FITTING_ROOM_MODE,
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "provider": used_provider,
        "person_fingerprint": data.get("person_fingerprint"),
        "garment_fingerprint": data.get("garment_fingerprint"),
        "garment_category": data.get("garment_category"),
        "outfit_categories": data.get("outfit_categories"),
        "outfit_piece_count": data.get("outfit_piece_count"),
        "combo_warning": data.get("combo_warning"),
        "stars_cost": cost,
        "consent_version": TRY_ON_CONSENT_VERSION,
    }
    if fallback_from:
        result["fallback_from"] = fallback_from
        result["operator_summary"] = (
            f"Completed via {used_provider} after OpenAI moderation. "
            f"openai={openai_operator_detail or ''}"
        )[:400]
    if isinstance(meta, dict) and used_provider != "openai":
        for k in (
            "prediction_ids",
            "credits_used",
            "fashn_calls",
            "layout",
            "generation_mode",
            "resolution",
            "fitting_room_fashn_path",
        ):
            if k in meta:
                result[k] = meta[k]
    job.status = "completed"
    job.error_message = None
    job.result_data = result
    slim = dict(data)
    slim.pop("person_image_base64", None)
    slim.pop("garment_image_base64", None)
    slim["images_stripped"] = True
    if used_provider != "openai":
        slim["provider"] = used_provider
    if fallback_from:
        slim["fallback_from"] = fallback_from
    job.input_data = slim
    return result
