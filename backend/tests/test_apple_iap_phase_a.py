"""Phase A — Apple StoreKit JWS verification + idempotent Stars credit."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services import apple_iap, iap_service
from app.services.apple_iap import VerifiedAppleTransaction
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _enable_apple_credit(monkeypatch):
    """Enable server confirm/reconcile only — purchasing (new buys) stays OFF."""
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()


# Back-compat alias used in older test names during Phase A hardening.
_enable_apple_purchasing = _enable_apple_credit


def _verified(
    *,
    txn: str = "2000000123456789",
    product: str = "stars_50",
    token: str | None = None,
    revoked: bool = False,
    env: str = "Sandbox",
    bundle: str = "app.fashionrise.studio",
    typ: str = "Consumable",
) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id=product,
        bundle_id=bundle,
        environment=env,
        type=typ,
        app_account_token=token,
        quantity=1,
        revocation_date=1 if revoked else None,
        in_app_ownership_type="PURCHASED",
        raw=SimpleNamespace(),
    )


def test_app_account_token_stable_opaque_uuid():
    uid = uuid.UUID("11111111-1111-4111-8111-111111111111")
    a = apple_iap.app_account_token_for_user(uid)
    b = apple_iap.app_account_token_for_user(uid)
    assert a == b
    uuid.UUID(a)  # valid UUID string
    # Different user → different token
    other = apple_iap.app_account_token_for_user(uuid.UUID("22222222-2222-4222-8222-222222222222"))
    assert other != a
    assert str(uid) not in a


def test_production_coerces_unverified_sandbox_off():
    from app.core.config import Settings

    cfg = Settings(
        environment="production",
        testing=True,
        secret_key="x" * 40,
        cors_origins="https://fashionrise.app",
        debug=False,
        iap_allow_unverified_sandbox=True,
    )
    assert cfg.iap_allow_unverified_sandbox is False


def test_confirm_disabled_while_credit_gate_off(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "iap.gate@example.com", "iapGate")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-1",
            "jws": "a.b.c",
        },
    )
    assert res.status_code == 503, res.text
    msg = res.json()["detail"]["message"].lower()
    assert "not enabled" in msg
    assert "credit" in msg or "recovery" in msg


def test_purchasing_gate_off_does_not_imply_credit_on(monkeypatch):
    """New-purchase availability must stay independent of credit/reconcile."""
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    get_settings.cache_clear()
    assert apple_iap.apple_purchasing_enabled() is False
    assert apple_iap.apple_credit_enabled() is False
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    get_settings.cache_clear()
    assert apple_iap.apple_purchasing_enabled() is False
    assert apple_iap.apple_credit_enabled() is True


def test_confirm_requires_jws_when_enabled(client, db_session, monkeypatch):
    _enable_apple_purchasing(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.nojws@example.com", "iapNoJws")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-1",
            "receipt": "legacy-receipt-only",
        },
    )
    assert res.status_code == 422, res.text
    assert "jws" in res.json()["detail"]["message"].lower()


def test_confirm_credits_from_verified_product_not_client(
    client, db_session, monkeypatch
):
    _enable_apple_purchasing(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.ok@example.com", "iapOk")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])
    token = apple_iap.app_account_token_for_user(user_id)

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="apple-txn-50", product="stars_150", token=token),
    )

    # Client lies about product_id → rejected
    bad = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "apple-txn-50",
            "jws": "header.payload.sig",
        },
    )
    assert bad.status_code == 403, bad.text

    ok = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_150",
            "transaction_id": "apple-txn-50",
            "jws": "header.payload.sig",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["stars_credited"] == 150
    assert body["already_processed"] is False
    assert body["product_id"] == "stars_150"

    # Idempotent reconfirm
    again = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_150",
            "transaction_id": "apple-txn-50",
            "jws": "header.payload.sig",
        },
    )
    assert again.status_code == 200, again.text
    assert again.json()["stars_credited"] == 0
    assert again.json()["already_processed"] is True
    assert again.json()["ai_stars"] == body["ai_stars"]


def test_confirm_rejects_refunded_verified_transaction(client, db_session, monkeypatch):
    _enable_apple_purchasing(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.ref@example.com", "iapRef")

    def boom(_jws: str) -> VerifiedAppleTransaction:
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Apple transaction was revoked or refunded")

    monkeypatch.setattr(apple_iap, "verify_signed_transaction_jws", boom)
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-ref",
            "jws": "header.payload.sig",
        },
    )
    assert res.status_code == 403, res.text
    assert "revoked" in res.json()["detail"]["message"].lower()


def test_confirm_rejects_missing_app_account_token(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.miss@example.com", "iapMiss")
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="txn-miss", token=None),
    )
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-miss",
            "jws": "header.payload.sig",
        },
    )
    assert res.status_code == 403, res.text
    msg = res.json()["detail"]["message"].lower()
    assert "appaccounttoken" in msg
    assert "required" in msg


def test_confirm_rejects_app_account_token_mismatch(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.tok@example.com", "iapTok")
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="txn-tok", token=str(uuid.uuid4())),
    )
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-tok",
            "jws": "header.payload.sig",
        },
    )
    assert res.status_code == 403, res.text
    assert "appaccounttoken" in res.json()["detail"]["message"].lower()


def test_confirm_accepts_matching_app_account_token(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.match@example.com", "iapMatch")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    token = apple_iap.app_account_token_for_user(uuid.UUID(me.json()["id"]))
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="txn-match", product="stars_50", token=token),
    )
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-match",
            "jws": "header.payload.sig",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["stars_credited"] == 50


def test_confirm_cross_account_rejected_by_token_then_conflict(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    a = register_with_invite(client, db_session, "iap.a@example.com", "iapA")
    b = register_with_invite(client, db_session, "iap.b@example.com", "iapB")
    me_a = client.get("/api/v1/auth/me", headers=_auth(a))
    me_b = client.get("/api/v1/auth/me", headers=_auth(b))
    token_a = apple_iap.app_account_token_for_user(uuid.UUID(me_a.json()["id"]))
    token_b = apple_iap.app_account_token_for_user(uuid.UUID(me_b.json()["id"]))
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="shared-txn", product="stars_50", token=token_a),
    )
    first = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(a),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "shared-txn",
            "jws": "header.payload.sig",
        },
    )
    assert first.status_code == 200, first.text

    # Other account presenting the same Apple JWS (still bound to A's token) → ownership 403
    stolen = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(b),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "shared-txn",
            "jws": "header.payload.sig",
        },
    )
    assert stolen.status_code == 403, stolen.text

    # If verification somehow claimed B's token on an already-credited txn id → 409
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn="shared-txn", product="stars_50", token=token_b),
    )
    second = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(b),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "shared-txn",
            "jws": "header.payload.sig",
        },
    )
    assert second.status_code == 409, second.text


def test_get_app_account_token(client, db_session, monkeypatch):
    _enable_apple_purchasing(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.aat@example.com", "iapAat")
    res = client.get("/api/v1/shop/iap/app-account-token", headers=_auth(tokens))
    assert res.status_code == 200, res.text
    tok = res.json()["app_account_token"]
    uuid.UUID(tok)
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    assert tok == apple_iap.app_account_token_for_user(uuid.UUID(me.json()["id"]))


def test_android_path_unchanged_staged(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "iap.and@example.com", "iapAnd")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "android",
            "product_id": "stars_50",
            "transaction_id": "gpa-1",
            "purchase_token": "tok",
        },
    )
    assert res.status_code == 503, res.text
    assert "google" in res.json()["detail"]["message"].lower()


def test_validated_payload_rejects_bundle_mismatch():
    from app.core.errors import ForbiddenError
    from appstoreserverlibrary.models.Environment import Environment
    from appstoreserverlibrary.models.Type import Type

    decoded = SimpleNamespace(
        bundleId="com.wrong.app",
        environment=Environment.SANDBOX,
        transactionId="1",
        originalTransactionId="1",
        productId="stars_50",
        type=Type.CONSUMABLE,
        inAppOwnershipType=None,
        revocationDate=None,
        quantity=1,
        appAccountToken=None,
    )
    get_settings.cache_clear()
    with pytest.raises(ForbiddenError, match="bundle"):
        apple_iap._validated_payload(decoded, expected_env=Environment.SANDBOX)


def test_validated_payload_rejects_non_consumable():
    from app.core.errors import ForbiddenError
    from appstoreserverlibrary.models.Environment import Environment
    from appstoreserverlibrary.models.Type import Type

    decoded = SimpleNamespace(
        bundleId="app.fashionrise.studio",
        environment=Environment.SANDBOX,
        transactionId="1",
        originalTransactionId="1",
        productId="stars_50",
        type=Type.NON_CONSUMABLE,
        inAppOwnershipType=None,
        revocationDate=None,
        quantity=1,
        appAccountToken=None,
    )
    with pytest.raises(ForbiddenError, match="consumable"):
        apple_iap._validated_payload(decoded, expected_env=Environment.SANDBOX)


def test_integrity_error_recovery_returns_idempotent(monkeypatch):
    """Unique-constraint race on insert maps to already_processed (no double credit)."""
    from sqlalchemy.exc import IntegrityError

    user = SimpleNamespace(id=uuid.uuid4(), ai_stars=10)
    existing = SimpleNamespace(
        user_id=user.id,
        product_id="stars_50",
        transaction_id="race-txn",
        stars_credited=50,
    )

    class FakeSession:
        def __init__(self) -> None:
            self.added = None
            self.rolled_back = False
            self.committed = False

        def add(self, row) -> None:
            self.added = row

        def flush(self) -> None:
            raise IntegrityError("duplicate", params=None, orig=Exception("uq"))

        def rollback(self) -> None:
            self.rolled_back = True

        def commit(self) -> None:
            self.committed = True

        def refresh(self, _obj) -> None:
            return None

        def scalar(self, _stmt):
            return user

    db = FakeSession()
    finds = {"n": 0}

    def find(_db, *, platform: str, transaction_id: str):
        finds["n"] += 1
        assert platform == "ios"
        assert transaction_id == "race-txn"
        # First call (pre-insert) → miss; after IntegrityError → hit.
        if finds["n"] == 1:
            return None
        return existing

    monkeypatch.setattr(iap_service, "_find_purchase", find)
    credited = {"called": False}

    def no_credit(*_a, **_k):
        credited["called"] = True
        raise AssertionError("must not credit after unique conflict")

    monkeypatch.setattr(iap_service.ai_stars, "credit_stars", no_credit)

    out = iap_service._persist_credit(
        db,  # type: ignore[arg-type]
        user,  # type: ignore[arg-type]
        platform="ios",
        product_id="stars_50",
        transaction_id="race-txn",
        stars=50,
    )
    assert db.rolled_back is True
    assert db.committed is False
    assert credited["called"] is False
    assert out["already_processed"] is True
    assert out["stars_credited"] == 0


def test_verify_jws_invalid_signature_mocked_library(monkeypatch):
    """Trusted library boundary: VerificationException → ForbiddenError."""
    _enable_apple_purchasing(monkeypatch)
    from app.core.errors import ForbiddenError
    from appstoreserverlibrary.signed_data_verifier import (
        VerificationException,
        VerificationStatus,
    )

    class FakeVerifier:
        def verify_and_decode_signed_transaction(self, _jws: str):
            raise VerificationException(VerificationStatus.VERIFICATION_FAILURE)

    monkeypatch.setattr(apple_iap, "_build_verifier", lambda env: FakeVerifier())
    monkeypatch.setattr(
        apple_iap,
        "_environment_from_unverified_jws",
        lambda jws: __import__(
            "appstoreserverlibrary.models.Environment", fromlist=["Environment"]
        ).Environment.SANDBOX,
    )
    with pytest.raises(ForbiddenError, match="signature"):
        apple_iap.verify_signed_transaction_jws("aaa.bbb.ccc")
