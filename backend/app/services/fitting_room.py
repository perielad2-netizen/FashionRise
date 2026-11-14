"""AI Fitting Room — person photo + clothing image → try-on preview (F1–F3).

Reuses the OpenAI Try On Person images.edit adapter. Fail-closed behind
``fitting_room_enabled`` / ``fitting_room_live_http``. No wardrobe, stylist,
shopping, or new billing. Charges existing Magic Stars only after success.
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
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.user import User
from app.services.ai_stars import assert_can_spend_magic
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


def fitting_room_enabled() -> bool:
    return bool(get_settings().fitting_room_enabled)


def fitting_room_live_armed() -> bool:
    settings = get_settings()
    return bool(settings.fitting_room_enabled and settings.fitting_room_live_http)


def preflight_public(*, user: User) -> dict[str, Any]:
    """No billable work — UI gate + consent copy + categories."""
    _ = user
    settings = get_settings()
    enabled = fitting_room_enabled()
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
        # Accept JPEG by re-encoding via provider path — store as-is; provider normalizes.
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


def enqueue_fitting_room_try_on(
    db: Session,
    user: User,
    *,
    person_image_base64: str,
    garment_image_base64: str,
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
    garment_png = _decode_png(garment_image_base64, field="garment_image_base64")
    category = _normalize_category(garment_category)

    # Stars check before enqueue — debit only after success (worker).
    assert_can_spend_magic(db, user)

    person_fp = hashlib.sha256(person_png).hexdigest()
    garment_fp = hashlib.sha256(garment_png).hexdigest()
    person_b64 = base64.b64encode(person_png).decode("ascii")
    garment_b64 = base64.b64encode(garment_png).decode("ascii")

    hints: list[str] = []
    if category != "auto":
        hints.append(f"garment_category:{category}")

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


def complete_fitting_room_job(db: Session, job: AIJob) -> dict[str, Any]:
    """Worker entry — OpenAI try-on; never debit Stars here (ai_worker helper does)."""
    data = job.input_data if isinstance(job.input_data, dict) else {}

    def _fail(msg: str, *, code: str = "FITTING_ROOM_FAILED") -> dict[str, Any]:
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

    try:
        from app.services.personal_try_on_provider import _try_on_provider_override

        # Live arming: Fitting Room flag OR injected test provider.
        # OpenAI adapter also requires MY_CROQUIS_AI_LIVE_HTTP (shared images.edit arm).
        if _try_on_provider_override is None and not fitting_room_live_armed():
            return _fail(
                "Fitting Room live AI is not armed on this server.",
                code="LIVE_HTTP_OFF",
            )
        provider = get_try_on_provider("openai")
        png, meta = provider.generate(
            photo_png=person_png, garment_png=garment_png, design_hints=hints
        )
    except ProviderNotAvailableError as exc:
        return _fail(str(exc)[:240], code="PROVIDER_UNAVAILABLE")
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

    result = {
        "status": "completed",
        "summary": "Fitting Room preview ready (concept preview — not a fit guarantee).",
        "bullets": [
            "Person photo and clothing image were not overwritten.",
            FITTING_ROOM_NOTICE,
            f"Prompt {TRY_ON_PROMPT_VERSION}",
        ],
        "image_url": url,
        "mode": FITTING_ROOM_MODE,
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "provider": "openai",
        "person_fingerprint": data.get("person_fingerprint"),
        "garment_fingerprint": data.get("garment_fingerprint"),
        "garment_category": data.get("garment_category"),
        "consent_version": TRY_ON_CONSENT_VERSION,
    }
    job.status = "completed"
    job.error_message = None
    job.result_data = result
    # Strip bulky inputs after success so the row stays lean.
    slim = dict(data)
    slim.pop("person_image_base64", None)
    slim.pop("garment_image_base64", None)
    slim["images_stripped"] = True
    job.input_data = slim
    return result
