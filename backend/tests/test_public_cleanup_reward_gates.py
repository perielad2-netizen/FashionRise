"""Durable public My Models cleanup + FashionRise Stars reward safety gates."""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models.competition import CompetitionAward, StarPayout
from app.models.gallery_item import GalleryItem
from app.models.personal_croquis import (
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.models.public_media_cleanup import PublicMediaCleanupQueue
from app.models.user import User
from app.services import public_media_cleanup as pmc
from app.services.competition_awards import credit_payout_idempotent, tick_competitions
from app.services.competition_clock import competition_week_start, previous_week_start
from app.services.login_streak import STREAK_REWARD_STARS, record_daily_checkin
from app.storage.croquis_unlink import CroquisUnlinkOutcome
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _user(db, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 96), color=(20, 90, 140)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_accepted_croquis(db, user: User, *, name: str = "Model") -> PersonalCroquis:
    storage = LocalStorageBackend()
    asset_id = uuid.uuid4()
    key = f"croquis/{user.id}/{asset_id}.png"
    raw = _png_bytes()
    storage.save_private_croquis_file(key=key, data=io.BytesIO(raw), content_type="image/png")
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=user.id,
        kind=KIND_CROQUIS_GENERATED,
        content_type="image/png",
        width=64,
        height=96,
        byte_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        storage_key=key,
    )
    croquis = PersonalCroquis(
        id=uuid.uuid4(),
        owner_id=user.id,
        display_name=name,
        status="uploaded",
    )
    db.add_all([asset, croquis])
    db.flush()
    db.add(
        PersonalCroquisVersion(
            id=uuid.uuid4(),
            croquis_id=croquis.id,
            owner_id=user.id,
            version=1,
            generated_asset_id=asset.id,
            status=VERSION_STATUS_ACCEPTED,
        )
    )
    db.commit()
    return croquis


def _publish(client, tokens, croquis_id: uuid.UUID) -> dict:
    settings = get_settings()
    digest = hashlib.sha256(settings.croquis_public_share_notice_text.encode("utf-8")).hexdigest()
    res = client.post(
        f"/api/v1/personal-croquis/{croquis_id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": digest,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_unpublish_removes_public_copy(client, db_session):
    tokens = register_with_invite(client, db_session, "uc1@example.com", "uc1")
    user = _user(db_session, "uc1@example.com")
    croquis = _seed_accepted_croquis(db_session, user)
    item = _publish(client, tokens, croquis.id)
    key = LocalStorageBackend().key_from_public_url(item["image_url"])
    assert key and LocalStorageBackend().resolve_existing_file(key=key) is not None

    unpub = client.delete(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
    )
    assert unpub.status_code == 200, unpub.text
    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is None
    assert LocalStorageBackend().resolve_existing_file(key=key) is None
    queued = db_session.scalars(
        select(PublicMediaCleanupQueue).where(PublicMediaCleanupQueue.storage_key == key)
    ).all()
    assert queued and all(q.processed_at is not None for q in queued)


def test_permanent_erase_removes_public_copy(client, db_session):
    tokens = register_with_invite(client, db_session, "uc2@example.com", "uc2")
    user = _user(db_session, "uc2@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Erase")
    item = _publish(client, tokens, croquis.id)
    key = LocalStorageBackend().key_from_public_url(item["image_url"])
    assert LocalStorageBackend().resolve_existing_file(key=key) is not None

    erased = client.delete(f"/api/v1/personal-croquis/{croquis.id}", headers=_auth(tokens))
    assert erased.status_code == 200, erased.text
    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is None
    assert LocalStorageBackend().resolve_existing_file(key=key) is None


def test_account_deletion_removes_public_copy(client, db_session):
    tokens = register_with_invite(client, db_session, "uc3@example.com", "uc3")
    user = _user(db_session, "uc3@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Acct")
    item = _publish(client, tokens, croquis.id)
    key = LocalStorageBackend().key_from_public_url(item["image_url"])
    assert LocalStorageBackend().resolve_existing_file(key=key) is not None

    deleted = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_auth(tokens),
        json={"confirm": "DELETE"},
    )
    assert deleted.status_code == 204, deleted.text
    assert LocalStorageBackend().resolve_existing_file(key=key) is None
    # Cleanup rows survive without a user FK.
    rows = db_session.scalars(
        select(PublicMediaCleanupQueue).where(PublicMediaCleanupQueue.storage_key == key)
    ).all()
    assert rows and all(r.processed_at is not None for r in rows)


