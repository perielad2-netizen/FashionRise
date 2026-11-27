"""Google Play financial reconcile — orders.get + entitlement classification."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.models.iap_google_notification import IapGoogleNotification
from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase
from app.models.user import User
from app.services import google_iap, google_play_reconcile, google_rtdn


def _user(db: Session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        username=email.split("@")[0][:20],
        hashed_password="x",
        is_active=True,
        ai_stars=100,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _purchase(db: Session, user: User, *, token: str, order: str) -> IapPurchase:
    row = IapPurchase(
        id=uuid.uuid4(),
        user_id=user.id,
        platform="android",
        product_id="stars_50",
        transaction_id=order,
        original_transaction_id=order,
        purchase_token=token,
        stars_credited=50,
        stars_clawed_back=0,
        status=STATUS_ACTIVE,
        environment="Sandbox",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _full_refund_order(*, order_id: str, token: str, product_id: str = "stars_50") -> google_iap.GooglePlayOrder:
    return google_iap.GooglePlayOrder(
        order_id=order_id,
        purchase_token=token,
        state="REFUNDED",
        create_time=None,
        last_event_time=None,
        product_ids=(product_id,),
        has_full_refund_event=True,
        has_partial_refund_events=False,
        has_cancellation_event=False,
        refund_reason="OTHER",
        refund_total_currency="ILS",
        refund_total_units="19",
        refund_total_nanos=900000000,
        points_details=None,
        raw={},
    )


def test_classify_full_refund_with_canceled_entitlement():
    order = _full_refund_order(order_id="GPA.x", token="t")
    decision, reason = google_play_reconcile.classify_recovery(
        order=order, entitlement="canceled", stars_outstanding=50
    )
    assert decision == "recover_full"
    assert "full_refund" in reason


def test_classify_requires_authoritative_refund_total():
    order = google_iap.GooglePlayOrder(
        order_id="GPA.x",
        purchase_token="t",
        state="REFUNDED",
        create_time=None,
        last_event_time=None,
        product_ids=("stars_50",),
        has_full_refund_event=True,
        has_partial_refund_events=False,
        has_cancellation_event=False,
        refund_reason="OTHER",
        refund_total_currency=None,
        refund_total_units=None,
        refund_total_nanos=None,
        points_details=None,
        raw={},
    )
    decision, reason = google_play_reconcile.classify_recovery(
        order=order, entitlement="canceled", stars_outstanding=50
    )
    assert decision == "review"
    assert "authoritative" in reason or "missing" in reason


def test_classify_refund_event_without_refunded_state_is_review():
    order = google_iap.GooglePlayOrder(
        order_id="GPA.x",
        purchase_token="t",
        state="PROCESSED",
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
    decision, reason = google_play_reconcile.classify_recovery(
        order=order, entitlement="canceled", stars_outstanding=50
    )
    assert decision == "review"
    assert "without_refunded_state" in reason


def test_classify_refund_without_revoke_is_review():
    order = _full_refund_order(order_id="GPA.x", token="t")
    decision, reason = google_play_reconcile.classify_recovery(
        order=order, entitlement="purchased", stars_outstanding=50
    )
    assert decision == "review"
    assert "without_entitlement_revoke" in reason


def test_classify_partial_and_pending():
    partial = google_iap.GooglePlayOrder(
        order_id="GPA.p",
        purchase_token="t",
        state="PARTIALLY_REFUNDED",
        create_time=None,
        last_event_time=None,
        product_ids=("stars_50",),
        has_full_refund_event=False,
        has_partial_refund_events=True,
        has_cancellation_event=False,
        refund_reason=None,
        refund_total_currency=None,
        refund_total_units=None,
        refund_total_nanos=None,
        points_details=None,
        raw={},
    )
    d, _ = google_play_reconcile.classify_recovery(
        order=partial, entitlement="canceled", stars_outstanding=50
    )
    assert d == "review"

    pending = google_iap.GooglePlayOrder(
        order_id="GPA.w",
        purchase_token="t",
        state="PENDING_REFUND",
        create_time=None,
        last_event_time=None,
        product_ids=("stars_50",),
        has_full_refund_event=False,
        has_partial_refund_events=False,
        has_cancellation_event=False,
        refund_reason=None,
        refund_total_currency=None,
        refund_total_units=None,
        refund_total_nanos=None,
        points_details=None,
        raw={},
    )
    d2, _ = google_play_reconcile.classify_recovery(
        order=pending, entitlement="canceled", stars_outstanding=50
    )
    assert d2 == "wait"


def test_identity_mismatch_never_deducts(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    user = _user(db_session, "reconcile-id@fashionrise.app")
    _purchase(db_session, user, token="id-token", order="GPA.id-1")
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    # Contradictory token / product on the Play order.
    bad = _full_refund_order(order_id="GPA.id-1", token="OTHER-TOKEN", product_id="stars_150")
    monkeypatch.setattr(google_iap, "get_order", lambda *_a, **_k: bad)
    report = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=False, order_id="GPA.id-1"
    )
    assert report["decisions"][0]["decision"] == "skip_identity"
    db_session.refresh(user)
    assert int(user.ai_stars) == 100


def test_dry_run_recover_and_apply_idempotent_with_rtdn(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IAP_GOOGLE_RTDN_VERIFY_OIDC", "false")
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    user = _user(db_session, "reconcile-orders@fashionrise.app")
    purchase = _purchase(
        db_session, user, token="orders-rec-token-1", order="GPA.orders-rec-1"
    )

    order = _full_refund_order(order_id="GPA.orders-rec-1", token="orders-rec-token-1")
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "get_order", lambda *_a, **_k: order)

    class _V:
        purchase_state = 1
        environment = "Sandbox"
        product_id = "stars_50"

    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: _V())
    monkeypatch.setattr(google_iap, "is_canceled", lambda _v: True)
    monkeypatch.setattr(google_iap, "is_pending", lambda _v: False)
    monkeypatch.setattr(google_iap, "is_purchased", lambda _v: False)

    real_execute = db_session.execute

    def _execute(stmt, *args, **kwargs):
        sql = str(getattr(stmt, "text", stmt))
        if "pg_advisory_xact_lock" in sql:
            return MagicMock()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", _execute)

    dry = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=True, order_id="GPA.orders-rec-1"
    )
    assert dry["dry_run"] is True
    assert dry["stars_would_recover"] == 50
    assert dry["decisions"][0]["decision"] == "recover_full"
    db_session.refresh(user)
    assert int(user.ai_stars) == 100  # dry-run must not mutate

    applied = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=False, order_id="GPA.orders-rec-1"
    )
    assert applied["dry_run"] is False
    assert applied["stars_recovered"] == 50
    assert applied["decisions"][0]["stars_recovered"] == 50
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 50
    assert int(purchase.stars_clawed_back) == 50

    # Duplicate RTDN canceled must not deduct again.
    import base64
    import json

    payload = {
        "version": "1.0",
        "packageName": google_iap.google_package_name(),
        "eventTimeMillis": "1",
        "oneTimeProductNotification": {
            "version": "1.0",
            "notificationType": 2,
            "purchaseToken": "orders-rec-token-1",
            "sku": "stars_50",
        },
    }
    body = {
        "message": {
            "messageId": "rtdn-dup-after-orders-reconcile",
            "data": base64.b64encode(json.dumps(payload).encode()).decode(),
        }
    }
    google_rtdn.process_google_rtdn(db_session, body=body, authorization=None)
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 50
    assert int(purchase.stars_clawed_back) == 50

    # Second reconcile apply is a no-op.
    again = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=False, order_id="GPA.orders-rec-1"
    )
    assert again["stars_recovered"] == 0
    db_session.refresh(user)
    assert int(user.ai_stars) == 50


def test_failed_reconcile_row_does_not_suppress_retry(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    user = _user(db_session, "reconcile-retry@fashionrise.app")
    purchase = _purchase(
        db_session, user, token="retry-token-1", order="GPA.retry-1"
    )
    db_session.add(
        IapGoogleNotification(
            id=uuid.uuid4(),
            message_id="orders-reconcile:retry-token-1",
            notification_type="orders_reconcile",
            package_name=google_iap.google_package_name(),
            purchase_token="retry-token-1",
            order_id="GPA.retry-1",
            product_id="stars_50",
            processing_state="failed",
            audit_meta={"policy": "prior_failure"},
        )
    )
    db_session.commit()

    order = _full_refund_order(order_id="GPA.retry-1", token="retry-token-1")
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)
    monkeypatch.setattr(google_iap, "get_order", lambda *_a, **_k: order)

    class _V:
        purchase_state = 1
        environment = "Sandbox"
        product_id = "stars_50"

    monkeypatch.setattr(google_iap, "verify_product_purchase", lambda **_k: _V())
    monkeypatch.setattr(google_iap, "is_canceled", lambda _v: True)
    monkeypatch.setattr(google_iap, "is_pending", lambda _v: False)
    monkeypatch.setattr(google_iap, "is_purchased", lambda _v: False)
    real_execute = db_session.execute

    def _execute(stmt, *args, **kwargs):
        sql = str(getattr(stmt, "text", stmt))
        if "pg_advisory_xact_lock" in sql:
            return MagicMock()
        return real_execute(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", _execute)

    applied = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=False, order_id="GPA.retry-1"
    )
    assert applied["stars_recovered"] == 50
    db_session.refresh(user)
    db_session.refresh(purchase)
    assert int(user.ai_stars) == 50
    assert int(purchase.stars_clawed_back) == 50


def test_orders_get_error_never_deducts(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    user = _user(db_session, "reconcile-err@fashionrise.app")
    _purchase(db_session, user, token="err-token", order="GPA.err-1")
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)

    def _boom(*_a, **_k):
        raise ServiceUnavailableError("timeout")

    monkeypatch.setattr(google_iap, "get_order", _boom)
    report = google_play_reconcile.reconcile_android_purchases(
        db_session, dry_run=False, order_id="GPA.err-1"
    )
    assert report["decisions"][0]["decision"] == "skip_error"
    db_session.refresh(user)
    assert int(user.ai_stars) == 100


def test_admin_snapshot_reads_persisted_only(db_session: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(google_iap, "google_iap_configured", lambda: True)

    def _must_not_call(*_a, **_k):
        raise AssertionError("Admin overview must not call live Play APIs")

    monkeypatch.setattr(google_iap, "get_order", _must_not_call)
    monkeypatch.setattr(google_iap, "verify_product_purchase", _must_not_call)

    google_play_reconcile.record_reconcile_run(
        db_session,
        status="success",
        dry_run=True,
        report={
            "scanned": 2,
            "provider_requests": 4,
            "stars_would_recover": 50,
            "stars_recovered": 0,
            "sandbox_scanned": 1,
            "production_scanned": 1,
            "counts": {"ok": 1, "recover_full": 1},
        },
    )
    snap = google_play_reconcile.admin_reconciliation_snapshot(db_session)
    assert snap["kind"] == "persisted"
    assert snap["source"] == "postgresql"
    assert snap["apply_enabled"] is False
    assert snap["last_successful_sync"]["scanned"] == 2
    assert "sandbox" in snap and "production" in snap
