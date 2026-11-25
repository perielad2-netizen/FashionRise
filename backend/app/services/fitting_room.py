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
from app.models.gallery_item import GalleryItem
from app.models.user import User
from app.services.ai_stars import assert_can_spend_fitting_room, fitting_room_cost
from app.services.look_color_lock import (
    extract_design_palette,
    lock_result_to_palette,
    palette_prompt_clause,
    palette_summary,
)
from app.services.look_plate_detect import detect_fashionrise_look_plate
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_PROMPT_VERSION,
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    get_try_on_provider,
)
from app.services.sunburst_try_on_prompt import (
    MODEL_B_SUNBURST_FOOTWEAR_CLAUSE,
    MODEL_B_SUNBURST_MODEL,
    MODEL_B_SUNBURST_PATH,
    MODEL_B_SUNBURST_PROMPT,
    MODEL_B_SUNBURST_PROMPT_VERSION,
    MODEL_B_SUNBURST_SKIN_TONE_CLAUSE,
)
from app.storage.local import LocalStorageBackend

# Re-export Model B sunburst constants for existing importers/tests.

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

# One product image per try-on. Side-by-side collage (dress+boot+gloves) is not
# reliable on FASHN Max / OpenAI — secondary pieces (boots, gloves) get dropped.
# Sequential multi-pass is a future option; until then keep the product honest.
MAX_OUTFIT_PIECES = 1
# Designer reward when another user successfully tries on their published Social look.
FITTING_ROOM_DESIGNER_TRYON_STARS = 2


def maybe_credit_designer_tryon_stars(db: Session, job: AIJob) -> bool:
    """Credit the Social look owner +2 Stars once per successful other-user Fitting Room try-on.

    Own designs never earn. Removed / non-public gallery items skip credit.
    Idempotent via ``star_payouts.payout_key``.
    """
    if job.job_type != FITTING_ROOM_JOB_TYPE or job.status != "completed":
        return False
    data = job.input_data if isinstance(job.input_data, dict) else {}
    if data.get("cancel_requested") is True:
        return False
    sources = data.get("garment_sources") if isinstance(data.get("garment_sources"), list) else []
    look_plate = str(data.get("garment_source") or "").strip().lower() == "fashionrise_look" or any(
        str(s).strip().lower() == "fashionrise_look" for s in sources
    )
    if not look_plate:
        return False
    raw_gid = data.get("source_gallery_item_id")
    if raw_gid is None or str(raw_gid).strip() == "":
        return False
    try:
        gid = uuid.UUID(str(raw_gid).strip())
    except (TypeError, ValueError):
        return False
    item = db.get(GalleryItem, gid)
    if item is None:
        return False
    if (item.visibility or "").strip().lower() != "public":
        return False
    if item.user_id == job.user_id:
        return False
    from app.services.competition_awards import credit_payout_idempotent

    credited = credit_payout_idempotent(
        db,
        user_id=item.user_id,
        amount=FITTING_ROOM_DESIGNER_TRYON_STARS,
        payout_key=f"fitting_room_designer_tryon:{job.id}",
        reason="fitting_room_designer_tryon",
    )
    if credited:
        _log = logging.getLogger(__name__)
        _log.info(
            "fitting_room_designer_tryon_credited job_id=%s designer_id=%s viewer_id=%s gallery_item_id=%s amount=%s",
            job.id,
            item.user_id,
            job.user_id,
            gid,
            FITTING_ROOM_DESIGNER_TRYON_STARS,
        )
    return credited


def fitting_room_enabled() -> bool:
    return bool(get_settings().fitting_room_enabled)


def fitting_room_live_armed() -> bool:
    settings = get_settings()
    return bool(settings.fitting_room_enabled and settings.fitting_room_live_http)


def _normalize_model_b_sunburst_allowlist() -> set[str]:
    raw = (get_settings().fitting_room_look_model_b_sunburst_owner_allowlist or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_on_model_b_sunburst_allowlist(user: User | Any) -> bool:
    """Optional restriction gate when an allowlist is configured.

    Empty allowlist = everyone (GA). Non-empty = only matching email/username/id
    (ops can shrink back to owner-only without flipping the feature flag).
    """
    allow = _normalize_model_b_sunburst_allowlist()
    if not allow:
        return True
    email = str(getattr(user, "email", "") or "").strip().lower()
    username = str(getattr(user, "username", "") or "").strip().lower()
    uid = str(getattr(user, "id", "") or "").strip().lower()
    return bool({email, username, uid} & allow)


def look_model_b_sunburst_flag_enabled() -> bool:
    return bool(get_settings().fitting_room_look_model_b_sunburst_enabled)


def look_model_b_sunburst_available_for_user(user: User | Any) -> bool:
    """True when Model B is the Fitting Room look path for this user."""
    return look_model_b_sunburst_flag_enabled() and user_on_model_b_sunburst_allowlist(user)


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
    settings = get_settings()
    enabled = fitting_room_enabled()
    cost = fitting_room_cost()
    model_b_available = look_model_b_sunburst_available_for_user(user)
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
            f"{cost} Stars per successful Fitting Room preview — one clothing or shoes "
            "image at a time."
        ),
        "max_outfit_pieces": MAX_OUTFIT_PIECES,
        "conflicting_category_sets": [sorted(s) for s in CONFLICTING_CATEGORY_SETS],
        "look_model_b_sunburst_available": model_b_available,
        "look_model_b_sunburst_model": MODEL_B_SUNBURST_MODEL,
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
    # Boots / footwear aliases → shoes (QA often leaves "auto" or says "boot").
    if cat in {"boot", "boots", "footwear", "shoe", "heels", "sneakers"}:
        cat = "shoes"
    if cat not in SUPPORTED_GARMENT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported garment category '{cat}'.",
        )
    return cat


def _outfit_categories(data: dict[str, Any]) -> list[str]:
    raw = data.get("outfit_categories")
    cats = [str(c).strip().lower() for c in raw] if isinstance(raw, list) else []
    primary = str(data.get("garment_category") or "").strip().lower()
    if primary and primary not in cats:
        cats = [primary, *cats]
    return cats


def _is_multi_piece_outfit(data: dict[str, Any]) -> bool:
    try:
        count = int(data.get("outfit_piece_count") or 0)
    except (TypeError, ValueError):
        count = 0
    if count > 1:
        return True
    return len(_outfit_categories(data)) > 1


def _outfit_includes_footwear(data: dict[str, Any]) -> bool:
    return "shoes" in _outfit_categories(data)


