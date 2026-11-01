"""Create My Croquis Stage C — AIJob worker for personal_croquis_generate.

Claims queued croquis jobs with a durable lease (SKIP LOCKED). Crash recovery
distinguishes definitely-not-sent (safe requeue) from possibly-sent
(reconciliation_required; hold spend; never auto paid retry).

Dispatch is fenced atomically: claim_token + croquis erase/version/source/consent
checks happen in one transaction before ``provider_called``. A stale worker or
an erase that wins before the fence cannot submit private bytes to a provider.

Generated-asset bytes are written only under the croquis attach lock (same TX
as the version CAS) so erase/reject cannot leave committed unreferenced rows;
failed paths unlink and enqueue cleanup for sweepable orphans.

Never logs image bytes or credentials.
"""

from __future__ import annotations

import hashlib
import io
import logging
import secrets
import uuid
from collections.abc import Callable
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
from app.models.personal_croquis_ai_consent import PersonalCroquisAiConsentBinding
from app.models.personal_croquis_spend import (
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.models.user import User
from app.models.user_consent_event import PURPOSE_CROQUIS_AI_PROVIDER, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_provider import (
    DESIGN_H,
    DESIGN_W,
    GEOMETRY_PROFILE_V1,
    ProviderNotAvailableError,
    ProviderOutcomeUnknownError,
    fit_contain_normalize_png,
    get_croquis_provider,
)
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

_ACTIVE_CLAIM_STATUSES = ("claimed", "running")

# Test-only hooks (never use in production):
# - pre-provider: after preliminary running mark, before final fence TX (lease/erase races)
# - pre-attach: after provider returns, before croquis-locked attach (post-fence erase)
_pre_provider_dispatch_hook: Callable[[AIJob], None] | None = None
_post_provider_pre_attach_hook: Callable[[AIJob], None] | None = None


class StaleClaimError(RuntimeError):
    """This worker no longer owns the job lease (recovered/reclaimed)."""


class DispatchAuthzError(RuntimeError):
    """Pre-provider authorization failed (consent/source/adults/erase)."""


def set_pre_provider_dispatch_hook(hook: Callable[[AIJob], None] | None) -> None:
    """Install/clear the offline test interleaving hook (never use in production)."""
    global _pre_provider_dispatch_hook
    _pre_provider_dispatch_hook = hook


def set_post_provider_pre_attach_hook(hook: Callable[[AIJob], None] | None) -> None:
    """Install/clear post-provider / pre-attach interleaving hook (tests only)."""
    global _post_provider_pre_attach_hook
    _post_provider_pre_attach_hook = hook


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


def _assert_dispatch_authorization(
    db: Session,
    *,
    croquis: PersonalCroquis,
    version: PersonalCroquisVersion,
    source_asset_id: uuid.UUID,
    ai_consent_id: uuid.UUID | None,
) -> bytes:
    """Revalidate owner/source/consent/adults/notice immediately before provider fence.

    Returns source PNG bytes when authorized. Raises DispatchAuthzError otherwise.
    """
    settings = get_settings()
    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        raise DispatchAuthzError("Croquis erased or deleted at dispatch")
    if croquis.source_asset_id is None or croquis.source_asset_id != source_asset_id:
        raise DispatchAuthzError("Croquis source asset no longer matches job payload")
    if version.owner_id != croquis.owner_id:
        raise DispatchAuthzError("Version owner mismatch at dispatch")

    owner = db.get(User, croquis.owner_id)
    if owner is None or not owner.is_active:
        raise DispatchAuthzError("Owner missing or inactive at dispatch")

    # Adults attestation must still be current (not enqueue-time only).
    attestation = pcs._latest_adults_attestation(db, owner)
    if attestation is None:
        raise DispatchAuthzError("Adults attestation missing/expired at dispatch")

    consent_id = ai_consent_id or version.ai_consent_id
    if consent_id is None:
        raise DispatchAuthzError("AI consent missing at dispatch")

    approved = (settings.my_croquis_ai_notice_text or "").strip()
    if not approved:
        raise DispatchAuthzError("AI notice text not approved at dispatch")
    expected_hash = hashlib.sha256(approved.encode("utf-8")).hexdigest()

    consent = (
        db.query(UserConsentEvent)
        .filter(
            UserConsentEvent.id == consent_id,
            UserConsentEvent.owner_id == owner.id,
            UserConsentEvent.purpose == PURPOSE_CROQUIS_AI_PROVIDER,
        )
        .one_or_none()
    )
    if consent is None:
        raise DispatchAuthzError("AI consent not found at dispatch")
    max_age = int(settings.my_croquis_ai_consent_max_age_seconds or 3600)
    if (_utcnow() - consent.created_at).total_seconds() > max_age:
        raise DispatchAuthzError("AI consent expired at dispatch")
    if consent.consent_version != settings.my_croquis_ai_consent_version:
        raise DispatchAuthzError("AI consent version outdated at dispatch")
    if consent.text_hash != expected_hash:
        raise DispatchAuthzError("AI consent notice hash stale at dispatch")

    binding = (
        db.query(PersonalCroquisAiConsentBinding)
        .filter(
            PersonalCroquisAiConsentBinding.consent_id == consent_id,
            PersonalCroquisAiConsentBinding.owner_id == owner.id,
            PersonalCroquisAiConsentBinding.croquis_id == croquis.id,
            PersonalCroquisAiConsentBinding.source_asset_id == source_asset_id,
        )
        .one_or_none()
    )
    if binding is None:
        raise DispatchAuthzError("AI consent not bound to current croquis source at dispatch")
    if binding.notice_text_hash != expected_hash:
        raise DispatchAuthzError("Bound AI consent notice hash stale at dispatch")

    source = db.get(PrivateMediaAsset, source_asset_id)
    if (
        source is None
        or source.owner_id != owner.id
        or source.erase_requested_at is not None
        or source.deleted_at is not None
        or source.bytes_purged_at is not None
    ):
        raise DispatchAuthzError("Source asset unavailable or retention-purged at dispatch")

    try:
        source_path = pcs.resolve_croquis_asset_file(db, owner, source_asset_id)
        return source_path.read_bytes()
    except Exception as exc:
        raise DispatchAuthzError(f"Source bytes unavailable at dispatch: {exc}") from exc


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


def _write_generated_file(*, owner_id: uuid.UUID, png_bytes: bytes) -> tuple[uuid.UUID, str, int, int]:
    """Write generated PNG to private storage; returns (asset_id, key, w, h). No DB row yet."""
    asset_id = uuid.uuid4()
    storage_key = f"croquis/{owner_id}/{asset_id}.png"
    LocalStorageBackend().save_private_croquis_file(
        key=storage_key, data=io.BytesIO(png_bytes), content_type="image/png"
    )
    with Image.open(io.BytesIO(png_bytes)) as img:
        width, height = img.size
    return asset_id, storage_key, width, height


def _delete_generated_bytes(storage_key: str) -> None:
    try:
        LocalStorageBackend().delete_private_croquis_file(key=storage_key)
    except Exception:
        logger.warning("Orphan croquis generated file cleanup failed for key=%s", storage_key)


def _enqueue_orphan_cleanup(
    db: Session, *, owner_id: uuid.UUID, asset_id: uuid.UUID | None, storage_key: str
) -> None:
    """Record a sweepable cleanup row for generated bytes that must not linger."""
    pcs._enqueue_cleanup(
        db,
        owner_id=owner_id,
        asset_id=asset_id,
        storage_key=storage_key,
        reason="croquis_generated_orphan",
    )


def _safe_delete_asset_row(db: Session, asset: PrivateMediaAsset) -> None:
    key = asset.storage_key
    owner_id = asset.owner_id
    asset_id = asset.id
    db.delete(asset)
    try:
        _enqueue_orphan_cleanup(db, owner_id=owner_id, asset_id=asset_id, storage_key=key)
        db.commit()
    except Exception:
        db.rollback()
        _delete_generated_bytes(key)
        return
    _delete_generated_bytes(key)


def _fence_for_provider_dispatch(
    db: Session,
    *,
    job_id: uuid.UUID,
    claim_token: str,
    reservation_id: uuid.UUID | None,
    croquis_id: uuid.UUID,
    version_id: uuid.UUID,
    source_asset_id: uuid.UUID,
    ai_consent_id: uuid.UUID | None,
) -> tuple[AIJob, bytes]:
    """Final pre-provider fence: claim + erase/authz + open reservation in one TX.

    Lock order matches permanent erase (croquis → version → job/reservation) to
    avoid deadlocks. Raises StaleClaimError if another worker reclaimed the lease.
    Raises DispatchAuthzError if erase/authz wins (fail closed, no provider call).
    On success commits ``provider_called=True`` with no unprotected gap after the
    final authorization checks.
    """
    croquis = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.id == croquis_id)
        .with_for_update()
        .one_or_none()
    )
    version = (
        db.query(PersonalCroquisVersion)
        .filter(PersonalCroquisVersion.id == version_id)
        .with_for_update()
        .one_or_none()
    )
    job = (
        db.query(AIJob)
        .filter(AIJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if (
        job is None
        or job.job_type != CROQUIS_GENERATE_JOB_TYPE
        or job.claim_token != claim_token
        or job.status not in _ACTIVE_CLAIM_STATUSES
    ):
        raise StaleClaimError("Croquis claim fence lost before provider submission")

    reservation = None
    if reservation_id is not None:
        reservation = (
            db.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.id == reservation_id)
            .with_for_update()
            .one_or_none()
        )
        if reservation is None or reservation.status != RESERVATION_OPEN:
            raise StaleClaimError("Spend reservation not open under claim fence")

    if croquis is None or version is None:
        raise DispatchAuthzError("Croquis/version missing at provider fence")
    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        raise DispatchAuthzError("Croquis erased at provider fence")
    if version.status != VERSION_STATUS_GENERATING:
        raise DispatchAuthzError(
            f"Version status {version.status} at provider fence (not generating)"
        )

    source_bytes = _assert_dispatch_authorization(
        db,
        croquis=croquis,
        version=version,
        source_asset_id=source_asset_id,
        ai_consent_id=ai_consent_id,
    )

    job.status = "running"
    job.claimed_at = _utcnow()
    db.add(job)
    if reservation is not None:
        reservation.provider_called = True
        db.add(reservation)
    db.commit()
    db.refresh(job)
    return job, source_bytes


def _assert_claim_owned(
    db: Session, *, job_id: uuid.UUID, claim_token: str
) -> AIJob:
    """Lock job and verify claim_token still owns the lease (no commit)."""
    job = (
        db.query(AIJob)
        .filter(AIJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if (
        job is None
        or job.job_type != CROQUIS_GENERATE_JOB_TYPE
        or job.claim_token != claim_token
        or job.status not in _ACTIVE_CLAIM_STATUSES
    ):
        raise StaleClaimError("Croquis claim fence lost before attach")
    return job


def _attach_generated_under_croquis_lock(
    db: Session,
    *,
    job_id: uuid.UUID,
    claim_token: str,
    croquis_id: uuid.UUID,
    version_id: uuid.UUID,
    owner_id: uuid.UUID,
    png_bytes: bytes,
    prompt_version: str | None,
    geometry_profile: str,
    settled: int,
) -> tuple[str, PrivateMediaAsset | None, str | None]:
    """Serialize attach with permanent erase; write generated bytes only if attachable.

    Returns (outcome, asset_or_none, storage_key_or_none) where outcome is
    'attached' | 'erased' | 'rejected'. On erased/rejected before write, no file
    is created. On rejected after write, caller must unlink + enqueue cleanup.
    """
    # Lock order: croquis → version → job (matches erase / provider fence).
    croquis = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.id == croquis_id)
        .with_for_update()
        .one_or_none()
    )
    version = (
        db.query(PersonalCroquisVersion)
        .filter(PersonalCroquisVersion.id == version_id)
        .with_for_update()
        .one_or_none()
    )
    _assert_claim_owned(db, job_id=job_id, claim_token=claim_token)

    erased = (
        croquis is None
        or croquis.erase_requested_at is not None
        or croquis.deleted_at is not None
    )
    if erased or version is None or version.status != VERSION_STATUS_GENERATING:
        return ("erased" if erased else "rejected", None, None)

    asset_id, storage_key, width, height = _write_generated_file(
        owner_id=owner_id, png_bytes=png_bytes
    )
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

    cas = db.execute(
        update(PersonalCroquisVersion)
        .where(
            PersonalCroquisVersion.id == version_id,
            PersonalCroquisVersion.status == VERSION_STATUS_GENERATING,
        )
        .values(
            generated_asset_id=asset.id,
            status=VERSION_STATUS_AWAITING_REVIEW,
            prompt_version=prompt_version,
            geometry_profile=geometry_profile,
            cost_cents=settled,
        )
    )
    if int(getattr(cas, "rowcount", 0) or 0) != 1:
        db.delete(asset)
        db.flush()
        return ("rejected", None, storage_key)
    return ("attached", asset, storage_key)


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
            # Clearing claim_token fences any still-running original worker.
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.provider_called = False
                db.add(reservation)
            if version is not None and version.status == VERSION_STATUS_GENERATING:
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
    expected_token = job.claim_token
    if not expected_token:
        job.status = "failed"
        job.error_message = "Claimed croquis job missing claim_token."
        db.add(job)
        db.commit()
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

    reservation_id = None
    if payload.get("reservation_id"):
        try:
            reservation_id = uuid.UUID(str(payload["reservation_id"]))
        except ValueError:
            reservation_id = None
    ai_consent_id = None
    if payload.get("ai_consent_id"):
        try:
            ai_consent_id = uuid.UUID(str(payload["ai_consent_id"]))
        except ValueError:
            ai_consent_id = None

    # Lock order: croquis → version → reservation (matches erase/reject serialization).
    croquis = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.id == croquis_id)
        .with_for_update()
        .one_or_none()
    )
    version = (
        db.query(PersonalCroquisVersion)
        .filter(PersonalCroquisVersion.id == version_id)
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
        reservation_id = reservation.id

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
    job.claimed_at = _utcnow()
    db.add(job)
    db.commit()

    # Deterministic interleaving point: after preliminary running mark, before the
    # final fenced authz+provider_called transaction (lease reclaim / erase races).
    if _pre_provider_dispatch_hook is not None:
        _pre_provider_dispatch_hook(job)

    # Definite pre-submit readiness BEFORE provider_called fence (LIVE_HTTP / key / model).
    adapter = get_croquis_provider()
    try:
        pre_ready = getattr(adapter, "assert_pre_submit_ready", None)
        if callable(pre_ready):
            pre_ready()
    except ProviderNotAvailableError as exc:
        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        if version is not None and version.status == VERSION_STATUS_GENERATING:
            version.status = VERSION_STATUS_FAILED
            db.add(version)
        if (
            reservation is not None
            and reservation.status == RESERVATION_OPEN
            and not reservation.provider_called
        ):
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        job_row = db.get(AIJob, job.id)
        if job_row is not None and job_row.claim_token == expected_token:
            job_row.status = "failed"
            job_row.error_message = f"Provider unavailable before spend: {exc}"[:500]
            job_row.claim_token = None
            db.add(job_row)
        db.commit()
        return

    try:
        job, source_bytes = _fence_for_provider_dispatch(
            db,
            job_id=job.id,
            claim_token=expected_token,
            reservation_id=reservation_id,
            croquis_id=croquis_id,
            version_id=version_id,
            source_asset_id=source_asset_id,
            ai_consent_id=ai_consent_id,
        )
    except StaleClaimError:
        # Another worker owns the lease — do not call provider and do not mutate their state.
        logger.info("Aborting stale croquis worker for job %s (fence lost)", job.id)
        db.rollback()
        return
    except DispatchAuthzError as exc:
        # Erase/authz won before provider_called — fail closed with zero provider spend.
        # Do not rollback: fence raised a Python authz error (not a DB abort) while holding
        # croquis/version/job locks; reuse that TX to release reservation + fail the job.
        job_id = job.id
        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        job_row = db.get(AIJob, job_id)
        if version is not None and version.status == VERSION_STATUS_GENERATING:
            version.status = VERSION_STATUS_FAILED
            db.add(version)
        if (
            reservation is not None
            and reservation.status == RESERVATION_OPEN
            and not reservation.provider_called
        ):
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        if job_row is not None and job_row.claim_token == expected_token:
            job_row.status = "failed"
            job_row.error_message = f"Dispatch fence denied: {exc}"[:500]
            job_row.claim_token = None
            db.add(job_row)
        db.commit()
        return

    # Request-in-flight boundary: provider_called is committed. If erase races after
    # this point, the provider may still be invoked; attach must discard the result.
    try:
        result = adapter.generate_line_art(source_bytes)
        png_bytes = validate_and_normalize_provider_png(result.png_bytes)
        owner_id_for_asset = job.user_id
        # Precise erase-vs-attach interleaving point (after provider, before store/attach).
        if _post_provider_pre_attach_hook is not None:
            _post_provider_pre_attach_hook(job)
        settled = (
            int(result.actual_cost_cents)
            if result.usage_source == "provider_usage"
            else int(result.estimated_cost_cents)
        )

        try:
            outcome, asset, orphan_key = _attach_generated_under_croquis_lock(
                db,
                job_id=job.id,
                claim_token=expected_token,
                croquis_id=croquis_id,
                version_id=version_id,
                owner_id=owner_id_for_asset,
                png_bytes=png_bytes,
                prompt_version=result.prompt_version,
                geometry_profile=result.geometry_profile or GEOMETRY_PROFILE_V1,
                settled=settled,
            )
        except StaleClaimError:
            logger.info("Aborting stale croquis attach for job %s (fence lost)", job.id)
            db.rollback()
            return

        reservation = _reservation_for_version(db, version_id)
        version = db.get(PersonalCroquisVersion, version_id)

        if outcome == "erased":
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.status = RESERVATION_SETTLED
                reservation.actual_cost_cents = settled
                reservation.error_detail = "Croquis erased after provider response; result discarded."
                db.add(reservation)
            if version is not None and version.status == VERSION_STATUS_GENERATING:
                version.status = VERSION_STATUS_FAILED
                db.add(version)
            job.status = "failed"
            job.error_message = "Croquis erased after provider response; result discarded."
            job.claim_token = None
            db.add(job)
            db.commit()
            return

        if outcome == "rejected":
            if reservation is not None and reservation.status == RESERVATION_OPEN:
                reservation.status = RESERVATION_SETTLED
                reservation.actual_cost_cents = settled
                reservation.error_detail = (
                    f"Provider completed but version status="
                    f"{getattr(version, 'status', '?')}; result discarded."
                )
                db.add(reservation)
            job.status = "failed"
            job.error_message = "Version no longer generating; result discarded."
            job.claim_token = None
            db.add(job)
            if orphan_key is not None:
                _enqueue_orphan_cleanup(
                    db, owner_id=owner_id_for_asset, asset_id=None, storage_key=orphan_key
                )
            db.commit()
            if orphan_key is not None:
                _delete_generated_bytes(orphan_key)
            return

        if asset is None:
            raise RuntimeError("attached outcome missing asset")

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
            "provider_job_id": result.provider_job_id,
            "cost_cents_settled": settled,
            "cost_usage_source": result.usage_source,
            "estimate_cents": int(payload.get("estimate_cents") or 0),
            "max_exposure_cents": int(payload.get("max_exposure_cents") or 0),
            "geometry_profile": result.geometry_profile or GEOMETRY_PROFILE_V1,
        }
        db.add(job)
        db.commit()
    except ProviderNotAvailableError as exc:
        # Typed definite no-billable-result refusal — safe $0 release even if the
        # fence already marked provider_called (LIVE_HTTP refuse, CrashBeforeSubmit,
        # or definitive HTTP 4xx rejection with no generated image).
        # Ambiguous post-submit failures MUST use ProviderOutcomeUnknownError.
        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        if version is not None:
            version.status = VERSION_STATUS_FAILED
            db.add(version)
        job.status = "failed"
        called = bool(reservation is not None and reservation.provider_called)
        job.error_message = (
            "Provider rejected the request (no generated image). You may retry with a new attempt."
            if called
            else "Provider unavailable before spend."
        )
        job.claim_token = None
        if reservation is not None:
            reservation.status = RESERVATION_RELEASED
            reservation.actual_cost_cents = 0
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(job)
        db.commit()
    except (ProviderOutcomeUnknownError, TimeoutError) as exc:
        # Post-submit / may-have-billed — hold exposure; block new-key retry.
        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        if version is not None:
            version.status = VERSION_STATUS_RECONCILIATION
            db.add(version)
        job.status = "failed"
        job.error_message = "Provider outcome unknown — reconciliation required."
        job.claim_token = None
        if reservation is not None:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
            db.add(reservation)
        db.add(job)
        db.commit()
    except StaleClaimError:
        db.rollback()
        return
    except Exception as exc:
        logger.exception("Croquis job %s failed", job.id)
        version = db.get(PersonalCroquisVersion, version_id)
        reservation = _reservation_for_version(db, version_id)
        if reservation is not None and reservation.provider_called:
            if version is not None:
                version.status = VERSION_STATUS_RECONCILIATION
                db.add(version)
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:500]
            job.error_message = "Provider failure after send — reconciliation required."
        else:
            if version is not None:
                version.status = VERSION_STATUS_FAILED
                db.add(version)
            if reservation is not None:
                reservation.status = RESERVATION_RELEASED
                reservation.actual_cost_cents = 0
                reservation.error_detail = str(exc)[:500]
            job.error_message = "Generation failed before provider spend."
        job.status = "failed"
        job.claim_token = None
        if reservation is not None:
            db.add(reservation)
        db.add(job)
        db.commit()


