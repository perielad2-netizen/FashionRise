"""Google Play IAP verify + RTDN — mocked Play API only (no live calls)."""

from __future__ import annotations

import base64
import json
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services import google_iap, google_rtdn, iap_service
from app.services.apple_iap import app_account_token_for_user
from fastapi.testclient import TestClient


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


def _user(db: Session, *, email: str = "android.tester@fashionrise.app") -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        username=f"u{uuid.uuid4().hex[:8]}",
        hashed_password=hash_password("Password123!"),
        is_active=True,
        email_verified=True,
        ai_stars=0,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def test_google_status_fail_closed(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    get_settings.cache_clear()
    r = client.get("/api/v1/shop/iap/google/status")
    assert r.status_code == 200
    body = r.json()
    assert body["purchasing_enabled"] is False
    assert body["credit_enabled"] is False
    assert body["verification_configured"] is False


def test_confirm_android_requires_token(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", '{"client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}')
    get_settings.cache_clear()
    user = _user(db_session)
    with pytest.raises(ValidationAppError):
        iap_service.confirm_purchase(
            db_session,
            user,
            platform="android",
            product_id="stars_50",
            transaction_id=None,
            purchase_token=None,
        )


def test_confirm_android_credits_once(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv(
        "IAP_GOOGLE_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}',
    )
    get_settings.cache_clear()
    user = _user(db_session)
    token = "google-purchase-token-abc"
    account = app_account_token_for_user(user.id)

    verified = google_iap.VerifiedGooglePurchase(
        product_id="stars_50",
        purchase_token=token,
        order_id="GPA.1234",
        package_name="app.fashionrise.studio",
        purchase_state=0,
        consumption_state=0,
        acknowledgement_state=0,
        obfuscated_external_account_id=account,
        environment="Production",
        quantity=1,
        raw={},
    )

    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: verified)
    # Advisory lock no-op under SQLite-ish sessions — execute still works on Postgres tests.
    result = iap_service.confirm_purchase(
        db_session,
        user,
        platform="android",
        product_id="stars_50",
        transaction_id="GPA.1234",
        purchase_token=token,
    )
    assert result["stars_credited"] == 50
    assert result["already_processed"] is False

    again = iap_service.confirm_purchase(
        db_session,
        user,
        platform="android",
        product_id="stars_50",
        transaction_id="GPA.1234",
        purchase_token=token,
    )
    assert again["already_processed"] is True
    assert again["stars_credited"] == 0
    db_session.refresh(user)
    assert int(user.ai_stars) == 50


def test_confirm_android_rejects_cross_account(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "true")
    get_settings.cache_clear()
    user = _user(db_session)
    other = app_account_token_for_user(uuid.uuid4())
    verified = google_iap.VerifiedGooglePurchase(
        product_id="stars_50",
        purchase_token="tok",
        order_id="GPA.1",
        package_name="app.fashionrise.studio",
        purchase_state=0,
        consumption_state=0,
        acknowledgement_state=0,
        obfuscated_external_account_id=other,
        environment="Production",
        quantity=1,
        raw={},
    )
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: verified)
    with pytest.raises(ForbiddenError):
        iap_service.confirm_purchase(
            db_session,
            user,
            platform="android",
            product_id="stars_50",
            transaction_id="GPA.1",
            purchase_token="tok",
        )


def test_confirm_android_pending_no_credit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "true")
    get_settings.cache_clear()
    user = _user(db_session)
    account = app_account_token_for_user(user.id)
    verified = google_iap.VerifiedGooglePurchase(
        product_id="stars_50",
        purchase_token="pending-tok",
        order_id="GPA.pending",
        package_name="app.fashionrise.studio",
        purchase_state=2,
        consumption_state=0,
        acknowledgement_state=0,
        obfuscated_external_account_id=account,
        environment="Production",
        quantity=1,
        raw={},
    )
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: verified)
    result = iap_service.confirm_purchase(
        db_session,
        user,
        platform="android",
        product_id="stars_50",
        transaction_id="GPA.pending",
        purchase_token="pending-tok",
    )
    assert result.get("pending") is True
    assert result["stars_credited"] == 0


def test_rtdn_test_notification(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "false")
    get_settings.cache_clear()
    payload = {"testNotification": {"version": "1.0"}, "packageName": "app.fashionrise.studio"}
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    body = {"message": {"messageId": "msg-1", "data": data}}
    out = google_rtdn.process_google_rtdn(db_session, body=body, authorization=None)
    assert out["ok"] is True
    assert out["type"] == "test"
    again = google_rtdn.process_google_rtdn(db_session, body=body, authorization=None)
    assert again["duplicate"] is True