def _outfit_needs_footwear_contract(data: dict[str, Any]) -> bool:
    """Multi-piece collages and explicit shoes must keep boots/footwear on the person.

    QA: dress + boot tagged ``auto`` → Max apparel-only prompt dropped the boot.
    """
    return _is_multi_piece_outfit(data) or _outfit_includes_footwear(data)


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
    source_gallery_item_id: uuid.UUID | None = None,
    prefer_model_b_sunburst: bool = False,
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
    look_detected_by: str | None = "client_tag" if look_plate else None
    look_detection: dict[str, Any] | None = None
    if (
        not look_plate
        and len(piece_bytes) == 1
        and bool(get_settings().fitting_room_look_detect_enabled)
    ):
        # The client tag is not load-bearing: older app bundles and outfit pieces
        # persisted on-device before the tag existed never send it.
        look_detection = detect_fashionrise_look_plate(piece_bytes[0])
        if look_detection.get("is_look"):
            look_plate = True
            look_detected_by = "content"

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
    look_analysis: dict[str, Any] | None = None
    if look_plate:
        look_analysis = analyze_fashionrise_look_plate(garment_png)
        look_color_lock = (
            look_analysis.get("look_color_lock")
            if isinstance(look_analysis.get("look_color_lock"), dict)
            else None
        )
        hints.extend(
            [
                "fashionrise_look_plate",
                "Ignore illustrated model body/skin; clothing design only.",
                "Render real fabric photo matching image-1 lighting; no sketch overlay.",
                "1:1 look design; photoreal cloth not illustration paste.",
                "Keep exact multi-tone colors (bodice vs skirt); do not unify panels.",
                "If the look shows shoes/heels/boots, replace photo footwear with those design shoes.",
                "Never replace the real person with the drawn look-plate model.",
            ]
        )
        hints.extend(
            [
                "Preserve sheer/tulle layering and high-low/short hems from the look — do not opaque-fill skirts.",
                "Do not cover legs the look leaves exposed; no invented opaque underlayers or long skirts.",
            ]
        )
        if look_analysis.get("sheer_legs"):
            hints.extend(
                [
                    "look_sheer_legs",
                    "Lower look region shows legs through sheer/cutaway layers — keep legs visible.",
                    "Do not fill an opaque skirt over exposed legs.",
                ]
            )
        if look_color_lock:
            hints.append(
                "COLOR LOCK: bodice "
                f"{look_color_lock.get('bodice_hex')} vs skirt "
                f"{look_color_lock.get('skirt_hex')} "
                f"({look_color_lock.get('relation')}); never average into one mid-tone."
            )
    if len(piece_bytes) > 1:
        hints.append(
            "MULTI_PIECE_COLLAGE: apply ALL panels from the garment collage onto the "
            "person as one coordinated outfit — clothing and footwear — without dropping "
            "earlier pieces, boots, or shoe panels."
        )
    if "shoes" in piece_cats:
        hints.append(
            "FOOTWEAR: fit the boots/shoes from the garment collage onto the person and "
            "replace the photo footwear — do not invent different shoes or drop the boot."
        )
    elif len(piece_bytes) > 1:
        # Second+ piece often left as ``auto`` (QA dress + boot). Still demand footwear
        # if any collage panel shows boots/shoes.
        hints.append(
            "If any collage panel shows boots, shoes, heels, or sneakers, fit that "
            "footwear onto the person and replace photo shoes — never drop boot panels."
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
            "look_detected_by": look_detected_by,
            "look_detection": look_detection,
            "look_color_lock": look_color_lock,
            "look_analysis": look_analysis,
            "look_sheer_legs": bool((look_analysis or {}).get("sheer_legs")),
            "combo_warning": combo_warning,
            "stars_cost": fitting_room_cost(),
            "design_hints": hints,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
            "prompt_version": TRY_ON_PROMPT_VERSION,
            "provider": "openai",
            "source_gallery_item_id": (
                str(source_gallery_item_id) if source_gallery_item_id is not None else None
            ),
            # Owner-only Model B opt-in. Worker ignores unless flag + allowlist.
            "prefer_model_b_sunburst": bool(prefer_model_b_sunburst),
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

# Multi-piece / shoes collage — Max supports footwear; apparel-only prompt was dropping boots.
FITTING_ROOM_MAX_OUTFIT_PROMPT = (
    "The product image may be a side-by-side collage of outfit pieces. Fit EVERY wearable "
    "fashion item from that collage onto the person — clothing AND footwear (boots, shoes, "
    "heels, flats, sneakers). Do not drop boot or shoe panels. Do not invent different "
    "shoes than the collage shows. Ignore handheld props, bottles, bags, phones, and "
    "background objects. Preserve each item's exact color, fabric, cut, and coverage. Keep "
    "the person's identity, face, hair, pose, lighting, background, and natural skin tone "
    "unchanged."
)

FITTING_ROOM_OPENAI_OUTFIT_PROMPT = (
    "Create a single photorealistic photograph of the person from image 1 wearing every "
    "outfit piece from image 2. Image 2 may be a side-by-side collage — apply ALL panels "
    "as one coordinated look, including boots/shoes/heels when present. Never drop footwear "
    "pieces or replace them with different shoes. Ignore props and background objects. "
    "Keep the person's face, hair, pose, proportions, background, lighting, and skin tone."
)

# Social Try on me plants a full look illustration (model + outfit), not a flat product plate.
# Keep short: FASHN Max truncates prompts at 1000 chars (color lock appends below).
FITTING_ROOM_LOOK_PLATE_PROMPT = (
    "FashionRise look illustration — ignore drawn body/face/hair; never replace the "
    "real person with the drawn figure. Transfer garments as REAL photographed clothing "
    "(not a sketch overlay). 1:1 design + exact panel hues (bodice vs skirt); keep short "
    "hem short. Keep sheer tulle/chiffon translucent — legs must stay visible where the "
    "look shows them through the skirt; never make the skirt opaque. If the look shows "
    "shoes/heels/boots, replace photo footwear with that look footwear. Match "
    "person-photo lighting. Keep identity, face, hair, pose, background, props, skin."
)

# ChatGPT-style Social look fit: person photo + FashionRise design illustration.
# Prefer this before materialize — simpler and keeps bright multi-tone colors.
FITTING_ROOM_LOOK_OPENAI_PROMPT = (
    "Edit image 1 only — the real person photo is the edit target. Dress that exact "
    "person in the FashionRise garment design from image 2 as real sewn clothing. "
    "Image 2 includes a drawn model — ignore that illustrated body, face, hair, and "
    "skin; never replace the real person with the drawn figure. Use the garment design "
    "and any shoes shown as part of the outfit. Keep cut, silhouette, neckline, straps, "
    "hem length (short stays short), asymmetry, coverage, layered petals/leaves, and "
    "every panel color exact (including bright two-tone upper vs lower — never unify "
    "hues, never crush a bright panel into black/grey). "
    "SHEER LAYERS: if image 2 shows legs through a sheer/tulle/chiffon skirt, the person's "
    "legs MUST remain visible through those sheer layers — never fill an opaque skirt over "
    "the legs or invent opaque underlayers. "
    "FOOTWEAR: if image 2 shows shoes, heels, flats, sneakers, or boots, replace image 1 "
    "footwear with those design shoes (same style, color, pattern) — do not keep photo "
    "boots when the design shows different shoes. Only keep image 1 footwear when image 2 "
    "shows no shoes. "
    "CRITICAL REALISM: render real fabric — weave, folds, photographic sheerness matching "
    "image 1 lighting with soft contact shadows. Do NOT paste sketch strokes, flat "
    "illustrated fills, airbrushed concept-art shading, floating petal stickers, or a "
    "sketched overlay. Preserve identity, face, hair, pose, proportions, background, "
    "props (including wings/sculptures), and natural skin tone."
)

# Max prompt for the moderation-fallback path when the reference is already a product photo.
FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT = (
    "Fit only the clothing from the product photograph onto the person as real fabric. "
    "Preserve multi-tone panel hues, cut, straps, hem length, and asymmetry exactly. Keep "
    "sheer tulle/chiffon and high-low openings — legs must stay visible where the product "
    "shows openings; never opaque-fill the skirt. Do not unify colors or paste sketch "
    "shading. If the product shows shoes/heels/boots, replace photo footwear with those "
    "shoes. Match person-photo lighting. Keep identity, face, hair, pose, background, "
    "props, and natural skin tone unchanged."
)

# Max prompt for a materialized look: the reference is a studio photo of the real
# garment on a white mannequin (see look_garment_normalize). Kept well under the
# 1000-char Max limit so the measured palette clause is never truncated.
FITTING_ROOM_LOOK_MATERIALIZED_MAX_PROMPT = (
    "Fit clothing from the product photo as real sewn fabric that drapes — never a flat "
    "illustration paste. Product is on a white mannequin; ignore mannequin body/head/"
    "hands/stand; transfer garment + any shoes shown. Preserve texture, cut, neckline, "
    "straps, layers, hem length. Petals/leaves/shoulder accents must attach on the body "
    "— never floating shapes. Keep sheer layers sheer with legs visible; opaque panels "
    "must cover original clothes. No invented leggings. If product shows shoes/boots, "
    "replace photo footwear. Match person-photo lighting. Keep identity, face, hair, "
    "pose, background, props, skin."
)

# Shared footwear + coverage contract for Social look try-ons.
# Design/product shoes win when present — photo boots must not stick around.
FITTING_ROOM_LOOK_FOOTWEAR_CLAUSE = (
    " FOOTWEAR: if the look/product shows shoes, sneakers, boots, flats, or heels, "
    "replace the person's photo footwear with that footwear (same style, color, and "
    "pattern) — do not keep the original photo boots. Only keep the person's shoes when "
    "the look shows no footwear. Do not invent leggings, opaque underlayers, or extra "
    "garments."
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


def _is_skin_like_rgb(r: int, g: int, b: int) -> bool:
    """Cheap skin heuristic for look-plate analysis (illustration + photo)."""
    if r < 80 or g < 35 or b < 20:
        return False
    if r <= g or r <= b:
        return False
    if abs(r - g) < 12:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    if (mx - mn) < 15:
        return False
    # Avoid saturated garment reds that are clearly fabric, not skin.
    sat = (mx - mn) / float(mx or 1)
    if sat > 0.55 and r > 160 and g < 90:
        return False
    return True


def _is_garment_chrominance_pixel(r: int, g: int, b: int) -> bool:
    """True for saturated non-skin garment pixels (any hue — not green-only)."""
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 36:
        return False
    sat = (mx - mn) / float(mx or 1)
    if sat < 0.12:
        return False
    if _is_skin_like_rgb(r, g, b):
        return False
    return True


def sample_look_garment_panel_colors(garment_png: bytes) -> dict[str, Any] | None:
    """Sample upper vs lower garment hues from a FashionRise look plate.

    Color-agnostic: works for any multi-tone garment (not green-only). Used to lock
    panel contrast so try-on providers do not wash both panels into one mid-tone.
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
                if not _is_garment_chrominance_pixel(r, g, b):
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


def _band_coverage_stats(
    px,
    *,
    w: int,
    h: int,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
) -> dict[str, float]:
    yy0, yy1 = int(h * y0), max(int(h * y0) + 1, int(h * y1))
    xx0, xx1 = int(w * x0), max(int(w * x0) + 1, int(w * x1))
    skin = garment = light = total = 0
    for y in range(yy0, yy1):
        for x in range(xx0, xx1):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            if mx < 28:
                continue
            total += 1
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            mn = min(r, g, b)
            sat = (mx - mn) / float(mx or 1)
            if _is_skin_like_rgb(r, g, b):
                skin += 1
            elif _is_garment_chrominance_pixel(r, g, b):
                garment += 1
            # Pale / translucent overlay over legs (illustration sheer often not "skin").
            if luma >= 135 and sat <= 0.38:
                light += 1
    if total <= 0:
        return {"skin": 0.0, "garment": 0.0, "light": 0.0, "total": 0.0}
    return {
        "skin": skin / float(total),
        "garment": garment / float(total),
        "light": light / float(total),
        "total": float(total),
    }


def analyze_look_plate_sheer_legs(garment_png: bytes) -> dict[str, Any]:
    """Detect visible legs through lower garment region (sheer / high-low / cutaway).

    Fashion illustrations often tint sheer layers (legs are not classic skin RGB).
    Also treat ankle openness + left/right asymmetry as sheer/cutaway signals.
    """
    empty = {
        "sheer_legs": False,
        "skin_ratio_lower": 0.0,
        "garment_ratio_lower": 0.0,
        "light_ratio_lower": 0.0,
        "ankle_open_ratio": 0.0,
        "sample_count": 0,
    }
    if not garment_png:
        return empty
    try:
        with Image.open(io.BytesIO(garment_png)) as im:
            im.load()
            rgb = im.convert("RGB")
    except Exception:  # noqa: BLE001
        return empty

    w, h = rgb.size
    if w < 8 or h < 16:
        return empty
    px = rgb.load()
    lower = _band_coverage_stats(px, w=w, h=h, x0=0.28, x1=0.72, y0=0.58, y1=0.92)
    mid = _band_coverage_stats(px, w=w, h=h, x0=0.28, x1=0.72, y0=0.45, y1=0.62)
    ankle = _band_coverage_stats(px, w=w, h=h, x0=0.28, x1=0.72, y0=0.78, y1=0.96)
    left = _band_coverage_stats(px, w=w, h=h, x0=0.18, x1=0.45, y0=0.58, y1=0.92)
    right = _band_coverage_stats(px, w=w, h=h, x0=0.55, x1=0.82, y0=0.58, y1=0.92)
    if lower["total"] < 80:
        return empty
    skin_ratio = lower["skin"]
    garment_ratio = lower["garment"]
    light_ratio = lower["light"]
    ankle_open = ankle["skin"] + ankle["light"]
    side_delta = abs(left["skin"] + left["light"] - (right["skin"] + right["light"]))
    # Visible legs in the lower band (photo or illustration cutaway).
    classic = skin_ratio >= 0.14
    # Illustrated sheer: mid skirt garment-heavy, ankle more open / pale.
    illustrated = (
        mid["garment"] >= 0.35
        and ankle_open >= 0.12
        and ankle["garment"] <= max(0.62, mid["garment"] - 0.08)
    )
    asymmetric = side_delta >= 0.08 and (
        left["skin"] + left["light"] >= 0.10 or right["skin"] + right["light"] >= 0.10
    )
    pale_mix = light_ratio >= 0.16 and garment_ratio >= 0.25 and skin_ratio >= 0.04
    cutaway_open = ankle_open >= 0.22 and skin_ratio >= 0.10
    sheer = bool(classic or illustrated or asymmetric or pale_mix or cutaway_open)
    return {
        "sheer_legs": sheer,
        "skin_ratio_lower": round(skin_ratio, 3),
        "garment_ratio_lower": round(garment_ratio, 3),
        "light_ratio_lower": round(light_ratio, 3),
        "ankle_open_ratio": round(ankle_open, 3),
        "side_open_delta": round(side_delta, 3),
        "sample_count": int(lower["total"]),
        "signals": {
            "classic": classic,
            "illustrated": illustrated,
            "asymmetric": asymmetric,
            "pale_mix": pale_mix,
            "cutaway_open": cutaway_open,
        },
    }


def analyze_fashionrise_look_plate(garment_png: bytes) -> dict[str, Any]:
    """Source-aware look analysis: color lock + sheer coverage (no paid AI)."""
    lock = sample_look_garment_panel_colors(garment_png)
    sheer = analyze_look_plate_sheer_legs(garment_png)
    return {
        "look_color_lock": lock,
        "sheer_legs": bool(sheer.get("sheer_legs")),
        "sheer": sheer,
        # ChatGPT clone (one images.edit) first; materialize only if that HTTP call fails.
        "preferred_path": "chatgpt_clone_direct",
    }


def _rgb_luma(rgb: list[int] | tuple[int, int, int]) -> float:
    return 0.299 * float(rgb[0]) + 0.587 * float(rgb[1]) + 0.114 * float(rgb[2])


def _rgb_saturation(rgb: list[int] | tuple[int, int, int]) -> float:
    r, g, b = float(rgb[0]) / 255.0, float(rgb[1]) / 255.0, float(rgb[2]) / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    if mx < 1e-6:
        return 0.0
    return (mx - mn) / mx


def _sample_result_panel_rgb(
    result_png: bytes, *, y0: float, y1: float
) -> tuple[int, int, int] | None:
    """Mean RGB of likely garment pixels in a band (includes near-black fabric).

    Outdoor try-ons have large sky/ground in the frame; we drop skin, paper whites,
    and bright low-saturation backdrop so a crushed black bodice is not averaged away.
    """
    if not result_png:
        return None
    try:
        with Image.open(io.BytesIO(result_png)) as im:
            im.load()
            rgb = im.convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    w, h = rgb.size
    if w < 8 or h < 16:
        return None
    px = rgb.load()
    yy0, yy1 = int(h * y0), max(int(h * y0) + 1, int(h * y1))
    xx0, xx1 = int(w * 0.30), max(int(w * 0.30) + 1, int(w * 0.70))
    rs: list[float] = []
    gs: list[float] = []
    bs: list[float] = []
    for y in range(yy0, yy1):
        for x in range(xx0, xx1):
            r, g, b = px[x, y]
            if _is_skin_like_rgb(r, g, b):
                continue
            if min(r, g, b) >= 230:
                continue
            luma = _rgb_luma((r, g, b))
            sat = _rgb_saturation((r, g, b))
            # Bright, weakly saturated backdrop (sky / pavement / paper).
            if luma >= 110 and sat < 0.22:
                continue
            rs.append(float(r))
            gs.append(float(g))
            bs.append(float(b))
    if len(rs) < 25:
        return None
    return (
        int(round(sum(rs) / len(rs))),
        int(round(sum(gs) / len(gs))),
        int(round(sum(bs) / len(bs))),
    )


def soft_check_look_color_fidelity(
    result_png: bytes,
    *,
    look_analysis: dict[str, Any] | None,
) -> list[str]:
    """Detect bright design panels crushed to near-black (the paid Social failure mode)."""
    warnings: list[str] = []
    analysis = look_analysis if isinstance(look_analysis, dict) else {}
    lock = analysis.get("look_color_lock")
    if not isinstance(lock, dict):
        return warnings
    # Multiple band layouts: look-plate proportions vs typical outdoor try-on crop.
    band_layouts = (
        {"bodice": (0.28, 0.46), "skirt": (0.52, 0.74)},
        {"bodice": (0.15, 0.32), "skirt": (0.38, 0.62)},
        {"bodice": (0.18, 0.36), "skirt": (0.42, 0.68)},
    )
    for bands in band_layouts:
        crushed = False
        for key, (y0, y1) in bands.items():
            design = lock.get(f"{key}_rgb")
            if not (isinstance(design, list) and len(design) == 3):
                continue
            result = _sample_result_panel_rgb(result_png, y0=y0, y1=y1)
            if result is None:
                continue
            design_l = _rgb_luma(design)
            result_l = _rgb_luma(result)
            design_s = _rgb_saturation(design)
            # Bright, saturated design panel must not collapse into charcoal/black.
            # Thresholds allow partial sky bleed in outdoor crops while still
            # catching the paid failure (vivid blue/pink → near-black bodice).
            if (
                design_l >= 90
                and design_s >= 0.25
                and result_l <= 78
                and (design_l - result_l) >= 28
            ):
                crushed = True
                break
        if crushed:
            warnings.append("color_crush_to_dark")
            break
    return warnings


def soft_check_look_tryon_result(
    result_png: bytes,
    *,
    look_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Local quality signals after try-on — no extra provider calls.

    Checks sheer coverage, color lock, color fidelity, and illustrated/sketch texture.
    Passing color+legs alone is not enough to mark a result high quality.
    """
    from app.services.look_garment_normalize import estimate_sketch_texture_score

    warnings: list[str] = []
    analysis = look_analysis if isinstance(look_analysis, dict) else {}
    sheer_expected = bool(analysis.get("sheer_legs"))
    result_sheer = analyze_look_plate_sheer_legs(result_png)
    skin_ratio = float(result_sheer.get("skin_ratio_lower") or 0.0)
    if sheer_expected and skin_ratio < 0.05:
        warnings.append("sheer_legs_likely_covered")
    lock = analysis.get("look_color_lock")
    if isinstance(lock, dict) and lock.get("relation") == "lighter_bodice":
        # Spot-check result still has lighter upper vs lower garment chrominance.
        result_lock = sample_look_garment_panel_colors(result_png)
        if (
            isinstance(result_lock, dict)
            and result_lock.get("relation") == "darker_bodice"
            and float(result_lock.get("luma_delta") or 0) < -8
        ):
            warnings.append("color_lock_inverted")
    warnings.extend(
        soft_check_look_color_fidelity(result_png, look_analysis=look_analysis)
    )
    texture = estimate_sketch_texture_score(result_png)
    if texture.get("illustrated_texture_suspected"):
        warnings.append("illustrated_texture_suspected")
    return {
        "ok": len(warnings) == 0,
        "warnings": warnings,
        "result_skin_ratio_lower": round(skin_ratio, 3),
        "sheer_expected": sheer_expected,
        "texture": texture,
    }


def _look_result_looks_illustrated(quality: dict[str, Any] | None) -> bool:
    if not isinstance(quality, dict):
        return False
    return "illustrated_texture_suspected" in (quality.get("warnings") or [])


def _look_result_needs_recovery(quality: dict[str, Any] | None) -> bool:
    """Soft texture OR color-crush → escalate; never cancel the paid try-on."""
    if not isinstance(quality, dict):
        return False
    warnings = quality.get("warnings") or []
    return any(
        w in warnings
        for w in (
            "illustrated_texture_suspected",
            "color_crush_to_dark",
            "color_lock_inverted",
        )
    )


# ChatGPT-documented Social look edit (2 images): person = edit target, design =
# garment reference. Used only when ``fitting_room_look_direct_edit_v2_enabled``.
# Does not require a materialized product plate.
FITTING_ROOM_DIRECT_EDIT_V2_PROMPT = (
    "Edit IMAGE 1, the real photograph.\n"
    "\n"
    "IMAGE 1 is the authoritative person and scene.\n"
    "IMAGE 2 is the authoritative garment design.\n"
    "\n"
    "Dress the person in IMAGE 1 with the EXACT garment shown in IMAGE 2.\n"
    "\n"
    "PRESERVE FROM IMAGE 1:\n"
    "- Face, identity, hairstyle, expression and skin tone\n"
    "- Body proportions, pose and camera angle\n"
    "- Background, lighting and environment\n"
    "- Original shoes unless the design explicitly shows different footwear\n"
    "\n"
    "TRANSFER FROM IMAGE 2:\n"
    "- Exact garment silhouette and length\n"
    "- All colors and their placement\n"
    "- Neckline, sleeves, seams, panels and layers\n"
    "- Patterns, decorations and distinctive details "
    "(petals, leaves, shoulder accents)\n"
    "\n"
    "CRITICAL COLOR RULE:\n"
    "Black sketch outlines are NOT black fabric.\n"
    "Never recolor bright blue, pink, purple or green garment panels into black, "
    "charcoal or gray.\n"
    "Preserve the actual colors visible in the design.\n"
    "\n"
    "FOOTWEAR:\n"
    "If IMAGE 2 shows shoes, heels, flats, sneakers, or boots as part of the outfit, "
    "replace IMAGE 1 footwear with those design shoes (same style, color, pattern). "
    "Do not keep photo boots when the design shows different shoes. "
    "Only keep IMAGE 1 footwear when IMAGE 2 shows no shoes.\n"
    "\n"
    "Replace only the clothing. Render the result as a natural photorealistic "
    "photograph with realistic fabric texture, folds, drape and contact shadows.\n"
    "\n"
    "The illustration's drawn face, body and background must NOT replace the real "
    "person.\n"
    "\n"
    "Output one completed photograph, not a collage."
)

# Identity-first prompt (v1). Used when ``fitting_room_look_identity_lock_enabled``.
# Prompt alone is insufficient — face pixels are also composited post-edit.
FITTING_ROOM_IDENTITY_V1_PROMPT = (
    "Edit the original photograph by replacing only the clothing with the provided "
    "fashion design.\n"
    "\n"
    "Images 1 and 2 are the SAME real person photograph — that exact individual is the "
    "absolute authority for identity, appearance, pose, and environment.\n"
    "Image 3 is the fashion design — garment reference ONLY.\n"
    "\n"
    "Do not regenerate the person's face, hair, or body. Do not beautify, smooth, slim, "
    "re-age, or face-swap. Preserve the same facial features, expression, skin tone and "
    "texture, hair color and curl pattern, body proportions, hands, and visible "
    "unchanged skin.\n"
    "\n"
    "Transfer the garment design faithfully: colors and placement, neckline, silhouette, "
    "decorative petals/leaves/shoulder pieces, material structure, and hem length "
    "(short stays short). Black sketch outlines are NOT black fabric — never crush "
    "bright blue, pink, purple, or green panels into black or gray.\n"
    "\n"
    "FOOTWEAR: if image 3 shows shoes/heels/boots, replace photo footwear with those "
    "design shoes; only keep photo shoes when image 3 shows no footwear.\n"
    "\n"
    "Make the garment look naturally worn, with realistic fabric texture, folds, "
    "gravity, and lighting matched to the person photo. Preserve background, wings, "
    "railings, sky, and framing.\n"
    "\n"
    "Never copy the illustrated model's face, body, or pose. Return one realistic "
    "edited photograph."
)

# Sentinel path label when identity gate rejects (no Stars — job fails closed).
LOOK_IDENTITY_REJECTED = "LOOK_IDENTITY_REJECTED"

# OpenAI cookbook try-on: edit the real photo; clothing refs only change clothes.
# Prefer a face-free product plate (materialize) as image 3 — look illustrations
# include a drawn model that otherwise competes for identity.
# API: person photo ×2 (images 1–2) + garment/product (image 3).
FITTING_ROOM_CHATGPT_CLONE_PROMPT = (
    "Edit the real photograph. Images 1 and 2 are the SAME real person photo — that "
    "exact woman is the ONLY identity to keep. Image 3 is clothing reference only. "
    "Output must be recognizably the same individual as images 1–2 — same face geometry, "
    "eyes, nose, mouth, smile, freckles/marks, skin tone, hair color and curl pattern, "
    "body proportions, pose, and hand placement. Do not invent a new model, beautify, "
    "smooth, slim, re-age, or face-swap. "
    "Image 3 may be a fashion illustration or a studio product photo. Ignore any drawn "
    "or mannequin body/face/hair/skin in image 3 — never copy that figure into the "
    "output. Use only the garment: cut, silhouette, neckline, straps, layers, petals, "
    "leaves, panel layout, and colors. "
    "Keep every panel color exact from image 3 — especially bright blues, pinks, "
    "purples, and greens; never crush them into black, charcoal, or muddy grey. "
    "Keep the exact hem length from image 3 (short mini stays short) and layered petal "
    "structure. Where the design is sheer or short, legs must stay visible. "
    "Replace her clothing with that design, fitted to her existing pose with realistic "
    "fabric drape, folds, and contact shadows. "
    "FOOTWEAR: if image 3 shows shoes, heels, flats, sneakers, or boots as part of the "
    "outfit, replace the person's photo footwear with those design shoes (same style, "
    "color, and pattern) — do not keep the original photo boots when the design shows "
    "different shoes. Only keep photo footwear when image 3 shows no shoes. "
    "Match the person photo's lighting, shadows, and color temperature. Preserve the "
    "full scene: background, props, sculptures, wings, railings, sky, ground, camera "
    "angle, and framing. Photoreal only — no sketch look. Do not add text, logos, or "
    "watermarks."
)

# When image 3 is already a materialized studio product (no competing face).
FITTING_ROOM_CHATGPT_CLONE_PRODUCT_PROMPT = (
    "Edit the real photograph. Images 1 and 2 are the SAME real person photo — that "
    "exact woman is the ONLY identity to keep. Image 3 is a studio product photograph "
    "of the garment on a white mannequin. Ignore the mannequin body/head/hands/stand. "
    "Dress that exact woman in the clothing from image 3. "
    "Output must be recognizably the same individual as images 1–2 — same face, "
    "expression, hair, skin tone, body proportions, pose, and hands. Do not invent a "
    "new model or beautify her. "
    "Transfer garment cut, layers, petals, leaves, colors, and hem length exactly. "
    "Keep bright blues/pinks/purples/greens — never crush into black. Short hems stay "
    "short; sheer layers stay sheer with legs visible. "
    "FOOTWEAR: if image 3 shows shoes/heels/boots, replace the person's photo footwear "
    "with those product shoes — do not keep photo boots when the product shows "
    "different shoes. Only keep photo footwear when image 3 shows no shoes. "
    "Match person-photo lighting. Preserve background, wings, railings, sky, framing. "
    "Photoreal fabric only — no sketch overlay."
)


def _chatgpt_style_look_prompt(data: dict[str, Any], hints: list[str]) -> str:
    """ChatGPT-clone prompt + optional measured COLOR LOCK hexes.

    Uses the product-plate prompt when the look was already materialized (no drawn
    face competing with the real person).
    """
    productized = bool(data.get("look_productized") or data.get("look_materialized"))
    prompt = (
        FITTING_ROOM_CHATGPT_CLONE_PRODUCT_PROMPT
        if productized
        else FITTING_ROOM_CHATGPT_CLONE_PROMPT
    )
    clause = ""
    raw = data.get("look_palette_clause")
    if isinstance(raw, str) and raw.strip():
        clause = raw.strip()
    else:
        clause = (_look_palette_clause(data) or "").strip()
    if clause and "COLOR LOCK" not in prompt:
        prompt = f"{prompt} {clause}"
    lock = data.get("look_color_lock")
    if isinstance(lock, dict):
        lock_clause = _look_color_lock_prompt_clause(lock)
        if lock_clause and lock_clause.strip() not in prompt:
            prompt = f"{prompt}{lock_clause}"
    # Keep hint budget tiny — ChatGPT wins with short prompts.
    evidence: list[str] = []
    for raw_h in hints:
        tip = " ".join(str(raw_h).split())
        if tip and tip not in evidence:
            evidence.append(tip[:100])
        if len(evidence) >= 3:
            break
    if evidence:
        prompt = f"{prompt} Design notes: " + "; ".join(evidence) + "."
    return prompt


def _direct_edit_v2_look_prompt(
    data: dict[str, Any], hints: list[str], *, identity_lock: bool = False
) -> str:
    """Direct-edit prompt: v2 (2-image) or identity-v1 (person×2 + garment)."""
    prompt = (
        FITTING_ROOM_IDENTITY_V1_PROMPT if identity_lock else FITTING_ROOM_DIRECT_EDIT_V2_PROMPT
    )
    clause = ""
    raw = data.get("look_palette_clause")
    if isinstance(raw, str) and raw.strip():
        clause = raw.strip()
    else:
        clause = (_look_palette_clause(data) or "").strip()
    # Measured hexes are hints only — never a destructive post color-lock.
    if clause and "COLOR LOCK" not in prompt:
        prompt = f"{prompt}\n\n{clause}"
    evidence: list[str] = []
    for raw_h in hints:
        tip = " ".join(str(raw_h).split())
        if tip and tip not in evidence:
            evidence.append(tip[:100])
        if len(evidence) >= 3:
            break
    if evidence:
        prompt = f"{prompt}\n\nDesign notes: " + "; ".join(evidence) + "."
    return prompt


class LookIdentityRejected(Exception):
    """Identity gate failed — do not deliver or fall through to more paid calls."""

    def __init__(self, meta: dict[str, Any]):
        super().__init__(LOOK_IDENTITY_REJECTED)
        self.meta = meta


def _resolve_look_openai_model(*, allow_legacy_fallback: bool) -> str:
    """Resolve Social look images.edit model from settings.

    When ``allow_legacy_fallback`` is False (direct-edit v2), never silently
    substitute a different model — unsupported / retired ids raise before HTTP.
    Legacy ChatGPT-clone may fall back to ``gpt-image-2`` for older deploys.
    """
    from app.services.sketch_openai import assert_image_model_editable, image_edit_capabilities

    settings = get_settings()
    model = (settings.fitting_room_look_openai_model or "chatgpt-image-latest").strip()
    if allow_legacy_fallback:
        caps = image_edit_capabilities(model)
        if caps is None or caps.status != "supported":
            model = "gpt-image-2"
    assert_image_model_editable(model)
    return model


def _run_direct_edit_v2_images_edit(
    *,
    person_png: bytes,
    look_png: bytes,
    prompt: str,
    identity_lock: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """One OpenAI images.edit for Social look direct path.

    Default: person + original design (2 images).
    Identity lock: person ×2 + design (3 images) — still no materialize / color-lock.
    Model from ``fitting_room_look_openai_model`` with no silent substitution.
    """
    from io import BytesIO

    from openai import OpenAI

    from app.services.personal_croquis_provider import extract_edit_png_bytes
    from app.services.sketch_openai import build_image_edit_kwargs

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise ProviderNotAvailableError("OPENAI_API_KEY missing")

    model = _resolve_look_openai_model(allow_legacy_fallback=False)
    quality = (settings.fitting_room_look_openai_quality or "high").strip()
    size = (settings.openai_image_size or "1024x1536").strip()

    kwargs = build_image_edit_kwargs(
        model=model,
        prompt=prompt,
        sketch=(person_png, "image/png"),
        size=size,
        quality=quality,
        fabric_swatch=(look_png, "image/png"),
    )
    person_file = ("person.png", BytesIO(person_png), "image/png")
    design_file = ("garment.png", BytesIO(look_png), "image/png")
    if identity_lock:
        # Structure B: person + identity duplicate + garment.
        kwargs["image"] = [
            person_file,
            ("person_identity.png", BytesIO(person_png), "image/png"),
            design_file,
        ]
        image_order = ["person", "person_identity", "garment"]
        identity_count = 2
    else:
        kwargs["image"] = [person_file, design_file]
        image_order = ["person", "garment"]
        identity_count = 1
    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    kwargs.pop("background", None)
    extra = dict(kwargs.get("extra_body") or {})
    extra["moderation"] = "low"
    kwargs["extra_body"] = extra

    logger.info(
        "Fitting Room direct-edit-v2 images.edit model=%s size=%s quality=%s "
        "images=%s identity_lock=%s",
        kwargs.get("model"),
        kwargs.get("size"),
        kwargs.get("quality"),
        "+".join(image_order),
        identity_lock,
    )

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=float(settings.openai_timeout_seconds or 180),
    )
    result = client.with_options(max_retries=0).images.edit(**kwargs)
    png = extract_edit_png_bytes(result)
    from app.services.look_identity_lock import IDENTITY_PROMPT_VERSION

    meta: dict[str, Any] = {
        "provider": "openai_images_edit",
        "model": kwargs.get("model"),
        "quality": kwargs.get("quality"),
        "size": kwargs.get("size"),
        "chatgpt_clone": True,
        "direct_edit_v2": True,
        "identity_lock": bool(identity_lock),
        "prompt_version": IDENTITY_PROMPT_VERSION if identity_lock else "direct_edit_v2",
        "input_fidelity": kwargs.get("input_fidelity"),
        "identity_image_count": identity_count,
        "design_image_count": 1,
        "image_order": image_order,
        "openai_calls": 1,
    }
    return png, meta


def _model_b_sunburst_look_prompt() -> str:
    """Proven compare Arm B prompt + footwear clause (single generation)."""
    return MODEL_B_SUNBURST_PROMPT


def _try_model_b_sunburst_look_fit(
    *,
    job_id: uuid.UUID,
    person_png: bytes,
    look_png: bytes,
    data: dict[str, Any],
) -> tuple[bytes, dict[str, Any], str, dict[str, Any] | None] | None:
    """One OpenAI images.edit: person + design via gpt-image-2.6-sunburst.

    No materialize, mask, face patch, color-lock, or paid fallback. Fail closed
    on provider error (caller must not chain another paid path).
    """
    from app.services.openai_person_garment_edit import run_openai_person_garment_images_edit
    from app.services.sketch_openai import assert_image_model_editable

    assert_image_model_editable(MODEL_B_SUNBURST_MODEL)
    prompt = _model_b_sunburst_look_prompt()
    try:
        png, meta = run_openai_person_garment_images_edit(
            person_png=person_png,
            design_png=look_png,
            model=MODEL_B_SUNBURST_MODEL,
            prompt=prompt,
            prompt_version=MODEL_B_SUNBURST_PROMPT_VERSION,
            path=MODEL_B_SUNBURST_PATH,
            quality="high",
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Fitting Room job %s Model B sunburst images.edit failed",
            job_id,
        )
        return None
    if not png:
        return None
    meta = dict(meta) if isinstance(meta, dict) else {}
    meta["fitting_room_look_path"] = MODEL_B_SUNBURST_PATH
    meta["model_b_sunburst"] = True
    meta["direct_edit_v2"] = False
    meta["chatgpt_clone"] = False
    # Soft quality: skip illustrated recovery / color-lock for this raw path.
    quality = {
        "ok": True,
        "warnings": [],
        "path": MODEL_B_SUNBURST_PATH,
        "skipped_soft_recovery": True,
    }
    data["look_model_b_sunburst"] = True
    data["look_chatgpt_clone"] = True  # skips result color-lock / recovery
    data["look_materialized"] = False
    data["look_normalized"] = False
    data.pop("look_productized", None)
    return png, meta, "openai", quality


def _try_direct_edit_v2_look_fit(
    *,
    job_id: Any,
    person_png: bytes,
    look_png: bytes,
    data: dict[str, Any],
    hints: list[str],
    look_analysis: dict[str, Any] | None,
) -> tuple[bytes, dict[str, Any], str, dict[str, Any]] | None:
    """Flagged ChatGPT-style direct edit: original person + original design only.

    Soft-checks are telemetry — never run result color-lock (black-bodice crush).
    When identity lock is ON: person×2 + garment, face-pixel composite, hard gate.
    Raises ``LookIdentityRejected`` when the gate fails (caller must not fall through).
    """
    settings = get_settings()
    if not bool(settings.fitting_room_look_direct_edit_v2_enabled):
        return None
    identity_lock = bool(settings.fitting_room_look_identity_lock_enabled)
    prompt = _direct_edit_v2_look_prompt(data, hints, identity_lock=identity_lock)
    try:
        png, meta = _run_direct_edit_v2_images_edit(
            person_png=person_png,
            look_png=look_png,
            prompt=prompt,
            identity_lock=identity_lock,
        )
    except Exception:  # noqa: BLE001
        logger.info(
            "Fitting Room job %s direct-edit-v2 images.edit failed",
            job_id,
            exc_info=True,
        )
        return None
    if not png:
        return None

    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)

    if identity_lock:
        from app.services.look_identity_lock import (
            composite_identity_from_person,
            validate_identity_lock,
        )

        try:
            png, id_meta = composite_identity_from_person(png, person_png)
        except Exception:  # noqa: BLE001
            logger.info(
                "Fitting Room job %s identity composite failed",
                job_id,
                exc_info=True,
            )
            id_meta = {"applied": False, "reason": "composite_error"}
        meta["look_identity_lock"] = id_meta
        gate = validate_identity_lock(png, person_png, composite_meta=id_meta)
        meta["look_identity_gate"] = gate
        if not gate.get("ok"):
            logger.info(
                "Fitting Room job %s identity gate REJECTED mad=%s reason=%s",
                job_id,
                gate.get("face_luma_mad"),
                gate.get("reason"),
            )
            raise LookIdentityRejected(meta)
        path_label = "chatgpt_direct_edit_v2_identity"
    else:
        path_label = "chatgpt_direct_edit_v2"

    quality = soft_check_look_tryon_result(png, look_analysis=look_analysis)
    meta["fitting_room_look_path"] = path_label
    meta["look_analysis"] = look_analysis
    meta["look_quality"] = quality
    meta["look_color_lock_skipped"] = True
    if _look_result_needs_recovery(quality):
        meta["look_quality_kept_despite_soft_check"] = True
        logger.info(
            "Fitting Room job %s direct-edit-v2 soft warnings=%s — keeping result",
            job_id,
            quality.get("warnings"),
        )
    logger.info(
        "Fitting Room job %s direct-edit-v2 accepted model=%s path=%s identity_lock=%s",
        job_id,
        meta.get("model"),
        path_label,
        identity_lock,
    )
    return png, meta, "openai", quality


def _run_chatgpt_clone_images_edit(
    *,
    person_png: bytes,
    look_png: bytes,
    prompt: str,
) -> tuple[bytes, dict[str, Any]]:
    """One OpenAI images.edit — person photo (×2 identity lock) + design plate.

    Uses ``fitting_room_look_openai_model`` (default ``chatgpt-image-latest``).
    Sends the person PNG twice so the look plate's drawn model cannot win the
    identity contest (OpenAI allows up to 16 edit images).
    Does **not** charcoal-matte the design, materialize, or color-lock.
    """
    from io import BytesIO

    from openai import OpenAI

    from app.services.personal_croquis_provider import extract_edit_png_bytes
    from app.services.sketch_openai import build_image_edit_kwargs

    settings = get_settings()
    if not (settings.openai_api_key or "").strip():
        raise ProviderNotAvailableError("OPENAI_API_KEY missing")

    model = _resolve_look_openai_model(allow_legacy_fallback=True)
    quality = (settings.fitting_room_look_openai_quality or "high").strip()
    size = (settings.openai_image_size or "1024x1536").strip()

    # Build base kwargs (quality/size/fidelity), then replace image list with
    # person × 2 + design so identity outvotes the illustrated figure in the look.
    kwargs = build_image_edit_kwargs(
        model=model,
        prompt=prompt,
        sketch=(person_png, "image/png"),
        size=size,
        quality=quality,
        fabric_swatch=(look_png, "image/png"),
    )
    person_file = ("person.png", BytesIO(person_png), "image/png")
    identity_file = ("person_identity.png", BytesIO(person_png), "image/png")
    design_file = ("design.png", BytesIO(look_png), "image/png")
    kwargs["image"] = [person_file, identity_file, design_file]
    kwargs["n"] = 1
    kwargs["output_format"] = "png"
    kwargs.pop("background", None)
    extra = dict(kwargs.get("extra_body") or {})
    extra["moderation"] = "low"
    kwargs["extra_body"] = extra

    client = OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        timeout=float(settings.openai_timeout_seconds or 180),
    )
    result = client.with_options(max_retries=0).images.edit(**kwargs)
    png = extract_edit_png_bytes(result)
    meta: dict[str, Any] = {
        "provider": "openai_images_edit",
        "model": kwargs.get("model"),
        "quality": kwargs.get("quality"),
        "size": kwargs.get("size"),
        "chatgpt_clone": True,
        "input_fidelity": kwargs.get("input_fidelity"),
        "identity_image_count": 2,
        "design_image_count": 1,
    }
    return png, meta


