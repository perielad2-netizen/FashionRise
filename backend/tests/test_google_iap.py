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