def test_rtdn_oidc_requires_exact_email(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("google.oauth2.id_token")
    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "true")
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_AUDIENCE",
        "https://fashionrise.app/api/v1/shop/iap/google/notifications",
    )
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_EXPECTED_EMAIL",
        "rtdn-push@fashionrise.iam.gserviceaccount.com",
    )
    get_settings.cache_clear()

    def _verify(token, _req, audience):
        assert audience.endswith("/iap/google/notifications")
        return {
            "email": "other@fashionrise.iam.gserviceaccount.com",
            "email_verified": True,
        }

    import google.oauth2.id_token as id_token_mod

    monkeypatch.setattr(id_token_mod, "verify_oauth2_token", _verify)
    with pytest.raises(ForbiddenError):
        google_rtdn._maybe_verify_oidc("Bearer fake-token")


def test_rtdn_oidc_accepts_expected_verified_email(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("google.oauth2.id_token")
    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "true")
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_AUDIENCE",
        "https://fashionrise.app/api/v1/shop/iap/google/notifications",
    )
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_EXPECTED_EMAIL",
        "rtdn-push@fashionrise.iam.gserviceaccount.com",
    )
    get_settings.cache_clear()

    def _verify(token, _req, audience):
        return {
            "email": "rtdn-push@fashionrise.iam.gserviceaccount.com",
            "email_verified": True,
        }

    import google.oauth2.id_token as id_token_mod

    monkeypatch.setattr(id_token_mod, "verify_oauth2_token", _verify)
    google_rtdn._maybe_verify_oidc("Bearer fake-token")


def test_rtdn_oidc_rejects_unverified_email_claim(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("google.oauth2.id_token")
    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "true")
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_AUDIENCE",
        "https://fashionrise.app/api/v1/shop/iap/google/notifications",
    )
    monkeypatch.setenv(
        "IAP_GOOGLE_RTDN_EXPECTED_EMAIL",
        "rtdn-push@fashionrise.iam.gserviceaccount.com",
    )
    get_settings.cache_clear()

    def _verify(token, _req, audience):
        return {
            "email": "rtdn-push@fashionrise.iam.gserviceaccount.com",
            "email_verified": False,
        }

    import google.oauth2.id_token as id_token_mod

    monkeypatch.setattr(id_token_mod, "verify_oauth2_token", _verify)
    with pytest.raises(ForbiddenError):
        google_rtdn._maybe_verify_oidc("Bearer fake-token")

def test_rtdn_voided_clawback_idempotent(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase

    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "false")
    get_settings.cache_clear()
    user = _user(db_session)
    user.ai_stars = 50
    db_session.commit()

    purchase = IapPurchase(
        id=uuid.uuid4(),
        user_id=user.id,
        platform="android",
        product_id="stars_50",
        transaction_id="GPA.void-1",
        original_transaction_id="GPA.void-1",
        purchase_token="void-token-1",
        stars_credited=50,
        stars_clawed_back=0,
        status=STATUS_ACTIVE,
        environment="Sandbox",
    )
    db_session.add(purchase)
    db_session.commit()

    canceled = google_iap.VerifiedGooglePurchase(
        product_id="stars_50",
        purchase_token="void-token-1",
        order_id="GPA.void-1",
        package_name="app.fashionrise.studio",
        purchase_state=1,
        consumption_state=1,
        acknowledgement_state=1,
        obfuscated_external_account_id=None,
        environment="Sandbox",
        quantity=1,
        raw={},
    )
    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: canceled)
    real_execute = db_session.execute

    def _execute(stmt, *args, **kwargs):
        sql = str(getattr(stmt, "text", stmt))
        if "pg_advisory_xact_lock" in sql:
            return MagicMock()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", _execute)

    payload = {
        "voidedPurchaseNotification": {
            "purchaseToken": "void-token-1",
            "orderId": "GPA.void-1",
        },
        "packageName": "app.fashionrise.studio",
    }
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    body = {"message": {"messageId": "void-msg-1", "data": data}}
    out = google_rtdn.process_google_rtdn(db_session, body=body, authorization=None)
    assert out["ok"] is True
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 0
    assert int(purchase.stars_clawed_back) == 50

    # Duplicate message — no second clawback
    again = google_rtdn.process_google_rtdn(db_session, body=body, authorization=None)
    assert again["duplicate"] is True
    db_session.refresh(user)
    assert int(user.ai_stars) == 0


