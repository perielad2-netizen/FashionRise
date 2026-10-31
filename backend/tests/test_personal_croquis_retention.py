"""Retention sweeper — dry-run, eligibility, bounded cleanup, retry."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta

from PIL import Image

from app.core.config import get_settings
from app.models.personal_croquis import (
    STATUS_UPLOADED,
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import KIND_CROQUIS_SOURCE, PrivateMediaAsset
from app.models.private_media_cleanup import PrivateMediaCleanupQueue
from app.services.personal_croquis_retention import run_retention_sweep
from app.services.personal_croquis_service import prepare_owner_account_croquis_cleanup
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _png(w=16, h=16) -> bytes:
    img = Image.new("RGB", (w, h), (1, 2, 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_source_asset(db_session, owner_id, *, created_at: datetime | None = None) -> PrivateMediaAsset:
    asset_id = uuid.uuid4()
    key = f"croquis/{owner_id}/{asset_id}.png"
    storage = LocalStorageBackend()
    storage.save_private_croquis_file(key=key, data=io.BytesIO(_png()))
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=owner_id,
        kind=KIND_CROQUIS_SOURCE,
        content_type="image/png",
        width=16,
        height=16,
        byte_size=32,
        sha256="a" * 64,
        storage_key=key,
    )
    db_session.add(asset)
    db_session.flush()
    if created_at is not None:
        asset.created_at = created_at
        db_session.add(asset)
        db_session.flush()
    return asset


def test_dry_run_has_zero_writes(client, db_session):
    register_with_invite(client, db_session, "ret_dry@example.com", "ret_dry")
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ret_dry@example.com").one()
    old = datetime.now(UTC) - timedelta(hours=48)
    asset = _make_source_asset(db_session, user.id, created_at=old)
    croquis = PersonalCroquis(
        id=uuid.uuid4(),
        owner_id=user.id,
        display_name="Abandoned",
        source_asset_id=asset.id,
        status=STATUS_UPLOADED,
    )
    db_session.add(croquis)
    db_session.commit()

    before_queue = db_session.query(PrivateMediaCleanupQueue).count()
    key = asset.storage_key
    result = run_retention_sweep(db_session, dry_run=True, batch_size=20)
    assert result.dry_run is True
    assert result.eligible_abandoned >= 1
    assert result.bytes_unlinked == 0
    assert db_session.query(PrivateMediaCleanupQueue).count() == before_queue
    storage = LocalStorageBackend()
    assert storage.resolve_private_croquis_file(key=key) is not None
    asset2 = db_session.get(PrivateMediaAsset, asset.id)
    assert asset2 is not None
    assert asset2.erase_requested_at is None
    assert asset2.bytes_purged_at is None


def test_abandoned_upload_expiry_apply(client, db_session):
    register_with_invite(client, db_session, "ret_ab@example.com", "ret_ab")
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ret_ab@example.com").one()
    old = datetime.now(UTC) - timedelta(hours=48)
    asset = _make_source_asset(db_session, user.id, created_at=old)
    croquis = PersonalCroquis(
        id=uuid.uuid4(),
        owner_id=user.id,
        display_name="Gone",
        source_asset_id=asset.id,
        status=STATUS_UPLOADED,
    )
    db_session.add(croquis)
    db_session.commit()

    result = run_retention_sweep(db_session, dry_run=False, batch_size=20)
    assert result.eligible_abandoned >= 1
    db_session.expire_all()
    asset2 = db_session.get(PrivateMediaAsset, asset.id)
    assert asset2 is not None
    assert asset2.erase_requested_at is not None
    assert asset2.bytes_purged_at is not None
    storage = LocalStorageBackend()
    assert storage.resolve_private_croquis_file(key=asset.storage_key) is None


def test_accepted_source_expiry_rule(client, db_session):
    register_with_invite(client, db_session, "ret_acc@example.com", "ret_acc")
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ret_acc@example.com").one()
    asset = _make_source_asset(db_session, user.id)
    croquis = PersonalCroquis(
        id=uuid.uuid4(),
        owner_id=user.id,
        display_name="Accepted",
        source_asset_id=asset.id,
        status=STATUS_UPLOADED,
    )
    db_session.add(croquis)
    db_session.flush()
    # Generated asset stub (no bytes required for eligibility query)
    gen_id = uuid.uuid4()
    gen_key = f"croquis/{user.id}/{gen_id}.png"
    LocalStorageBackend().save_private_croquis_file(key=gen_key, data=io.BytesIO(_png()))
    gen = PrivateMediaAsset(
        id=gen_id,
        owner_id=user.id,
        kind="croquis_generated",
        content_type="image/png",
        width=16,
        height=16,
        byte_size=16,
        sha256="b" * 64,
        storage_key=gen_key,
    )
    db_session.add(gen)
    db_session.flush()
    accepted_at = datetime.now(UTC) - timedelta(hours=48)
    ver = PersonalCroquisVersion(
        id=uuid.uuid4(),
        croquis_id=croquis.id,
        owner_id=user.id,
        version=1,
        generated_asset_id=gen_id,
        status=VERSION_STATUS_ACCEPTED,
        accepted_at=accepted_at,
        geometry_profile="fit_contain_768x1024_v1",
    )
    db_session.add(ver)
    db_session.commit()

    result = run_retention_sweep(db_session, dry_run=False, batch_size=20)
    assert result.eligible_accepted_source >= 1
    db_session.expire_all()
    croquis2 = db_session.get(PersonalCroquis, croquis.id)
    assert croquis2.source_asset_id is None
    # Generated asset preserved for pins
    assert LocalStorageBackend().resolve_private_croquis_file(key=gen_key) is not None


def test_bounded_cleanup_and_retry_after_failure(client, db_session, monkeypatch):
    register_with_invite(client, db_session, "ret_retry@example.com", "ret_retry")
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ret_retry@example.com").one()
    assets = [_make_source_asset(db_session, user.id) for _ in range(3)]
    db_session.commit()
    for asset in assets:
        db_session.add(
            PrivateMediaCleanupQueue(
                id=uuid.uuid4(),
                owner_id=user.id,
                asset_id=asset.id,
                storage_key=asset.storage_key,
                reason="test",
            )
        )
    db_session.commit()

    # First pass: force unlink failure
    monkeypatch.setattr(
        "app.services.personal_croquis_retention._safe_unlink",
        lambda key: False,
    )
    # And make resolve still find the file
    result1 = run_retention_sweep(db_session, dry_run=False, batch_size=2)
    assert result1.queue_processed == 2
    assert result1.failures >= 1

    monkeypatch.undo()
    result2 = run_retention_sweep(db_session, dry_run=False, batch_size=10)
    assert result2.bytes_unlinked >= 1


def test_account_deletion_snapshots_cleanup_keys(client, db_session):
    register_with_invite(client, db_session, "ret_acct@example.com", "ret_acct")
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ret_acct@example.com").one()
    asset = _make_source_asset(db_session, user.id)
    db_session.commit()
    n = prepare_owner_account_croquis_cleanup(db_session, user.id)
    assert n == 1
    queued = (
        db_session.query(PrivateMediaCleanupQueue)
        .filter(PrivateMediaCleanupQueue.reason == "account_deletion")
        .all()
    )
    assert len(queued) == 1
    assert queued[0].storage_key == asset.storage_key
    # Designs / fabrics untouched — only croquis queue entries
    assert get_settings().my_croquis_upload_enabled is False