def claim_croquis_job_by_id(db: Session, job_id: uuid.UUID) -> AIJob:
    """Claim exactly one queued croquis job by primary key (fail closed).

    Used by the authorized one-call executor so a reused disposable DB cannot
    accidentally submit an older queued job's source to the provider.
    Does not scan/claim other queued jobs. Refuses if the row is missing,
    wrong type/status, or locked by another worker.
    """
    from sqlalchemy.exc import OperationalError

    try:
        job = db.scalar(
            select(AIJob)
            .where(AIJob.id == job_id)
            .with_for_update(of=AIJob, nowait=True)
        )
    except OperationalError as exc:
        db.rollback()
        raise RuntimeError(
            f"Croquis job {job_id} is locked by another worker — refusing one-call claim"
        ) from exc
    if job is None:
        db.rollback()
        raise RuntimeError(f"Croquis job {job_id} not found for one-call claim")
    if job.job_type != CROQUIS_GENERATE_JOB_TYPE:
        db.rollback()
        raise RuntimeError(
            f"Job {job_id} type={job.job_type!r} is not {CROQUIS_GENERATE_JOB_TYPE}"
        )
    if job.status != "queued":
        db.rollback()
        raise RuntimeError(
            f"Croquis job {job_id} status={job.status!r} — expected queued for one-call claim"
        )
    job.status = "claimed"
    job.claimed_at = _utcnow()
    job.claim_token = secrets.token_hex(16)
    job.error_message = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_specific_croquis_job(db: Session, job_id: uuid.UUID) -> None:
    """Claim + process exactly ``job_id`` — never the oldest-queue tick path."""
    job = claim_croquis_job_by_id(db, job_id)
    process_claimed_croquis_job(db, job)


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
