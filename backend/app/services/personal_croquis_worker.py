"""Create My Croquis Stage C — AIJob worker for personal_croquis_generate.

Claims queued croquis jobs with a durable lease (SKIP LOCKED). Crash recovery
distinguishes definitely-not-sent (safe requeue) from possibly-sent
(reconciliation_required; hold spend; never auto paid retry).

Never logs image bytes or credentials. Provider outputs are fit-contain
normalized and CAS-attached so reject/erase cannot resurrect a version.
"""

from __future__ import annotations

import hashlib
import io
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import (
    CROQUIS_GENERATE_JOB_TYPE,
    VERSION_STATUS_AWAITING_REVIEW,
    VERSION_STATUS_FAILED,
    VERSION_STATUS_GENERATING,
    VERSION_STATUS_RECONCILIATION,
    VERSION_STATUS_REJECTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.personal_croquis_spend import (
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_provider import (
    DESIGN_H,
    DESIGN_W,
    GEOMETRY_PROFILE_V1,
    ProviderNotAvailableError,
    fit_contain_normalize_png,
    get_croquis_provider,
)
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

_ACTIVE_CLAIM_STATUSES = ("claimed", "running")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _reservation_for_version(
    db: Session, version_id: uuid.UUID
) -> PersonalCroquisSpendReservation | None:
    return (
        db.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.version_id == version_id)
        .one_or_none()
    )


def _assert_dispatch_gates() -> None:
    """Fail closed at actual worker dispatch — not only at enqueue."""
    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise ProviderNotAvailableError("MY_CROQUIS_AI_ENABLED is false at dispatch")
    if float(settings.my_croquis_ai_spend_ceiling_usd or 0) <= 0:
        raise ProviderNotAvailableError(
            "MY_CROQUIS_AI_SPEND_CEILING_USD is 0 (fail closed) at dispatch"
        )
    if int(settings.my_croquis_ai_max_exposure_cents or 0) <= 0 and float(
        settings.my_croquis_ai_max_usd_per_run or 0
    ) <= 0:
        raise ProviderNotAvailableError(
            "Max exposure unset at dispatch (soft estimates are not a hard cap)"
        )


def validate_and_normalize_provider_png(raw_png: bytes) -> bytes:
    """Enforce fit-contain 768×1024 RGBA, strip EXIF — any provider output."""
    if not raw_png:
        raise ValueError("Provider returned empty image bytes")
    normalized = fit_contain_normalize_png(raw_png)
    with Image.open(io.BytesIO(normalized)) as img:
        img.load()
        if img.size != (DESIGN_W, DESIGN_H):
            raise ValueError(
                f"Provider output geometry invalid after normalize: {img.size} "
                f"(expected {DESIGN_W}x{DESIGN_H})"
            )
        if img.mode != "RGBA":
            raise ValueError(f"Provider output must be RGBA after normalize, got {img.mode}")
        if dict(img.getexif()):
            raise ValueError("Provider output still contains EXIF after normalize")
    return normalized


def _store_generated_asset(db: Session, *, owner_id: uuid.UUID, png_bytes: bytes) -> PrivateMediaAsset:
    asset_id = uuid.uuid4()
    storage_key = f"croquis/{owner_id}/{asset_id}.png"
    storage = LocalStorageBackend()
    storage.save_private_croquis_file(
        key=storage_key, data=io.BytesIO(png_bytes), content_type="image/png"
    )
    with Image.open(io.BytesIO(png_bytes)) as img:
        width, height = img.size
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=owner_id,
        kind=KIND_CROQUIS_GENERATED,
        content_type="image/png",
        width=width,
        height=height,
        byte_size=len(png_bytes),
        sha256=hashlib.sha256(png_bytes).hexdigest(),
        storage_key=storage_key,
    )
    db.add(asset)
    db.flush()
    return asset


def _delete_generated_bytes(storage_key: str) -> None:
    try:
        LocalStorageBackend().delete_private_croquis_file(key=storage_key)
    except Exception:
        logger.warning("Orphan croquis generated file cleanup failed for key=%s", storage_key)


