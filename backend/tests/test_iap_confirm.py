"""Store IAP confirm — fail-closed gates, sandbox-tester exception, unknown products."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.services import apple_iap
from app.services.apple_iap import VerifiedAppleTransaction
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _gates_public_off(monkeypatch, *, tester_emails: str = "") -> None:
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_SANDBOX_TESTER_EMAILS", tester_emails)
    monkeypatch.setenv("IAP_APPLE_SHARED_SECRET", "")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()


def _verified(
    *,
    user_id: uuid.UUID,
    txn: str,
    product: str = "stars_50",
    environment: str = "Sandbox",
) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id=product,
        bundle_id="app.fashionrise.studio",
        environment=environment,
        type="Consumable",
        app_account_token=apple_iap.app_account_token_for_user(user_id),
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=object(),
    )


def test_iap_confirm_fail_closed_while_apple_credit_disabled(client, db_session, monkeypatch):
    _gates_public_off(monkeypatch, tester_emails="")

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


def test_allowlisted_tester_sandbox_transaction_credits(client, db_session, monkeypatch):
    """Allowlisted tester + verified Sandbox txn → credit while public gates OFF."""
    _gates_public_off(monkeypatch, tester_emails="iap.tester@example.com")

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

    verified = _verified(user_id=user_id, txn="2000000999000999", environment="Sandbox")
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


def test_allowlisted_tester_production_transaction_denied_when_public_credit_off(
    client, db_session, monkeypatch
):
    """Allowlisted tester + verified Production txn + public credit OFF → denied."""
    _gates_public_off(monkeypatch, tester_emails="iap.tester.prod@example.com")

    tokens = register_with_invite(client, db_session, "iap.tester.prod@example.com", "iapTProd")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])

    verified = _verified(user_id=user_id, txn="1000000999000001", environment="Production")
    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", lambda jws: verified)
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "1000000999000001",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 403, res.text
    assert "sandbox" in res.json()["detail"]["message"].lower()


def test_non_allowlisted_user_sandbox_transaction_denied(client, db_session, monkeypatch):
    """Non-allowlisted user + Sandbox transaction → denied while public gates OFF."""
    _gates_public_off(monkeypatch, tester_emails="iap.tester@example.com")

    outsider = register_with_invite(client, db_session, "iap.outsider@example.com", "iapOut")
    out_status = client.get("/api/v1/shop/iap/apple/status", headers=_auth(outsider))
    assert out_status.json()["purchasing_enabled"] is False
    assert out_status.json()["credit_enabled"] is False
    assert out_status.json()["sandbox_tester"] is False

    me = client.get("/api/v1/auth/me", headers=_auth(outsider))
    user_id = uuid.UUID(me.json()["id"])
    verified = _verified(user_id=user_id, txn="2000000999000888", environment="Sandbox")
    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", lambda jws: verified)

    blocked = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(outsider),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "2000000999000888",
            "jws": "a.b.c",
        },
    )
    assert blocked.status_code == 503, blocked.text


def test_invalid_signature_denied_for_allowlisted_tester(client, db_session, monkeypatch):
    """Invalid Apple signature → denied (never credits)."""
    _gates_public_off(monkeypatch, tester_emails="iap.tester.sig@example.com")

    tokens = register_with_invite(client, db_session, "iap.tester.sig@example.com", "iapTSig")

    def boom(_jws: str):
        raise ForbiddenError("Apple transaction signature verification failed")

    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", boom)
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-bad-sig",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 403, res.text
    assert "signature" in res.json()["detail"]["message"].lower()


def test_global_credit_enabled_accepts_verified_production(client, db_session, monkeypatch):
    """Global production credit ON + verified Production txn → normal credit."""
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_APPLE_SANDBOX_TESTER_EMAILS", "")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()

    tokens = register_with_invite(client, db_session, "iap.prod.user@example.com", "iapProd")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])

    verified = _verified(user_id=user_id, txn="1000000999000777", environment="Production")
    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", lambda jws: verified)
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "1000000999000777",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["stars_credited"] == 50


def test_status_allowlist_uses_authenticated_db_email_not_spoofable(
    client, db_session, monkeypatch
):
    """Status sandbox_tester comes from JWT→DB user email, not client fields."""
    _gates_public_off(monkeypatch, tester_emails="iap.tester@example.com")

    outsider = register_with_invite(client, db_session, "iap.outsider2@example.com", "iapOut2")
    # Query-string / header spoof attempts must not flip allowlist.
    res = client.get(
        "/api/v1/shop/iap/apple/status?email=iap.tester@example.com",
        headers={
            **_auth(outsider),
            "X-User-Email": "iap.tester@example.com",
        },
    )
    assert res.status_code == 200
    assert res.json()["sandbox_tester"] is False
    assert res.json()["purchasing_enabled"] is False

    # Garbage bearer → treated as anonymous (optional auth), gates OFF.
    anon = client.get(
        "/api/v1/shop/iap/apple/status",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert anon.status_code == 200
    assert anon.json()["sandbox_tester"] is False
    assert anon.json()["purchasing_enabled"] is False


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
