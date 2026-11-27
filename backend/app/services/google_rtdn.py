"""Google Play Real-time Developer Notifications (Pub/Sub push) + voided purchases.

Authenticated by Google OIDC bearer when ``IAP_GOOGLE_RTDN_VERIFY_OIDC=true``
(default). Credits never originate here — only clawbacks / reconciliation.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.models.iap_google_notification import IapGoogleNotification
from app.models.iap_purchase import (
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.user import User
from app.services import ai_stars, google_iap

_log = logging.getLogger(__name__)

# oneTimeProductNotification.notificationType
_OTN_PURCHASED = 1
_OTN_CANCELED = 2


def process_google_rtdn(db: Session, *, body: dict[str, Any], authorization: str | None) -> dict[str, Any]:
    """Handle a Pub/Sub push envelope. Always ack with 200 when durable-recorded."""
    _maybe_verify_oidc(authorization)

    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, dict):
        raise ValidationAppError("Invalid Pub/Sub envelope")
    message_id = str(message.get("messageId") or message.get("message_id") or "").strip()
    if not message_id:
        raise ValidationAppError("Pub/Sub messageId required")

    existing = db.scalar(
        select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
    )
    if existing is not None:
        return {"ok": True, "duplicate": True, "state": existing.processing_state}

    data_b64 = message.get("data")
    if not data_b64:
        raise ValidationAppError("Pub/Sub message data required")
    try:
        raw = base64.b64decode(data_b64)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValidationAppError("Invalid RTDN payload encoding") from exc
    if not isinstance(payload, dict):
        raise ValidationAppError("Invalid RTDN payload")

    package_name = str(payload.get("packageName") or "").strip() or None
    expected = google_iap.google_package_name()
    if package_name and package_name != expected:
        raise ForbiddenError("RTDN packageName mismatch")

    row = IapGoogleNotification(
        id=uuid.uuid4(),
        message_id=message_id,
        notification_type="unknown",
        package_name=package_name or expected,
        processing_state="received",
        audit_meta={"keys": sorted(payload.keys())},
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "duplicate": True}

    try:
        if "voidedPurchaseNotification" in payload:
            _handle_voided(db, row, payload["voidedPurchaseNotification"])
        elif "oneTimeProductNotification" in payload:
            _handle_one_time(db, row, payload["oneTimeProductNotification"])
        elif "testNotification" in payload:
            row.notification_type = "test"
            row.processing_state = "applied"
            row.audit_meta = {**(row.audit_meta or {}), "test": True}
        else:
            row.notification_type = "ignored"
            row.processing_state = "ignored"
            row.audit_meta = {**(row.audit_meta or {}), "detail": "unsupported_notification"}
        db.commit()
    except Exception:  # noqa: BLE001
        _log.exception("google_rtdn_process_failed")
        db.rollback()
        raise ServiceUnavailableError("Google RTDN processing temporarily unavailable")

    return {"ok": True, "duplicate": False, "state": row.processing_state, "type": row.notification_type}


def reconcile_voided_purchases(db: Session, *, lookback_days: int = 30) -> dict[str, Any]:
    """Optional operator poll of voidedpurchases.list (no auto-schedule required)."""
    if not google_iap.google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")
    # Deferred: voidedpurchases.list needs startTime/endTime millis.
    # RTDN is the primary path; this stub documents the operator hook.
    _ = lookback_days
    _ = db
    return {
        "ok": True,
        "note": "Use RTDN for refunds; call Play voidedpurchases.list manually if backfill needed.",
    }


def _maybe_verify_oidc(authorization: str | None) -> None:
    settings = get_settings()
    if not bool(getattr(settings, "iap_google_rtdn_verify_oidc", True)):
        return
    if not (authorization or "").strip().lower().startswith("bearer "):
        raise ForbiddenError("Google RTDN requires OIDC Bearer token")
    # Full Google JWKS verification is enabled when audience is configured.
    audience = (getattr(settings, "iap_google_rtdn_audience", "") or "").strip()
    if not audience:
        # Fail closed for production shape: require audience when verify is on.
        if settings.environment == "production":
            raise ServiceUnavailableError(
                "IAP_GOOGLE_RTDN_AUDIENCE must be set when RTDN OIDC verify is enabled"
            )
        return
    token = authorization.split(" ", 1)[1].strip()
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests

        claims = id_token.verify_oauth2_token(token, grequests.Request(), audience)
        email = str(claims.get("email") or "")
        if not email.endswith("gserviceaccount.com"):
            raise ForbiddenError("RTDN OIDC email is not a Google service account")
    except ForbiddenError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ForbiddenError("Invalid Google RTDN OIDC token") from exc


def _handle_voided(db: Session, row: IapGoogleNotification, voided: Any) -> None:
    if not isinstance(voided, dict):
        row.processing_state = "failed"
        return
    token = str(voided.get("purchaseToken") or "").strip() or None
    order_id = str(voided.get("orderId") or "").strip() or None
    row.notification_type = "voided"
    row.purchase_token = token
    row.order_id = order_id
    purchase = _find_purchase(db, purchase_token=token, order_id=order_id)
    if purchase is None:
        row.processing_state = "unmatched"
        return
    _clawback_purchase(db, row, purchase, kind="VOIDED")


def _handle_one_time(db: Session, row: IapGoogleNotification, otn: Any) -> None:
    if not isinstance(otn, dict):
        row.processing_state = "failed"
        return
    token = str(otn.get("purchaseToken") or "").strip() or None
    sku = str(otn.get("sku") or "").strip() or None
    ntype = int(otn.get("notificationType") or 0)
    row.purchase_token = token
    row.product_id = sku
    if ntype == _OTN_PURCHASED:
        row.notification_type = "one_time_purchased"
        # Credit is client-confirm only — record for audit.
        purchase = _find_purchase(db, purchase_token=token, order_id=None)
        if purchase is not None:
            row.iap_purchase_id = purchase.id
            row.user_id = purchase.user_id
            row.processing_state = "applied"
        else:
            row.processing_state = "unmatched"
        return
    if ntype == _OTN_CANCELED:
        row.notification_type = "one_time_canceled"
        purchase = _find_purchase(db, purchase_token=token, order_id=None)
        if purchase is None:
            row.processing_state = "unmatched"
            return
        _clawback_purchase(db, row, purchase, kind="CANCELED")
        return
    row.notification_type = f"one_time_{ntype}"
    row.processing_state = "ignored"


def _find_purchase(
    db: Session, *, purchase_token: str | None, order_id: str | None
) -> IapPurchase | None:
    if purchase_token:
        row = db.scalar(
            select(IapPurchase).where(
                IapPurchase.platform == "android",
                IapPurchase.purchase_token == purchase_token,
            )
        )
        if row is not None:
            return row
    if order_id:
        return db.scalar(
            select(IapPurchase).where(
                IapPurchase.platform == "android",
                IapPurchase.transaction_id == order_id,
            )
        )
    return None


def _clawback_purchase(
    db: Session,
    row: IapGoogleNotification,
    purchase: IapPurchase,
    *,
    kind: str,
) -> None:
    user = db.scalar(select(User).where(User.id == purchase.user_id).with_for_update())
    if user is None:
        row.processing_state = "failed"
        return
    credited = int(purchase.stars_credited or 0)
    clawed = int(purchase.stars_clawed_back or 0)
    need = max(0, credited - clawed)
    row.iap_purchase_id = purchase.id
    row.user_id = user.id
    if need <= 0:
        if purchase.status not in (STATUS_REFUNDED, STATUS_REVOKED):
            purchase.status = STATUS_REFUNDED
        row.processing_state = "applied"
        row.audit_meta = {**(row.audit_meta or {}), "policy": "nothing_to_claw"}
        return

    from_balance, added_debt, balance_after, debt_after = ai_stars.apply_iap_clawback(
        db, user, stars_to_recover=need
    )
    purchase.stars_clawed_back = clawed + need
    purchase.status = STATUS_REVOKED if kind == "VOIDED" else STATUS_REFUNDED
    adj = IapStarsAdjustment(
        id=uuid.uuid4(),
        user_id=user.id,
        iap_purchase_id=purchase.id,
        notification_id=None,
        platform="android",
        transaction_id=purchase.transaction_id,
        adjustment_kind=kind,
        stars_delta_balance=-from_balance,
        stars_delta_debt=added_debt,
        balance_after=balance_after,
        debt_after=debt_after,
        note=f"google_rtdn:{kind}",
    )
    db.add(adj)
    row.processing_state = "applied"
    row.audit_meta = {
        **(row.audit_meta or {}),
        "from_balance": from_balance,
        "debt_add": added_debt,
    }
