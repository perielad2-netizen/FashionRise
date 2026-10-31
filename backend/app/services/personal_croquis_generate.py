"""Create My Croquis Stage C — enqueue generate + spend reservation + accept/reject.

See design §9.2. Defaults fail closed (AI gate OFF, spend ceiling 0).
Provider work runs in the croquis worker tick — never inline paid HTTP here.
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
from app.models.personal_croquis_spend import (
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


def _get_valid_ai_consent(
    db: Session,
    user: User,
    consent_id: uuid.UUID,
) -> UserConsentEvent:
    settings = get_settings()
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
    age = (_utcnow() - row.created_at).total_seconds()
    if age > max_age:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent has expired; acknowledge again before generate.",
        )
    if row.consent_version != settings.my_croquis_ai_consent_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-provider consent version is outdated.",
        )
    return row


def _advisory_lock_user(db: Session, user_id: uuid.UUID) -> None:
    key = int(user_id.int % (2**63 - 1))
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})


def _sum_billable_cents(db: Session, *, owner_id: uuid.UUID | None, since: datetime | None) -> int:
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
            PersonalCroquisSpendReservation.estimate_cents,
            PersonalCroquisSpendReservation.actual_cost_cents,
        ).where(*clauses)
    ).all()
    total = 0
    for status_s, estimate, actual in rows:
        if status_s == RESERVATION_SETTLED and actual is not None:
            total += int(actual)
        else:
            total += int(estimate or 0)
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


def _assert_spend_allowed(db: Session, user: User, *, estimate_cents: int) -> None:
    settings = get_settings()
    ceiling_cents = int(round(float(settings.my_croquis_ai_spend_ceiling_usd or 0) * 100))
    if ceiling_cents <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis AI spend ceiling is 0 (fail closed).",
        )
    max_run = int(round(float(settings.my_croquis_ai_max_usd_per_run or 0) * 100))
    if max_run > 0 and estimate_cents > max_run:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Estimated cost exceeds per-run Create My Croquis spend limit.",
        )
    day_ago = _utcnow() - timedelta(days=1)
    day_spent = _sum_billable_cents(db, owner_id=user.id, since=day_ago)
    max_day = int(round(float(settings.my_croquis_ai_max_usd_per_user_day or 0) * 100))
    if max_day > 0 and day_spent + estimate_cents > max_day:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Daily Create My Croquis AI spend limit reached.",
        )
    total_spent = _sum_billable_cents(db, owner_id=None, since=None)
    if total_spent + estimate_cents > ceiling_cents:
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


def _replay_or_conflict(
    db: Session, user: User, key: str
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
                "Use a new idempotency_key after operator review."
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
                    "Use a new idempotency_key after operator review."
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
        # generating / awaiting_review / accepted → safe idempotent replay
        return existing

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
    """Reserve spend + enqueue AIJob. Does not call the provider."""
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

    ai_consent = _get_valid_ai_consent(db, user, ai_consent_id)
    settings = get_settings()
    estimate = int(settings.my_croquis_ai_estimate_cents or 0)
    if estimate <= 0:
        estimate = 1

    replay = _replay_or_conflict(db, user, key)
    if replay is not None:
        return replay

    _advisory_lock_user(db, user.id)
    # Re-check after lock (concurrent double-spend).
    replay = _replay_or_conflict(db, user, key)
    if replay is not None:
        return replay
    _assert_spend_allowed(db, user, estimate_cents=estimate)

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
        version_id=version_id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
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
            "source_asset_id": str(croquis.source_asset_id),
            "reservation_id": str(reservation.id),
            "idempotency_key": key,
            "estimate_cents": estimate,
            "geometry_profile": GEOMETRY_PROFILE_V1,
            # Never store image bytes / base64 here.
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


# Back-compat alias used by routes / older tests.
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
    row = pcs.get_exact_version(db, user, croquis_id, version)
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
    # Reject does not mutate earlier accepted pins. Release open reservation if still open
    # and provider was never called; otherwise keep settled/reconciliation accounting.
    res = (
        db.query(PersonalCroquisSpendReservation)
        .filter(
            PersonalCroquisSpendReservation.version_id == row.id,
            PersonalCroquisSpendReservation.owner_id == user.id,
        )
        .one_or_none()
    )
    if res is not None and res.status == RESERVATION_OPEN and not res.provider_called:
        res.status = RESERVATION_RELEASED
        res.actual_cost_cents = 0
        db.add(res)
        # Cancel queued job if present
        if row.provider_job_id:
            try:
                job_uuid = uuid.UUID(row.provider_job_id)
            except ValueError:
                job_uuid = None
            if job_uuid:
                job = db.get(AIJob, job_uuid)
                if job is not None and job.status == "queued":
                    job.status = "failed"
                    job.error_message = "Rejected by owner before provider submission."
                    db.add(job)
    row.status = VERSION_STATUS_REJECTED
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
