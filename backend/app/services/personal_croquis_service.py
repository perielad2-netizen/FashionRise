"""Create My Croquis Stage A — consent, gated upload, ownership, archive/erase.

No provider / paid AI calls. Upload defaults OFF. AI gate remains independent.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.upload_validation import read_stream_with_limit
from app.models.personal_croquis import (
    STATUS_ARCHIVED,
    STATUS_ERASED,
    STATUS_UPLOADED,
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import (
    KIND_CROQUIS_GENERATED,
    KIND_CROQUIS_SOURCE,
    PrivateMediaAsset,
)
from app.models.private_media_cleanup import PrivateMediaCleanupQueue
from app.models.user import User
from app.models.user_consent_event import (
    PURPOSE_ADULTS_BETA,
    PURPOSE_CROQUIS_AI_PROVIDER,
    PURPOSE_CROQUIS_STORAGE,
    UserConsentEvent,
)
from app.services.personal_croquis_image import normalize_croquis_source_bytes
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

_CONTROL = re.compile(r"[\u0000-\u001F\u007F-\u009F\u2028\u2029]")

# Non-authoritative draft markers — never accepted as configured notice text.
_BLOCKED_DRAFT_MARKERS = frozenset(
    {
        "UNAPPROVED_DRAFT_STORAGE_CONSENT_PLACEHOLDER",
        "UNAPPROVED_DRAFT_AI_PROVIDER_CONSENT_PLACEHOLDER",
        "UNAPPROVED_DRAFT_ADULTS_BETA_ATTESTATION_PLACEHOLDER",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _approved_notice_text(*, purpose: str) -> str:
    """Return configured notice text or raise — empty/draft placeholders fail closed."""
    settings = get_settings()
    if purpose == PURPOSE_ADULTS_BETA:
        text = (settings.my_croquis_adults_notice_text or "").strip()
        version = settings.my_croquis_adults_attestation_version
    elif purpose == PURPOSE_CROQUIS_STORAGE:
        text = (settings.my_croquis_storage_notice_text or "").strip()
        version = settings.my_croquis_storage_consent_version
    elif purpose == PURPOSE_CROQUIS_AI_PROVIDER:
        text = (settings.my_croquis_ai_notice_text or "").strip()
        version = settings.my_croquis_ai_consent_version
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown consent purpose.")
    if not text or text in _BLOCKED_DRAFT_MARKERS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Create My Croquis consent collection is not authorized (notice text not approved).",
        )
    # Draft version ids are non-authoritative unless paired with synthetic test fixtures.
    if "draft" in (version or "").lower() and not text.startswith("SYNTHETIC_TEST_"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Create My Croquis consent collection is not authorized (draft notice version).",
        )
    return text


def _require_explicit_ack(
    *,
    purpose: str,
    acknowledged: bool,
    adults_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> tuple[str, str, str]:
    """Validate explicit client acknowledgment against configured approved notice."""
    settings = get_settings()
    if purpose == PURPOSE_ADULTS_BETA:
        expected_version = settings.my_croquis_adults_attestation_version
        if not adults_attested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit adults-only attestation is required.",
            )
    elif purpose == PURPOSE_CROQUIS_STORAGE:
        expected_version = settings.my_croquis_storage_consent_version
        if not acknowledged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit storage consent acknowledgment is required.",
            )
        if not adults_attested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adults-only attestation flag is required on storage consent.",
            )
    elif purpose == PURPOSE_CROQUIS_AI_PROVIDER:
        expected_version = settings.my_croquis_ai_consent_version
        if not acknowledged:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit AI-provider consent acknowledgment is required.",
            )
        if not adults_attested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adults-only attestation flag is required on AI consent.",
            )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown consent purpose.")

    notice = _approved_notice_text(purpose=purpose)
    if notice_version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent notice version is not current.",
        )
    expected_hash = _hash_text(notice)
    if notice_text_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent notice text hash does not match the approved notice.",
        )
    return expected_version, expected_hash, notice


def normalize_croquis_display_name(raw: str | None, fallback: str = "My croquis") -> str:
    settings = get_settings()
    text = (raw or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    if _CONTROL.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display name contains characters that are not allowed.",
        )
    name = " ".join(text.split()).strip()
    if not name:
        name = fallback
    if len(name) > settings.croquis_name_max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Keep the display name to {settings.croquis_name_max_length} characters or fewer.",
        )
    return name


def read_croquis_upload_bytes(stream, max_bytes: int) -> bytes:
    try:
        return read_stream_with_limit(stream, max_bytes)
    except ValueError as exc:
        settings = get_settings()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_croquis_upload_size_mb} MB)",
        ) from exc


def _require_upload_gate() -> None:
    settings = get_settings()
    if not settings.my_croquis_upload_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Create My Croquis photo upload is disabled.",
        )


def record_adults_attestation(
    db: Session,
    user: User,
    *,
    adults_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> UserConsentEvent:
    """Self-attestation only — not independent age verification.

    Requires explicit ``adults_attested=True`` and a hash of the configured
    approved notice. Empty/draft placeholder notices fail closed.
    """
    version, text_hash, _notice = _require_explicit_ack(
        purpose=PURPOSE_ADULTS_BETA,
        acknowledged=True,
        adults_attested=adults_attested,
        notice_version=notice_version,
        notice_text_hash=notice_text_hash,
    )
    row = UserConsentEvent(
        id=uuid.uuid4(),
        owner_id=user.id,
        purpose=PURPOSE_ADULTS_BETA,
        consent_version=version,
        adults_attested=True,
        text_hash=text_hash,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _latest_adults_attestation(db: Session, user: User) -> UserConsentEvent | None:
    settings = get_settings()
    try:
        expected_hash = _hash_text(_approved_notice_text(purpose=PURPOSE_ADULTS_BETA))
    except HTTPException:
        return None
    cutoff = _utcnow() - timedelta(seconds=settings.my_croquis_adults_attestation_max_age_seconds)
    return (
        db.query(UserConsentEvent)
        .filter(
            UserConsentEvent.owner_id == user.id,
            UserConsentEvent.purpose == PURPOSE_ADULTS_BETA,
            UserConsentEvent.adults_attested.is_(True),
            UserConsentEvent.consent_version == settings.my_croquis_adults_attestation_version,
            UserConsentEvent.text_hash == expected_hash,
            UserConsentEvent.created_at >= cutoff,
        )
        .order_by(UserConsentEvent.created_at.desc())
        .first()
    )


def record_storage_consent(
    db: Session,
    user: User,
    *,
    acknowledged: bool,
    adults_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> UserConsentEvent:
    attestation = _latest_adults_attestation(db, user)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only beta attestation is required before storage consent.",
        )
    version, text_hash, _notice = _require_explicit_ack(
        purpose=PURPOSE_CROQUIS_STORAGE,
        acknowledged=acknowledged,
        adults_attested=adults_attested,
        notice_version=notice_version,
        notice_text_hash=notice_text_hash,
    )
    row = UserConsentEvent(
        id=uuid.uuid4(),
        owner_id=user.id,
        purpose=PURPOSE_CROQUIS_STORAGE,
        consent_version=version,
        adults_attested=True,
        text_hash=text_hash,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def record_ai_consent(
    db: Session,
    user: User,
    *,
    acknowledged: bool,
    adults_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> UserConsentEvent:
    """Record AI-provider consent only — Stage A does not execute providers."""
    attestation = _latest_adults_attestation(db, user)
    if attestation is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only beta attestation is required before AI consent.",
        )
    version, text_hash, _notice = _require_explicit_ack(
        purpose=PURPOSE_CROQUIS_AI_PROVIDER,
        acknowledged=acknowledged,
        adults_attested=adults_attested,
        notice_version=notice_version,
        notice_text_hash=notice_text_hash,
    )
    row = UserConsentEvent(
        id=uuid.uuid4(),
        owner_id=user.id,
        purpose=PURPOSE_CROQUIS_AI_PROVIDER,
        consent_version=version,
        adults_attested=True,
        text_hash=text_hash,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _get_valid_storage_consent(
    db: Session,
    user: User,
    consent_id: uuid.UUID,
) -> UserConsentEvent:
    settings = get_settings()
    row = (
        db.query(UserConsentEvent)
        .filter(UserConsentEvent.id == consent_id, UserConsentEvent.owner_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid storage consent is required.",
        )
    if row.purpose != PURPOSE_CROQUIS_STORAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent purpose is not valid for photo storage.",
        )
    if row.consent_version != settings.my_croquis_storage_consent_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage consent version is not current.",
        )
    if not row.adults_attested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults-only attestation is required.",
        )
    try:
        expected_hash = _hash_text(_approved_notice_text(purpose=PURPOSE_CROQUIS_STORAGE))
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Create My Croquis consent collection is not authorized (notice text not approved).",
        ) from exc
    if row.text_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage consent notice is not current.",
        )
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age = _utcnow() - created
    if age > timedelta(seconds=settings.my_croquis_storage_consent_max_age_seconds):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage consent has expired.",
        )
    return row


def _enqueue_cleanup(
    db: Session,
    *,
    owner_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    storage_key: str,
    reason: str,
) -> None:
    db.add(
        PrivateMediaCleanupQueue(
            id=uuid.uuid4(),
            owner_id=owner_id,
            asset_id=asset_id,
            storage_key=storage_key,
            reason=reason,
        )
    )


def _safe_unlink_croquis(storage_key: str) -> bool:
    from app.storage.croquis_unlink import CroquisUnlinkOutcome

    storage = LocalStorageBackend()
    try:
        outcome = storage.delete_private_croquis_file(key=storage_key)
    except ValueError:
        logger.warning("croquis_cleanup_rejected_key asset_namespace=private_croquis")
        return False
    except OSError as exc:
        logger.warning("croquis_cleanup_unlink_failed err_type=%s", type(exc).__name__)
        return False
    return outcome in {CroquisUnlinkOutcome.REMOVED, CroquisUnlinkOutcome.ALREADY_ABSENT}


def upload_source_photo(
    db: Session,
    user: User,
    *,
    raw: bytes,
    declared_content_type: str | None,
    storage_consent_id: uuid.UUID,
    display_name: str | None = None,
) -> PersonalCroquis:
    """Consent-gated source upload. Requires MY_CROQUIS_UPLOAD_ENABLED."""
    _require_upload_gate()
    consent = _get_valid_storage_consent(db, user, storage_consent_id)
    png_bytes, content_type, width, height = normalize_croquis_source_bytes(
        raw, declared_content_type=declared_content_type
    )
    asset_id = uuid.uuid4()
    croquis_id = uuid.uuid4()
    storage_key = f"croquis/{user.id}/{asset_id}.png"
    sha256 = hashlib.sha256(png_bytes).hexdigest()
    storage = LocalStorageBackend()

    wrote = False
    try:
        storage.save_private_croquis_file(
            key=storage_key, data=io.BytesIO(png_bytes), content_type=content_type
        )
        wrote = True
        asset = PrivateMediaAsset(
            id=asset_id,
            owner_id=user.id,
            kind=KIND_CROQUIS_SOURCE,
            content_type=content_type,
            width=width,
            height=height,
            byte_size=len(png_bytes),
            sha256=sha256,
            storage_key=storage_key,
        )
        attestation = _latest_adults_attestation(db, user)
        croquis = PersonalCroquis(
            id=croquis_id,
            owner_id=user.id,
            display_name=normalize_croquis_display_name(display_name),
            source_asset_id=asset_id,
            status=STATUS_UPLOADED,
            storage_consent_id=consent.id,
            adults_attestation_at=attestation.created_at if attestation else _utcnow(),
        )
        db.add(asset)
        db.flush()  # ensure asset exists before croquis FK
        db.add(croquis)
        db.commit()
        db.refresh(croquis)
        return croquis
    except Exception:
        db.rollback()
        if wrote:
            _safe_unlink_croquis(storage_key)
        raise


def list_personal_croquis(db: Session, user: User) -> list[PersonalCroquis]:
    return (
        db.query(PersonalCroquis)
        .filter(
            PersonalCroquis.owner_id == user.id,
            PersonalCroquis.archived_at.is_(None),
            PersonalCroquis.deleted_at.is_(None),
            PersonalCroquis.erase_requested_at.is_(None),
        )
        .order_by(PersonalCroquis.created_at.desc())
        .all()
    )


def get_owned_croquis(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    include_archived: bool = False,
    include_erased: bool = False,
) -> PersonalCroquis:
    q = db.query(PersonalCroquis).filter(
        PersonalCroquis.id == croquis_id,
        PersonalCroquis.owner_id == user.id,
    )
    if not include_erased:
        q = q.filter(
            PersonalCroquis.deleted_at.is_(None),
            PersonalCroquis.erase_requested_at.is_(None),
        )
    if not include_archived:
        q = q.filter(PersonalCroquis.archived_at.is_(None))
    row = q.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")
    return row


def latest_accepted_version(
    db: Session, user: User, croquis_id: uuid.UUID
) -> PersonalCroquisVersion | None:
    return (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.croquis_id == croquis_id,
            PersonalCroquisVersion.owner_id == user.id,
            PersonalCroquisVersion.status == VERSION_STATUS_ACCEPTED,
        )
        .order_by(PersonalCroquisVersion.version.desc())
        .first()
    )


def get_exact_version(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    version: int,
) -> PersonalCroquisVersion:
    # Ownership on croquis first — never leak existence across owners.
    get_owned_croquis(db, user, croquis_id, include_archived=True, include_erased=True)
    row = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.croquis_id == croquis_id,
            PersonalCroquisVersion.owner_id == user.id,
            PersonalCroquisVersion.version == version,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis version not found")
    return row


def get_owned_media_asset(
    db: Session,
    user: User,
    asset_id: uuid.UUID,
    *,
    allow_erased_meta: bool = False,
) -> PrivateMediaAsset:
    row = (
        db.query(PrivateMediaAsset)
        .filter(PrivateMediaAsset.id == asset_id, PrivateMediaAsset.owner_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if not allow_erased_meta and (
        row.erase_requested_at is not None or row.bytes_purged_at is not None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return row


def resolve_croquis_asset_file(db: Session, user: User, asset_id: uuid.UUID) -> Path:
    row = get_owned_media_asset(db, user, asset_id, allow_erased_meta=False)
    if row.bytes_purged_at is not None or row.erase_requested_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    storage = LocalStorageBackend()
    path = storage.resolve_private_croquis_file(key=row.storage_key)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    try:
        path.resolve().relative_to(storage.public_upload_root())
    except ValueError:
        return path
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")


def archive_croquis(db: Session, user: User, croquis_id: uuid.UUID) -> PersonalCroquis:
    row = get_owned_croquis(db, user, croquis_id, include_archived=False)
    now = _utcnow()
    row.archived_at = now
    row.status = STATUS_ARCHIVED
    row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def request_permanent_erase(db: Session, user: User, croquis_id: uuid.UUID) -> PersonalCroquis:
    """Mark croquis + related assets for erase; enqueue filesystem cleanup.

    Idempotent: repeat calls on an already-erased croquis succeed without remapping.
    Does not mutate design drawing data or remap historical pins.
    """
    row = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.id == croquis_id, PersonalCroquis.owner_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")

    now = _utcnow()
    if row.erase_requested_at is not None:
        db.refresh(row)
        return row

    row.erase_requested_at = now
    row.deleted_at = now
    row.status = STATUS_ERASED
    row.updated_at = now

    asset_ids: set[uuid.UUID] = set()
    if row.source_asset_id:
        asset_ids.add(row.source_asset_id)
    versions = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.croquis_id == row.id,
            PersonalCroquisVersion.owner_id == user.id,
        )
        .all()
    )
    for ver in versions:
        if ver.generated_asset_id:
            asset_ids.add(ver.generated_asset_id)

    for aid in asset_ids:
        asset = (
            db.query(PrivateMediaAsset)
            .filter(PrivateMediaAsset.id == aid, PrivateMediaAsset.owner_id == user.id)
            .first()
        )
        if asset is None:
            continue
        if asset.erase_requested_at is None:
            asset.erase_requested_at = now
            asset.deleted_at = now
            db.add(asset)
        if asset.bytes_purged_at is None:
            _enqueue_cleanup(
                db,
                owner_id=user.id,
                asset_id=asset.id,
                storage_key=asset.storage_key,
                reason="permanent_erase",
            )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def insert_accepted_version_for_tests(
    db: Session,
    user: User,
    croquis: PersonalCroquis,
    *,
    generated_png: bytes,
    geometry_profile: str = "fit_contain_768x1024_v1",
) -> PersonalCroquisVersion:
    """Internal helper used by tests / Stage B prep — not a public generate endpoint.

    Allocates ``version = max+1`` with a new immutable generated asset.
    """
    if croquis.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Croquis not found")
    asset_id = uuid.uuid4()
    storage_key = f"croquis/{user.id}/{asset_id}.png"
    storage = LocalStorageBackend()
    storage.save_private_croquis_file(
        key=storage_key, data=io.BytesIO(generated_png), content_type="image/png"
    )
    # Probe dimensions from PNG without trusting caller.
    from PIL import Image

    with Image.open(io.BytesIO(generated_png)) as img:
        width, height = img.size
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=user.id,
        kind=KIND_CROQUIS_GENERATED,
        content_type="image/png",
        width=width,
        height=height,
        byte_size=len(generated_png),
        sha256=hashlib.sha256(generated_png).hexdigest(),
        storage_key=storage_key,
    )
    db.add(asset)
    db.flush()

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
        generated_asset_id=asset_id,
        status=VERSION_STATUS_ACCEPTED,
        geometry_profile=geometry_profile,
        accepted_at=_utcnow(),
    )
    db.add(version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _safe_unlink_croquis(storage_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version identity conflict.",
        ) from exc
    db.refresh(version)
    return version


def prepare_owner_account_croquis_cleanup(db: Session, owner_id: uuid.UUID) -> int:
    """Snapshot croquis storage keys into the cleanup queue (same DB transaction).

    **Does not commit.** Caller must include this in the same successful
    transaction as account deletion. If that transaction rolls back, erase
    markers and queue rows roll back with it — the sweeper must not delete
    an active user's photos after a failed account deletion.

    Queue rows intentionally have no FK to ``users``, so after a successful
    commit that deletes the user, key metadata remains for filesystem unlink.
    Does not modify designs or fabric assets.
    """
    assets = (
        db.query(PrivateMediaAsset)
        .filter(PrivateMediaAsset.owner_id == owner_id, PrivateMediaAsset.bytes_purged_at.is_(None))
        .all()
    )
    count = 0
    now = _utcnow()
    for asset in assets:
        asset.erase_requested_at = asset.erase_requested_at or now
        asset.deleted_at = asset.deleted_at or now
        _enqueue_cleanup(
            db,
            owner_id=owner_id,
            asset_id=asset.id,
            storage_key=asset.storage_key,
            reason="account_deletion",
        )
        count += 1
        db.add(asset)
    db.flush()
    return count
