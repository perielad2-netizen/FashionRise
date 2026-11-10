"""Phase B — ASN V2 refund/revoke, debt liability, confirm-after-refund."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import get_settings
from app.models.iap_apple_notification import IapAppleNotification
from app.models.iap_purchase import (
    STATUS_ACTIVE,
    STATUS_BLOCKED,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    IapPurchase,
)
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.user import User
from app.services import ai_stars, apple_asn, apple_iap
from app.services.apple_iap import VerifiedAppleNotification, VerifiedAppleTransaction
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _enable_apple_credit(monkeypatch):
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()


def _verified_txn(
    *,
    txn: str = "2000000999000001",
    product: str = "stars_500",
    token: str | None = None,
    env: str = "Sandbox",
) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id=product,
        bundle_id="app.fashionrise.studio",
        environment=env,
        type="Consumable",
        app_account_token=token,
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=SimpleNamespace(),
    )


def _verified_asn(
    *,
    ntype: str,
    txn: VerifiedAppleTransaction,
    uuid_s: str | None = None,
    subtype: str | None = None,
) -> VerifiedAppleNotification:
    return VerifiedAppleNotification(
        notification_uuid=uuid_s or str(uuid.uuid4()),
        notification_type=ntype,
        subtype=subtype,
        environment=txn.environment,
        signed_date=1,
        transaction=txn,
        raw=SimpleNamespace(),
    )


def test_apple_shop_status_gates_default_off(client, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_SANDBOX_TESTER_EMAILS", "")
    get_settings.cache_clear()
    res = client.get("/api/v1/shop/iap/apple/status")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["purchasing_enabled"] is False
    assert body["credit_enabled"] is False
    assert body.get("sandbox_tester") is False
    assert {p["product_id"] for p in body["products"]} == {
        "stars_50",
        "stars_150",
        "stars_500",
    }


def test_asn_rejects_missing_payload(client):
    res = client.post("/api/v1/shop/iap/apple/notifications", json={})
    assert res.status_code == 422


def test_asn_rejects_invalid_signed_payload(client, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()
    res = client.post(
        "/api/v1/shop/iap/apple/notifications",
        json={"signedPayload": "not.a.jws"},
    )
    # Validation or forbidden — never 200 without verification.
    assert res.status_code in (403, 422, 503), res.text


def test_refund_full_balance_clawback(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.ref.full@example.com", "iapRefFull")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])
    token = apple_iap.app_account_token_for_user(user_id)
    txn = "apple-ref-full-1"

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified_txn(txn=txn, product="stars_50", token=token),
    )
    conf = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={"platform": "ios", "product_id": "stars_50", "jws": "a.b.c"},
    )
    assert conf.status_code == 200, conf.text
    credited = conf.json()["ai_stars"]

    asn = _verified_asn(ntype="REFUND", txn=_verified_txn(txn=txn, product="stars_50", token=token))
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    res = client.post(
        "/api/v1/shop/iap/apple/notifications",
        json={"signedPayload": "a.b.c"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["processing_state"] == "applied"

    user = db_session.get(User, user_id)
    assert user is not None
    db_session.refresh(user)
    # Starter + 50 - 50 clawback of IAP portion: clawback recovers min(balance, 50).
    # Starter was 10, after credit 60, after full 50 clawback → 10, debt 0.
    assert int(user.ai_stars) == credited - 50
    assert int(user.ai_stars_iap_debt or 0) == 0
    purchase = db_session.scalar(
        select(IapPurchase).where(IapPurchase.transaction_id == txn)
    )
    assert purchase is not None
    assert purchase.status == STATUS_REFUNDED
    assert int(purchase.stars_clawed_back) == 50


def test_refund_partial_spend_creates_debt(db_session, monkeypatch):
    """Buy 500, spend 450, refund → claw 50 + debt 450."""
    _enable_apple_credit(monkeypatch)
    user = User(
        email=f"debt_{uuid.uuid4().hex[:8]}@example.com",
        username=f"debt_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    # Ignore starter for clarity: set exact balances after a hypothetical 500 credit.
    user.ai_stars = 50  # spent 450 of 500; starter ignored in this unit scenario
    user.ai_stars_iap_debt = 0
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"debt-txn-{uuid.uuid4().hex[:8]}"
    purchase = IapPurchase(
        user_id=user.id,
        platform="ios",
        product_id="stars_500",
        transaction_id=txn,
        original_transaction_id=txn,
        environment="Sandbox",
        status=STATUS_ACTIVE,
        stars_credited=500,
    )
    db_session.add(purchase)
    db_session.commit()

    asn = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn=txn, product="stars_500", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "applied"

    db_session.refresh(user)
    assert int(user.ai_stars) == 0
    assert int(user.ai_stars_iap_debt) == 450

    # Subsequent legitimate credit settles debt first.
    bal = ai_stars.credit_stars(db_session, user, 100, reason="test_settle")
    db_session.commit()
    db_session.refresh(user)
    assert bal == 0
    assert int(user.ai_stars) == 0
    assert int(user.ai_stars_iap_debt) == 350

    bal2 = ai_stars.credit_stars(db_session, user, 400, reason="test_settle2")
    db_session.commit()
    db_session.refresh(user)
    assert bal2 == 50
    assert int(user.ai_stars_iap_debt) == 0


def test_duplicate_notification_uuid_noop(db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    user = User(
        email=f"dup_{uuid.uuid4().hex[:8]}@example.com",
        username=f"dup_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=60,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"dup-txn-{uuid.uuid4().hex[:8]}"
    db_session.add(
        IapPurchase(
            user_id=user.id,
            platform="ios",
            product_id="stars_50",
            transaction_id=txn,
            original_transaction_id=txn,
            status=STATUS_ACTIVE,
            stars_credited=50,
        )
    )
    db_session.commit()

    n_uuid = str(uuid.uuid4())
    asn = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn=txn, product="stars_50", token=token),
        uuid_s=n_uuid,
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)

    first = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    second = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    db_session.refresh(user)
    assert int(user.ai_stars) == 10  # 60-50
    # Only one adjustment
    count = db_session.scalars(select(IapStarsAdjustment)).all()
    assert len([a for a in count if a.transaction_id == txn]) == 1


def test_duplicate_refund_distinct_uuid_no_double_claw(db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    user = User(
        email=f"dup2_{uuid.uuid4().hex[:8]}@example.com",
        username=f"dup2_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=60,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"dup2-txn-{uuid.uuid4().hex[:8]}"
    db_session.add(
        IapPurchase(
            user_id=user.id,
            platform="ios",
            product_id="stars_50",
            transaction_id=txn,
            status=STATUS_ACTIVE,
            stars_credited=50,
        )
    )
    db_session.commit()
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)

    for _ in range(2):
        asn = _verified_asn(
            ntype="REFUND",
            txn=_verified_txn(txn=txn, product="stars_50", token=token),
        )
        monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p, a=asn: a)
        apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")

    db_session.refresh(user)
    assert int(user.ai_stars) == 10
    assert int(user.ai_stars_iap_debt) == 0
    adjs = db_session.scalars(
        select(IapStarsAdjustment).where(IapStarsAdjustment.transaction_id == txn)
    ).all()
    assert len(adjs) == 1


def test_refund_reversed_restores_without_fresh_credit(db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    user = User(
        email=f"rev_{uuid.uuid4().hex[:8]}@example.com",
        username=f"rev_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=10,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"rev-txn-{uuid.uuid4().hex[:8]}"
    db_session.add(
        IapPurchase(
            user_id=user.id,
            platform="ios",
            product_id="stars_50",
            transaction_id=txn,
            status=STATUS_ACTIVE,
            stars_credited=50,
        )
    )
    # Simulate post-credit balance then refund clawback path via ASN.
    user.ai_stars = 60
    db_session.commit()
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)

    asn_refund = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn=txn, product="stars_50", token=token),
    )
    monkeypatch.setattr(
        apple_iap, "verify_signed_notification_payload", lambda p: asn_refund
    )
    apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    db_session.refresh(user)
    assert int(user.ai_stars) == 10

    asn_rev = _verified_asn(
        ntype="REFUND_REVERSED",
        txn=_verified_txn(txn=txn, product="stars_50", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn_rev)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 60
    purchase = db_session.scalar(select(IapPurchase).where(IapPurchase.transaction_id == txn))
    assert purchase is not None
    assert purchase.status == STATUS_REFUND_REVERSED

    # Second reverse is no-op
    asn_rev2 = _verified_asn(
        ntype="REFUND_REVERSED",
        txn=_verified_txn(txn=txn, product="stars_50", token=token),
    )
    monkeypatch.setattr(
        apple_iap, "verify_signed_notification_payload", lambda p: asn_rev2
    )
    apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    db_session.refresh(user)
    assert int(user.ai_stars) == 60


def test_refund_before_confirm_blocks_credit(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.early@example.com", "iapEarly")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])
    token = apple_iap.app_account_token_for_user(user_id)
    txn = "apple-early-refund-1"
    starter = me.json()["ai_stars"]

    asn = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn=txn, product="stars_150", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)
    note = client.post(
        "/api/v1/shop/iap/apple/notifications",
        json={"signedPayload": "a.b.c"},
    )
    assert note.status_code == 200, note.text
    assert note.json()["processing_state"] == "unmatched"

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified_txn(txn=txn, product="stars_150", token=token),
    )
    conf = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={"platform": "ios", "product_id": "stars_150", "jws": "a.b.c"},
    )
    assert conf.status_code == 200, conf.text
    body = conf.json()
    assert body["stars_credited"] == 0
    assert body.get("blocked") is True
    assert body["ai_stars"] == starter

    purchase = db_session.scalar(select(IapPurchase).where(IapPurchase.transaction_id == txn))
    assert purchase is not None
    assert purchase.status == STATUS_BLOCKED
    assert int(purchase.stars_credited) == 0


def test_revoke_mirrors_refund_policy(db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    user = User(
        email=f"rvk_{uuid.uuid4().hex[:8]}@example.com",
        username=f"rvk_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=160,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"rvk-{uuid.uuid4().hex[:8]}"
    db_session.add(
        IapPurchase(
            user_id=user.id,
            platform="ios",
            product_id="stars_150",
            transaction_id=txn,
            status=STATUS_ACTIVE,
            stars_credited=150,
        )
    )
    db_session.commit()
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)
    asn = _verified_asn(
        ntype="REVOKE",
        txn=_verified_txn(txn=txn, product="stars_150", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 10
    purchase = db_session.scalar(select(IapPurchase).where(IapPurchase.transaction_id == txn))
    assert purchase is not None
    assert purchase.status == "revoked"


def test_ignored_subscription_notification(db_session, monkeypatch):
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)
    asn = VerifiedAppleNotification(
        notification_uuid=str(uuid.uuid4()),
        notification_type="DID_RENEW",
        subtype=None,
        environment="Sandbox",
        signed_date=1,
        transaction=None,
        raw=SimpleNamespace(),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "ignored"


def test_credit_after_refund_idempotent_conflict(client, db_session, monkeypatch):
    _enable_apple_credit(monkeypatch)
    tokens = register_with_invite(client, db_session, "iap.postref@example.com", "iapPostRef")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])
    token = apple_iap.app_account_token_for_user(user_id)
    txn = "apple-post-ref-1"

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified_txn(txn=txn, product="stars_50", token=token),
    )
    assert (
        client.post(
            "/api/v1/shop/iap/confirm",
            headers=_auth(tokens),
            json={"platform": "ios", "product_id": "stars_50", "jws": "a.b.c"},
        ).status_code
        == 200
    )

    asn = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn=txn, product="stars_50", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    assert (
        client.post(
            "/api/v1/shop/iap/apple/notifications",
            json={"signedPayload": "a.b.c"},
        ).status_code
        == 200
    )

    again = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={"platform": "ios", "product_id": "stars_50", "jws": "a.b.c"},
    )
    assert again.status_code == 200
    assert again.json()["stars_credited"] == 0
    assert again.json().get("already_processed") is True


def test_unmatched_notification_not_assigned_cross_account(db_session, monkeypatch):
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)
    asn = _verified_asn(
        ntype="REFUND",
        txn=_verified_txn(txn="unknown-txn-x", product="stars_50", token=str(uuid.uuid4())),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "unmatched"
    row = db_session.scalar(
        select(IapAppleNotification).where(
            IapAppleNotification.notification_uuid == asn.notification_uuid
        )
    )
    assert row is not None
    assert row.user_id is None
    assert row.iap_purchase_id is None
