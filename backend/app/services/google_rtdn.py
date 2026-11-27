"""Google Play Real-time Developer Notifications (Pub/Sub push) + voided purchases.

Authenticated by Google OIDC bearer when ``IAP_GOOGLE_RTDN_VERIFY_OIDC=true``
(default). Credits never originate here — only clawbacks / reconciliation.

OIDC requires:
  - Bearer token verified against ``IAP_GOOGLE_RTDN_AUDIENCE``
  - ``email`` claim exact-match to ``IAP_GOOGLE_RTDN_EXPECTED_EMAIL``
  - ``email_verified`` claim true

Clawbacks take the same purchase-token advisory lock as confirm, re-check
authoritative Play purchase state, and never deduct more than
``stars_credited - stars_clawed_back`` (Stars debt policy unchanged).
"""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select, text
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

_MAX_VOIDED_LOOKBACK_DAYS = 30


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
    """Operator poll of ``purchases.voidedpurchases.list`` (in-app only, ≤30d).

    Each voided token is recorded under a durable synthetic ``message_id`` so
    RTDN and reconcile cannot claw the same purchase twice.
    """
    if not google_iap.google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")

    days = max(1, min(int(lookback_days or 30), _MAX_VOIDED_LOOKBACK_DAYS))
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - (days * 24 * 60 * 60 * 1000)

    voided = google_iap.list_voided_purchases(start_time_ms=start_ms, end_time_ms=end_ms)
    scanned = 0
    applied = 0
    duplicates = 0
    unmatched = 0
    skipped = 0

    for item in voided:
        scanned += 1
        message_id = f"voidedpurchases:{item.purchase_token}:{item.order_id or 'no-order'}"
        existing = db.scalar(
            select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
        )
        if existing is not None:
            duplicates += 1
            continue

        row = IapGoogleNotification(
            id=uuid.uuid4(),
            message_id=message_id,
            notification_type="voided_reconcile",
            package_name=google_iap.google_package_name(),
            purchase_token=item.purchase_token,
            order_id=item.order_id,
            processing_state="received",
            audit_meta={
                "source": "voidedpurchases.list",
                "voided_time_millis": item.voided_time_millis,
            },
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            duplicates += 1
            continue

        purchase = _find_purchase(
            db, purchase_token=item.purchase_token, order_id=item.order_id
        )
        if purchase is None:
            row.processing_state = "unmatched"
            unmatched += 1
            db.commit()
            continue

        _clawback_purchase(
            db,
            row,
            purchase,
            kind="VOIDED",
            product_id_hint=None,
            authoritative="voidedpurchases",
        )
        if row.processing_state == "applied":
            applied += 1
        else:
            skipped += 1
        db.commit()

    return {
        "ok": True,
        "lookback_days": days,
        "scanned": scanned,
        "applied": applied,
        "duplicates": duplicates,
        "unmatched": unmatched,
        "skipped": skipped,
    }


def reconcile_canceled_active_purchases(db: Session, *, limit: int = 200) -> dict[str, Any]:
    """Backfill clawbacks when Play ``products.get`` shows canceled but RTDN/voided missed.

    Sandbox / Console refunds sometimes set ``purchaseState=1`` without a Pub/Sub
    cancel/void notification and without appearing in ``voidedpurchases.list``.
    Scan active Android rows that still have unrecovered Stars and claw back when
    Play confirms canceled (or 404). Idempotent via durable ``message_id``.
    """
    if not google_iap.google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")

    cap = max(1, min(int(limit or 200), 500))
    rows = list(
        db.scalars(
            select(IapPurchase)
            .where(
                IapPurchase.platform == "android",
                IapPurchase.purchase_token.is_not(None),
                IapPurchase.stars_credited > IapPurchase.stars_clawed_back,
            )
            .order_by(IapPurchase.created_at.asc())
            .limit(cap)
        ).all()
    )

    scanned = 0
    applied = 0
    duplicates = 0
    skipped = 0
    failed = 0

    for purchase in rows:
        scanned += 1
        token = (purchase.purchase_token or "").strip()
        if not token:
            skipped += 1
            continue
        message_id = f"products-canceled:{token}"
        existing = db.scalar(
            select(IapGoogleNotification).where(IapGoogleNotification.message_id == message_id)
        )
        if existing is not None:
            duplicates += 1
            continue

        try:
            play_check = _assert_play_voided_or_canceled(
                purchase_token=token,
                product_id=purchase.product_id,
                authoritative="products.get",
            )
        except Exception:  # noqa: BLE001
            _log.exception("canceled_reconcile_play_check_failed purchase_id=%s", purchase.id)
            failed += 1
            continue

        if not play_check.get("ok"):
            skipped += 1
            continue

        row = IapGoogleNotification(
            id=uuid.uuid4(),
            message_id=message_id,
            notification_type="canceled_reconcile",
            package_name=google_iap.google_package_name(),
            purchase_token=token,
            order_id=purchase.transaction_id,
            product_id=purchase.product_id,
            processing_state="received",
            audit_meta={
                "source": "products.get_canceled_reconcile",
                "play": play_check,
            },
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            duplicates += 1
            continue

        _clawback_purchase(
            db,
            row,
            purchase,
            kind="CANCELED",
            product_id_hint=purchase.product_id,
            authoritative="products.get",
        )
        if row.processing_state == "applied":
            applied += 1
        else:
            skipped += 1
        db.commit()

    return {
        "ok": True,
        "scanned": scanned,
        "applied": applied,
        "duplicates": duplicates,
        "skipped": skipped,
        "failed": failed,
    }


def _maybe_verify_oidc(authorization: str | None) -> None:
    settings = get_settings()
    if not bool(getattr(settings, "iap_google_rtdn_verify_oidc", True)):
        return
    if not (authorization or "").strip().lower().startswith("bearer "):
        raise ForbiddenError("Google RTDN requires OIDC Bearer token")

    audience = (getattr(settings, "iap_google_rtdn_audience", "") or "").strip()
    expected_email = (
        getattr(settings, "iap_google_rtdn_expected_email", "") or ""
    ).strip().lower()

    # Fail closed whenever verify is on: audience + dedicated push identity required.
    if not audience:
        raise ServiceUnavailableError(
            "IAP_GOOGLE_RTDN_AUDIENCE must be set when RTDN OIDC verify is enabled"
        )
    if not expected_email:
        raise ServiceUnavailableError(
            "IAP_GOOGLE_RTDN_EXPECTED_EMAIL must be set when RTDN OIDC verify is enabled"
        )
    if not expected_email.endswith(".gserviceaccount.com"):
        raise ServiceUnavailableError(
            "IAP_GOOGLE_RTDN_EXPECTED_EMAIL must be a Google service account email"
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        from google.auth.transport import requests as grequests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(token, grequests.Request(), audience)
    except ForbiddenError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ForbiddenError("Invalid Google RTDN OIDC token") from exc

    email = str(claims.get("email") or "").strip().lower()
    if email != expected_email:
        raise ForbiddenError("RTDN OIDC email does not match configured push identity")
    if claims.get("email_verified") is not True:
        raise ForbiddenError("RTDN OIDC email_verified claim required")


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
    _clawback_purchase(
        db,
        row,
        purchase,
        kind="VOIDED",
        product_id_hint=purchase.product_id,
        authoritative="products.get",
    )


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
        _clawback_purchase(
            db,
            row,
            purchase,
            kind="CANCELED",
            product_id_hint=sku or purchase.product_id,
            authoritative="products.get",
        )
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


def _assert_play_voided_or_canceled(
    *,
    purchase_token: str,
    product_id: str | None,
    authoritative: str,
) -> dict[str, Any]:
    """Confirm Play still treats the purchase as canceled/voided before clawback.

    ``voidedpurchases`` source is itself authoritative (list membership).
    ``products.get`` must show canceled (or 404 after revoke).
    """
    if authoritative == "voidedpurchases":
        return {"source": "voidedpurchases", "ok": True}

    pid = (product_id or "").strip()
    if not pid:
        # Without SKU we cannot call products.get — fail closed for RTDN clawback.
        raise ServiceUnavailableError(
            "Google RTDN clawback requires product_id for purchases.products.get"
        )
    try:
        verified = google_iap.verify_product_purchase(
            product_id=pid, purchase_token=purchase_token
        )
    except ForbiddenError as exc:
        # purchases.products.get 404 → purchase gone from Play (treat as voided).
        if "not found" in str(exc).lower():
            return {"source": "products.get", "ok": True, "not_found": True}
        raise

    if google_iap.is_canceled(verified):
        return {
            "source": "products.get",
            "ok": True,
            "purchase_state": verified.purchase_state,
            "environment": verified.environment,
        }
    if google_iap.is_pending(verified) or google_iap.is_purchased(verified):
        return {
            "source": "products.get",
            "ok": False,
            "purchase_state": verified.purchase_state,
            "environment": verified.environment,
        }
    return {
        "source": "products.get",
        "ok": True,
        "purchase_state": verified.purchase_state,
        "environment": verified.environment,
    }


def _clawback_purchase(
    db: Session,
    row: IapGoogleNotification,
    purchase: IapPurchase,
    *,
    kind: str,
    product_id_hint: str | None,
    authoritative: str,
) -> None:
    token = (purchase.purchase_token or row.purchase_token or "").strip()
    if not token:
        row.processing_state = "failed"
        row.audit_meta = {**(row.audit_meta or {}), "policy": "missing_purchase_token"}
        return

    # Serialize vs confirm + concurrent RTDN/reconcile on the same token.
    purchase_id = purchase.id
    lock_key = google_iap.purchase_token_lock_key(token)
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    # Drop identity-map stale values so concurrent clawbacks see committed
    # stars_clawed_back / status after the advisory lock is held.
    db.expire_all()
    locked_purchase = db.scalar(
        select(IapPurchase)
        .where(IapPurchase.id == purchase_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_purchase is None:
        row.processing_state = "failed"
        return

    play_check = _assert_play_voided_or_canceled(
        purchase_token=token,
        product_id=product_id_hint or locked_purchase.product_id,
        authoritative=authoritative,
    )
    if not play_check.get("ok"):
        row.processing_state = "ignored"
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "play_not_voided",
            "play": play_check,
        }
        row.iap_purchase_id = locked_purchase.id
        row.user_id = locked_purchase.user_id
        return

    user = db.scalar(
        select(User)
        .where(User.id == locked_purchase.user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        row.processing_state = "failed"
        return

    credited = int(locked_purchase.stars_credited or 0)
    clawed = int(locked_purchase.stars_clawed_back or 0)
    need = max(0, credited - clawed)
    row.iap_purchase_id = locked_purchase.id
    row.user_id = user.id
    if need <= 0:
        if locked_purchase.status not in (STATUS_REFUNDED, STATUS_REVOKED):
            locked_purchase.status = STATUS_REFUNDED
        row.processing_state = "applied"
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "nothing_to_claw",
            "play": play_check,
        }
        return

    from_balance, added_debt, balance_after, debt_after = ai_stars.apply_iap_clawback(
        db, user, stars_to_recover=need
    )
    locked_purchase.stars_clawed_back = clawed + need
    locked_purchase.status = STATUS_REVOKED if kind == "VOIDED" else STATUS_REFUNDED
    adj = IapStarsAdjustment(
        id=uuid.uuid4(),
        user_id=user.id,
        iap_purchase_id=locked_purchase.id,
        notification_id=None,
        platform="android",
        transaction_id=locked_purchase.transaction_id,
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
        "play": play_check,
    }