def test_fs_failure_keeps_queue_and_retry_succeeds(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "uc4@example.com", "uc4")
    user = _user(db_session, "uc4@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Retry")
    item = _publish(client, tokens, croquis.id)
    key = LocalStorageBackend().key_from_public_url(item["image_url"])
    assert key

    # First immediate attempt fails; queue stays pending; file still present.
    with monkeypatch.context() as m:
        m.setattr(
            LocalStorageBackend,
            "delete_public_fashionrise_model_file",
            lambda self, *, key: CroquisUnlinkOutcome.FAILED,
        )
        unpub = client.delete(
            f"/api/v1/personal-croquis/{croquis.id}/publish",
            headers=_auth(tokens),
        )
        assert unpub.status_code == 200, unpub.text

    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is None
    pending = db_session.scalar(
        select(PublicMediaCleanupQueue).where(
            PublicMediaCleanupQueue.storage_key == key,
            PublicMediaCleanupQueue.processed_at.is_(None),
        )
    )
    assert pending is not None
    assert pending.attempts >= 1
    assert pending.last_error == "unlink_failed"
    assert LocalStorageBackend().resolve_existing_file(key=key) is not None

    result = pmc.process_public_cleanup_queue(db_session, limit=20)
    assert result["removed"] + result["absent"] >= 1
    db_session.expire_all()
    done = db_session.scalar(
        select(PublicMediaCleanupQueue).where(PublicMediaCleanupQueue.storage_key == key)
    )
    assert done is not None and done.processed_at is not None
    assert LocalStorageBackend().resolve_existing_file(key=key) is None


def test_missing_file_counts_as_success(db_session):
    key = f"fashionrise-model-{uuid.uuid4().hex}.png"
    owner = uuid.uuid4()
    pmc.enqueue_public_model_cleanup(
        db_session, owner_id=owner, storage_key=key, reason="test_absent"
    )
    db_session.commit()
    result = pmc.process_public_cleanup_queue(db_session, limit=10)
    assert result["absent"] >= 1
    row = db_session.scalar(
        select(PublicMediaCleanupQueue).where(PublicMediaCleanupQueue.storage_key == key)
    )
    assert row is not None and row.processed_at is not None


def test_malicious_key_rejected(db_session):
    owner = uuid.uuid4()
    assert (
        pmc.enqueue_public_model_cleanup(
            db_session,
            owner_id=owner,
            storage_key="../private_croquis/evil.png",
            reason="evil",
        )
        is None
    )
    assert (
        LocalStorageBackend().delete_public_fashionrise_model_file(
            key="croquis/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.png"
        )
        is CroquisUnlinkOutcome.UNSAFE
    )


def test_rollback_does_not_delete_public_file(client, db_session):
    tokens = register_with_invite(client, db_session, "uc5@example.com", "uc5")
    user = _user(db_session, "uc5@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Rollback")
    item = _publish(client, tokens, croquis.id)
    key = LocalStorageBackend().key_from_public_url(item["image_url"])
    assert LocalStorageBackend().resolve_existing_file(key=key) is not None

    from app.services import personal_croquis_publish as pcp

    # Nested savepoint: enqueue + delete gallery, then roll back — file must remain.
    nested = db_session.begin_nested()
    removed, queued_key = pcp.remove_owned_croquis_gallery_entry(
        db_session, croquis_id=croquis.id, owner_id=user.id, reason="test_rollback"
    )
    assert removed and queued_key == key
    nested.rollback()
    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is not None
    assert LocalStorageBackend().resolve_existing_file(key=key) is not None
    assert (
        db_session.scalar(
            select(PublicMediaCleanupQueue).where(
                PublicMediaCleanupQueue.storage_key == key,
                PublicMediaCleanupQueue.reason == "test_rollback",
            )
        )
        is None
    )


