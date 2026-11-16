"""Durable cleanup for FashionRise My Models public upload copies."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.public_media_cleanup import PublicMediaCleanupQueue
from app.storage.croquis_unlink import CroquisUnlinkOutcome
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def enqueue_public_model_cleanup(
    db: Session,
    *,
    owner_id: uuid.UUID,
    storage_key: str,
    reason: str,
    croquis_id: uuid.UUID | None = None,
    gallery_item_id: uuid.UUID | None = None,
) -> PublicMediaCleanupQueue | None:
    """Queue a public model key for durable unlink (same transaction as caller).

    Validates the key shape before enqueue. Idempotent for a pending identical key.
    Returns None when the key is rejected as unsafe (nothing queued).
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
    )
    db.add(row)
    db.flush()
    return row


def attempt_public_cleanup_now(
    db: Session,
    *,
    storage_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    limit: int = 50,
) -> dict:
    """Process pending public cleanup rows (immediate post-commit + sweeper).

    Already-absent files count as success. Failures stay queued with attempts/error.
    """
    q = (
        select(PublicMediaCleanupQueue)
        .where(PublicMediaCleanupQueue.processed_at.is_(None))
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
