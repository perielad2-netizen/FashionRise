"""Offline retention / erasure sweeper for Create My Croquis Stage A.

Deterministic, bounded, dry-run capable. Must NOT be installed as a production
timer by Stage A. Does not claim that backups/snapshots are purged.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.personal_croquis import (
    STATUS_ERASED,
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import KIND_CROQUIS_SOURCE, PrivateMediaAsset
from app.models.private_media_cleanup import PrivateMediaCleanupQueue
from app.storage.croquis_unlink import CroquisUnlinkOutcome
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class RetentionSweepResult:
    dry_run: bool
    examined: int = 0
    eligible_source_expiry: int = 0
    eligible_abandoned: int = 0
    eligible_accepted_source: int = 0
    queue_processed: int = 0
    bytes_unlinked: int = 0
    already_absent: int = 0
    failures: int = 0
    unsafe: int = 0
    asset_ids_touched: list[str] = field(default_factory=list)


def _unlink_croquis(storage_key: str) -> CroquisUnlinkOutcome:
    storage = LocalStorageBackend()
    try:
        return storage.delete_private_croquis_file(key=storage_key)
    except (ValueError, OSError) as exc:
        logger.warning(
            "croquis_retention_unlink_failed err_type=%s",
            type(exc).__name__,
        )
        # ValueError from validation → unsafe; OSError → failed
        if isinstance(exc, ValueError):
            return CroquisUnlinkOutcome.UNSAFE
        return CroquisUnlinkOutcome.FAILED


def _mark_source_for_purge(
    db: Session,
    asset: PrivateMediaAsset,
    *,
    reason: str,
    dry_run: bool,
    result: RetentionSweepResult,
) -> None:
    result.asset_ids_touched.append(str(asset.id))
    if dry_run:
        return
    now = _utcnow()
    asset.erase_requested_at = asset.erase_requested_at or now
    asset.deleted_at = asset.deleted_at or now
    db.add(asset)
    # Clear croquis source FK references without remapping generated pins.
    croquis_rows = (
        db.query(PersonalCroquis)
        .filter(PersonalCroquis.source_asset_id == asset.id)
        .all()
    )
    for croquis in croquis_rows:
        croquis.source_asset_id = None
        db.add(croquis)
    existing = (
        db.query(PrivateMediaCleanupQueue)
        .filter(
            PrivateMediaCleanupQueue.asset_id == asset.id,
            PrivateMediaCleanupQueue.processed_at.is_(None),
        )
        .first()
    )
    if existing is None:
        db.add(
            PrivateMediaCleanupQueue(
                id=uuid.uuid4(),
                owner_id=asset.owner_id,
                asset_id=asset.id,
                storage_key=asset.storage_key,
                reason=reason,
            )
        )


def _find_abandoned_sources(db: Session, *, now: datetime, limit: int) -> list[PrivateMediaAsset]:
    settings = get_settings()
    cutoff = now - timedelta(hours=settings.my_croquis_abandoned_upload_hours)
    candidates = (
        db.query(PrivateMediaAsset)
        .filter(
            PrivateMediaAsset.kind == KIND_CROQUIS_SOURCE,
            PrivateMediaAsset.bytes_purged_at.is_(None),
            PrivateMediaAsset.created_at < cutoff,
        )
        .order_by(PrivateMediaAsset.created_at.asc())
        .limit(limit * 4)
        .all()
    )
    out: list[PrivateMediaAsset] = []
    for asset in candidates:
        croquis = (
            db.query(PersonalCroquis)
            .filter(PersonalCroquis.source_asset_id == asset.id)
            .first()
        )
        if croquis is None:
            out.append(asset)
        else:
            accepted = (
                db.query(PersonalCroquisVersion)
                .filter(
                    PersonalCroquisVersion.croquis_id == croquis.id,
                    PersonalCroquisVersion.status == VERSION_STATUS_ACCEPTED,
                )
                .first()
            )
            if accepted is None:
                out.append(asset)
        if len(out) >= limit:
            break
    return out


def _find_max_age_sources(db: Session, *, now: datetime, limit: int) -> list[PrivateMediaAsset]:
    settings = get_settings()
    cutoff = now - timedelta(days=settings.my_croquis_source_retention_days)
    return (
        db.query(PrivateMediaAsset)
        .filter(
            PrivateMediaAsset.kind == KIND_CROQUIS_SOURCE,
            PrivateMediaAsset.bytes_purged_at.is_(None),
            PrivateMediaAsset.created_at < cutoff,
        )
        .order_by(PrivateMediaAsset.created_at.asc())
        .limit(limit)
        .all()
    )


def _find_accepted_sources_to_purge(
    db: Session, *, now: datetime, limit: int
) -> list[PrivateMediaAsset]:
    settings = get_settings()
    cutoff = now - timedelta(hours=settings.my_croquis_accepted_source_purge_hours)
    versions = (
        db.query(PersonalCroquisVersion)
        .filter(
            PersonalCroquisVersion.status == VERSION_STATUS_ACCEPTED,
            PersonalCroquisVersion.accepted_at.isnot(None),
            PersonalCroquisVersion.accepted_at < cutoff,
        )
        .order_by(PersonalCroquisVersion.accepted_at.asc())
        .limit(limit * 4)
        .all()
    )
    out: list[PrivateMediaAsset] = []
    seen: set[uuid.UUID] = set()
    for ver in versions:
        croquis = db.get(PersonalCroquis, ver.croquis_id)
        if croquis is None or croquis.source_asset_id is None:
            continue
        if croquis.source_asset_id in seen:
            continue
        asset = db.get(PrivateMediaAsset, croquis.source_asset_id)
        if asset is None or asset.bytes_purged_at is not None:
            continue
        if asset.kind != KIND_CROQUIS_SOURCE:
            continue
        seen.add(asset.id)
        out.append(asset)
        if len(out) >= limit:
            break
    return out


def process_cleanup_queue(
    db: Session,
    *,
    dry_run: bool,
    limit: int,
    result: RetentionSweepResult,
) -> None:
    """Process pending unlinks with fail-closed semantics.

    - REMOVED / ALREADY_ABSENT → mark processed; set bytes_purged_at when asset known
    - UNSAFE / FAILED → keep queued, record error, increment failures (never purged)
    """
    pending = (
        db.query(PrivateMediaCleanupQueue)
        .filter(PrivateMediaCleanupQueue.processed_at.is_(None))
        .order_by(PrivateMediaCleanupQueue.enqueued_at.asc())
        .limit(limit)
        .all()
    )
    now = _utcnow()
    for item in pending:
        result.examined += 1
        result.queue_processed += 1
        if dry_run:
            continue
        item.attempts = int(item.attempts or 0) + 1
        outcome = _unlink_croquis(item.storage_key)

        if outcome is CroquisUnlinkOutcome.UNSAFE:
            item.last_error = "unsafe_storage_key"
            result.failures += 1
            result.unsafe += 1
            db.add(item)
            continue
        if outcome is CroquisUnlinkOutcome.FAILED:
            item.last_error = "unlink_failed"
            result.failures += 1
            db.add(item)
            continue

        # Success paths: removed or verifiably already absent under private croquis root.
        item.processed_at = now
        item.last_error = None
        if item.asset_id is not None:
            asset = db.get(PrivateMediaAsset, item.asset_id)
            if asset is not None and asset.bytes_purged_at is None:
                asset.bytes_purged_at = now
                db.add(asset)
            if item.asset_id:
                result.asset_ids_touched.append(str(item.asset_id))
        if outcome is CroquisUnlinkOutcome.REMOVED:
            result.bytes_unlinked += 1
        else:
            result.already_absent += 1
        db.add(item)


def run_retention_sweep(
    db: Session,
    *,
    dry_run: bool = True,
    batch_size: int | None = None,
) -> RetentionSweepResult:
    """Run one bounded retention pass. Default dry_run=True (zero writes)."""
    settings = get_settings()
    limit = batch_size if batch_size is not None else settings.my_croquis_cleanup_batch_size
    limit = max(1, min(int(limit), 500))
    result = RetentionSweepResult(dry_run=dry_run)
    now = _utcnow()

    abandoned = _find_abandoned_sources(db, now=now, limit=limit)
    result.eligible_abandoned = len(abandoned)
    for asset in abandoned:
        result.examined += 1
        _mark_source_for_purge(db, asset, reason="abandoned_upload", dry_run=dry_run, result=result)

    max_age = _find_max_age_sources(db, now=now, limit=limit)
    result.eligible_source_expiry = len(max_age)
    for asset in max_age:
        if str(asset.id) in result.asset_ids_touched:
            continue
        result.examined += 1
        _mark_source_for_purge(db, asset, reason="source_max_age", dry_run=dry_run, result=result)

    accepted_sources = _find_accepted_sources_to_purge(db, now=now, limit=limit)
    result.eligible_accepted_source = len(accepted_sources)
    for asset in accepted_sources:
        if str(asset.id) in result.asset_ids_touched:
            continue
        result.examined += 1
        _mark_source_for_purge(
            db, asset, reason="accepted_source_expiry", dry_run=dry_run, result=result
        )

    erased = (
        db.query(PersonalCroquis)
        .filter(
            PersonalCroquis.status == STATUS_ERASED,
            PersonalCroquis.erase_requested_at.isnot(None),
        )
        .limit(limit)
        .all()
    )
    for _croquis in erased:
        result.examined += 1

    if not dry_run:
        db.flush()
    process_cleanup_queue(db, dry_run=dry_run, limit=limit, result=result)

    if not dry_run:
        db.commit()
    return result
