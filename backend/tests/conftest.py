import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("AI_WORKER_ENABLED", "false")
# Integration tests exercise invited registration. Production default remains false.
os.environ.setdefault("REGISTRATION_ENABLED", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("CORS_ORIGINS", "https://fashionrise.app")
# Do not trust client-supplied forwarding headers in the test process by default.
os.environ.setdefault("TRUST_PROXY_HEADERS", "false")

from app.main import app  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.test_db_guard import UnsafeTestDatabaseError, assert_safe_test_database_url  # noqa: E402
from app.db.base import Base, import_models  # noqa: E402
from app.db.session import get_db  # noqa: E402

# Ensure settings pick up REGISTRATION_ENABLED from the env set above.
get_settings.cache_clear()


def _resolve_safe_test_db_url() -> str:
    """Fail closed: only an explicit, non-production DATABASE_URL_TEST is accepted."""
    explicit = os.environ.get("DATABASE_URL_TEST")
    app_url = os.environ.get("DATABASE_URL") or None
    # Prefer env app URL; if absent, compare against settings only for equality checks
    # without using settings as a fallback target.
    if not app_url:
        try:
            app_url = get_settings().database_url
        except Exception:  # noqa: BLE001
            app_url = None
    return assert_safe_test_database_url(explicit, app_database_url=app_url)


@pytest.fixture(scope="session")
def db_url() -> str:
    try:
        return _resolve_safe_test_db_url()
    except UnsafeTestDatabaseError as exc:
        pytest.exit(f"Refusing to run destructive tests: {exc}", returncode=2)


@pytest.fixture(scope="session")
def engine(db_url):
    # Re-assert immediately before create/drop so a mutated env cannot slip through.
    assert_safe_test_database_url(
        db_url,
        app_database_url=os.environ.get("DATABASE_URL") or get_settings().database_url,
    )
    import_models()
    eng = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        assert_safe_test_database_url(
            db_url,
            app_database_url=os.environ.get("DATABASE_URL") or get_settings().database_url,
        )
        Base.metadata.drop_all(bind=eng)
        eng.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session) -> TestClient:
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
