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

from app.main import app  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base, import_models  # noqa: E402
from app.db.session import get_db  # noqa: E402

# Ensure settings pick up REGISTRATION_ENABLED from the env set above.
get_settings.cache_clear()



@pytest.fixture(scope="session")
def db_url() -> str:
    url = (
        os.environ.get("DATABASE_URL_TEST")
        or os.environ.get("DATABASE_URL")
        or get_settings().database_url
    )
    if not url:
        pytest.skip("Set DATABASE_URL_TEST (or DATABASE_URL) for API integration tests.")
    return url


@pytest.fixture(scope="session")
def engine(db_url):
    import_models()
    eng = create_engine(db_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
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
