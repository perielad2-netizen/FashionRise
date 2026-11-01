"""Real disposable PostgreSQL Alembic-014 smoke for one-call isolation (0 HTTP)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.test_db_guard import assert_safe_test_database_url
from app.db.base import import_models
from app.models.personal_croquis import PersonalCroquis, PersonalCroquisVersion
from app.models.private_media_asset import PrivateMediaAsset
from app.models.user import User
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_one_call import (
    APPROVED_FIXTURE_SHA256,
    ONE_CALL_STORAGE_MARKER,
    OneCallGuardError,
    assert_alembic_revision_014,
    assert_dedicated_one_call_storage,
    assert_disposable_db_fresh_for_one_call,
    assert_source_asset_sha,
    load_approved_fixture_bytes,
)
from tests.croquis_test_fixtures import (
    SYNTHETIC_ADULTS_NOTICE,
    SYNTHETIC_AI_NOTICE,
    SYNTHETIC_STORAGE_NOTICE,
    adults_body,
    storage_body,
)

ONE_CALL_ISO_DB = "fashionrise_one_call_test"
ONE_CALL_ISO_URL = (
    f"postgresql+psycopg2://fashionrise_test:fashionrise_test@"
    f"localhost:5432/{ONE_CALL_ISO_DB}"
)


def _truncate_croquis_tables(engine) -> None:
    """Empty croquis-related tables without dropping Alembic 014 schema/triggers."""
    with engine.begin() as conn:
        # Order respects FKs that may still point at versions/assets.
        for tbl in (
            "personal_croquis_spend_reservations",
            "personal_croquis_ai_consent_bindings",
            "personal_croquis_version",
            "personal_croquis",
            "ai_jobs",
            "private_media_cleanup_queue",
            "private_media_assets",
        ):
            conn.execute(text(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def pg014_engine():
    """Require the dedicated Alembic-014 disposable DB (never fashionrise_beta)."""
    url = assert_safe_test_database_url(
        ONE_CALL_ISO_URL,
        app_database_url=os.environ.get("DATABASE_URL"),
        require_env_name="ONE_CALL_ISO_URL",
    )
    # Safety: name must be the isolation DB.
    assert ONE_CALL_ISO_DB in url
    import_models()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        rev = assert_alembic_revision_014(engine)
        assert rev == "014"
        _truncate_croquis_tables(engine)
        # Also clear users created by prior smoke runs (optional FK targets).
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        yield engine
    finally:
        _truncate_croquis_tables(engine)
        engine.dispose()


@pytest.fixture()
def dedicated_storage(tmp_path, monkeypatch):
    root = tmp_path / ONE_CALL_STORAGE_MARKER / "storage"
    root.mkdir(parents=True)
    get_settings.cache_clear()
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(root))
    monkeypatch.setenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", SYNTHETIC_ADULTS_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_STORAGE_NOTICE_TEXT", SYNTHETIC_STORAGE_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_AI_NOTICE_TEXT", SYNTHETIC_AI_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()
    settings = get_settings()
    assert assert_dedicated_one_call_storage(settings) == root.resolve()
    yield root
    get_settings.cache_clear()


def test_pg014_alembic_and_fresh_then_reuse_refused(pg014_engine):
    assert assert_alembic_revision_014(pg014_engine) == "014"
    assert_disposable_db_fresh_for_one_call(pg014_engine)

    Session = sessionmaker(bind=pg014_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        user = User(
            email=f"iso_{uuid.uuid4().hex[:8]}@example.invalid",
            username=f"iso_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("x"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        croquis = PersonalCroquis(
            id=uuid.uuid4(),
            owner_id=user.id,
            display_name="stale",
            status="ready",
        )
        version = PersonalCroquisVersion(
            id=uuid.uuid4(),
            croquis_id=croquis.id,
            owner_id=user.id,
            version=1,
            status="generating",
            geometry_profile="fit_contain_768x1024_v1",
            idempotency_key=f"stale-{uuid.uuid4().hex}",
        )
        db.add(croquis)
        db.add(version)
        db.commit()
    finally:
        db.close()

    with pytest.raises(OneCallGuardError, match="reused disposable DB"):
        assert_disposable_db_fresh_for_one_call(pg014_engine)


def test_pg014_upload_stored_source_sha_matches_fixture(pg014_engine, dedicated_storage):
    """Upload approved fixture on real 014 schema; stored private bytes must match SHA."""
    _ = dedicated_storage
    Session = sessionmaker(bind=pg014_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        assert_disposable_db_fresh_for_one_call(pg014_engine)
        user = User(
            email=f"sha_{uuid.uuid4().hex[:8]}@example.invalid",
            username=f"sha_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("x"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        adults = adults_body()
        pcs.record_adults_attestation(db, user, **adults)
        storage = pcs.record_storage_consent(db, user, **storage_body())
        source = load_approved_fixture_bytes()
        croquis = pcs.upload_source_photo(
            db,
            user,
            raw=source,
            declared_content_type="image/png",
            storage_consent_id=storage.id,
            display_name="pg014-sha",
        )
        asset = db.get(PrivateMediaAsset, croquis.source_asset_id)
        assert asset is not None
        digest = assert_source_asset_sha(
            storage_key=asset.storage_key,
            expected_sha256=APPROVED_FIXTURE_SHA256,
        )
        assert digest == APPROVED_FIXTURE_SHA256
        # After upload the DB is no longer fresh for a one-call start.
        with pytest.raises(OneCallGuardError, match="reused disposable DB"):
            assert_disposable_db_fresh_for_one_call(pg014_engine)
    finally:
        db.close()
