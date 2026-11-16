"""Durable cleanup for FashionRise My Models public upload copies."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.public_media_cleanup import PublicMediaCleanupQueue
from app.storage.croquis_unlink import CroquisUnlinkOutcome
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_QUARANTINED = "quarantined"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _url_sha256(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def enqueue_public_model_cleanup(
    db: Session,
    *,
    owner_id: uuid.UUID,
    storage_key: str,
    reason: str,
    croquis_id: uuid.UUID | None = None,
    gallery_item_id: uuid.UUID | None = None,
    source_url: str | None = None,
) -> PublicMediaCleanupQueue | None:
    """Queue a public model key for durable unlink (same transaction as caller).

    Validates the key shape before enqueue. Idempotent for a pending identical key.
    Returns None when the key is rejected as unsafe — callers should quarantine.
    """
    storage = LocalStorageBackend()
    try:
        safe = storage.validate_fashionrise_model_public_key(storage_key)
    except ValueError:
        logger.warning(
            "public_cleanup_enqueue_rejected owner_id=%s reason=%s",
            owner_id,
            reason,
        )
        return None

    existing = db.scalar(
        select(PublicMediaCleanupQueue).where(
            PublicMediaCleanupQueue.storage_key == safe,
            PublicMediaCleanupQueue.status == STATUS_PENDING,
            PublicMediaCleanupQueue.processed_at.is_(None),
        )
    )
    if existing is not None:
        return existing

    row = PublicMediaCleanupQueue(
        id=uuid.uuid4(),
        owner_id=owner_id,
        croquis_id=croquis_id,
        gallery_item_id=gallery_item_id,
        storage_key=safe,
        reason=reason,
        status=STATUS_PENDING,
        source_url_sha256=_url_sha256(source_url),
    )
    db.add(row)
    db.flush()
    return row


def quarantine_unmappable_public_cleanup(
    db: Session,
    *,
    owner_id: uuid.UUID,
    reason: str,
    croquis_id: uuid.UUID | None = None,
    gallery_item_id: uuid.UUID | None = None,
    source_url: str | None = None,
    detail: str = "unmappable_or_unsafe_public_key",
) -> PublicMediaCleanupQueue:
    """Fail-closed provenance when a public URL/key cannot be safely mapped.

    Never deletes files. Does not mark durable file cleanup as successful.
    """
    # Stable placeholder key — not a deletable public path.
    placeholder = f"quarantine:{gallery_item_id or croquis_id or owner_id}"
    existing = db.scalar(
        select(PublicMediaCleanupQueue).where(
            PublicMediaCleanupQueue.storage_key == placeholder,
            PublicMediaCleanupQueue.status == STATUS_QUARANTINED,
        )
    )
    if existing is not None:
        return existing

    now = _utcnow()
    row = PublicMediaCleanupQueue(
        id=uuid.uuid4(),
        owner_id=owner_id,
        croquis_id=croquis_id,
        gallery_item_id=gallery_item_id,
        storage_key=placeholder,
        reason=reason,
        status=STATUS_QUARANTINED,
        source_url_sha256=_url_sha256(source_url),
        enqueued_at=now,
        processed_at=now,
        attempts=0,
        last_error=detail,
    )
    db.add(row)
    db.flush()
    logger.warning(
        "public_cleanup_quarantined owner_id=%s gallery_item_id=%s reason=%s",
        owner_id,
        gallery_item_id,
        reason,
    )
    return row


def attempt_public_cleanup_now(
    db: Session,
    *,
    storage_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    limit: int = 50,
) -> dict:
    """Process pending public cleanup rows (immediate post-commit + sweeper).

    Already-absent files count as success. Failures stay queued with attempts/error.
    Quarantined rows are never treated as successful file deletion.
    """
    q = (
        select(PublicMediaCleanupQueue)
        .where(
            PublicMediaCleanupQueue.status == STATUS_PENDING,
            PublicMediaCleanupQueue.processed_at.is_(None),
        )
        .order_by(PublicMediaCleanupQueue.enqueued_at.asc())
        .limit(max(1, min(int(limit), 500)))
    )
    if storage_keys:
        keys = [k for k in storage_keys if k]
        if not keys:
            return {"processed": 0, "removed": 0, "absent": 0, "failed": 0, "unsafe": 0}
        q = q.where(PublicMediaCleanupQueue.storage_key.in_(keys))

    pending = list(db.scalars(q).all())
    storage = LocalStorageBackend()
    removed = absent = failed = unsafe = 0
    now = _utcnow()
    for item in pending:
        item.attempts = int(item.attempts or 0) + 1
        outcome = storage.delete_public_fashionrise_model_file(key=item.storage_key)
        if outcome is CroquisUnlinkOutcome.UNSAFE:
            item.last_error = "unsafe_storage_key"
            item.status = STATUS_QUARANTINED
            item.processed_at = now
            unsafe += 1
            failed += 1
            db.add(item)
            continue
        if outcome is CroquisUnlinkOutcome.FAILED:
            item.last_error = "unlink_failed"
            failed += 1
            db.add(item)
            continue
        item.processed_at = now
        item.status = STATUS_DONE
        item.last_error = None
        db.add(item)
        if outcome is CroquisUnlinkOutcome.REMOVED:
            removed += 1
        else:
            absent += 1
    if pending:
        db.commit()
    return {
        "processed": len(pending),
        "removed": removed,
        "absent": absent,
        "failed": failed,
        "unsafe": unsafe,
    }


def process_public_cleanup_queue(db: Session, *, limit: int = 50) -> dict:
    """Background sweeper entrypoint — retries failed public unlinks."""
    return attempt_public_cleanup_now(db, limit=limit)