def _try_chatgpt_style_look_fit(
    *,
    job_id: Any,
    person_png: bytes,
    look_png: bytes,
    data: dict[str, Any],
    hints: list[str],
    look_analysis: dict[str, Any] | None,
    look_palette: dict[str, Any] | None,
    look_color_lock_on: bool,
    path_label: str = "chatgpt_clone_direct",
) -> tuple[bytes, dict[str, Any], str, dict[str, Any]] | None:
    """ChatGPT clone: one images.edit of person + garment/product plate.

    Soft-checks are telemetry only — we do **not** run result color-lock (that path
    crushed bright blues to black). Prefer a materialized product plate as
    ``look_png`` so the look illustration's drawn face cannot steal identity.
    """
    settings = get_settings()
    if not bool(settings.fitting_room_look_chatgpt_clone_enabled):
        return None
    prompt = _chatgpt_style_look_prompt(data, hints)
    try:
        png, meta = _run_chatgpt_clone_images_edit(
            person_png=person_png,
            look_png=look_png,
            prompt=prompt,
        )
    except Exception:  # noqa: BLE001
        logger.info(
            "Fitting Room job %s ChatGPT-clone images.edit failed path=%s",
            job_id,
            path_label,
            exc_info=True,
        )
        return None
    if not png:
        return None
    # Do NOT run lock_result_to_palette here — that path crushed bright blues to black.
    _ = look_palette, look_color_lock_on  # retained for call-site compatibility
    quality = soft_check_look_tryon_result(png, look_analysis=look_analysis)
    if not isinstance(meta, dict):
        meta = {}
    meta = dict(meta)
    meta["fitting_room_look_path"] = path_label
    meta["look_analysis"] = look_analysis
    meta["look_quality"] = quality
    meta["look_color_lock_skipped"] = True
    if _look_result_needs_recovery(quality):
        # Keep the clone result anyway — ChatGPT does not reject soft heuristics.
        meta["look_quality_kept_despite_soft_check"] = True
        logger.info(
            "Fitting Room job %s ChatGPT-clone soft warnings=%s path=%s — keeping result",
            job_id,
            quality.get("warnings"),
            path_label,
        )
    logger.info(
        "Fitting Room job %s ChatGPT-clone accepted model=%s path=%s",
        job_id,
        meta.get("model"),
        path_label,
    )
    return png, meta, "openai", quality


