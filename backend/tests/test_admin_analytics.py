"""Admin console access + overview smoke tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.admin import user_is_admin
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User
from app.db.session import get_db


@pytest.fixture()
def client(db_session: Session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _user(db: Session, *, username: str, is_admin: bool = False) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("Password123!"),
        is_active=True,
        is_admin=is_admin,
        ai_stars=10,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_allowlisted_username_is_admin(db_session: Session):
    u = _user(db_session, username="PeriShilat", is_admin=False)
    assert user_is_admin(u) is True


def test_random_user_is_not_admin(db_session: Session):
    u = _user(db_session, username="regular_user", is_admin=False)
    assert user_is_admin(u) is False


def test_overview_forbidden_for_non_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="nobody")
    r = client.get("/api/v1/admin/overview", headers=_auth(u))
    assert r.status_code == 403


def test_overview_ok_for_allowlisted(client: TestClient, db_session: Session):
    u = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/overview", headers=_auth(u))
    assert r.status_code == 200
    body = r.json()
    assert "users" in body
    assert "stars" in body
    assert "revenue" in body
    assert "moderation" in body
    assert body["users"]["total"] >= 1


def test_reports_ok_for_flag_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="ops_admin", is_admin=True)
    r = client.get("/api/v1/admin/reports", headers=_auth(u))
    assert r.status_code == 200
    assert "items" in r.json()
