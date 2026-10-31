"""Create My Croquis Stage C — AIJob worker for personal_croquis_generate.

Claims queued croquis jobs (SKIP LOCKED). Never logs image bytes or credentials.
Unknown provider outcomes leave spend reservations in reconciliation_required.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from app.services.personal_croquis_provider import (
    ProviderNotAvailableError,
    get_croquis_provider,
)
from app.services import personal_croquis_service as pcs
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)


def _store_generated_asset(db: Session, *, owner_id: uuid.UUID, png_bytes: bytes) -> PrivateMediaAsset:
    asset_id = uuid.uuid4()
    storage_key = f"croquis/{owner_id}/{asset_id}.png"
    storage = LocalStorageBackend()
    storage.save_private_croquis_file(
        key=storage_key, data=io.BytesIO(png_bytes), content_type="image/png"
    )
    from PIL import Image

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


def _reservation_for_version(
    db: Session, version_id: uuid.UUID
) -> PersonalCroquisSpendReservation | None:
    return (
        db.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.version_id == version_id)
        .one_or_none()
    )


def process_claimed_croquis_job(db: Session, job: AIJob) -> None:
    """Execute one claimed croquis generate job to awaiting_review / failure / reconciliation."""
    payload = job.input_data if isinstance(job.input_data, dict) else {}
    try:
        version_id = uuid.UUID(str(payload["version_id"]))
        croquis_id = uuid.UUID(str(payload["croquis_id"]))
        source_asset_id = uuid.UUID(str(payload["source_asset_id"]))
    except (KeyError, ValueError) as exc:
        job.status = "failed"
        job.error_message = "Invalid croquis job payload."
        db.add(job)
        db.commit()
        raise ValueError("invalid croquis job payload") from exc

    version = db.get(PersonalCroquisVersion, version_id)
    croquis = db.get(PersonalCroquis, croquis_id)
    reservation = _reservation_for_version(db, version_id)

    if version is None or croquis is None:
        job.status = "failed"
        job.error_message = "Croquis version missing."
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
        if reservation and reservation.status == RESERVATION_OPEN and not reservation.provider_called:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            db.add(reservation)
        db.add(job)
        db.commit()
        return

    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        version.status = VERSION_STATUS_FAILED
        job.status = "failed"
        job.error_message = "Croquis erased during processing."
        if reservation and reservation.status == RESERVATION_OPEN and not reservation.provider_called:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            db.add(reservation)
        db.add(version)
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
        db.add(job)
        db.commit()
        return

    # Mark job running (version stays generating until reviewable).
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
    if reservation is not None:
        reservation.provider_called = True
        db.add(reservation)
        db.commit()

    try:
        result = adapter.generate_line_art(source_bytes)
        asset = _store_generated_asset(db, owner_id=version.owner_id, png_bytes=result.png_bytes)
        version.generated_asset_id = asset.id
        version.status = VERSION_STATUS_AWAITING_REVIEW
        version.prompt_version = result.prompt_version
        version.geometry_profile = result.geometry_profile
        # Prefer provider-reported usage when present; otherwise keep estimate label.
        settled = (
            int(result.actual_cost_cents)
            if result.usage_source == "provider_usage"
            else int(result.estimated_cost_cents)
        )
        version.cost_cents = settled
        if reservation is not None:
            reservation.status = RESERVATION_SETTLED
            reservation.actual_cost_cents = settled
            reservation.error_detail = None
            db.add(reservation)
        job.status = "completed"
        job.result_data = {
            "version_id": str(version.id),
            "version": version.version,
            "status": VERSION_STATUS_AWAITING_REVIEW,
            "generated_asset_id": str(asset.id),
            "cost_cents_settled": settled,
            "cost_usage_source": result.usage_source,
            "estimate_cents": int(payload.get("estimate_cents") or 0),
            "geometry_profile": result.geometry_profile,
            # No image bytes / URLs.
        }
        db.add(version)
        db.add(job)
        db.commit()
    except ProviderNotAvailableError as exc:
        version.status = VERSION_STATUS_FAILED
        job.status = "failed"
        job.error_message = "Provider unavailable before spend."
        if reservation is not None:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.provider_called = False
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(version)
        db.add(job)
        db.commit()
    except TimeoutError as exc:
        version.status = VERSION_STATUS_RECONCILIATION
        job.status = "failed"
        job.error_message = "Provider outcome unknown — reconciliation required."
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
        db.add(version)
        if reservation is not None:
            db.add(reservation)
        db.add(job)
        db.commit()


def run_croquis_worker_tick(db: Session, *, limit: int = 4) -> int:
    """Claim up to *limit* queued personal_croquis_generate jobs."""
    processed = 0
    for _ in range(limit):
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
            break
        process_claimed_croquis_job(db, job)
        processed += 1
    return processed