# Stronger OpenAI hints when the first try-on still looked like a Magic paste.
_LOOK_PHOTOREAL_RECOVERY_HINTS = (
    "CRITICAL RECOVERY: a prior try-on looked like a flat illustration paste or sticker "
    "overlay. Re-render as a real camera photograph of sewn fabric on the person — "
    "visible weave, gravity drape, soft contact shadows, scene lighting matched.",
    "Opaque garment panels must fully replace the person's original clothes underneath. "
    "No floating petals/leaves, no sketched outlines, no airbrushed concept-art shading.",
)


def _fitting_room_openai_recovery_prompt(data: dict[str, Any], hints: list[str]) -> str:
    """OpenAI V2.8 + look hints + photoreal recovery boost."""
    base = _fitting_room_openai_prompt(data, hints) or ""
    from app.services.personal_try_on_provider import build_try_on_prompt

    if not base.strip():
        base = build_try_on_prompt(list(hints) + list(_LOOK_PHOTOREAL_RECOVERY_HINTS))
        return base
    # Append recovery hints (build_try_on_prompt already applied for look_normalized).
    extra = " ".join(_LOOK_PHOTOREAL_RECOVERY_HINTS)
    return f"{base} {extra}".strip()


def _recover_illustrated_look_tryon(
    *,
    job_id: Any,
    person_png: bytes,
    product_png: bytes,
    data: dict[str, Any],
    hints: list[str],
    look_analysis: dict[str, Any] | None,
    look_palette: dict[str, Any] | None,
    look_color_lock_on: bool,
    initial_png: bytes,
    initial_meta: dict[str, Any],
    initial_quality: dict[str, Any],
    initial_provider: str,
) -> tuple[bytes, dict[str, Any], str, dict[str, Any]]:
    """Escalate OpenAI recovery → FASHN Max until photoreal, else keep best attempt.

    Never cancels a paid Fitting Room look solely because the soft texture/color check
    flagged issues — keep trying harder providers, then deliver the best image.
    Prefer results without ``color_crush_to_dark`` over darker crushed ones.
    """
    attempts: list[dict[str, Any]] = [
        {
            "step": "initial",
            "provider": initial_provider,
            "illustrated": _look_result_looks_illustrated(initial_quality),
            "warnings": list(initial_quality.get("warnings") or []),
        }
    ]
    best_png = initial_png
    best_meta = dict(initial_meta) if isinstance(initial_meta, dict) else {}
    best_provider = initial_provider
    best_quality = initial_quality

    def _quality_rank(quality: dict[str, Any] | None) -> tuple[int, int, int]:
        """Higher is better: no crush beats crush; no illustration beats illustration."""
        warnings = (quality or {}).get("warnings") or []
        crush = 0 if "color_crush_to_dark" in warnings else 1
        texture = 0 if "illustrated_texture_suspected" in warnings else 1
        invert = 0 if "color_lock_inverted" in warnings else 1
        return (crush, texture, invert)

    def _consider(candidate: bytes, meta: dict[str, Any], provider: str, quality: dict[str, Any]) -> bool:
        nonlocal best_png, best_meta, best_provider, best_quality
        if _quality_rank(quality) >= _quality_rank(best_quality):
            best_png, best_meta, best_provider, best_quality = (
                candidate,
                meta if isinstance(meta, dict) else {},
                provider,
                quality,
            )
        return not _look_result_needs_recovery(quality)

    def _maybe_color_lock(candidate: bytes) -> bytes:
        if not (look_palette and look_color_lock_on):
            return candidate
        try:
            locked, _lock_meta = lock_result_to_palette(candidate, person_png, look_palette)
            return locked
        except Exception:  # noqa: BLE001
            logger.warning(
                "Fitting Room job %s recovery color lock failed", job_id, exc_info=True
            )
            return candidate

    # 1) OpenAI photoreal recovery retry (stronger anti-paste + anti-black-crush).
    try:
        provider = get_try_on_provider("openai")
        recovery_prompt = _fitting_room_openai_recovery_prompt(data, hints)
        if "COLOR FIDELITY" not in recovery_prompt:
            recovery_prompt = (
                f"{recovery_prompt} COLOR FIDELITY: keep every bright panel bright — "
                "never darken vivid blue/pink/purple/green into black or charcoal."
            )
        # When not materialized, recovery_prompt via look_normalized product path is wrong —
        # use ChatGPT-style direct prompt on the look plate / product bytes we were given.
        if not data.get("look_materialized"):
            recovery_prompt = _chatgpt_style_look_prompt(data, hints)
        png, meta = provider.generate(
            photo_png=person_png,
            garment_png=product_png,
            design_hints=hints,
            prompt_override=recovery_prompt,
        )
        if png:
            png = _maybe_color_lock(png)
            quality = soft_check_look_tryon_result(png, look_analysis=look_analysis)
            illustrated = _look_result_looks_illustrated(quality)
            attempts.append(
                {
                    "step": "openai_photoreal_recovery",
                    "provider": "openai",
                    "illustrated": illustrated,
                    "warnings": list(quality.get("warnings") or []),
                }
            )
            meta_dict = meta if isinstance(meta, dict) else {}
            if _consider(png, meta_dict, "openai", quality):
                best_meta = dict(best_meta)
                best_meta["fitting_room_look_path"] = (
                    "materialize_then_openai_recovery"
                    if data.get("look_materialized")
                    else "direct_openai_recovery"
                )
                best_meta["look_quality_recovery"] = attempts
                if isinstance(initial_meta, dict) and initial_meta.get("look_materialize"):
                    best_meta.setdefault("look_materialize", initial_meta.get("look_materialize"))
                best_meta.setdefault("look_analysis", look_analysis)
                logger.info(
                    "Fitting Room job %s recovery succeeded via OpenAI photoreal retry",
                    job_id,
                )
                return best_png, best_meta, best_provider, best_quality
    except Exception:  # noqa: BLE001
        attempts.append(
            {
                "step": "openai_photoreal_recovery",
                "provider": "openai",
                "error": "provider_failed",
            }
        )
        logger.info(
            "Fitting Room job %s OpenAI photoreal recovery failed — trying Max",
            job_id,
            exc_info=True,
        )

    # 2) FASHN Max quality · 2k on the product / look reference.
    if _fashn_max_fallback_armed():
        try:
            png, meta = _generate_look_try_on_via_max(
                person_png=person_png,
                product_png=product_png,
                palette=look_palette,
                data=data,
            )
            if png:
                png = _maybe_color_lock(png)
                quality = soft_check_look_tryon_result(png, look_analysis=look_analysis)
                illustrated = _look_result_looks_illustrated(quality)
                attempts.append(
                    {
                        "step": "fashn_max_recovery",
                        "provider": str((meta or {}).get("provider") or "fashn_tryon_max"),
                        "illustrated": illustrated,
                        "warnings": list(quality.get("warnings") or []),
                    }
                )
                meta_dict = meta if isinstance(meta, dict) else {}
                provider_name = str(meta_dict.get("provider") or "fashn_tryon_max")
                accepted = _consider(png, meta_dict, provider_name, quality)
                best_meta = dict(best_meta)
                best_meta["fitting_room_look_path"] = (
                    "materialize_then_max_recovery"
                    if accepted
                    else "materialize_then_max_recovery_soft"
                )
                if isinstance(initial_meta, dict) and initial_meta.get("look_materialize"):
                    best_meta.setdefault("look_materialize", initial_meta.get("look_materialize"))
                best_meta.setdefault("look_analysis", look_analysis)
                if accepted:
                    best_meta["look_quality_recovery"] = attempts
                    logger.info(
                        "Fitting Room job %s recovery succeeded via FASHN Max",
                        job_id,
                    )
                    return best_png, best_meta, best_provider, best_quality
        except Exception:  # noqa: BLE001
            attempts.append(
                {
                    "step": "fashn_max_recovery",
                    "provider": "fashn_tryon_max",
                    "error": "provider_failed",
                }
            )
            logger.info(
                "Fitting Room job %s Max recovery failed — keeping best prior attempt",
                job_id,
                exc_info=True,
            )

    # Soft check may false-positive on busy outdoor photos; never cancel after paid
    # generation — deliver the best attempt with recovery telemetry.
    if not isinstance(best_meta, dict):
        best_meta = {}
    best_meta = dict(best_meta)
    best_meta.setdefault(
        "fitting_room_look_path",
        (initial_meta or {}).get("fitting_room_look_path")
        if isinstance(initial_meta, dict)
        else "materialize_then_openai_kept_after_recovery",
    )
    if isinstance(initial_meta, dict) and initial_meta.get("look_materialize"):
        best_meta.setdefault("look_materialize", initial_meta.get("look_materialize"))
    best_meta.setdefault("look_analysis", look_analysis)
    best_meta["look_quality_recovery"] = attempts
    best_meta["look_quality_kept_despite_soft_check"] = True
    logger.info(
        "Fitting Room job %s keeping best look attempt after recovery attempts=%s",
        job_id,
        len(attempts),
    )
    return best_png, best_meta, best_provider, best_quality


