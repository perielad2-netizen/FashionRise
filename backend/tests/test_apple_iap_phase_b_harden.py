"""Phase B hardening — ASN retry, confirm/refund races, refund cycles, debt conservation."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.security import hash_password
from app.models.iap_apple_notification import IapAppleNotification
from app.models.iap_purchase import (
    STATUS_ACTIVE,
    STATUS_BLOCKED,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.user import User
from app.services import ai_stars, apple_asn, apple_iap, iap_service
from app.services.apple_iap import VerifiedAppleNotification, VerifiedAppleTransaction
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _enable_credit(monkeypatch) -> None:
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)


def _txn(
    *,
    txn: str,
    product: str = "stars_50",
    token: str | None = None,
) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id=product,
        bundle_id="app.fashionrise.studio",
        environment="Sandbox",
        type="Consumable",
        app_account_token=token,
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=SimpleNamespace(),
    )


def _asn(
    *,
    ntype: str,
    txn: VerifiedAppleTransaction,
    uuid_s: str | None = None,
) -> VerifiedAppleNotification:
    return VerifiedAppleNotification(
        notification_uuid=uuid_s or str(uuid.uuid4()),
        notification_type=ntype,
        subtype=None,
        environment=txn.environment,
        signed_date=1_700_000_000_000,
        transaction=txn,
        raw=SimpleNamespace(),
    )


def test_failed_notification_same_uuid_is_retryable(engine, monkeypatch):
    """Persisted failure then successful redelivery of the identical notification UUID."""
    _enable_credit(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    n_uuid = str(uuid.uuid4())
    txn = f"retry-{uuid.uuid4().hex[:10]}"

    boot = SessionLocal()
    try:
        user = User(
            email=f"retry_{uuid.uuid4().hex[:8]}@example.com",
            username=f"retry_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            ai_stars=60,
            ai_stars_iap_debt=0,
        )
        boot.add(user)
        boot.flush()
        token = apple_iap.app_account_token_for_user(user.id)
        boot.add(
            IapPurchase(
                user_id=user.id,
                platform="ios",
                product_id="stars_50",
                transaction_id=txn,
                status=STATUS_ACTIVE,
                stars_credited=50,
            )
        )
        boot.commit()
        user_id = user.id
    finally:
        boot.close()

    asn = _asn(ntype="REFUND", txn=_txn(txn=txn, token=token), uuid_s=n_uuid)
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)

    calls = {"n": 0}
    real_claw = ai_stars.apply_iap_clawback

    def boom(db, user, *, stars_to_recover):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated_crash")
        return real_claw(db, user, stars_to_recover=stars_to_recover)

    monkeypatch.setattr(apple_asn.ai_stars, "apply_iap_clawback", boom)

    db1 = SessionLocal()
    try:
        with pytest.raises(ServiceUnavailableError):
            apple_asn.process_apple_notification(db1, signed_payload="a.b.c")
    finally:
        db1.close()

    check = SessionLocal()
    try:
        row = check.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == n_uuid
            )
        )
        assert row is not None
        assert row.processing_state == "failed"
    finally:
        check.close()

    db2 = SessionLocal()
    try:
        out = apple_asn.process_apple_notification(db2, signed_payload="a.b.c")
        assert out["processing_state"] == "applied"
        assert out["notification_uuid"] == n_uuid
    finally:
        db2.close()

    check2 = SessionLocal()
    try:
        u = check2.get(User, user_id)
        assert u is not None
        assert int(u.ai_stars) == 10
        assert (
            check2.scalar(
                select(func.count())
                .select_from(IapStarsAdjustment)
                .where(IapStarsAdjustment.transaction_id == txn)
            )
            == 1
        )
        again = apple_asn.process_apple_notification(check2, signed_payload="a.b.c")
        assert again["duplicate"] is True
        assert again["processing_state"] == "applied"
        assert (
            check2.scalar(
                select(func.count())
                .select_from(IapStarsAdjustment)
                .where(IapStarsAdjustment.transaction_id == txn)
            )
            == 1
        )
    finally:
        check2.close()


def test_refund_then_reverse_then_refund_cycle(db_session, monkeypatch):
    _enable_credit(monkeypatch)
    user = User(
        email=f"cycle_{uuid.uuid4().hex[:8]}@example.com",
        username=f"cycle_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=60,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"cycle-{uuid.uuid4().hex[:10]}"
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

    def run(ntype: str) -> dict:
        payload = _asn(ntype=ntype, txn=_txn(txn=txn, token=token))
        monkeypatch.setattr(
            apple_iap, "verify_signed_notification_payload", lambda p, a=payload: a
        )
        return apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")

    assert run("REFUND")["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 10

    # Duplicate REFUND — no second claw.
    assert run("REFUND")["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 10

    assert run("REFUND_REVERSED")["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 60
    purchase = db_session.scalar(select(IapPurchase).where(IapPurchase.transaction_id == txn))
    assert purchase is not None
    assert purchase.status == STATUS_REFUND_REVERSED

    # Duplicate reverse — no double credit.
    assert run("REFUND_REVERSED")["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 60

    # Later REFUND after reverse (valid consumable cycle).
    assert run("REFUND")["processing_state"] == "applied"
    db_session.refresh(user)
    assert int(user.ai_stars) == 10
    assert purchase is not None
    db_session.refresh(purchase)
    assert purchase.status == STATUS_REFUNDED
    assert int(purchase.stars_clawed_back) == 100
    assert int(purchase.stars_restored) == 50


def test_refund_reversed_before_takeback_quarantined(db_session, monkeypatch):
    _enable_credit(monkeypatch)
    user = User(
        email=f"oo_{uuid.uuid4().hex[:8]}@example.com",
        username=f"oo_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=60,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"oo-{uuid.uuid4().hex[:10]}"
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

    asn = _asn(ntype="REFUND_REVERSED", txn=_txn(txn=txn, token=token))
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    out = apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    assert out["processing_state"] == "needs_reconciliation"
    db_session.refresh(user)
    assert int(user.ai_stars) == 60  # no invented credit


def test_debt_conservation_across_credit_and_reverse(db_session, monkeypatch):
    """Buy 500, spend 450, refund → debt 450; credit 200 settles; reverse restores net."""
    _enable_credit(monkeypatch)
    user = User(
        email=f"cons_{uuid.uuid4().hex[:8]}@example.com",
        username=f"cons_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        is_active=True,
        ai_stars=50,
        ai_stars_iap_debt=0,
    )
    db_session.add(user)
    db_session.flush()
    token = apple_iap.app_account_token_for_user(user.id)
    txn = f"cons-{uuid.uuid4().hex[:10]}"
    db_session.add(
        IapPurchase(
            user_id=user.id,
            platform="ios",
            product_id="stars_500",
            transaction_id=txn,
            status=STATUS_ACTIVE,
            stars_credited=500,
        )
    )
    db_session.commit()

    asn = _asn(
        ntype="REFUND",
        txn=_txn(txn=txn, product="stars_500", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    db_session.refresh(user)
    assert int(user.ai_stars) == 0
    assert int(user.ai_stars_iap_debt) == 450

    # Legitimate later credit settles debt first.
    ai_stars.credit_stars(db_session, user, 200, reason="later")
    db_session.commit()
    db_session.refresh(user)
    assert int(user.ai_stars) == 0
    assert int(user.ai_stars_iap_debt) == 250

    # Reverse restores remaining claw (500): reduces debt 250, balance +250.
    asn2 = _asn(
        ntype="REFUND_REVERSED",
        txn=_txn(txn=txn, product="stars_500", token=token),
    )
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn2)
    apple_asn.process_apple_notification(db_session, signed_payload="a.b.c")
    db_session.refresh(user)
    assert int(user.ai_stars_iap_debt) == 0
    assert int(user.ai_stars) == 250


def test_pg_confirm_vs_refund_either_order(engine, monkeypatch):
    """Separate connections: confirm∥refund never leave active+credited after refund."""
    _enable_credit(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"race-{uuid.uuid4().hex[:12]}"
    email = f"race_{uuid.uuid4().hex[:8]}@example.com"

    boot = SessionLocal()
    try:
        user = User(
            email=email,
            username=f"u_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
        )
        ai_stars.apply_new_user_stars(user)
        starter = int(user.ai_stars)
        boot.add(user)
        boot.commit()
        boot.refresh(user)
        user_id = user.id
        token = apple_iap.app_account_token_for_user(user_id)
    finally:
        boot.close()

    barrier = threading.Barrier(2, timeout=10)

    def do_confirm() -> str:
        monkeypatch.setattr(
            apple_iap,
            "verify_signed_transaction_jws",
            lambda jws: _txn(txn=txn_id, token=token),
        )
        db = SessionLocal()
        try:
            u = db.get(User, user_id)
            assert u is not None
            barrier.wait()
            out = iap_service.confirm_purchase(
                db,
                u,
                platform="ios",
                product_id="stars_50",
                transaction_id=txn_id,
                jws="a.b.c",
            )
            return f"confirm:{out.get('blocked')}:{out.get('stars_credited')}:{out.get('status')}"
        finally:
            db.close()

    def do_refund() -> str:
        asn = _asn(ntype="REFUND", txn=_txn(txn=txn_id, token=token))
        monkeypatch.setattr(
            apple_iap, "verify_signed_notification_payload", lambda p: asn
        )
        db = SessionLocal()
        try:
            barrier.wait()
            out = apple_asn.process_apple_notification(db, signed_payload="a.b.c")
            return f"refund:{out['processing_state']}"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(do_confirm), pool.submit(do_refund)]
        results = [f.result(timeout=30) for f in as_completed(futures)]

    assert any(r.startswith("confirm:") for r in results)
    assert any(r.startswith("refund:") for r in results)

    check = SessionLocal()
    try:
        purchase = check.scalar(
            select(IapPurchase).where(IapPurchase.transaction_id == txn_id)
        )
        u = check.get(User, user_id)
        assert purchase is not None
        assert u is not None
        # Never end as active with a full unreclaimed credit after a refund raced.
        if purchase.status == STATUS_ACTIVE:
            pytest.fail("purchase left ACTIVE after concurrent refund")
        if purchase.status == STATUS_BLOCKED:
            assert int(purchase.stars_credited) == 0
            assert int(u.ai_stars) == starter
        else:
            assert purchase.status in (STATUS_REFUNDED, STATUS_REVOKED)
            # Net: starter only (50 credited then clawed) or starter if blocked path.
            assert int(u.ai_stars) == starter
            assert int(u.ai_stars_iap_debt or 0) == 0
            adj = check.scalar(
                select(func.count())
                .select_from(IapStarsAdjustment)
                .where(IapStarsAdjustment.transaction_id == txn_id)
            )
            # Blocked path may have 0 adjustments; refunded path has 1.
            assert int(adj or 0) in (0, 1)
    finally:
        check.close()


def test_confirm_after_unmatched_refund_blocks(client, db_session, monkeypatch):
    _enable_credit(monkeypatch)
    tokens = register_with_invite(
        client, db_session, "iap.harden.block@example.com", "iapHardenBlock"
    )
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    user_id = uuid.UUID(me.json()["id"])
    token = apple_iap.app_account_token_for_user(user_id)
    txn = "harden-unmatched-1"
    starter = me.json()["ai_stars"]

    asn = _asn(ntype="REFUND", txn=_txn(txn=txn, product="stars_150", token=token))
    monkeypatch.setattr(apple_iap, "verify_signed_notification_payload", lambda p: asn)
    note = client.post(
        "/api/v1/shop/iap/apple/notifications",
        json={"signedPayload": "a.b.c"},
    )
    assert note.status_code == 200
    assert note.json()["processing_state"] == "unmatched"

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _txn(txn=txn, product="stars_150", token=token),
    )
    conf = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={"platform": "ios", "product_id": "stars_150", "jws": "a.b.c"},
    )
    assert conf.status_code == 200
    assert conf.json()["stars_credited"] == 0
    assert conf.json().get("blocked") is True
    assert conf.json()["ai_stars"] == starter
    purchase = db_session.scalar(select(IapPurchase).where(IapPurchase.transaction_id == txn))
    assert purchase is not None
    assert purchase.status == STATUS_BLOCKED
