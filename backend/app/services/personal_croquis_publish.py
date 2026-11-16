"""Publish an accepted My Model into FashionRise (explicit public consent required)."""

from __future__ import annotations

import hashlib
import io
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.gallery_item import GalleryItem
from app.models.personal_croquis import (
    STATUS_ARCHIVED,
    STATUS_ERASED,
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
)
from app.models.private_media_asset import PrivateMediaAsset
from app.models.user import User
from app.models.user_consent_event import PURPOSE_CROQUIS_PUBLIC_SHARE, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.storage.local import LocalStorageBackend


def gallery_item_for_croquis(db: Session, croquis_id: uuid.UUID) -> GalleryItem | None:
    return db.scalar(select(GalleryItem).where(GalleryItem.croquis_id == croquis_id))


def unlink_public_upload_keys(keys: list[str] | tuple[str, ...] | set[str]) -> None:
    """Best-effort remove of public FashionRise copies (never touches private croquis root)."""
    if not keys:
        return
    storage = LocalStorageBackend()
    for key in keys:
        if not key:
            continue
        try:
            storage.delete_file(key=key)
        except OSError:
            pass


def remove_owned_croquis_gallery_entry(
    db: Session,
    *,
    croquis_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> tuple[bool, str | None]:
    """Delete this owner's FashionRise gallery row for a My Model (no commit).

    Returns ``(removed, public_storage_key)``. ``removed`` is False when already
    unpublished or not owned. Does not touch unrelated gallery entries.
    """
    item = gallery_item_for_croquis(db, croquis_id)
    if item is None or item.user_id != owner_id:
        return False, None
    storage = LocalStorageBackend()
    key = storage.key_from_public_url(item.image_url)
    db.delete(item)
    db.flush()
    return True, key


def public_croquis_gallery_keys_for_owner(db: Session, owner_id: uuid.UUID) -> list[str]:
    """Public upload keys for My Model → FashionRise copies owned by ``owner_id``."""
    storage = LocalStorageBackend()
    rows = db.scalars(
        select(GalleryItem).where(
            GalleryItem.user_id == owner_id,
            GalleryItem.croquis_id.isnot(None),
        )
    ).all()
    keys: list[str] = []
    for row in rows:
        key = storage.key_from_public_url(row.image_url)
        if key:
            keys.append(key)
    return keys


def _record_public_share_consent(
    db: Session,
    user: User,
    *,
    public_share_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> None:
    settings = get_settings()
    if not public_share_attested:
        raise ValidationAppError(
            "Confirm you have the rights to publish this personal model and grant "
            "FashionRise permission to display it publicly."
        )
    expected_version = (settings.croquis_public_share_consent_version or "").strip()
    notice = (settings.croquis_public_share_notice_text or "").strip()
    if not expected_version or not notice:
        raise ValidationAppError("My Model publish consent is not configured on this server yet.")
    if notice_version != expected_version:
        raise ValidationAppError("My Model publish notice version is not current.")
    expected_hash = hashlib.sha256(notice.encode("utf-8")).hexdigest()
    if notice_text_hash.lower() != expected_hash.lower():
        raise ValidationAppError("My Model publish notice text does not match the approved copy.")
    db.add(
        UserConsentEvent(
            id=uuid.uuid4(),
            owner_id=user.id,
            purpose=PURPOSE_CROQUIS_PUBLIC_SHARE,
            consent_version=expected_version,
            adults_attested=False,
            text_hash=expected_hash,
        )
    )
    db.flush()


def _public_still_from_private_asset(db: Session, user: User, asset_id: uuid.UUID) -> str:
    """Copy private generated still into public uploads — never expose private asset URLs."""
    path = pcs.resolve_croquis_asset_file(db, user, asset_id)
    raw = path.read_bytes()
    if not raw:
        raise ValidationAppError("Model image is not available to publish")
    key = f"fashionrise-model-{uuid.uuid4().hex}.png"
    return LocalStorageBackend().save_file(
        key=key, data=io.BytesIO(raw), content_type="image/png"
    )


def publish_personal_croquis(
    db: Session,
    user: User,
    croquis_id: uuid.UUID,
    *,
    public_share_attested: bool,
    notice_version: str,
    notice_text_hash: str,
) -> GalleryItem:
    croquis = pcs.get_owned_croquis(db, user, croquis_id, include_archived=True)
    if croquis.erase_requested_at is not None or croquis.deleted_at is not None:
        raise NotFoundError("Personal model not found")
    if croquis.archived_at is not None or croquis.status == STATUS_ARCHIVED:
        raise ValidationAppError("Unarchive the personal model before publishing to FashionRise")
    if croquis.status == STATUS_ERASED:
        raise NotFoundError("Personal model not found")

    existing = gallery_item_for_croquis(db, croquis.id)
    if existing is not None:
        if existing.user_id != user.id:
            raise ConflictError("Personal model is already on FashionRise")
        # Idempotent re-publish refreshes title / visibility after consent.
        _record_public_share_consent(
            db,
            user,
            public_share_attested=public_share_attested,
            notice_version=notice_version,
            notice_text_hash=notice_text_hash,
        )
        existing.title = (croquis.display_name or "My Model")[:300]
        existing.visibility = "public"
        existing.moderation_status = "ok"
        db.add(existing)
        from app.services.competition_groups import enroll_on_activity

        enroll_on_activity(db, user.id)
        db.commit()
        db.refresh(existing)
        return existing

    latest = pcs.latest_accepted_version(db, user, croquis.id)
    if latest is None or latest.status != VERSION_STATUS_ACCEPTED:
        raise ValidationAppError("Only accepted personal models can be published to FashionRise")
    if latest.generated_asset_id is None:
        raise ValidationAppError("Accepted model image is missing")

    asset = db.get(PrivateMediaAsset, latest.generated_asset_id)
    if asset is None or asset.owner_id != user.id:
        raise ValidationAppError("Accepted model image is missing")
    # Never publish raw source photographs — only the accepted generated still.
    if asset.kind != "croquis_generated":
        raise ValidationAppError("Only accepted generated model stills can be published")

    _record_public_share_consent(
        db,
        user,
        public_share_attested=public_share_attested,
        notice_version=notice_version,
        notice_text_hash=notice_text_hash,
    )
    image_url = _public_still_from_private_asset(db, user, asset.id)
    item = GalleryItem(
        croquis_id=croquis.id,
        user_id=user.id,
        title=(croquis.display_name or "My Model")[:300],
        image_url=image_url,
        visibility="public",
        moderation_status="ok",
    )
    db.add(item)
    from app.services.competition_groups import enroll_on_activity

    enroll_on_activity(db, user.id)
    db.commit()
    db.refresh(item)
    return item


def unpublish_personal_croquis(db: Session, user: User, croquis_id: uuid.UUID) -> PersonalCroquis:
    croquis = pcs.get_owned_croquis(db, user, croquis_id, include_archived=True)
    removed, key = remove_owned_croquis_gallery_entry(
        db, croquis_id=croquis.id, owner_id=user.id
    )
    if not removed:
        raise NotFoundError("Personal model is not on FashionRise")
    db.commit()
    if key:
        unlink_public_upload_keys([key])
    return croquis