def reinforce_look_plate_panel_colors(
    garment_png: bytes,
    lock: dict[str, Any] | None,
    *,
    strength: float = 0.42,
    skip_skin: bool = True,
) -> bytes:
    """Mildly pull upper/lower garment pixels toward measured panel means.

    Helps FASHN Max see the bodice/skirt split instead of averaging to one mid-tone.
    Skips skin-like pixels so sheer/leg regions are not painted opaque.
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
            if skip_skin and _is_skin_like_rgb(r, g, b):
                continue
            if not _is_garment_chrominance_pixel(r, g, b):
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
        "Never average panels into one mid-tone."
    )


def _look_palette_clause(data: dict[str, Any]) -> str:
    """Measured palette sentence (preferred) or the legacy two-band lock sentence."""
    clause = data.get("look_palette_clause")
    if isinstance(clause, str) and clause.strip():
        return clause
    lock = data.get("look_color_lock")
    return _look_color_lock_prompt_clause(lock if isinstance(lock, dict) else None)


def _look_materialized_max_prompt(palette: dict[str, Any] | None) -> str:
    return FITTING_ROOM_LOOK_MATERIALIZED_MAX_PROMPT + palette_prompt_clause(palette)


def _fitting_room_max_prompt(data: dict[str, Any]) -> str:
    if not _is_fashionrise_look_plate(data):
        if _outfit_needs_footwear_contract(data):
            return FITTING_ROOM_MAX_OUTFIT_PROMPT
        return FITTING_ROOM_MAX_PROMPT
    clause = _look_palette_clause(data)
    sheer = bool((data.get("look_analysis") or {}).get("sheer_legs")) if isinstance(data.get("look_analysis"), dict) else bool(data.get("look_sheer_legs"))
    sheer_clause = (
        " CRITICAL SHEER: keep tulle/chiffon translucent — legs visible where the look "
        "shows them; never opaque-fill the skirt."
        if sheer and not data.get("look_productized")
        else ""
    )
    # Already productized look → shorter product-fit prompt; else illustration prompt.
    base = (
        FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT
        if data.get("look_productized")
        else FITTING_ROOM_LOOK_PLATE_PROMPT
    )
    # normalize_max_prompt truncates at 1000 — keep color lock near the front.
    merged = base[:680] + clause + sheer_clause
    return merged if (clause or sheer_clause) else base


def _fitting_room_openai_prompt(data: dict[str, Any], hints: list[str]) -> str | None:
    """Look-plate / multi-piece outfit prompt override; None → provider default."""
    if not _is_fashionrise_look_plate(data):
        if _outfit_needs_footwear_contract(data):
            return FITTING_ROOM_OPENAI_OUTFIT_PROMPT
        return None
    clause = _look_palette_clause(data)
    sheer = bool((data.get("look_analysis") or {}).get("sheer_legs")) if isinstance(data.get("look_analysis"), dict) else bool(data.get("look_sheer_legs"))
    sheer_boost = (
        " SOURCE NOTE: lower garment region shows skin through sheer/cutaway "
        "layers — preserve that openness on the person."
        if sheer
        else ""
    )
    evidence: list[str] = []
    for raw in hints:
        tip = " ".join(str(raw).split())
        if not tip:
            continue
        evidence.append(tip[:120])
        if len(evidence) >= 6:
            break
    if data.get("look_normalized"):
        # Match model Try On Person: same Model B sunburst contract, with look-only
        # hints so opaque panels replace street clothes (paid Fitting Room failure mode).
        from app.services.personal_try_on_provider import build_try_on_prompt

        look_hints: list[str] = list(evidence)
        look_hints.append(
            "Image 2 is a studio product photograph of the real garment on a white "
            "retail mannequin — ignore the mannequin; fit only the clothing."
        )
        look_hints.append(
            "Wherever the product shows opaque fabric, fully replace the person's "
            "original clothes in those regions — do not leave street clothes showing "
            "through opaque panels."
        )
        look_hints.append(
            "Attached petals, leaves, or shoulder accents must sit on the body as "
            "part of the garment — never floating detached shapes or stickers."
        )
        if clause.strip():
            look_hints.append(clause.strip()[:120])
        if sheer:
            look_hints.append(
                "Lower garment shows skin through sheer/open layers — preserve that "
                "openness; do not invent opaque underlayers."
            )
        look_hints.append(
            "If the product shows shoes/heels/boots, replace the person's photo "
            "footwear with those shoes — do not keep photo boots."
        )
        look_hints.append(
            "Preserve the person's exact face, hair, pose, proportions, background, "
            "and props (including wings/sculptures) — do not invent a new model."
        )
        return build_try_on_prompt(look_hints)
    prompt = FITTING_ROOM_LOOK_OPENAI_PROMPT + clause + sheer_boost + FITTING_ROOM_LOOK_FOOTWEAR_CLAUSE
    if evidence:
        prompt += " Design evidence: " + "; ".join(evidence) + "."
    return prompt


def _ensure_look_color_lock(
    garment_png: bytes, data: dict[str, Any]
) -> dict[str, Any] | None:
    """Return look_color_lock from job data, sampling the plate when missing."""
    if not _is_fashionrise_look_plate(data):
        return None
    if not isinstance(data.get("look_analysis"), dict):
        analysis = analyze_fashionrise_look_plate(garment_png)
        data["look_analysis"] = analysis
        data["look_sheer_legs"] = bool(analysis.get("sheer_legs"))
        if analysis.get("look_color_lock") and not data.get("look_color_lock"):
            data["look_color_lock"] = analysis["look_color_lock"]
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
    """Return garment bytes for providers; reinforce multi-tone look plates when locked.

    Sheer looks skip reinforce — pulling skirt chrominance over skin-like pixels was
    filling translucent layers opaque before try-on.
    """
    # Already a studio product photo — do not apply the legacy flat illustration recolor.
    if data.get("look_materialized") or data.get("look_productized"):
        return garment_png
    lock = _ensure_look_color_lock(garment_png, data)
    if not lock:
        return garment_png
    analysis = data.get("look_analysis") if isinstance(data.get("look_analysis"), dict) else {}
    sheer = bool(analysis.get("sheer_legs") or data.get("look_sheer_legs"))
    if sheer:
        return garment_png
    return reinforce_look_plate_panel_colors(garment_png, lock, strength=0.36)


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


def _native_product_prep(*, product_png: bytes, source_fingerprint: str):
    """FASHN prep that keeps a studio product photo at its native resolution.

    ``prep_from_approved_product_pieces`` fits every reference into 768×1024, which
    costs a 1024×1536 product a third of its fabric detail before Max ever sees it.
    """
    from app.services.fashn_garment_prep import GarmentPrepResult, PreparedPiece

    with Image.open(io.BytesIO(product_png)) as im:
        im.load()
        rgb = im.convert("RGB")
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    plate = buf.getvalue()
    piece = PreparedPiece(
        category="one-pieces",
        png_bytes=plate,
        bbox=(0, 0, rgb.width, rgb.height),
        opaque_pixels=rgb.width * rgb.height,
        fill_ratio=1.0,
        edge_ratio=0.0,
    )
    return GarmentPrepResult(
        layout="one_piece",
        pieces=(piece,),
        composite_png=plate,
        source_fingerprint=source_fingerprint,
        fashn_calls=1,
        quality_ok=True,
        quality_notes="Materialized look product photo (native resolution).",
    )


def _generate_look_try_on_via_max(
    *,
    person_png: bytes,
    product_png: bytes,
    palette: dict[str, Any] | None,
    data: dict[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    """FASHN Try-On Max (quality · 2k) with a materialized look product photo."""
    prep = _native_product_prep(
        product_png=product_png,
        source_fingerprint=str(data.get("garment_fingerprint") or "fitting-room-look"),
    )
    provider = get_try_on_provider("fashn_max")
    png, meta = provider.generate(
        photo_png=person_png,
        garment_png=product_png,
        prep=prep,
        generation_mode="quality",
        resolution="2k",
        prompt=_look_materialized_max_prompt(palette),
    )
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("provider", "fashn_tryon_max")
    meta["fitting_room_fashn_path"] = "max_quality_2k"
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
    # Social look plates are illustrations with a drawn model. Pipeline:
    # 0a) Owner-only Model B sunburst (gpt-image-2.6-sunburst): person + design,
    #     one images.edit, footwear prompt clause. OFF by default; prefer flag.
    # 0b) Optional flagged direct-edit v2: person + original design (2 images) —
    #    OFF by default; A/B vs materialize→clone. No extra paid chain on success.
    # 1) Materialize → face-free product plate (identity-safe)
    # 2) ChatGPT clone: person×2 + product (dress + design shoes)
    # 3) If materialize fails → clone on raw look; then V2.8 / Max recovery
    look_analysis = data.get("look_analysis") if isinstance(data.get("look_analysis"), dict) else None
    if look_plate and look_analysis is None:
        look_analysis = analyze_fashionrise_look_plate(garment_png)
        data["look_analysis"] = look_analysis
        data["look_sheer_legs"] = bool(look_analysis.get("sheer_legs"))
        if look_analysis.get("look_color_lock") and not data.get("look_color_lock"):
            data["look_color_lock"] = look_analysis["look_color_lock"]
    look_sheer = bool((look_analysis or {}).get("sheer_legs") or data.get("look_sheer_legs"))

    look_color_lock_on = bool(get_settings().fitting_room_look_color_lock_enabled)
    look_palette: dict[str, Any] | None = None
    look_plate_original_png = garment_png
    if look_plate:
        try:
            look_palette = extract_design_palette(garment_png)
        except Exception:  # noqa: BLE001
            logger.warning("Fitting Room job %s look palette extraction failed", job.id, exc_info=True)
        data["look_palette"] = palette_summary(look_palette)
        data["look_palette_clause"] = palette_prompt_clause(look_palette)

    look_materialize_meta: dict[str, Any] | None = None
    look_direct_quality: dict[str, Any] | None = None
    if look_plate and _try_on_provider_override is None:
        settings = get_settings()
        product_png: bytes | None = None

        # 0a) Model B sunburst — default look path when flag (+ optional allowlist).
        # Single fashion-look illustration only. Fail closed on miss (no paid chain).
        # prefer_model_b_sunburst remains accepted for older clients but is not required.
        job_user = db.get(User, job.user_id) if job.user_id is not None else None
        model_b_eligible = (
            job_user is not None
            and look_model_b_sunburst_available_for_user(job_user)
            and not _is_multi_piece_outfit(data)
            and not bool(settings.fitting_room_look_identity_lock_enabled)
        )
        if model_b_eligible:
            model_b = _try_model_b_sunburst_look_fit(
                job_id=job.id,
                person_png=person_png,
                look_png=look_plate_original_png,
                data=data,
            )
            if model_b is not None:
                png, meta, used_provider, look_direct_quality = model_b
                logger.info(
                    "Fitting Room job %s Social look via Model B sunburst "
                    "model=%s path=%s",
                    job.id,
                    (meta or {}).get("model") if isinstance(meta, dict) else None,
                    MODEL_B_SUNBURST_PATH,
                )
            else:
                slim = dict(data)
                slim.pop("person_image_base64", None)
                slim.pop("garment_image_base64", None)
                slim["images_stripped"] = True
                job.input_data = slim
                result = _fail(
                    "Fitting Room Model B preview could not finish. "
                    "No automatic retry — try again later.",
                    code="MODEL_B_SUNBURST_FAILED",
                )
                result["fitting_room_look_path"] = MODEL_B_SUNBURST_PATH
                result["model"] = MODEL_B_SUNBURST_MODEL
                result["openai_calls"] = 1
                job.result_data = result
                return result

        # 0b) Flagged ChatGPT-documented direct edit (person + original artwork).
        # On success: one images.edit only. Identity reject → fail closed (no more paid).
        # Technical miss → fall through unchanged.
        if png is None and bool(settings.fitting_room_look_direct_edit_v2_enabled):
            try:
                direct_v2 = _try_direct_edit_v2_look_fit(
                    job_id=job.id,
                    person_png=person_png,
                    look_png=look_plate_original_png,
                    data=data,
                    hints=hints,
                    look_analysis=look_analysis,
                )
            except LookIdentityRejected as exc:
                slim = dict(data)
                slim.pop("person_image_base64", None)
                slim.pop("garment_image_base64", None)
                slim["images_stripped"] = True
                job.input_data = slim
                reject_meta = exc.meta if isinstance(exc.meta, dict) else {}
                result = _fail(
                    "Fitting Room could not keep your face identical in this preview. "
                    "No Stars were charged. Try again.",
                    code=LOOK_IDENTITY_REJECTED,
                )
                result["fitting_room_look_path"] = "chatgpt_direct_edit_v2_identity_rejected"
                result["look_identity_gate"] = reject_meta.get("look_identity_gate")
                result["look_identity_lock"] = reject_meta.get("look_identity_lock")
                result["model"] = reject_meta.get("model")
                result["openai_calls"] = reject_meta.get("openai_calls", 1)
                job.result_data = result
                return result
            if direct_v2 is not None:
                png, meta, used_provider, look_direct_quality = direct_v2
                data["look_direct_openai"] = True
                data["look_chatgpt_clone"] = True
                data["look_direct_edit_v2"] = True
                if isinstance(meta, dict) and meta.get("identity_lock"):
                    data["look_identity_lock"] = True
                data["look_materialized"] = False
                data["look_normalized"] = False
                data.pop("look_productized", None)
                logger.info(
                    "Fitting Room job %s Social look via direct-edit-v2 images.edit "
                    "model=%s path=%s detected_by=%s",
                    job.id,
                    (meta or {}).get("model") if isinstance(meta, dict) else None,
                    (meta or {}).get("fitting_room_look_path")
                    if isinstance(meta, dict)
                    else "chatgpt_direct_edit_v2",
                    data.get("look_detected_by"),
                )
            else:
                logger.info(
                    "Fitting Room job %s direct-edit-v2 missed — falling through to "
                    "materialize/chatgpt-clone production path",
                    job.id,
                )

        # 1) Materialize first when enabled — removes the drawn model's face so
        # ChatGPT-clone cannot identity-swap toward the illustration.
        if png is None and bool(settings.fitting_room_look_materialize_enabled):
            try:
                import app.services.look_garment_normalize as look_materialize

                product_png, look_materialize_meta = look_materialize.materialize_fashionrise_look(
                    look_png=look_plate_original_png,
                    palette=look_palette,
                    color_lock=look_color_lock_on,
                )
                data["look_materialized"] = True
                data["look_normalized"] = True
                data["look_productized"] = True
                garment_png = product_png
                logger.info(
                    "Fitting Room job %s Social look materialized before ChatGPT-clone "
                    "(calls=%s lock=%s detected_by=%s)",
                    job.id,
                    (look_materialize_meta or {}).get("openai_calls"),
                    ((look_materialize_meta or {}).get("color_lock") or {}).get("applied"),
                    data.get("look_detected_by"),
                )
            except Exception:  # noqa: BLE001
                product_png = None
                look_materialize_meta = None
                data["look_materialized"] = False
                data["look_normalized"] = False
                data.pop("look_productized", None)
                logger.info(
                    "Fitting Room job %s look materialize failed — ChatGPT-clone on raw look",
                    job.id,
                    exc_info=True,
                )

        if png is None:
            clone_ref = product_png or look_plate_original_png
            path_label = (
                "chatgpt_clone_product" if product_png is not None else "chatgpt_clone_direct"
            )
            direct = _try_chatgpt_style_look_fit(
                job_id=job.id,
                person_png=person_png,
                look_png=clone_ref,
                data=data,
                hints=hints,
                look_analysis=look_analysis,
                look_palette=look_palette,
                look_color_lock_on=look_color_lock_on,
                path_label=path_label,
            )
            if direct is not None:
                png, meta, used_provider, look_direct_quality = direct
                if look_materialize_meta is not None and isinstance(meta, dict):
                    meta = dict(meta)
                    meta["look_materialize"] = look_materialize_meta
                data["look_direct_openai"] = True
                data["look_chatgpt_clone"] = True
                if product_png is None:
                    data["look_materialized"] = False
                    data["look_normalized"] = False
                    data.pop("look_productized", None)
                logger.info(
                    "Fitting Room job %s Social look via ChatGPT-clone images.edit "
                    "model=%s path=%s detected_by=%s",
                    job.id,
                    (meta or {}).get("model") if isinstance(meta, dict) else None,
                    path_label,
                    data.get("look_detected_by"),
                )
            elif product_png is not None:
                # Clone failed after materialize — fall through to V2.8 on product plate.
                meta = {
                    "fitting_room_look_path": "materialize_then_openai",
                    "look_analysis": look_analysis,
                    "look_sheer_legs": look_sheer,
                    "look_materialize": look_materialize_meta,
                    "look_chatgpt_clone_attempted": True,
                }
                png = None
                logger.info(
                    "Fitting Room job %s ChatGPT-clone failed after materialize — OpenAI V2.8 next",
                    job.id,
                )
            else:
                # No product + clone failed — try materialize for V2.8 path (legacy).
                try:
                    import app.services.look_garment_normalize as look_materialize

                    garment_png, look_materialize_meta = look_materialize.materialize_fashionrise_look(
                        look_png=look_plate_original_png,
                        palette=look_palette,
                        color_lock=look_color_lock_on,
                    )
                    data["look_materialized"] = True
                    data["look_normalized"] = True
                    data["look_productized"] = True
                    meta = {
                        "fitting_room_look_path": "materialize_then_openai",
                        "look_analysis": look_analysis,
                        "look_sheer_legs": look_sheer,
                        "look_materialize": look_materialize_meta,
                        "look_direct_openai_attempted": True,
                    }
                    png = None
                    logger.info(
                        "Fitting Room job %s Social look materialized after clone fail — "
                        "OpenAI V2.8 next (calls=%s lock=%s detected_by=%s)",
                        job.id,
                        look_materialize_meta.get("openai_calls"),
                        (look_materialize_meta.get("color_lock") or {}).get("applied"),
                        data.get("look_detected_by"),
                    )
                except Exception:  # noqa: BLE001
                    logger.info(
                        "Fitting Room job %s look materialize failed — retrying raw-look direct fit",
                        job.id,
                        exc_info=True,
                    )
                    data["look_materialized"] = False
                    data["look_normalized"] = False
                    data.pop("look_productized", None)
                    # Force-accept a second direct attempt even if soft-check is noisy.
                    try:
                        provider = get_try_on_provider("openai")
                        prompt = _chatgpt_style_look_prompt(data, hints)
                        png, meta = provider.generate(
                            photo_png=person_png,
                            garment_png=look_plate_original_png,
                            design_hints=hints,
                            prompt_override=prompt,
                        )
                        if not isinstance(meta, dict):
                            meta = {}
                        meta["fitting_room_look_path"] = "direct_openai_after_materialize_fail"
                        meta["look_analysis"] = look_analysis
                        used_provider = "openai"
                        if not png:
                            raise ProviderNotAvailableError("empty direct look result")
                    except Exception:  # noqa: BLE001
                        slim = dict(data)
                        slim.pop("person_image_base64", None)
                        slim.pop("garment_image_base64", None)
                        slim["images_stripped"] = True
                        job.input_data = slim
                        return _fail(
                            "Fitting Room could not finish this look preview. "
                            "Try again in a moment. No Stars were charged.",
                            code="LOOK_MATERIALIZE_FAILED",
                        )

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
            if data.get("look_normalized"):
                garment_for_openai = garment_png
            else:
                garment_for_openai = _garment_png_for_look_plate(garment_png, data)
            openai_prompt = _fitting_room_openai_prompt(data, hints)
            generate_kwargs: dict[str, Any] = {
                "photo_png": person_png,
                "garment_png": garment_for_openai,
                "design_hints": hints,
            }
            if openai_prompt:
                generate_kwargs["prompt_override"] = openai_prompt
            look_path_pref = (
                meta.get("fitting_room_look_path") if isinstance(meta, dict) else None
            )
            look_analysis_pref = (
                meta.get("look_analysis") if isinstance(meta, dict) else None
            )
            look_materialize_pref = (
                meta.get("look_materialize") if isinstance(meta, dict) else None
            )
            look_quality_max_rejected_pref = (
                meta.get("look_quality_max_rejected") if isinstance(meta, dict) else None
            )
            png, meta = provider.generate(**generate_kwargs)
            if not isinstance(meta, dict):
                meta = {}
            if look_path_pref:
                meta.setdefault("fitting_room_look_path", look_path_pref)
            if look_analysis_pref is not None:
                meta.setdefault("look_analysis", look_analysis_pref)
            if look_materialize_pref is not None:
                meta.setdefault("look_materialize", look_materialize_pref)
            if look_quality_max_rejected_pref is not None:
                meta.setdefault(
                    "look_quality_max_rejected", look_quality_max_rejected_pref
                )
            used_provider = "openai"
        except ProviderNotAvailableError as exc:
            openai_operator_detail = str(exc)[:400]
            if _openai_exc_is_moderation(exc) and _fashn_fallback_armed():
                if look_plate and not data.get("look_materialized"):
                    # Never Max (or any try-on) a raw Fashion Magic illustration —
                    # that path pastes painted texture onto the person photo.
                    return _fail(
                        "Fitting Room could not finish this look preview. "
                        "No Stars were charged.",
                        code="LOOK_MATERIALIZE_REQUIRED",
                    )
                logger.info(
                    "Fitting Room job %s OpenAI moderation — falling back to FASHN Max",
                    job.id,
                )
                try:
                    if look_plate and data.get("look_materialized"):
                        look_path_pref = (
                            meta.get("fitting_room_look_path")
                            if isinstance(meta, dict)
                            else None
                        )
                        look_materialize_pref = (
                            meta.get("look_materialize")
                            if isinstance(meta, dict)
                            else None
                        )
                        png, meta = _generate_look_try_on_via_max(
                            person_png=person_png,
                            product_png=garment_png,
                            palette=look_palette,
                            data=data,
                        )
                        if not isinstance(meta, dict):
                            meta = {}
                        meta["fitting_room_look_path"] = (
                            look_path_pref or "materialize_then_max_after_openai_moderation"
                        )
                        if look_materialize_pref is not None:
                            meta.setdefault("look_materialize", look_materialize_pref)
                        meta.setdefault("look_analysis", look_analysis)
                        meta["look_sheer_legs"] = look_sheer
                    else:
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

    look_chatgpt_clone = bool(
        data.get("look_chatgpt_clone")
        or data.get("look_direct_edit_v2")
        or data.get("look_model_b_sunburst")
        or (
            isinstance(meta, dict)
            and (
                meta.get("chatgpt_clone")
                or meta.get("direct_edit_v2")
                or meta.get("model_b_sunburst")
                or meta.get("fitting_room_look_path")
                in {
                    "chatgpt_clone_direct",
                    "chatgpt_clone_product",
                    "chatgpt_direct_edit_v2",
                    "chatgpt_direct_edit_v2_identity",
                    MODEL_B_SUNBURST_PATH,
                }
            )
        )
    )

    look_final_lock: dict[str, Any] | None = None
    if look_plate and look_palette and look_color_lock_on and not look_chatgpt_clone:
        # Providers drift hue/depth even from a correct product photo; pull the garment
        # (only the pixels the try-on changed) back to the measured design palette.
        # Skip on ChatGPT-clone — post color-lock was crushing bright blues to black.
        try:
            png, look_final_lock = lock_result_to_palette(png, person_png, look_palette)
        except Exception:  # noqa: BLE001
            logger.warning("Fitting Room job %s final color lock failed", job.id, exc_info=True)
            look_final_lock = {"stage": "result", "applied": False, "reason": "error"}
    elif look_chatgpt_clone:
        look_final_lock = {
            "stage": "result",
            "applied": False,
            "reason": (
                "skipped_model_b_sunburst"
                if data.get("look_model_b_sunburst")
                else "skipped_chatgpt_clone"
            ),
        }

    look_quality: dict[str, Any] | None = look_direct_quality
    if look_plate and png and not look_chatgpt_clone:
        look_quality = soft_check_look_tryon_result(
            png, look_analysis=look_analysis
        )
        if _look_result_needs_recovery(look_quality):
            # Soft texture or bright→black color crush — escalate, never cancel.
            logger.info(
                "Fitting Room job %s look soft-check needs recovery warnings=%s path=%s",
                job.id,
                look_quality.get("warnings"),
                (meta or {}).get("fitting_room_look_path") if isinstance(meta, dict) else None,
            )
            # Prefer materialized product when available; else the original look plate.
            recovery_garment = (
                garment_png
                if data.get("look_materialized")
                else look_plate_original_png
            )
            png, meta, used_provider, look_quality = _recover_illustrated_look_tryon(
                job_id=job.id,
                person_png=person_png,
                product_png=recovery_garment,
                data=data,
                hints=hints,
                look_analysis=look_analysis,
                look_palette=look_palette,
                look_color_lock_on=look_color_lock_on,
                initial_png=png,
                initial_meta=meta if isinstance(meta, dict) else {},
                initial_quality=look_quality,
                initial_provider=used_provider,
            )
            if not png:
                return _fail(
                    "Fitting Room could not finish this look preview. No Stars were charged.",
                    code="LOOK_RECOVERY_EMPTY",
                )
    elif look_chatgpt_clone and look_quality is None and png:
        look_quality = soft_check_look_tryon_result(png, look_analysis=look_analysis)

    key = f"ai/{job.id.hex}_fitting_{uuid.uuid4().hex[:10]}.png"
    url = LocalStorageBackend().save_file(key=key, data=io.BytesIO(png), content_type="image/png")

    cost = int(data.get("stars_cost") or fitting_room_cost())
    result = {
        "status": "completed",
        "summary": "Fitting Room preview ready (concept preview — not a fit guarantee).",
        "bullets": [
            "Person photo and clothing image were not overwritten.",
            FITTING_ROOM_NOTICE,
            f"Flat Stars charge on success: {cost}.",
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
        # Best-effort FASHN financial ledger (never fail Fitting Room completion).
        try:
            from app.services.ai_cost_accounting import record_fashn_prediction

            details = meta.get("prediction_credit_details")
            if isinstance(details, list) and details:
                for d in details:
                    if not isinstance(d, dict):
                        continue
                    pid = str(d.get("prediction_id") or "").strip()
                    if not pid:
                        continue
                    hdr_present = bool(d.get("credits_header_present"))
                    hdr_credits = d.get("credits_from_header")
                    record_fashn_prediction(
                        db,
                        prediction_id=pid,
                        feature="fitting_room",
                        final_status="completed",
                        user_id=job.user_id,
                        job_id=job.id,
                        model=str(meta.get("model") or "")[:128] or None,
                        generation_mode=str(meta.get("generation_mode") or "")[:64] or None,
                        resolution=str(meta.get("resolution") or "")[:64] or None,
                        output_count=1,
                        credits_consumed=int(hdr_credits)
                        if hdr_present and hdr_credits is not None
                        else None,
                        credits_header_present=hdr_present,
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Fitting Room FASHN cost ledger write failed (non-fatal)")
    if isinstance(meta, dict):
        if meta.get("fitting_room_look_path"):
            result["fitting_room_look_path"] = meta.get("fitting_room_look_path")
        # Non-sensitive A/B provenance (model + image roles). Never secrets.
        for k in (
            "model",
            "quality",
            "size",
            "direct_edit_v2",
            "model_b_sunburst",
            "identity_lock",
            "prompt_version",
            "image_order",
            "identity_image_count",
            "design_image_count",
            "look_color_lock_skipped",
            "openai_calls",
            "look_identity_lock",
            "look_identity_gate",
            "preprocessing",
            "postprocessing",
            "materialize",
            "color_lock",
            "mask",
            "face_patch",
            "paid_retries",
        ):
            if meta.get(k) is not None:
                result[k] = meta.get(k)
        if meta.get("look_materialize"):
            materialize = meta.get("look_materialize") or {}
            result["look_materialize"] = {
                k: materialize.get(k)
                for k in (
                    "provider",
                    "prompt_kind",
                    "model",
                    "quality",
                    "openai_calls",
                    "usage",
                    "check",
                    "color_lock",
                )
            }
        if meta.get("look_quality_max_rejected") is not None:
            result["look_quality_max_rejected"] = meta.get("look_quality_max_rejected")
        if meta.get("look_quality_recovery") is not None:
            result["look_quality_recovery"] = meta.get("look_quality_recovery")
        if meta.get("look_quality_kept_despite_soft_check"):
            result["look_quality_kept_despite_soft_check"] = True
        if meta.get("look_analysis") is not None:
            result["look_analysis"] = meta.get("look_analysis")
        elif look_analysis is not None:
            result["look_analysis"] = look_analysis
    elif look_analysis is not None:
        result["look_analysis"] = look_analysis
    if look_plate:
        result["look_detected_by"] = data.get("look_detected_by")
        result["look_palette"] = palette_summary(look_palette)
        if look_final_lock is not None:
            result["look_color_lock_final"] = look_final_lock
    if look_quality is not None:
        result["look_quality"] = look_quality
        if not look_quality.get("ok"):
            logger.info(
                "Fitting Room job %s look quality warnings=%s path=%s",
                job.id,
                look_quality.get("warnings"),
                result.get("fitting_room_look_path"),
            )
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
