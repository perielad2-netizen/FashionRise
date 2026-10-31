"""Create My Croquis Stage C — enqueue generate + spend reservation + accept/reject.

P0 hardening: global spend lock, max exposure reserve, croquis/source reconciliation
gate, source-bound AI consent, reject/erase CAS safety.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import (
    CROQUIS_GENERATE_JOB_TYPE,
    VERSION_STATUS_ACCEPTED,
    VERSION_STATUS_AWAITING_REVIEW,
    VERSION_STATUS_FAILED,
    VERSION_STATUS_GENERATING,
    VERSION_STATUS_RECONCILIATION,
    VERSION_STATUS_REJECTED,
    PersonalCroquisVersion,
)
from app.models.personal_croquis_ai_consent import PersonalCroquisAiConsentBinding
from app.models.personal_croquis_spend import (
    CROQUIS_SPEND_GLOBAL_LOCK_KEY,
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.user import User
from app.models.user_consent_event import PURPOSE_CROQUIS_AI_PROVIDER, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_provider import GEOMETRY_PROFILE_V1

_BILLABLE_RESERVATION_STATUSES = (
    RESERVATION_OPEN,
    RESERVATION_SETTLED,
    RESERVATION_RECONCILIATION,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _require_ai_gate() -> None:
    settings = get_settings()
    if not settings.my_croquis_ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis AI generation is not enabled.",
        )


def _lock_spend_tx(db: Session, user_id: uuid.UUID) -> None:
    """Serialize operator-wide ceiling then per-user claims (deterministic order)."""
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": CROQUIS_SPEND_GLOBAL_LOCK_KEY})
    user_key = int(user_id.int % (2**63 - 1))
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": user_key})


def _sum_billable_cents(db: Session, *, owner_id: uuid.UUID | None, since: datetime | None) -> int:
    """Sum reserved exposure (max_exposure) for open/recon; actual for settled when set."""
    clauses = [
        PersonalCroquisSpendReservation.status.in_(_BILLABLE_RESERVATION_STATUSES),
    ]
    if owner_id is not None:
        clauses.append(PersonalCroquisSpendReservation.owner_id == owner_id)
    if since is not None:
        clauses.append(PersonalCroquisSpendReservation.created_at >= since)
    rows = db.execute(
        select(
            PersonalCroquisSpendReservation.status,
            PersonalCroquisSpendReservation.max_exposure_cents,
            PersonalCroquisSpendReservation.estimate_cents,
            PersonalCroquisSpendReservation.actual_cost_cents,
        ).where(*clauses)
    ).all()
    total = 0
    for status_s, max_exp, estimate, actual in rows:
        if status_s == RESERVATION_SETTLED:
            total += int(actual if actual is not None else (max_exp or estimate or 0))
        else:
            total += int(max_exp or estimate or 0)
    return total


def _count_generations_today(db: Session, user: User) -> int:
    day_ago = _utcnow() - timedelta(days=1)
    return int(
        db.scalar(
            select(func.count())
            .select_from(PersonalCroquisSpendReservation)
            .where(
                PersonalCroquisSpendReservation.owner_id == user.id,
                PersonalCroquisSpendReservation.created_at >= day_ago,
                PersonalCroquisSpendReservation.status.in_(_BILLABLE_RESERVATION_STATUSES),
            )
        )
        or 0
    )


def resolve_max_exposure_cents() -> int:
    """Conservative maximum authorized exposure for one generate (cents). Fail closed if unset."""
    settings = get_settings()
    max_exp = int(settings.my_croquis_ai_max_exposure_cents or 0)
    max_run = int(round(float(settings.my_croquis_ai_max_usd_per_run or 0) * 100))
    if max_exp <= 0 and max_run <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Create My Croquis max exposure is unset (MY_CROQUIS_AI_MAX_EXPOSURE_CENTS / "
                "MY_CROQUIS_AI_MAX_USD_PER_RUN). Fail closed — soft estimates are not a hard cap."
            ),
        )
    if max_exp <= 0:
        max_exp = max_run
    if max_run > 0 and max_exp > max_run:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Max exposure exceeds per-run Create My Croquis spend limit.",
        )
    return max_exp


def _assert_spend_allowed(db: Session, user: User, *, max_exposure_cents: int) -> None:
    settings = get_settings()
    ceiling_cents = int(round(float(settings.my_croquis_ai_spend_ceiling_usd or 0) * 100))
    if ceiling_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis AI spend ceiling is 0 (fail closed).",
        )
    max_day = int(round(float(settings.my_croquis_ai_max_usd_per_user_day or 0) * 100))
    if max_day <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis daily spend limit is unset (fail closed).",
        )
    max_run = int(round(float(settings.my_croquis_ai_max_usd_per_run or 0) * 100))
    if max_run <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis per-run spend limit is unset (fail closed).",
        )
    if max_exposure_cents > max_run:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Max exposure exceeds per-run Create My Croquis spend limit.",
        )
    day_ago = _utcnow() - timedelta(days=1)
    day_spent = _sum_billable_cents(db, owner_id=user.id, since=day_ago)
    if day_spent + max_exposure_cents > max_day:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis AI spend limit reached.",
        )
    total_spent = _sum_billable_cents(db, owner_id=None, since=None)
    if total_spent + max_exposure_cents > ceiling_cents:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator Create My Croquis AI spend ceiling reached.",
        )
    max_gens = int(settings.my_croquis_ai_max_generations_per_user_day or 0)
    if max_gens > 0 and _count_generations_today(db, user) >= max_gens:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis generation limit reached.",
        )


def _assert_no_open_reconciliation(db: Session, *, croquis_id: uuid.UUID, source_asset_id: uuid.UUID) -> None:
    """Block any new paid attempt while croquis/source has unresolved provider outcome."""
    open_recon = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.status == RESERVATION_RECONCILIATION,
            (
                (PersonalCroquisSpendReservation.croquis_id == croquis_id)
                | (PersonalCroquisSpendReservation.source_asset_id == source_asset_id)
            ),
        )
        .first()
    )
    if open_recon is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Previous generate needs operator reconciliation for this croquis/source — "
                "no new paid attempt until resolved. Idempotent replay of the same key only."
            ),
        )
    open_ver = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.croquis_id == croquis_id,
            PersonalCroquisVersion.status == VERSION_STATUS_RECONCILIATION,
        )
        .first()
    )
    if open_ver is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Previous generate needs operator reconciliation for this croquis — "
                "no new paid attempt until resolved."
            ),
        )


def _get_valid_bound_ai_consent(
    db: Session,
    user: User,
    consent_id: uuid.UUID,
    *,
    croquis_id: uuid.UUID,
    source_asset_id: uuid.UUID,
) -> tuple[UserConsentEvent, PersonalCroquisAiConsentBinding]:
    settings = get_settings()
    # Re-validate adults attestation is still current.
    attestation = pcs._latest_adults_attestation(db, user)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only beta attestation is required before generate.",
        )
    row = (
        db.query(UserConsentEvent)
        .filter(
            UserConsentEvent.id == consent_id,
            UserConsentEvent.owner_id == user.id,
            UserConsentEvent.purpose == PURPOSE_CROQUIS_AI_PROVIDER,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid AI-provider consent is required before generate.",
        )
    max_age = int(settings.my_croquis_ai_consent_max_age_seconds or 3600)
    if (_utcnow() - row.created_at).total_seconds() > max_age:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent has expired; acknowledge again before generate.",
        )
    if row.consent_version != settings.my_croquis_ai_consent_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent version is outdated.",
        )
    # Approved notice hash must still match configured (fail closed if empty).
    approved = (settings.my_croquis_ai_notice_text or "").strip()
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI-provider notice text is not approved.",
        )
    import hashlib

    expected_hash = hashlib.sha256(approved.encode("utf-8")).hexdigest()
    if row.text_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent notice hash does not match approved notice text.",
        )
    binding = (
        db.query(PersonalCroquisAiConsentBinding)
        .filter(
            PersonalCroquisAiConsentBinding.consent_id == consent_id,
            PersonalCroquisAiConsentBinding.owner_id == user.id,
            PersonalCroquisAiConsentBinding.croquis_id == croquis_id,
            PersonalCroquisAiConsentBinding.source_asset_id == source_asset_id,
        )
        .one_or_none()
    )
    if binding is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent is not bound to this croquis source photo.",
        )
    if binding.notice_text_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bound AI consent notice hash is stale.",
        )
    return row, binding


def _replay_or_conflict(
    db: Session, user: User, key: str, *, croquis_id: uuid.UUID, source_asset_id: uuid.UUID
) -> PersonalCroquisVersion | None:
    existing_res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.owner_id == user.id,
            PersonalCroquisSpendReservation.idempotency_key == key,
        )
        .one_or_none()
    )
    if existing_res is not None and existing_res.status == RESERVATION_RECONCILIATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Previous generate needs reconciliation — no automatic paid retry. "
                "Operator review required; do not mint a new idempotency key."
            ),
        )

    existing = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.owner_id == user.id,
            PersonalCroquisVersion.idempotency_key == key,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.status == VERSION_STATUS_RECONCILIATION:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Previous generate needs reconciliation — no automatic paid retry. "
                    "Operator review required; do not mint a new idempotency key."
                ),
            )
        if existing.status == VERSION_STATUS_FAILED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Previous generate failed for this idempotency_key — use a new key to retry.",
            )
        if existing.status == VERSION_STATUS_REJECTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Previous generate was rejected for this idempotency_key — use a new key.",
            )
        return existing

    # Different key: still block if croquis/source has unresolved reconciliation.
    _assert_no_open_reconciliation(db, croquis_id=croquis_id, source_asset_id=source_asset_id)

    if existing_res is not None:
        if existing_res.version_id:
            ver = db.get(PersonalCroquisVersion, existing_res.version_id)
            if ver is not None and ver.status in (
                VERSION_STATUS_GENERATING,
                VERSION_STATUS_AWAITING_REVIEW,
                VERSION_STATUS_ACCEPTED,
            ):
                return ver
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already reserved; retry with the same key after settle or a new key.",
        )
    return None


def enqueue_personal_croquis_generate(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    ai_consent_id: uuid.UUID,
    idempotency_key: str,
) -> PersonalCroquisVersion:
    """Reserve max exposure + enqueue AIJob. Does not call the provider."""
    _require_ai_gate()
    key = (idempotency_key or "").strip()
    if not key or len(key) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key is required (1–128 chars).",
        )

    croquis = pcs.get_owned_croquis(db, user, croquis_id)
    if croquis.source_asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source photo required before generate.",
        )
    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")

    source_asset_id = croquis.source_asset_id
    ai_consent, _binding = _get_valid_bound_ai_consent(
        db,
        user,
        ai_consent_id,
        croquis_id=croquis.id,
        source_asset_id=source_asset_id,
    )
    settings = get_settings()
    estimate = max(1, int(settings.my_croquis_ai_estimate_cents or 0))
    max_exposure = resolve_max_exposure_cents()

    replay = _replay_or_conflict(
        db, user, key, croquis_id=croquis.id, source_asset_id=source_asset_id
    )
    if replay is not None:
        return replay

    _lock_spend_tx(db, user.id)
    replay = _replay_or_conflict(
        db, user, key, croquis_id=croquis.id, source_asset_id=source_asset_id
    )
    if replay is not None:
        return replay
    _assert_no_open_reconciliation(db, croquis_id=croquis.id, source_asset_id=source_asset_id)
    _assert_spend_allowed(db, user, max_exposure_cents=max_exposure)

    max_ver = (
        db.query(func.max(PersonalCroquisVersion.version))
        .filter(PersonalCroquisVersion.croquis_id == croquis.id)
        .scalar()
    )
    next_ver = int(max_ver or 0) + 1
    version_id = uuid.uuid4()
    job_id = uuid.uuid4()
    version = PersonalCroquisVersion(
        id=version_id,
        croquis_id=croquis.id,
        owner_id=user.id,
        version=next_ver,
        status=VERSION_STATUS_GENERATING,
        ai_consent_id=ai_consent.id,
        idempotency_key=key,
        geometry_profile=GEOMETRY_PROFILE_V1,
        provider_job_id=str(job_id),
    )
    reservation = PersonalCroquisSpendReservation(
        id=uuid.uuid4(),
        owner_id=user.id,
        croquis_id=croquis.id,
        source_asset_id=source_asset_id,
        version_id=version_id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
        max_exposure_cents=max_exposure,
        provider_called=False,
    )
    job = AIJob(
        id=job_id,
        user_id=user.id,
        design_id=None,
        job_type=CROQUIS_GENERATE_JOB_TYPE,
        status="queued",
        input_data={
            "croquis_id": str(croquis.id),
            "version_id": str(version_id),
            "source_asset_id": str(source_asset_id),
            "reservation_id": str(reservation.id),
            "idempotency_key": key,
            "estimate_cents": estimate,
            "max_exposure_cents": max_exposure,
            "geometry_profile": GEOMETRY_PROFILE_V1,
            "ai_consent_id": str(ai_consent.id),
        },
    )
    db.add(version)
    db.add(reservation)
    db.add(job)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency or version conflict.",
        ) from exc
    db.refresh(version)
    return version


generate_personal_croquis_version = enqueue_personal_croquis_generate


def accept_personal_croquis_version(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    version: int,
) -> PersonalCroquisVersion:
    row = pcs.get_exact_version(db, user, croquis_id, version)
    if row.status == VERSION_STATUS_ACCEPTED:
        return row
    if row.status != VERSION_STATUS_AWAITING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version status {row.status} cannot be accepted.",
        )
    if row.generated_asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version has no generated asset to accept.",
        )
    croquis = pcs.get_owned_croquis(db, user, croquis_id, include_archived=True)
    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")
    row.status = VERSION_STATUS_ACCEPTED
    row.accepted_at = _utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def reject_personal_croquis_version(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    version: int,
) -> PersonalCroquisVersion:
    # Lock version row so worker CAS cannot race past reject.
    row = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.croquis_id == croquis_id,
            PersonalCroquisVersion.owner_id == user.id,
            PersonalCroquisVersion.version == version,
        )
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        # Ownership check for 404 semantics
        pcs.get_owned_croquis(db, user, croquis_id, include_archived=True, include_erased=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis version not found")
    if row.status == VERSION_STATUS_REJECTED:
        return row
    if row.status == VERSION_STATUS_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted versions are immutable and cannot be rejected.",
        )
    if row.status not in (VERSION_STATUS_AWAITING_REVIEW, VERSION_STATUS_GENERATING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version status {row.status} cannot be rejected.",
        )
    res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.version_id == row.id,
            PersonalCroquisSpendReservation.owner_id == user.id,
        )
        .with_for_update()
        .one_or_none()
    )
    orphan_asset_id = row.generated_asset_id
    if res is not None and res.status == RESERVATION_OPEN and not res.provider_called:
        res.status = RESERVATION_RELEASED
        res.actual_cost_cents = 0
        db.add(res)
        if row.provider_job_id:
            try:
                job_uuid = uuid.UUID(row.provider_job_id)
            except ValueError:
                job_uuid = None
            if job_uuid:
                job = db.get(AIJob, job_uuid)
                if job is not None and job.status in ("queued", "claimed", "running"):
                    job.status = "failed"
                    job.error_message = "Rejected by owner before provider submission."
                    db.add(job)
    # If provider already called / settled, keep spend exposure; discard preview asset.
    row.status = VERSION_STATUS_REJECTED
    row.generated_asset_id = None
    db.add(row)
    db.commit()
    if orphan_asset_id is not None:
        _safe_delete_generated_asset(db, orphan_asset_id)
    db.refresh(row)
    return row


def _safe_delete_generated_asset(db: Session, asset_id: uuid.UUID) -> None:
    from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
    from app.storage.local import LocalStorageBackend

    asset = db.get(PrivateMediaAsset, asset_id)
    if asset is None or asset.kind != KIND_CROQUIS_GENERATED:
        return
    key = asset.storage_key
    db.delete(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        return
    try:
        LocalStorageBackend().delete_private_croquis_file(key=key)
    except Exception:
        pass
