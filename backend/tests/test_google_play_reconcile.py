"""Google Play financial reconcile — orders.get + entitlement classification."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
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


def test_classify_full_refund_with_canceled_entitlement():
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
        refund_total_currency="ILS",
        refund_total_units="19",
        refund_total_nanos=900000000,
        points_details=None,
        raw={},
    )
    decision, reason = google_play_reconcile.classify_recovery(
        order=order, entitlement="canceled", stars_outstanding=50
    )
    assert decision == "recover_full"
    assert "full_refund" in reason


def test_classify_refund_without_revoke_is_review():
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
        refund_total_currency="ILS",
        refund_total_units="19",
        refund_total_nanos=0,
        points_details=None,
        raw={},
    )
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

    order = google_iap.GooglePlayOrder(
        order_id="GPA.orders-rec-1",
        purchase_token="orders-rec-token-1",
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
