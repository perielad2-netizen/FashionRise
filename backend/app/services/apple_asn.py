"""App Store Server Notifications V2 — durable, idempotent refund/revoke handling.

Consumable Stars policy (not subscription renewal semantics):

- ``REFUND`` / ``REVOKE``: prevent new credit; claw back remaining Stars from the
  purchase; any shortfall becomes ``users.ai_stars_iap_debt`` (balance never < 0).
- ``REFUND_REVERSED``: restore previously clawed Stars for that purchase only
  (debt first, then balance). Never invents a fresh purchase credit.
- Duplicate notification UUIDs and duplicate financial kinds are no-ops.
- Notifications before confirm: persist as ``unmatched`` / create ``blocked``
  purchase when ``appAccountToken`` maps to a known purchase later on confirm.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.models.iap_apple_notification import IapAppleNotification
from app.models.iap_purchase import (
    STATUS_BLOCKED,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.user import User
from app.services import ai_stars, apple_iap

_log = logging.getLogger(__name__)

# Consumable Stars — only these ASN types mutate wallet state in Phase B.
_TAKEBACK_TYPES = frozenset({"REFUND", "REVOKE"})
_RESTORE_TYPES = frozenset({"REFUND_REVERSED"})
_HANDLED_TYPES = _TAKEBACK_TYPES | _RESTORE_TYPES

# Max signedPayload characters (~512 KiB). Apple payloads are far smaller.
MAX_SIGNED_PAYLOAD_CHARS = 512 * 1024


def process_apple_notification(db: Session, *, signed_payload: str) -> dict[str, Any]:
    """Verify + apply one ASN V2 notification. Safe under concurrent workers."""
    raw = (signed_payload or "").strip()
    if not raw:
        raise ValidationAppError("signedPayload is required")
    if len(raw) > MAX_SIGNED_PAYLOAD_CHARS:
        raise ValidationAppError("signedPayload exceeds size limit")

    if not apple_iap.apple_iap_configured():
        raise ServiceUnavailableError("Apple IAP verification is not configured")

    verified = apple_iap.verify_signed_notification_payload(raw)

    existing = db.scalar(
        select(IapAppleNotification).where(
            IapAppleNotification.notification_uuid == verified.notification_uuid
        )
    )
    if existing is not None:
        return _receipt_payload(existing, duplicate=True)

    txn = verified.transaction
    row = IapAppleNotification(
        id=uuid.uuid4(),
        notification_uuid=verified.notification_uuid,
        notification_type=verified.notification_type,
        subtype=verified.subtype,
        environment=verified.environment,
        transaction_id=txn.transaction_id if txn else None,
        original_transaction_id=txn.original_transaction_id if txn else None,
        product_id=txn.product_id if txn else None,
        app_account_token=(txn.app_account_token if txn else None),
        processing_state="processing",
        processing_attempts=1,
        audit_meta={
            "signed_date": verified.signed_date,
            "has_transaction": txn is not None,
        },
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        again = db.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == verified.notification_uuid
            )
        )
        if again is None:
            raise
        return _receipt_payload(again, duplicate=True)

    try:
        _apply_verified_notification(db, row, verified)
        db.commit()
    except IntegrityError:
        # Concurrent financial adjustment — reload and treat as applied/ignored.
        db.rollback()
        again = db.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == verified.notification_uuid
            )
        )
        if again is None:
            raise
        return _receipt_payload(again, duplicate=True)
    except Exception:
        db.rollback()
        # Persist failure state in a fresh attempt without losing the UUID uniqueness.
        fail_db_row = db.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == verified.notification_uuid
            )
        )
        if fail_db_row is not None:
            fail_db_row.processing_state = "failed"
            fail_db_row.processing_attempts = int(fail_db_row.processing_attempts or 0) + 1
            fail_db_row.last_error = "processing_error"
            fail_db_row.updated_at = datetime.now(UTC)
            db.commit()
        _log.exception(
            "apple_asn_process_failed uuid_suffix=%s type=%s",
            verified.notification_uuid[-8:],
            verified.notification_type,
        )
        raise

    db.refresh(row)
    return _receipt_payload(row, duplicate=False)


def pending_takeback_for_transaction(db: Session, *, transaction_id: str) -> IapAppleNotification | None:
    """Return an unmatched/applied takeback ASN for this Apple transaction id."""
    txn = (transaction_id or "").strip()
    if not txn:
        return None
    return db.scalar(
        select(IapAppleNotification)
        .where(
            IapAppleNotification.transaction_id == txn,
            IapAppleNotification.notification_type.in_(tuple(_TAKEBACK_TYPES)),
            IapAppleNotification.processing_state.in_(("unmatched", "applied", "ignored")),
        )
        .order_by(IapAppleNotification.created_at.asc())
        .limit(1)
    )


def _apply_verified_notification(
    db: Session,
    row: IapAppleNotification,
    verified: apple_iap.VerifiedAppleNotification,
) -> None:
    ntype = verified.notification_type
    if ntype not in _HANDLED_TYPES:
        # TEST and subscription lifecycle events: acknowledge, no wallet mutation.
        row.processing_state = "ignored"
        row.processed_at = datetime.now(UTC)
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "ignored_non_consumable_takeback",
        }
        return

    txn = verified.transaction
    if txn is None:
        row.processing_state = "failed"
        row.last_error = "missing_nested_transaction"
        row.processed_at = datetime.now(UTC)
        return

    purchase = _find_ios_purchase(db, transaction_id=txn.transaction_id)
    if purchase is None and txn.original_transaction_id:
        purchase = _find_ios_purchase(db, transaction_id=txn.original_transaction_id)

    if purchase is None:
        # Persist unmatched — confirm path will refuse credit when it sees this.
        row.processing_state = "unmatched"
        row.processed_at = datetime.now(UTC)
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "unmatched_awaiting_purchase",
        }
        _log.info(
            "apple_asn_unmatched type=%s txn_suffix=%s",
            ntype,
            txn.transaction_id[-12:],
        )
        return

    # Lock purchase + user for financial mutation.
    locked_purchase = db.scalar(
        select(IapPurchase).where(IapPurchase.id == purchase.id).with_for_update()
    )
    if locked_purchase is None:
        row.processing_state = "failed"
        row.last_error = "purchase_missing_under_lock"
        return

    user = db.scalar(select(User).where(User.id == locked_purchase.user_id).with_for_update())
    if user is None:
        row.processing_state = "failed"
        row.last_error = "user_missing"
        return

    # Ownership: if nested appAccountToken present, it must match purchase owner.
    expected = apple_iap.app_account_token_for_user(user.id)
    got = (txn.app_account_token or "").strip()
    if got and got.lower() != expected.lower():
        row.processing_state = "failed"
        row.last_error = "app_account_token_mismatch"
        _log.warning(
            "apple_asn_token_mismatch purchase_id=%s type=%s",
            locked_purchase.id,
            ntype,
        )
        raise ForbiddenError("Apple notification appAccountToken does not match purchase owner")

    row.user_id = user.id
    row.iap_purchase_id = locked_purchase.id

    if ntype in _TAKEBACK_TYPES:
        _apply_takeback(db, row, user, locked_purchase, kind=ntype)
    else:
        _apply_refund_reversed(db, row, user, locked_purchase)

    # Helpers may set ignored/failed; only default to applied when still processing.
    if row.processing_state == "processing":
        row.processing_state = "applied"
    if row.processed_at is None:
        row.processed_at = datetime.now(UTC)


def _apply_takeback(
    db: Session,
    row: IapAppleNotification,
    user: User,
    purchase: IapPurchase,
    *,
    kind: str,
) -> None:
    """REFUND / REVOKE — claw back remaining credited Stars once."""
    if purchase.status == STATUS_BLOCKED:
        # Never credited — nothing to claw; ensure still blocked.
        row.audit_meta = {**(row.audit_meta or {}), "policy": "already_blocked"}
        return

    already = db.scalar(
        select(IapStarsAdjustment).where(
            IapStarsAdjustment.iap_purchase_id == purchase.id,
            IapStarsAdjustment.adjustment_kind.in_(("REFUND", "REVOKE")),
        )
    )
    if already is not None:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "takeback_already_applied"}
        return

    credited = max(0, int(purchase.stars_credited or 0))
    prior_claw = max(0, int(purchase.stars_clawed_back or 0))
    need = max(0, credited - prior_claw)
    if need <= 0 and purchase.status in (STATUS_REFUNDED, STATUS_REVOKED):
        row.audit_meta = {**(row.audit_meta or {}), "policy": "nothing_to_claw"}
        return

    from_balance, added_debt, balance_after, debt_after = ai_stars.apply_iap_clawback(
        db, user, stars_to_recover=need
    )
    purchase.stars_clawed_back = prior_claw + need
    purchase.status = STATUS_REVOKED if kind == "REVOKE" else STATUS_REFUNDED

    adj = IapStarsAdjustment(
        id=uuid.uuid4(),
        user_id=user.id,
        iap_purchase_id=purchase.id,
        notification_id=row.id,
        platform=purchase.platform,
        transaction_id=purchase.transaction_id,
        adjustment_kind=kind,
        stars_delta_balance=-from_balance,
        stars_delta_debt=added_debt,
        balance_after=balance_after,
        debt_after=debt_after,
        note=f"asn:{kind}",
    )
    db.add(adj)
    try:
        db.flush()
    except IntegrityError:
        # Concurrent worker won the unique (purchase, kind) race — do not claw twice.
        # Roll back only the failed adjustment insert by expiring and re-reading.
        db.expire_all()
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "takeback_lost_unique_race",
        }
        # Re-load purchase/user so we do not commit a double clawback from this worker.
        # Raise to outer handler which rolls back this notification attempt; Apple retries
        # and finds takeback already applied.
        raise
    _log.info(
        "apple_asn_takeback kind=%s user_id=%s stars=%s from_balance=%s debt_add=%s",
        kind,
        user.id,
        need,
        from_balance,
        added_debt,
    )


def _apply_refund_reversed(
    db: Session,
    row: IapAppleNotification,
    user: User,
    purchase: IapPurchase,
) -> None:
    """REFUND_REVERSED — restore prior clawback only; never a fresh purchase credit."""
    existing = db.scalar(
        select(IapStarsAdjustment).where(
            IapStarsAdjustment.iap_purchase_id == purchase.id,
            IapStarsAdjustment.adjustment_kind == "REFUND_REVERSED",
        )
    )
    if existing is not None:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "restore_already_applied"}
        return

    takeback = db.scalar(
        select(IapStarsAdjustment).where(
            IapStarsAdjustment.iap_purchase_id == purchase.id,
            IapStarsAdjustment.adjustment_kind.in_(("REFUND", "REVOKE")),
        )
    )
    if takeback is None:
        # No prior takeback on our ledger — do not invent Stars.
        row.processing_state = "ignored"
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "refund_reversed_without_prior_takeback",
        }
        row.processed_at = datetime.now(UTC)
        return

    clawed = max(0, int(purchase.stars_clawed_back or 0) - int(purchase.stars_restored or 0))
    if clawed <= 0:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "nothing_to_restore"}
        return

    debt_reduced, balance_added, balance_after, debt_after = ai_stars.restore_iap_clawback(
        db, user, stars_to_restore=clawed
    )
    purchase.stars_restored = int(purchase.stars_restored or 0) + clawed
    purchase.status = STATUS_REFUND_REVERSED

    adj = IapStarsAdjustment(
        id=uuid.uuid4(),
        user_id=user.id,
        iap_purchase_id=purchase.id,
        notification_id=row.id,
        platform=purchase.platform,
        transaction_id=purchase.transaction_id,
        adjustment_kind="REFUND_REVERSED",
        stars_delta_balance=balance_added,
        stars_delta_debt=-debt_reduced,
        balance_after=balance_after,
        debt_after=debt_after,
        note="asn:REFUND_REVERSED",
    )
    db.add(adj)
    db.flush()
    _log.info(
        "apple_asn_refund_reversed user_id=%s restored=%s debt_reduced=%s balance_add=%s",
        user.id,
        clawed,
        debt_reduced,
        balance_added,
    )


def _find_ios_purchase(db: Session, *, transaction_id: str) -> IapPurchase | None:
    return db.scalar(
        select(IapPurchase).where(
            IapPurchase.platform == "ios",
            IapPurchase.transaction_id == transaction_id,
        )
    )


def _receipt_payload(row: IapAppleNotification, *, duplicate: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "duplicate": duplicate,
        "notification_uuid": row.notification_uuid,
        "notification_type": row.notification_type,
        "processing_state": row.processing_state,
    }