def test_reconcile_canceled_active_purchases_delegates_and_respects_apply_gate(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """Legacy path must not claw from products.get alone or bypass apply=false."""
    from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase
    from app.services import google_play_reconcile

    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "false")
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "false")
    get_settings.cache_clear()
    user = _user(db_session, email="canceled-rec@fashionrise.app")
    user.ai_stars = 80
    db_session.commit()
    purchase = IapPurchase(
        id=uuid.uuid4(),
        user_id=user.id,
        platform="android",
        product_id="stars_50",
        transaction_id="GPA.cancel-rec-1",
        original_transaction_id="GPA.cancel-rec-1",
        purchase_token="cancel-rec-token-1",
        stars_credited=50,
        stars_clawed_back=0,
        status=STATUS_ACTIVE,
        environment="Sandbox",
    )
    db_session.add(purchase)
    db_session.commit()

    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)

    order = google_iap.GooglePlayOrder(
        order_id="GPA.cancel-rec-1",
        purchase_token="cancel-rec-token-1",
        state="REFUNDED",
        create_time=None,
        last_event_time=None,
        product_ids=("stars_50",),
        has_full_refund_event=True,
        has_partial_refund_events=False,
        has_cancellation_event=False,
        refund_reason="OTHER",
        refund_total_currency="ILS",
        refund_total_units="19",
        refund_total_nanos=0,
        points_details=None,
        raw={},
    )
    monkeypatch.setattr(google_iap, "get_order", lambda *_a, **_k: order)

    class _V:
        purchase_state = 1
        environment = "Sandbox"
        product_id = "stars_50"

    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: _V())
    monkeypatch.setattr(google_iap, "is_canceled", lambda _v: True)
    monkeypatch.setattr(google_iap, "is_pending", lambda _v: False)
    monkeypatch.setattr(google_iap, "is_purchased", lambda _v: False)

    # Apply OFF → dry-run; products.get canceled alone must not deduct.
    dry = google_rtdn.reconcile_canceled_active_purchases(db_session)
    assert dry["ok"] is True
    assert dry["delegated_to"] == "google_play_reconcile"
    assert dry["dry_run"] is True
    assert dry["applied"] == 0
    db_session.refresh(user)
    assert int(user.ai_stars) == 80

    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    real_execute = db_session.execute

    def _execute(stmt, *args, **kwargs):
        sql = str(getattr(stmt, "text", stmt))
        if "pg_advisory_xact_lock" in sql or "pg_try_advisory_xact_lock" in sql:
            return MagicMock()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", _execute)

    applied = google_rtdn.reconcile_canceled_active_purchases(db_session)
    assert applied["dry_run"] is False
    assert applied["stars_recovered"] == 50
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 30
    assert int(purchase.stars_clawed_back) == 50

    # Admin snapshot must read Postgres only (no live Play).
    snap = google_play_reconcile.admin_reconciliation_snapshot(db_session)
    assert snap["kind"] == "persisted"
    assert snap["source"] == "postgresql"


def test_reconcile_voided_purchases(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase

    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "false")
    get_settings.cache_clear()
    user = _user(db_session, email="reconcile@fashionrise.app")
    user.ai_stars = 150
    db_session.commit()
    purchase = IapPurchase(
        id=uuid.uuid4(),
        user_id=user.id,
        platform="android",
        product_id="stars_150",
        transaction_id="GPA.rec-1",
        original_transaction_id="GPA.rec-1",
        purchase_token="rec-token-1",
        stars_credited=150,
        stars_clawed_back=0,
        status=STATUS_ACTIVE,
        environment="Sandbox",
    )
    db_session.add(purchase)
    db_session.commit()

    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(
        google_iap,
        "list_voided_purchases",
        lambda **_k: [
            google_iap.VoidedGooglePurchase(
                purchase_token="rec-token-1",
                order_id="GPA.rec-1",
                voided_time_millis=1,
                raw={},
            )
        ],
    )
    real_execute = db_session.execute

    def _execute(stmt, *args, **kwargs):
        sql = str(getattr(stmt, "text", stmt))
        if "pg_advisory_xact_lock" in sql:
            return MagicMock()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", _execute)

    first = google_rtdn.reconcile_voided_purchases(db_session, lookback_days=7)
    assert first["ok"] is True
    assert first["applied"] == 1
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 0
    assert int(purchase.stars_clawed_back) == 150

    second = google_rtdn.reconcile_voided_purchases(db_session, lookback_days=7)
    assert second["duplicates"] >= 1
    assert second["applied"] == 0
    db_session.refresh(user)
    assert int(user.ai_stars) == 0


def test_license_tester_gate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_LICENSE_TESTER_EMAILS", "android.tester@fashionrise.app")
    get_settings.cache_clear()
    user = MagicMock(email="android.tester@fashionrise.app")
    assert google_iap.google_purchasing_enabled_for(user) is True
    assert google_iap.google_credit_enabled_for(user) is True
    other = MagicMock(email="other@example.com")
    assert google_iap.google_purchasing_enabled_for(other) is False


def test_license_tester_rejects_production_purchase(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IAP_GOOGLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_GOOGLE_LICENSE_TESTER_EMAILS", "android.tester@fashionrise.app")
    monkeypatch.setenv(
        "IAP_GOOGLE_SERVICE_ACCOUNT_JSON",
        '{"type":"service_account","client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}',
    )
    get_settings.cache_clear()
    user = _user(db_session)
    account = app_account_token_for_user(user.id)
    verified = google_iap.VerifiedGooglePurchase(
        product_id="stars_50",
        purchase_token="prod-tok",
        order_id="GPA.prod",
        package_name="app.fashionrise.studio",
        purchase_state=0,
        consumption_state=0,
        acknowledgement_state=0,
        obfuscated_external_account_id=account,
        environment="Production",
        quantity=1,
        raw={},
    )
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: verified)
    with pytest.raises(ForbiddenError):
        iap_service.confirm_purchase(
            db_session,
            user,
            platform="android",
            product_id="stars_50",
            transaction_id="GPA.prod",
            purchase_token="prod-tok",
        )
