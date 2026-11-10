"""Store IAP confirm — fail-closed gates and unknown products."""

import uuid

from app.core.config import get_settings
from app.services import apple_iap
from app.services.apple_iap import VerifiedAppleTransaction
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def test_iap_confirm_fail_closed_while_apple_credit_disabled(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_SANDBOX_TESTER_EMAILS", "")
    monkeypatch.setenv("IAP_APPLE_SHARED_SECRET", "")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    get_settings.cache_clear()

    tokens = register_with_invite(client, db_session, "iap.user@example.com", "iapUser")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-test-1",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 503, res.text
    msg = res.json()["detail"]["message"].lower()
    assert "not enabled" in msg
    assert "credit" in msg or "recovery" in msg


def test_iap_status_and_confirm_allow_sandbox_tester_while_public_gates_off(
    client, db_session, monkeypatch
):
    """Designated tester emails unlock Buy/confirm without public gate flip."""
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_SANDBOX_TESTER_EMAILS", "iap.tester@example.com")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()

    public = client.get("/api/v1/shop/iap/apple/status")
    assert public.status_code == 200
    assert public.json()["purchasing_enabled"] is False
    assert public.json()["credit_enabled"] is False
    assert public.json().get("sandbox_tester") is False

    tokens = register_with_invite(client, db_session, "iap.tester@example.com", "iapTester")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])

    status = client.get("/api/v1/shop/iap/apple/status", headers=_auth(tokens))
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["purchasing_enabled"] is True
    assert body["credit_enabled"] is True
    assert body["sandbox_tester"] is True

    outsider = register_with_invite(client, db_session, "iap.outsider@example.com", "iapOut")
    out_status = client.get("/api/v1/shop/iap/apple/status", headers=_auth(outsider))
    assert out_status.json()["purchasing_enabled"] is False
    assert out_status.json()["sandbox_tester"] is False

    token = apple_iap.app_account_token_for_user(user_id)
    verified = VerifiedAppleTransaction(
        transaction_id="2000000999000999",
        original_transaction_id="2000000999000999",
        product_id="stars_50",
        bundle_id="app.fashionrise.studio",
        environment="Sandbox",
        type="Consumable",
        app_account_token=token,
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=object(),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", lambda jws: verified)
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "2000000999000999",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["stars_credited"] == 50

    blocked = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(outsider),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-outsider",
            "jws": "a.b.c",
        },
    )
    assert blocked.status_code == 503, blocked.text


def test_iap_confirm_rejects_unknown_product(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    from app.core.config import get_settings as gs

    gs.cache_clear()

    tokens = register_with_invite(client, db_session, "iap2@example.com", "iapUser2")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "android",
            "product_id": "stars_999",
            "transaction_id": "txn-2",
            "purchase_token": "tok",
        },
    )
    assert res.status_code == 422, res.text
