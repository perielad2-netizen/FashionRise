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
from PIL import Image
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
    return decoded


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
    elif garment_image_base64:
        piece_bytes.append(_decode_png(garment_image_base64, field="garment_image_base64"))
        piece_cats.append(_normalize_category(garment_category))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide garment_image_base64 or garment_pieces.",
        )

    category = piece_cats[0] if len(piece_cats) == 1 else "auto"
    combo_warning = combo_warning_for_categories(piece_cats)

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
    category, prep = _fitting_room_garment_prep(garment_png=garment_png, data=data)

    if _fashn_max_fallback_armed():
        try:
            max_provider = get_try_on_provider("fashn_max")
            png, meta = max_provider.generate(
                photo_png=person_png,
                garment_png=garment_png,
                prep=prep,
                generation_mode="quality",
                resolution="2k",
                prompt=FITTING_ROOM_MAX_PROMPT,
            )
            if not isinstance(meta, dict):
                meta = {}
            meta.setdefault("provider", "fashn_tryon_max")
            meta["fitting_room_fashn_path"] = "max_quality_2k"
            return png, meta
        except ProviderNotAvailableError:
            logger.info("Fitting Room Max unavailable — trying FASHN v1.6")
        except ProviderOutcomeUnknownError:
            raise

    provider = get_try_on_provider("fashn")
    png, meta = provider.generate(
        photo_png=person_png,
        garment_png=garment_png,
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

    # Swimwear / lingerie / dresses: prefer Try-On Max quality first (skip OpenAI
    # moderation landmines and get the better garment fidelity model).
    prefer_max_first = (
        _fashn_max_fallback_armed()
        and _fashn_category_for_fitting_room(data) == "one-pieces"
        and _try_on_provider_override is None
    )
    if prefer_max_first:
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
            png, meta = provider.generate(
                photo_png=person_png, garment_png=garment_png, design_hints=hints
            )
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
