"""Admin console access + overview regression (PM corrections A–L)."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.admin import is_reserved_admin_username, user_is_admin
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.ai_job import AIJob
from app.models.garment_design import GarmentDesign
from app.models.iap_purchase import (
    STATUS_ACTIVE,
    STATUS_REFUNDED,
    IapPurchase,
)
from app.models.user import User
from app.services.admin_analytics import set_classification


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


def _user(
    db: Session,
    *,
    username: str,
    is_admin: bool = False,
    classification: str = "UNCLASSIFIED",
    ai_stars: int = 10,
    unlimited: bool = False,
    is_active: bool = True,
) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"{username}@example.com",
        username=username,
        hashed_password=hash_password("Password123!"),
        is_active=is_active,
        is_admin=is_admin,
        ai_stars=ai_stars,
        ai_stars_unlimited=unlimited,
        account_classification=classification,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def _add_purchase(
    db: Session,
    user: User,
    *,
    product_id: str = "stars_50",
    environment: str = "Production",
    status: str = STATUS_ACTIVE,
    stars: int = 50,
    created_at: datetime | None = None,
) -> IapPurchase:
    row = IapPurchase(
        user_id=user.id,
        platform="ios",
        product_id=product_id,
        transaction_id=f"txn-{uuid.uuid4()}",
        environment=environment,
        status=status,
        stars_credited=stars,
        stars_clawed_back=0,
    )
    db.add(row)
    db.flush()
    if created_at is not None:
        row.created_at = created_at
    db.commit()
    db.refresh(row)
    return row


# ── Auth ──────────────────────────────────────────────────────────────


def test_allowlisted_username_is_admin(db_session: Session):
    u = _user(db_session, username="PeriShilat", is_admin=False)
    assert user_is_admin(u) is True


def test_random_user_is_not_admin(db_session: Session):
    u = _user(db_session, username="regular_user", is_admin=False)
    assert user_is_admin(u) is False


def test_inactive_allowlisted_is_not_admin(db_session: Session):
    u = _user(db_session, username="yanivprbk", is_active=False)
    assert user_is_admin(u) is False


def test_reserved_username_case_insensitive():
    assert is_reserved_admin_username("PeriShilat")
    assert is_reserved_admin_username("YANIVPRBK")
    assert not is_reserved_admin_username("someone_else")


def test_classification_does_not_grant_admin(db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    target = _user(db_session, username="shopper_cls", classification="UNCLASSIFIED")
    set_classification(
        db_session,
        target=target,
        actor=admin,
        to_classification="OWNER",
        reason="manual_review_owner",
    )
    db_session.commit()
    db_session.refresh(target)
    assert target.account_classification == "OWNER"
    assert target.is_admin is False
    assert user_is_admin(target) is False


def test_overview_forbidden_for_non_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="nobody")
    r = client.get("/api/v1/admin/overview", headers=_auth(u))
    assert r.status_code == 403


def test_inactive_admin_cannot_access(client: TestClient, db_session: Session):
    u = _user(db_session, username="yanivprbk", is_active=False)
    r = client.get("/api/v1/admin/overview", headers=_auth(u))
    assert r.status_code in (401, 403)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/overview",
        "/api/v1/admin/customers",
        "/api/v1/admin/reports",
        "/api/v1/admin/metrics/dictionary",
        "/api/v1/admin/classification/dry-run",
        "/api/v1/admin/classification/options",
    ],
)
def test_every_admin_endpoint_forbidden_for_non_admin(
    client: TestClient, db_session: Session, path: str
):
    u = _user(db_session, username=f"nope_{path[-8:]}")
    r = client.get(path, headers=_auth(u))
    assert r.status_code == 403


def test_overview_ok_for_allowlisted(client: TestClient, db_session: Session):
    u = _user(db_session, username="yanivprbk", classification="CUSTOMER")
    r = client.get("/api/v1/admin/overview?audience=all", headers=_auth(u))
    assert r.status_code == 200
    body = r.json()
    assert "users" in body
    assert "stars" in body
    assert "revenue" in body
    assert "moderation" in body
    assert body["users"]["enabled"] >= 1
    assert body["users"]["active"] == body["users"]["enabled"]
    assert body["audience_default"] == "customers"


def test_reports_ok_for_flag_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="ops_admin", is_admin=True)
    r = client.get("/api/v1/admin/reports", headers=_auth(u))
    assert r.status_code == 200
    assert "items" in r.json()


# ── Audience isolation ─────────────────────────────────────────────────


def test_audience_isolation_customers_vs_internal(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    cust = _user(db_session, username="cust_a", classification="CUSTOMER")
    internal = _user(db_session, username="qa_bot", classification="QA_AUTOMATION")
    db_session.add(
        GarmentDesign(
            id=uuid.uuid4(),
            user_id=cust.id,
            title="cust design",
            garment_category="dress",
            design_data={},
        )
    )
    db_session.add(
        GarmentDesign(
            id=uuid.uuid4(),
            user_id=internal.id,
            title="qa design",
            garment_category="dress",
            design_data={},
        )
    )
    db_session.commit()

    r_cust = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    r_int = client.get(
        "/api/v1/admin/overview?audience=internal&range=all_time",
        headers=_auth(admin),
    )
    assert r_cust.status_code == 200
    assert r_int.status_code == 200
    assert r_cust.json()["content"]["designs_saved"] >= 1
    assert r_int.json()["content"]["designs_saved"] >= 1
    # Crossing audiences must not silently equal all accounts when both exist.
    r_all = client.get(
        "/api/v1/admin/overview?audience=all&range=all_time",
        headers=_auth(admin),
    )
    assert r_all.json()["content"]["designs_saved"] >= (
        r_cust.json()["content"]["designs_saved"]
        + r_int.json()["content"]["designs_saved"]
    )


def test_unclassified_audience(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    _user(db_session, username="mystery", classification="UNCLASSIFIED")
    r = client.get(
        "/api/v1/admin/overview?audience=unclassified&range=all_time",
        headers=_auth(admin),
    )
    assert r.status_code == 200
    assert r.json()["users"]["registered"] >= 1


def test_invalid_audience_rejected(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/overview?audience=hackers", headers=_auth(admin))
    assert r.status_code == 400


def test_invalid_range_rejected(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/overview?range=last_week", headers=_auth(admin))
    assert r.status_code == 400


def test_default_audience_is_customers(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    _user(db_session, username="only_customer", classification="CUSTOMER")
    _user(db_session, username="only_qa", classification="QA_AUTOMATION")
    r = client.get("/api/v1/admin/overview", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["audience"] == "customers"
    # Only CUSTOMER accounts in filter (admin + qa excluded unless classified).
    assert body["users"]["registered"] >= 1


# ── Revenue ────────────────────────────────────────────────────────────


def test_overview_excludes_sandbox_iap_from_revenue(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="buyer_sandbox", classification="CUSTOMER")
    _add_purchase(db_session, buyer, environment="Sandbox")
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["revenue"]["purchases_counted"] == 0
    assert body["revenue"]["gross_list_price_usd"] == 0
    assert body["stars"]["stars_purchased_net"] == 0
    assert body["revenue"]["sandbox_purchases_excluded"] >= 1


def test_unknown_environment_excluded(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="buyer_unk", classification="CUSTOMER")
    _add_purchase(db_session, buyer, environment="StagingXYZ")
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    body = r.json()
    assert body["revenue"]["purchases_counted"] == 0
    assert body["revenue"]["unknown_environment_excluded"] >= 1


def test_production_purchase_counts(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="buyer_prod", classification="CUSTOMER")
    _add_purchase(db_session, buyer, environment="Production", product_id="stars_50")
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    body = r.json()
    assert body["revenue"]["purchases_counted"] == 1
    assert body["revenue"]["gross_list_price_usd"] == pytest.approx(5.99)
    assert body["revenue"]["kind"] == "estimated"
    assert body["users"]["paying_customers"] >= 1


def test_refund_accounting(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="buyer_ref", classification="CUSTOMER")
    _add_purchase(db_session, buyer, environment="Production", status=STATUS_REFUNDED)
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    body = r.json()
    assert body["revenue"]["refunds_counted"] >= 1
    assert body["revenue"]["refunds_list_price_usd"] >= 5.99
    assert body["revenue"]["purchases_counted"] == 0


def test_lifetime_revenue_beyond_50_display_rows(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    buyer = _user(db_session, username="whale", classification="CUSTOMER")
    for i in range(55):
        _add_purchase(
            db_session,
            buyer,
            product_id="stars_50",
            environment="Production",
            stars=50,
        )
    r = client.get(f"/api/v1/admin/customers/{buyer.id}", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert len(body["purchases"]["items"]) <= 50
    # 55 * 5.99 catalog list price
    assert body["purchases"]["lifetime_list_price_usd"] == pytest.approx(55 * 5.99)


# ── AI / Stars honesty ─────────────────────────────────────────────────


def test_overview_counts_completed_magic_not_succeeded(
    client: TestClient, db_session: Session
):
    admin = _user(db_session, username="yanivprbk")
    designer = _user(db_session, username="magic_user", classification="CUSTOMER")
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
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ai_usage"]["magic_completed"] >= 1
    assert body["ai_usage"]["status_semantics"] == "completed"


def test_unlimited_account_included_in_ai_usage(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    unlimited = _user(
        db_session,
        username="owner_ul",
        classification="CUSTOMER",
        unlimited=True,
        ai_stars=0,
    )
    db_session.add(
        AIJob(
            id=uuid.uuid4(),
            user_id=unlimited.id,
            design_id=None,
            job_type="fitting_room_try_on",
            status="completed",
            input_data={},
            result_data={},
        )
    )
    db_session.commit()
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    assert r.json()["ai_usage"]["fitting_room_completed"] >= 1
    assert r.json()["stars"]["unlimited_wallets"] >= 1


def test_free_paid_stars_attribution_unavailable(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk", classification="CUSTOMER")
    r = client.get("/api/v1/admin/overview?audience=all", headers=_auth(admin))
    body = r.json()
    assert body["stars"]["free_vs_paid_attribution"]["kind"] == "unavailable"
    assert body["stars"]["stars_spent_total_est"] is None
    assert "stars.free_vs_paid_attribution" in body["unavailable"]


def test_global_ops_labeled_separately(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/overview?audience=customers", headers=_auth(admin))
    body = r.json()
    assert body["operations_global"]["scope_label"] == "Global / All Accounts"
    assert body["moderation"]["audience_scoped"] is False
    assert "Global" in (body["ai_usage"].get("jobs_scope_label") or "")


def test_missing_dau_wau_unavailable_not_zero(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/overview?audience=all", headers=_auth(admin))
    body = r.json()
    assert body["engagement"]["dau"]["kind"] == "unavailable"
    assert body["engagement"]["wau"]["kind"] == "unavailable"
    assert "engagement.dau" in body["unavailable"]


# ── Classification ─────────────────────────────────────────────────────


def test_classification_patch_and_does_not_grant_admin(
    client: TestClient, db_session: Session
):
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


def test_classification_requires_reason(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    target = _user(db_session, username="needs_reason")
    r = client.patch(
        f"/api/v1/admin/customers/{target.id}/classification",
        headers=_auth(admin),
        json={"classification": "CUSTOMER", "reason": "ab"},
    )
    assert r.status_code == 422 or r.status_code == 400


def test_classification_concurrency_conflict(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    target = _user(db_session, username="race_target", classification="UNCLASSIFIED")
    r = client.patch(
        f"/api/v1/admin/customers/{target.id}/classification",
        headers=_auth(admin),
        json={
            "classification": "CUSTOMER",
            "reason": "first_write",
            "expected_classification": "QA_AUTOMATION",
        },
    )
    assert r.status_code == 409


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


def test_suggest_does_not_mark_unlimited_as_owner(db_session: Session):
    from app.services.admin_analytics import suggest_classification

    u = _user(db_session, username="ul_user", unlimited=True)
    sug = suggest_classification(u)
    assert sug["suggested"] != "OWNER"
    assert sug["authoritative"] is False


# ── Customers pagination ───────────────────────────────────────────────


def test_customers_list_forbidden_for_non_admin(client: TestClient, db_session: Session):
    u = _user(db_session, username="nobody2")
    r = client.get("/api/v1/admin/customers", headers=_auth(u))
    assert r.status_code == 403


def test_customers_pagination(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    for i in range(30):
        _user(db_session, username=f"page_user_{i:02d}", classification="CUSTOMER")
    r1 = client.get(
        "/api/v1/admin/customers?audience=all&limit=10&offset=0&sort=username_asc",
        headers=_auth(admin),
    )
    r2 = client.get(
        "/api/v1/admin/customers?audience=all&limit=10&offset=10&sort=username_asc",
        headers=_auth(admin),
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    assert b1["total"] >= 30
    assert len(b1["items"]) == 10
    assert b1["has_more"] is True
    ids1 = {i["id"] for i in b1["items"]}
    ids2 = {i["id"] for i in b2["items"]}
    assert ids1.isdisjoint(ids2)


def test_metric_dictionary(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    r = client.get("/api/v1/admin/metrics/dictionary", headers=_auth(admin))
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == "ai.magic_completed_in_range" for i in items)
    assert any(i["id"] == "users.enabled" for i in items)


def test_wallet_aggregation_audience_scoped(client: TestClient, db_session: Session):
    admin = _user(db_session, username="yanivprbk")
    _user(db_session, username="wallet_c", classification="CUSTOMER", ai_stars=100)
    _user(db_session, username="wallet_q", classification="QA_AUTOMATION", ai_stars=500)
    r = client.get(
        "/api/v1/admin/overview?audience=customers&range=all_time",
        headers=_auth(admin),
    )
    # Only customer wallets in sum (admin may also be unclassified).
    assert r.json()["stars"]["wallet_balance_sum"] >= 100
    assert r.json()["stars"]["wallet_balance_sum_period"] == "snapshot"
