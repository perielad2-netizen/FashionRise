"""Personal Try On Person — enqueue + worker completion.

Freeze garment artwork + croquis/source binding at enqueue. Resolve the original
photograph on the server from the owner's accepted croquis version. Spend uses
``PersonalCroquisSpendReservation`` under the same operator ceilings as croquis
generate (idempotency keys prefixed ``try_on:``).
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import VERSION_STATUS_ACCEPTED
from app.models.personal_croquis_spend import (
    CROQUIS_SPEND_GLOBAL_LOCK_KEY,
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import KIND_CROQUIS_SOURCE
from app.models.user import User
from app.models.user_consent_event import PURPOSE_TRY_ON_PERSON, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_generate import (
    _count_generations_today,
    _lock_spend_tx,
    _sum_billable_cents,
    resolve_max_exposure_cents,
)
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
)
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_JOB_TYPE,
    TRY_ON_NOTICE_TEXT,
    TRY_ON_PROMPT_VERSION,
    estimate_try_on_cost_cents,
    get_try_on_provider,
    try_on_notice_text_hash,
)
from app.storage.local import LocalStorageBackend

_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$", re.DOTALL | re.IGNORECASE)
_BILLABLE = (RESERVATION_OPEN, RESERVATION_SETTLED, RESERVATION_RECONCILIATION)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _require_ai_gate() -> None:
    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis AI is not enabled (required for Try On Person).",
        )


def _decode_garment_png(data_url: str) -> bytes:
    raw = (data_url or "").strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is required.")
    m = _DATA_URL_RE.match(raw)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Garment artwork must be a PNG/JPEG/WebP data URL.",
        )
    try:
        blob = base64.b64decode(m.group(2), validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork base64 is invalid."
        ) from exc
    if len(blob) < 32:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is empty.")
    max_bytes = int(get_settings().max_upload_size_mb or 8) * 1024 * 1024
    if len(blob) > max_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is too large.")
    # Fail closed if not a real PNG with alpha-capable content for try-on identity.
    from PIL import Image

    try:
        with Image.open(io.BytesIO(blob)) as img:
            img.load()
            if img.width < 8 or img.height < 8:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork is too small."
                )
            # Convert to PNG bytes for provider.
            out = io.BytesIO()
            img.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Garment artwork could not be decoded."
        ) from exc


def _record_try_on_consent(db: Session, user: User) -> UserConsentEvent:
    """Record one-action try-on consent for this enqueue (immutable event)."""
    attestation = pcs._latest_adults_attestation(db, user)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only beta attestation is required before Try On Person.",
        )
    row = UserConsentEvent(
        id=uuid.uuid4(),
        owner_id=user.id,
        purpose=PURPOSE_TRY_ON_PERSON,
        consent_version=TRY_ON_CONSENT_VERSION,
        adults_attested=True,
        text_hash=try_on_notice_text_hash(),
    )
    db.add(row)
    db.flush()
    return row


def _find_try_on_by_idempotency(db: Session, user_id: uuid.UUID, key: str) -> AIJob | None:
    return db.scalar(
        select(AIJob)
        .where(
            AIJob.user_id == user_id,
            AIJob.job_type == TRY_ON_JOB_TYPE,
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .order_by(AIJob.created_at.desc())
        .limit(1)
    )


def enqueue_personal_try_on(
    db: Session,
    user: User,
    *,
    croquis_id: uuid.UUID,
    croquis_version: int,
    garment_image_base64: str,
    idempotency_key: str,
    design_id: uuid.UUID | None,
    source_revision: int,
    content_fingerprint: str,
    consent_acknowledged: bool,
    consent_version: str,
) -> AIJob:
    """Validate, reserve spend, freeze garment, enqueue ``personal_try_on`` job."""
    _require_ai_gate()
    settings = get_settings()

    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="idempotency_key is required.")
    if not key.startswith("try_on:"):
        # Namespace spend unique constraint away from croquis generate keys.
        key = f"try_on:{key}"

    if not consent_acknowledged:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Try On Person requires explicit consent acknowledgment.",
        )
    if consent_version != TRY_ON_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Try On Person consent version is outdated.",
        )
    if try_on_notice_text_hash() != hashlib.sha256(TRY_ON_NOTICE_TEXT.encode("utf-8")).hexdigest():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Notice hash mismatch.")

    fp = (content_fingerprint or "").strip()
    if not fp or len(fp) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="content_fingerprint is required."
        )
    if not isinstance(source_revision, int) or source_revision < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="source_revision must be a positive integer."
        )

    # Idempotent replay before spend lock when possible.
    existing = _find_try_on_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing

    croquis = pcs.get_owned_croquis(db, user, croquis_id)
    if croquis.source_asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This croquis has no retained original photo for Try On Person.",
        )
    version = pcs.get_exact_version(db, user, croquis_id, croquis_version)
    if version.status != VERSION_STATUS_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Try On Person requires an accepted personal croquis version.",
        )

    source = pcs.get_owned_media_asset(db, user, croquis.source_asset_id, allow_erased_meta=False)
    if source.kind != KIND_CROQUIS_SOURCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original photograph binding is invalid.",
        )
    if source.bytes_purged_at is not None or source.erase_requested_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Original photograph is no longer available for Try On Person.",
        )
    # Prove bytes still exist before billing.
    pcs.resolve_croquis_asset_file(db, user, source.id)

    garment_png = _decode_garment_png(garment_image_base64)
    garment_fp = hashlib.sha256(garment_png).hexdigest()

    max_exposure = resolve_max_exposure_cents()
    estimate = estimate_try_on_cost_cents()
    ceiling_cents = int(round(float(settings.my_croquis_ai_spend_ceiling_usd or 0) * 100))
    day_cap = int(round(float(settings.my_croquis_ai_max_usd_per_user_day or 0) * 100))
    max_gens = int(settings.my_croquis_ai_max_generations_per_user_day or 0)

    _lock_spend_tx(db, user.id)

    # Re-check idempotency under lock.
    existing = _find_try_on_by_idempotency(db, user.id, key)
    if existing is not None:
        return existing
    existing_res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.owner_id == user.id,
            PersonalCroquisSpendReservation.idempotency_key == key,
        )
        .one_or_none()
    )
    if existing_res is not None:
        if existing_res.status == RESERVATION_RECONCILIATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Previous Try On Person needs reconciliation — no automatic paid retry.",
            )
        # Reservation without job — refuse silent re-bill.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Try On Person idempotency key already used — recover the existing job or use a new key.",
        )

    if max_gens > 0 and _count_generations_today(db, user) >= max_gens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis / Try On Person generation limit reached.",
        )
    operator_total = _sum_billable_cents(db, owner_id=None, since=None)
    if ceiling_cents > 0 and operator_total + max_exposure > ceiling_cents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator AI spend ceiling would be exceeded.",
        )
    if day_cap > 0:
        day_ago = _utcnow() - timedelta(days=1)
        user_day = _sum_billable_cents(db, owner_id=user.id, since=day_ago)
        if user_day + max_exposure > day_cap:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily AI spend limit would be exceeded.",
            )

    consent = _record_try_on_consent(db, user)
    reservation = PersonalCroquisSpendReservation(
        id=uuid.uuid4(),
        owner_id=user.id,
        croquis_id=croquis.id,
        source_asset_id=source.id,
        version_id=version.id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
        max_exposure_cents=max_exposure,
        provider_called=False,
    )
    db.add(reservation)

    # Store garment as base64 in input (same pattern as sketch_polish) — immutable freeze.
    garment_b64 = base64.b64encode(garment_png).decode("ascii")
    input_data: dict[str, Any] = {
        "idempotency_key": key,
        "croquis_id": str(croquis.id),
        "croquis_version": int(version.version),
        "source_asset_id": str(source.id),
        "version_id": str(version.id),
        "garment_image_base64": f"data:image/png;base64,{garment_b64}",
        "garment_fingerprint": garment_fp,
        "content_fingerprint": fp,
        "source_revision": int(source_revision),
        "consent_id": str(consent.id),
        "consent_version": TRY_ON_CONSENT_VERSION,
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "reservation_id": str(reservation.id),
        "mode": "try_on_person",
    }

    job = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        design_id=design_id,
        job_type=TRY_ON_JOB_TYPE,
        status="queued",
        input_data=input_data,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Lost race on spend unique — return existing job if present.
        existing = _find_try_on_by_idempotency(db, user.id, key)
        if existing is not None:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Try On Person could not be enqueued (idempotency conflict).",
        ) from exc
    db.refresh(job)
    return job


def complete_try_on_job(db: Session, job: AIJob) -> dict[str, Any]:
    """Worker entry: call provider once, store private look image, settle spend."""
    if job.job_type != TRY_ON_JOB_TYPE:
        raise ValueError(f"unexpected job_type {job.job_type!r}")
    data = job.input_data if isinstance(job.input_data, dict) else {}
    reservation_id = data.get("reservation_id")
    reservation: PersonalCroquisSpendReservation | None = None
    if reservation_id:
        try:
            reservation = db.get(PersonalCroquisSpendReservation, uuid.UUID(str(reservation_id)))
        except Exception:  # noqa: BLE001
            reservation = None

    def _fail(msg: str, *, settle_release: bool = True) -> dict[str, Any]:
        job.status = "failed"
        job.error_message = msg[:240]
        if reservation is not None and reservation.status == RESERVATION_OPEN:
            if settle_release:
                reservation.status = RESERVATION_RELEASED
                reservation.error_detail = msg[:500]
        return {"status": "failed", "summary": msg, "mode": "try_on_person"}

    try:
        user = db.get(User, job.user_id)
        if user is None:
            return _fail("Owner account missing for Try On Person.")
        croquis_id = uuid.UUID(str(data["croquis_id"]))
        source_asset_id = uuid.UUID(str(data["source_asset_id"]))
        croquis_version = int(data["croquis_version"])
        # Re-validate ownership + source still present (no wrong-photo attribution).
        croquis = pcs.get_owned_croquis(db, user, croquis_id)
        if croquis.source_asset_id != source_asset_id:
            return _fail("Original photograph binding changed — refusing Try On Person.")
        version = pcs.get_exact_version(db, user, croquis_id, croquis_version)
        if version.status != VERSION_STATUS_ACCEPTED:
            return _fail("Croquis version is no longer accepted.")
        photo_path = pcs.resolve_croquis_asset_file(db, user, source_asset_id)
        photo_png = photo_path.read_bytes()
        garment_png = _decode_garment_png(str(data.get("garment_image_base64") or ""))
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "Try On Person validation failed."
        return _fail(detail)
    except Exception:  # noqa: BLE001
        return _fail("Try On Person could not load the frozen photo or garment.")

    try:
        provider = get_try_on_provider()
        if reservation is not None:
            reservation.provider_called = True
            db.flush()
        png, meta = provider.generate(photo_png=photo_png, garment_png=garment_png)
    except ProviderNotAvailableError as exc:
        # Definitive pre-submit or HTTP 4xx refusal — release reservation at $0.
        return _fail(str(exc)[:240], settle_release=True)
    except ProviderOutcomeUnknownError as exc:
        # Ambiguous post-dispatch — hold reservation in reconciliation, no auto-retry.
        if reservation is not None and reservation.status == RESERVATION_OPEN:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
        job.status = "failed"
        job.error_message = (
            "Try On Person outcome is unknown after the provider call. "
            "No automatic retry — contact support if you were charged."
        )[:240]
        return {
            "status": "failed",
            "summary": job.error_message,
            "mode": "try_on_person",
            "reconciliation_required": True,
        }

    key = f"ai/{job.id.hex}_tryon_{uuid.uuid4().hex[:10]}.png"
    storage = LocalStorageBackend()
    url = storage.save_file(key=key, data=io.BytesIO(png), content_type="image/png")

    actual = meta.get("actual_cost_cents")
    if reservation is not None and reservation.status == RESERVATION_OPEN:
        reservation.status = RESERVATION_SETTLED
        reservation.actual_cost_cents = int(actual) if isinstance(actual, int) else reservation.estimate_cents
        reservation.provider_called = True

    result = {
        "status": "completed",
        "summary": "Try On Person preview ready (concept preview — not a fit guarantee).",
        "bullets": [
            "Original photo and sketch were not overwritten.",
            "Face, pose and background preserved where the model allowed.",
            f"Prompt {TRY_ON_PROMPT_VERSION}",
        ],
        "image_url": url,
        "mode": "try_on_person",
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "croquis_id": str(data.get("croquis_id")),
        "croquis_version": data.get("croquis_version"),
        "source_asset_id": str(data.get("source_asset_id")),
        "garment_fingerprint": data.get("garment_fingerprint"),
        "content_fingerprint": data.get("content_fingerprint"),
        "source_revision": data.get("source_revision"),
        "cost_cents": reservation.actual_cost_cents if reservation else actual,
    }
    job.status = "completed"
    job.error_message = None
    job.result_data = result
    return result


def try_on_preflight_public() -> dict[str, Any]:
    """Safe public preflight for FE (no image bytes)."""
    settings = get_settings()
    return {
        "enabled": bool(settings.my_croquis_ai_enabled and settings.my_croquis_ai_spend_ceiling_usd > 0),
        "live_http": bool(settings.my_croquis_ai_live_http),
        "consent_version": TRY_ON_CONSENT_VERSION,
        "notice_text": TRY_ON_NOTICE_TEXT,
        "notice_hash": try_on_notice_text_hash(),
        "prompt_version": TRY_ON_PROMPT_VERSION,
        "estimate_cents": estimate_try_on_cost_cents(),
        "max_exposure_cents": int(settings.my_croquis_ai_max_exposure_cents or 0),
    }
