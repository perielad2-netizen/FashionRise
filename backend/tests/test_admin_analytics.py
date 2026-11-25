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


def test_overview_excludes_sandbox_iap_from_revenue(client: TestClient, db_session: Session):
    from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase

    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="buyer_sandbox")
    db_session.add(
        IapPurchase(
            user_id=buyer.id,
            platform="ios",
            product_id="stars_50",
            transaction_id="sandbox-txn-1",
            environment="Sandbox",
            status=STATUS_ACTIVE,
            stars_credited=50,
            stars_clawed_back=0,
        )
    )
    db_session.commit()
    r = client.get("/api/v1/admin/overview", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["revenue"]["purchases_counted"] == 0
    assert body["revenue"]["gross_list_price_usd"] == 0
    assert body["stars"]["stars_purchased_net"] == 0
    assert body["revenue"]["sandbox_purchases_excluded"] >= 1


def test_overview_counts_completed_magic_not_succeeded(client: TestClient, db_session: Session):
    from app.models.ai_job import AIJob

    admin = _user(db_session, username="yanivprbk")
    designer = _user(db_session, username="magic_user")
    for status in ("completed", "succeeded"):
        db_session.add(
            AIJob(
                id=uuid.uuid4(),
                user_id=designer.id,
                design_id=None,
                job_type="sketch_polish",
                status=status,
                input_data={},
                result_data={"stars_debited": True} if status == "completed" else {},
            )
        )
    db_session.commit()
    r = client.get("/api/v1/admin/overview", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["ai_usage"]["magic_completed"] >= 1
    assert body["ai_usage"]["status_semantics"] == "completed"


def test_classification_patch_and_does_not_grant_admin(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    target = _user(db_session, username="shopper_one")
    assert target.is_admin is False
    r = client.patch(
        f"/api/v1/admin/customers/{target.id}/classification",
        headers=_auth(admin),
        json={"classification": "CUSTOMER", "reason": "manual_review", "note": "real signup"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["classification"] == "CUSTOMER"
    db_session.refresh(target)
    assert target.account_classification == "CUSTOMER"
    assert target.is_admin is False


def test_customers_list_forbidden_for_non_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="nobody2")
    r = client.get("/api/v1/admin/customers", headers=_auth(u))
    assert r.status_code == 403


def test_classification_dry_run_no_writes(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    target = _user(db_session, username="maybe_customer")
    before = target.account_classification
    r = client.get("/api/v1/admin/classification/dry-run", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert "actionable_suggestions" in body
    assert "Dry-run" in body["note"]
    db_session.refresh(target)
    assert target.account_classification == before


def test_metric_dictionary(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/metrics/dictionary", headers=_auth(admin))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == "ai.magic_completed" for i in items)
