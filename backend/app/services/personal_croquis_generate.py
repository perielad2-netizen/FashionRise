"""Create My Croquis Stage C — generate + spend reservation protocol.

See design §9.2. Defaults fail closed (AI gate OFF, spend ceiling 0).
No automatic paid retries. Idempotent by (owner_id, idempotency_key).
"""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.personal_croquis import (
    VERSION_STATUS_ACCEPTED,
    VERSION_STATUS_FAILED,
    VERSION_STATUS_GENERATING,
    VERSION_STATUS_RECONCILIATION,
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
from app.models.user import User
from app.models.user_consent_event import PURPOSE_CROQUIS_AI_PROVIDER, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_provider import (
    GEOMETRY_PROFILE_V1,
    CroquisProvider,
    ProviderNotAvailableError,
    get_croquis_provider,
)
from app.storage.local import LocalStorageBackend

# Open + reconciliation count against ceilings (unknown outcomes remain charged).
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
    # Session-level advisory lock keyed by user UUID bits (concurrency-safe spend).
    key = int(user_id.int % (2**63 - 1))
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})


def _sum_billable_cents(db: Session, *, owner_id: uuid.UUID | None, since: datetime | None) -> int:
    # Open/reconciliation use estimate; settled uses actual when present (fail-closed).
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


def _store_generated_asset(
    db: Session,
    user: User,
    *,
    png_bytes: bytes,
) -> PrivateMediaAsset:
    asset_id = uuid.uuid4()
    storage_key = f"croquis/{user.id}/{asset_id}.png"
    storage = LocalStorageBackend()
    storage.save_private_croquis_file(
        key=storage_key, data=io.BytesIO(png_bytes), content_type="image/png"
    )
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        width, height = img.size
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=user.id,
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


def generate_personal_croquis_version(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    ai_consent_id: uuid.UUID,
    idempotency_key: str,
    provider: CroquisProvider | None = None,
) -> PersonalCroquisVersion:
    """Consent + gate + spend-reservation generate. Idempotent on (owner, key)."""
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
        estimate = 1  # never reserve $0 when gate is intentionally on for tests

    # Idempotent replay / no auto paid retry for unknown outcomes.
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
        return existing

    if existing_res is not None:
        if existing_res.version_id:
            ver = db.get(PersonalCroquisVersion, existing_res.version_id)
            if ver is not None and ver.status == VERSION_STATUS_ACCEPTED:
                return ver
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key already reserved; retry with the same key after settle or a new key.",
        )

    _advisory_lock_user(db, user.id)
    _assert_spend_allowed(db, user, estimate_cents=estimate)

    max_ver = (
        db.query(func.max(PersonalCroquisVersion.version))
        .filter(PersonalCroquisVersion.croquis_id == croquis.id)
        .scalar()
    )
    next_ver = int(max_ver or 0) + 1
    version = PersonalCroquisVersion(
        id=uuid.uuid4(),
        croquis_id=croquis.id,
        owner_id=user.id,
        version=next_ver,
        status=VERSION_STATUS_GENERATING,
        ai_consent_id=ai_consent.id,
        idempotency_key=key,
        geometry_profile=GEOMETRY_PROFILE_V1,
    )
    reservation = PersonalCroquisSpendReservation(
        id=uuid.uuid4(),
        owner_id=user.id,
        croquis_id=croquis.id,
        version_id=version.id,
        idempotency_key=key,
        status=RESERVATION_OPEN,
        estimate_cents=estimate,
        provider_called=False,
    )
    db.add(version)
    db.add(reservation)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency or version conflict.",
        ) from exc

    # Commit reservation before provider so open spend counts under concurrency.
    db.commit()
    db.refresh(version)
    db.refresh(reservation)

    source_path = pcs.resolve_croquis_asset_file(db, user, croquis.source_asset_id)
    source_bytes = source_path.read_bytes()
    adapter = provider or get_croquis_provider()

    try:
        # Mark provider_called only once we are about to invoke the adapter.
        reservation.provider_called = True
        db.add(reservation)
        db.commit()

        result = adapter.generate_line_art(source_bytes)

        asset = _store_generated_asset(db, user, png_bytes=result.png_bytes)
        version.generated_asset_id = asset.id
        version.status = VERSION_STATUS_ACCEPTED
        version.accepted_at = _utcnow()
        version.provider_job_id = result.provider_job_id
        version.cost_cents = int(result.cost_cents)
        version.prompt_version = result.prompt_version
        version.geometry_profile = result.geometry_profile or GEOMETRY_PROFILE_V1
        reservation.status = RESERVATION_SETTLED
        reservation.actual_cost_cents = int(result.cost_cents)
        reservation.version_id = version.id
        db.add(version)
        db.add(reservation)
        db.commit()
        db.refresh(version)
        return version
    except ProviderNotAvailableError as exc:
        # Provider never reached a paid endpoint — release $0.
        reservation.status = RESERVATION_RELEASED
        reservation.actual_cost_cents = 0
        reservation.provider_called = False
        reservation.error_detail = str(exc)
        version.status = VERSION_STATUS_FAILED
        db.add(reservation)
        db.add(version)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except TimeoutError as exc:
        # Unknown outcome after send — hold estimate against ceiling; no auto retry.
        reservation.status = RESERVATION_RECONCILIATION
        reservation.error_detail = str(exc)
        version.status = VERSION_STATUS_RECONCILIATION
        db.add(reservation)
        db.add(version)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Provider outcome unknown — reservation held for reconciliation. "
                "No automatic paid retry."
            ),
        ) from exc
    except Exception as exc:
        if reservation.provider_called:
            reservation.status = RESERVATION_RECONCILIATION
            reservation.error_detail = str(exc)[:2000]
            version.status = VERSION_STATUS_RECONCILIATION
            db.add(reservation)
            db.add(version)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Provider failure after send — reconciliation required; no automatic retry.",
            ) from exc
        reservation.status = RESERVATION_RELEASED
        reservation.actual_cost_cents = 0
        reservation.error_detail = str(exc)[:2000]
        version.status = VERSION_STATUS_FAILED
        db.add(reservation)
        db.add(version)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Create My Croquis generation failed before provider spend.",
        ) from exc