def test_weekly_rewards_default_off_no_stars(db_session, monkeypatch):
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_ENABLED", "false")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.fashionrise_weekly_rewards_enabled is False

    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    # Create a past open week via tick while rewards disabled.
    tick_competitions(db_session, now=now)
    db_session.commit()
    past = previous_week_start(now)
    # Force an open past week settle path.
    from app.services.competition_groups import ensure_competition_week

    ensure_competition_week(db_session, now=past)
    db_session.commit()
    tick_competitions(db_session, now=now + timedelta(days=7))
    db_session.commit()

    awards = db_session.scalars(select(CompetitionAward)).all()
    payouts = db_session.scalars(
        select(StarPayout).where(StarPayout.reason.like("competition_%"))
    ).all()
    assert awards == []
    assert payouts == []
    get_settings.cache_clear()


def test_weekly_rewards_respect_launch_boundary(db_session, monkeypatch):
    launch_sunday = competition_week_start(datetime(2026, 11, 23, tzinfo=timezone.utc))
    monkeypatch.setenv("FASHIONRISE_WEEKLY_REWARDS_ENABLED", "true")
    monkeypatch.setenv(
        "FASHIONRISE_WEEKLY_REWARDS_LAUNCH_WEEK_START",
        launch_sunday.date().isoformat(),
    )
    get_settings.cache_clear()

    # Pre-launch week must not credit even with flag on.
    credited = credit_payout_idempotent(
        db_session,
        user_id=uuid.uuid4(),
        amount=50,
        payout_key="competition:2026-11-16:g0:top_design",
        reason="competition_top_design",
    )
    # user missing → False; also gate would block — ensure no payout row for pre-launch settle path
    from app.services.fashionrise_reward_gates import week_eligible_for_weekly_rewards

    assert week_eligible_for_weekly_rewards(competition_week_start(datetime(2026, 11, 16, tzinfo=timezone.utc))) is False
    assert week_eligible_for_weekly_rewards(launch_sunday) is True
    assert credited is False
    get_settings.cache_clear()


def test_streak_rewards_default_off(client, db_session, monkeypatch):
    monkeypatch.setenv("FASHIONRISE_STREAK_REWARDS_ENABLED", "false")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "st1@example.com", "st1")
    user = _user(db_session, "st1@example.com")

    day0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    for i in range(7):
        status = record_daily_checkin(db_session, user, now=day0 + timedelta(days=i))
    assert status.current_streak == 7
    assert status.rewards_enabled is False
    assert status.stars_awarded == 0
    assert status.rewarded_this_checkin is False
    payouts = db_session.scalars(
        select(StarPayout).where(StarPayout.user_id == user.id, StarPayout.reason == "login_streak")
    ).all()
    assert payouts == []

    me = client.get("/api/v1/competitions/streak", headers=_auth(tokens))
    assert me.status_code == 200
    assert me.json()["rewards_enabled"] is False
    get_settings.cache_clear()


def test_streak_rewards_enabled_idempotent(client, db_session, monkeypatch):
    monkeypatch.setenv("FASHIONRISE_STREAK_REWARDS_ENABLED", "true")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "st2@example.com", "st2user")
    user = _user(db_session, "st2@example.com")

    day0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    for i in range(6):
        record_daily_checkin(db_session, user, now=day0 + timedelta(days=i))
    first = record_daily_checkin(db_session, user, now=day0 + timedelta(days=6))
    assert first.rewarded_this_checkin is True
    assert first.stars_awarded == STREAK_REWARD_STARS
    again = record_daily_checkin(db_session, user, now=day0 + timedelta(days=6))
    assert again.rewarded_this_checkin is False
    assert again.stars_awarded == 0
    payouts = db_session.scalars(
        select(StarPayout).where(StarPayout.user_id == user.id, StarPayout.reason == "login_streak")
    ).all()
    assert len(payouts) == 1
    _ = tokens
    get_settings.cache_clear()