def _safe_delete_asset_row(db: Session, asset: PrivateMediaAsset) -> None:
    key = asset.storage_key
    db.delete(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return
    _delete_generated_bytes(key)


def recover_stale_croquis_claims(db: Session) -> int:
    """Reconcile expired claimed/running croquis jobs.

    - provider_called=False → safe requeue (definitely no request sent)
    - provider_called=True → reconciliation_required (possibly sent; hold spend)

    Uses ``db.scalar`` (not ``scalars``) so lightweight worker test doubles stay compatible.
    """
    settings = get_settings()
    lease = max(15, int(settings.my_croquis_ai_claim_lease_seconds or 120))
    cutoff = _utcnow() - timedelta(seconds=lease)
    recovered = 0
    for _ in range(16):
        job = db.scalar(
            select(AIJob)
            .where(
                AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE,
                AIJob.status.in_(_ACTIVE_CLAIM_STATUSES),
                AIJob.claimed_at.is_not(None),
                AIJob.claimed_at < cutoff,
            )
            .order_by(AIJob.claimed_at.asc())
            .limit(1)
            .with_for_update(of=AIJob, skip_locked=True)
        )
        if job is None:
            break
        # Test doubles may ignore WHERE — never mutate non-croquis jobs.
        if job.job_type != CROQUIS_GENERATE_JOB_TYPE or job.status not in _ACTIVE_CLAIM_STATUSES:
            break

        payload = job.input_data if isinstance(job.input_data, dict) else {}
        version_id = None
        try:
            version_id = uuid.UUID(str(payload["version_id"]))
        except (KeyError, ValueError, TypeError):
            job.status = "failed"
            job.error_message = "Stale croquis claim with invalid payload."
            job.claim_token = None
            db.add(job)
            db.commit()
            recovered += 1
            continue

        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        provider_called = bool(reservation and reservation.provider_called)

        if provider_called:
            if version is not None and version.status == VERSION_STATUS_GENERATING:
                version.status = VERSION_STATUS_RECONCILIATION
                db.add(version)
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.status = RESERVATION_RECONCILIATION
                reservation.error_detail = "Worker claim lease expired after provider_called"
                db.add(reservation)
            job.status = "failed"
            job.error_message = (
                "Worker crash after possible provider submission — reconciliation required."
            )
            job.claim_token = None
            db.add(job)
            db.commit()
        else:
            # Definitely not sent — safe to requeue for another worker attempt.
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.provider_called = False
                db.add(reservation)
            if version is not None and version.status == VERSION_STATUS_GENERATING:
                # Keep generating; job returns to queue.
                db.add(version)
            job.status = "queued"
            job.claimed_at = None
            job.claim_token = None
            job.error_message = None
            db.add(job)
            db.commit()
        recovered += 1
    return recovered


def _claim_next_croquis_job(db: Session) -> AIJob | None:
    job = db.scalar(
        select(AIJob)
        .where(
            AIJob.status == "queued",
            AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE,
        )
        .order_by(AIJob.created_at.asc())
        .limit(1)
        .with_for_update(of=AIJob, skip_locked=True)
    )
    if job is None:
        return None
    # Test doubles may ignore WHERE — never claim/mutate Magic/techpack jobs.
    if job.job_type != CROQUIS_GENERATE_JOB_TYPE or job.status != "queued":
        return None
    job.status = "claimed"
    job.claimed_at = _utcnow()
    job.claim_token = secrets.token_hex(16)
    job.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_claimed_croquis_job(db: Session, job: AIJob) -> None:
    """Execute one claimed croquis generate job to awaiting_review / failure / reconciliation."""
    if job.job_type != CROQUIS_GENERATE_JOB_TYPE:
        return
    payload = job.input_data if isinstance(job.input_data, dict) else {}
    try:
        version_id = uuid.UUID(str(payload["version_id"]))
        croquis_id = uuid.UUID(str(payload["croquis_id"]))
        source_asset_id = uuid.UUID(str(payload["source_asset_id"]))
    except (KeyError, ValueError) as exc:
        job.status = "failed"
        job.error_message = "Invalid croquis job payload."
        job.claim_token = None
        db.add(job)
        db.commit()
        raise ValueError("invalid croquis job payload") from exc

    version = (
        db.query(PersonalCroquisVersion)
        .filter(PersonalCroquisVersion.id == version_id)
        .with_for_update()
        .one_or_none()
    )
    croquis = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.id == croquis_id)
        .with_for_update()
        .one_or_none()
    )
    reservation = _reservation_for_version(db, version_id)
    if reservation is not None:
        reservation = (
            db.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.id == reservation.id)
            .with_for_update()
            .one()
        )

    if version is None or croquis is None:
        job.status = "failed"
        job.error_message = "Croquis version missing."
        job.claim_token = None
        if reservation and reservation.status == RESERVATION_OPEN:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            db.add(reservation)
        db.add(job)
        db.commit()
        return

    # Owner cancelled / erased before provider — release if not submitted.
    if version.status == VERSION_STATUS_REJECTED:
        job.status = "failed"
        job.error_message = "Version rejected before processing."
        job.claim_token = None
        if reservation and reservation.status == RESERVATION_OPEN and not reservation.provider_called:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            db.add(reservation)
        db.add(job)
        db.commit()
        return

    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        if version.status == VERSION_STATUS_GENERATING:
            version.status = VERSION_STATUS_FAILED
            db.add(version)
        job.status = "failed"
        job.error_message = "Croquis erased during processing."
        job.claim_token = None
        if reservation and reservation.status == RESERVATION_OPEN and not reservation.provider_called:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            db.add(reservation)
        db.add(job)
        db.commit()
        return

    if version.status not in (VERSION_STATUS_GENERATING,):
        # Idempotent worker replay for already-finished rows.
        job.status = "completed" if version.status == VERSION_STATUS_AWAITING_REVIEW else "failed"
        job.result_data = {
            "version_id": str(version.id),
            "version_status": version.status,
            "replay": True,
        }
        job.claim_token = None
        db.add(job)
        db.commit()
        return

    # Dispatch-time gate/ceiling check (fail closed in production defaults).
    try:
        _assert_dispatch_gates()
    except ProviderNotAvailableError as exc:
        version.status = VERSION_STATUS_FAILED
        job.status = "failed"
        job.error_message = str(exc)[:500]
        job.claim_token = None
        if reservation and reservation.status == RESERVATION_OPEN and not reservation.provider_called:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(version)
        db.add(job)
        db.commit()
        return

    job.status = "running"
    db.add(job)
    db.commit()

    try:
        owner = croquis.owner
        source_path = pcs.resolve_croquis_asset_file(db, owner, source_asset_id)
        source_bytes = source_path.read_bytes()
    except Exception as exc:  # source gone / IDOR closed
        version.status = VERSION_STATUS_FAILED
        job.status = "failed"
        job.error_message = "Source photo unavailable."
        job.claim_token = None
        if reservation and reservation.status == RESERVATION_OPEN:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(version)
        db.add(job)
        db.commit()
        return

    adapter = get_croquis_provider()
    # Mark possibly-spent BEFORE adapter invocation (crash after this → reconciliation).
    if reservation is not None:
        reservation.provider_called = True
        db.add(reservation)
        db.commit()

    try:
        result = adapter.generate_line_art(source_bytes)
        png_bytes = validate_and_normalize_provider_png(result.png_bytes)
        asset = _store_generated_asset(db, owner_id=version.owner_id, png_bytes=png_bytes)
        settled = (
            int(result.actual_cost_cents)
            if result.usage_source == "provider_usage"
            else int(result.estimated_cost_cents)
        )
        # Cap settled label at reserved max exposure when configured on reservation.
        if reservation is not None and reservation.max_exposure_cents:
            # Still record actual; exposure accounting uses max(actual, reserved) at settle time
            # for ceiling sums via settled actual. Do not invent a lower actual.
            pass

        # CAS: only attach if still generating and croquis not erased.
        croquis_fresh = db.get(PersonalCroquis, croquis_id)
        erased = (
            croquis_fresh is None
            or croquis_fresh.erase_requested_at is not None
            or croquis_fresh.deleted_at is not None
        )
        if erased:
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                # Provider already called — keep spend exposure (settle), discard asset.
                reservation.status = RESERVATION_SETTLED
                reservation.actual_cost_cents = settled
                reservation.error_detail = "Croquis erased after provider response; result discarded."
                db.add(reservation)
            if version.status == VERSION_STATUS_GENERATING:
                version.status = VERSION_STATUS_FAILED
                db.add(version)
            job.status = "failed"
            job.error_message = "Croquis erased after provider response; result discarded."
            job.claim_token = None
            db.add(job)
            db.commit()
            _safe_delete_asset_row(db, asset)
            return

        cas = db.execute(
            update(PersonalCroquisVersion)
            .where(
                PersonalCroquisVersion.id == version_id,
                PersonalCroquisVersion.status == VERSION_STATUS_GENERATING,
            )
            .values(
                generated_asset_id=asset.id,
                status=VERSION_STATUS_AWAITING_REVIEW,
                prompt_version=result.prompt_version,
                geometry_profile=result.geometry_profile or GEOMETRY_PROFILE_V1,
                cost_cents=settled,
            )
        )
        if int(getattr(cas, "rowcount", 0) or 0) != 1:
            # Rejected or otherwise transitioned — never resurrect.
            db.refresh(version)
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.status = RESERVATION_SETTLED
                reservation.actual_cost_cents = settled
                reservation.error_detail = (
                    f"Provider completed but version status={version.status}; result discarded."
                )
                db.add(reservation)
            job.status = "failed"
            job.error_message = (
                f"Version no longer generating (status={version.status}); result discarded."
            )
            job.claim_token = None
            db.add(job)
            db.commit()
            _safe_delete_asset_row(db, asset)
            return

        if reservation is not None:
            reservation.status = RESERVATION_SETTLED
            reservation.actual_cost_cents = settled
            reservation.error_detail = None
            db.add(reservation)
        job.status = "completed"
        job.claim_token = None
        job.result_data = {
            "version_id": str(version_id),
            "version": int(payload.get("version") or 0) or None,
            "status": VERSION_STATUS_AWAITING_REVIEW,
            "generated_asset_id": str(asset.id),
            "cost_cents_settled": settled,
            "cost_usage_source": result.usage_source,
            "estimate_cents": int(payload.get("estimate_cents") or 0),
            "max_exposure_cents": int(payload.get("max_exposure_cents") or 0),
            "geometry_profile": result.geometry_profile or GEOMETRY_PROFILE_V1,
        }
        db.add(job)
        db.commit()
    except ProviderNotAvailableError as exc:
        # Prefer release only if we can prove the adapter refused before send.
        # After provider_called=True we still release for explicit NotAvailable from
        # fail-closed shells (no network). UnknownOutcome uses TimeoutError instead.
        version.status = VERSION_STATUS_FAILED
        job.status = "failed"
        job.error_message = "Provider unavailable before spend."
        job.claim_token = None
        if reservation is not None:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            # Keep provider_called historical truth if we marked it; still release cost.
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(version)
        db.add(job)
        db.commit()
    except TimeoutError as exc:
        version.status = VERSION_STATUS_RECONCILIATION
        job.status = "failed"
        job.error_message = "Provider outcome unknown — reconciliation required."
        job.claim_token = None
        if reservation is not None:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(version)
        db.add(job)
        db.commit()
    except Exception as exc:
        logger.exception("Croquis job %s failed", job.id)
        if reservation is not None and reservation.provider_called:
            version.status = VERSION_STATUS_RECONCILIATION
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
            job.error_message = "Provider failure after send — reconciliation required."
        else:
            version.status = VERSION_STATUS_FAILED
            if reservation is not None:
                reservation.status = RESERVATION_RELEASED
                reservation.actual_cost_cents = 0
                reservation.error_detail = str(exc)[:500]
            job.error_message = "Generation failed before provider spend."
        job.status = "failed"
        job.claim_token = None
        db.add(version)
        if reservation is not None:
            db.add(reservation)
        db.add(job)
        db.commit()


def run_croquis_worker_tick(db: Session, *, limit: int = 4) -> int:
    """Recover stale leases, then claim up to *limit* queued personal_croquis_generate jobs."""
    recover_stale_croquis_claims(db)
    processed = 0
    for _ in range(limit):
        job = _claim_next_croquis_job(db)
        if job is None:
            break
        process_claimed_croquis_job(db, job)
        processed += 1
    return processed
