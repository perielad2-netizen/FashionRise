"""App Store Server Notifications V2 — durable, idempotent refund/revoke handling.

Consumable Stars policy (not subscription renewal semantics):

- ``REFUND`` / ``REVOKE``: prevent new credit; claw back remaining Stars from the
  purchase; any shortfall becomes ``users.ai_stars_iap_debt`` (balance never < 0).
- ``REFUND_REVERSED``: restore previously clawed Stars for that purchase only
  (debt first, then balance). Never invents a fresh purchase credit.
- Duplicate notification UUIDs: terminal states (applied/ignored) are idempotent
  2xx; failed/unmatched/processing are safely retried under row locks.
- Notifications before confirm: persist as ``unmatched``; confirm under the same
  per-transaction advisory lock refuses credit and records ``blocked``.

Concurrency: confirm and ASN both take ``pg_advisory_xact_lock`` on
``iap:ios:<transaction_id>`` **before** mutating purchases/wallets (then lock
purchase, then user — never the reverse).
"""

from __future__ import annotations

import logging
import uuid
import zlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError
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
from app.services import ai_stars, apple_iap

_log = logging.getLogger(__name__)

# Consumable Stars — only these ASN types mutate wallet state in Phase B.
_TAKEBACK_TYPES = frozenset({"REFUND", "REVOKE"})
_RESTORE_TYPES = frozenset({"REFUND_REVERSED"})
_HANDLED_TYPES = _TAKEBACK_TYPES | _RESTORE_TYPES

# Terminal success states — Apple redelivery is a no-op 2xx.
_TERMINAL_OK = frozenset({"applied", "ignored"})
# States that must be re-attempted (or re-evaluated) on redelivery.
_RETRYABLE = frozenset({"failed", "processing", "unmatched", "needs_reconciliation"})

# Max signedPayload characters (~512 KiB). Apple payloads are far smaller.
MAX_SIGNED_PAYLOAD_CHARS = 512 * 1024

# Advisory-lock namespace (arbitrary stable int; not a secret).
_IAP_LOCK_NS = 728401


def lock_apple_transaction(db: Session, transaction_id: str) -> None:
    """Exclusive transaction-scoped lock shared by confirm + ASN paths.

    Lock order (deadlock-safe):
      1. advisory(txn)
      2. iap_purchases row (FOR UPDATE)
      3. users row (FOR UPDATE)
    """
    txn = (transaction_id or "").strip()
    if not txn:
        return
    key = zlib.crc32(f"iap:ios:{txn}".encode()) & 0x7FFFFFFF
    db.execute(text("SELECT pg_advisory_xact_lock(:ns, :k)"), {"ns": _IAP_LOCK_NS, "k": key})


def process_apple_notification(db: Session, *, signed_payload: str) -> dict[str, Any]:
    """Verify + apply one ASN V2 notification. Safe under concurrent workers.

    Returns a receipt dict on durable success / terminal idempotency.
    Raises ``ServiceUnavailableError`` after persisting ``failed`` when Apple
    should redeliver (transient processing errors).
    """
    raw = (signed_payload or "").strip()
    if not raw:
        raise ValidationAppError("signedPayload is required")
    if len(raw) > MAX_SIGNED_PAYLOAD_CHARS:
        raise ValidationAppError("signedPayload exceeds size limit")

    if not apple_iap.apple_iap_configured():
        raise ServiceUnavailableError("Apple IAP verification is not configured")

    verified = apple_iap.verify_signed_notification_payload(raw)
    # Phase 1: durable receipt commit so apply crashes cannot erase the UUID.
    row = _ensure_notification_receipt(db, verified)

    if row.processing_state in _TERMINAL_OK:
        return _receipt_payload(row, duplicate=True)

    # Phase 2: lock + apply in a fresh transaction unit.
    try:
        row = _lock_notification_by_uuid(db, verified.notification_uuid)
        if row is None:
            raise ServiceUnavailableError("Apple notification receipt missing")
        if row.processing_state in _TERMINAL_OK:
            db.commit()
            return _receipt_payload(row, duplicate=True)

        row.processing_attempts = int(row.processing_attempts or 0) + 1
        row.processing_state = "processing"
        row.last_error = None
        row.updated_at = datetime.now(UTC)
        db.flush()

        txn_id = (
            verified.transaction.transaction_id if verified.transaction else None
        ) or row.transaction_id
        if txn_id:
            lock_apple_transaction(db, txn_id)
        _apply_verified_notification(db, row, verified)
        db.commit()
    except ForbiddenError as exc:
        _mark_notification_failed(db, verified.notification_uuid, str(exc)[:200])
        raise
    except IntegrityError:
        db.rollback()
        again = _lock_notification_by_uuid(db, verified.notification_uuid)
        if again is not None and again.processing_state in _TERMINAL_OK:
            db.commit()
            return _receipt_payload(again, duplicate=True)
        _mark_notification_failed(db, verified.notification_uuid, "integrity_conflict")
        raise ServiceUnavailableError(
            "Apple notification processing conflict; retry"
        ) from None
    except Exception as exc:
        _log.exception(
            "apple_asn_process_failed uuid_suffix=%s type=%s",
            verified.notification_uuid[-8:],
            verified.notification_type,
        )
        _mark_notification_failed(
            db, verified.notification_uuid, type(exc).__name__[:80]
        )
        raise ServiceUnavailableError(
            "Apple notification processing temporarily unavailable"
        ) from exc

    db.refresh(row)
    # Failed after durable apply attempt → non-2xx so Apple redelivers.
    if row.processing_state == "failed":
        raise ServiceUnavailableError(
            "Apple notification processing failed; retry"
        )
    return _receipt_payload(row, duplicate=False)


def pending_takeback_for_transaction(
    db: Session, *, transaction_id: str
) -> IapAppleNotification | None:
    """Any durable REFUND/REVOKE for this txn blocks first-time credit.

    Includes unmatched/failed/processing — Apple already signaled a takeback.
    Caller must hold ``lock_apple_transaction`` first.
    """
    txn = (transaction_id or "").strip()
    if not txn:
        return None
    return db.scalar(
        select(IapAppleNotification)
        .where(
            IapAppleNotification.transaction_id == txn,
            IapAppleNotification.notification_type.in_(tuple(_TAKEBACK_TYPES)),
        )
        .order_by(IapAppleNotification.created_at.asc())
        .limit(1)
    )


def attach_unmatched_takebacks_to_purchase(
    db: Session,
    *,
    purchase: IapPurchase,
    user: User,
) -> list[IapAppleNotification]:
    """Link unmatched ASN takebacks to a newly created blocked/active purchase.

    Does not invent ownership from product similarity — only exact transaction_id
    (or original_transaction_id == purchase.transaction_id for the same Apple txn).
    """
    txn = purchase.transaction_id
    rows = list(
        db.scalars(
            select(IapAppleNotification)
            .where(
                IapAppleNotification.notification_type.in_(
                    tuple(_HANDLED_TYPES)
                ),
                IapAppleNotification.processing_state.in_(
                    ("unmatched", "needs_reconciliation", "failed", "processing")
                ),
                (
                    (IapAppleNotification.transaction_id == txn)
                    | (IapAppleNotification.original_transaction_id == txn)
                ),
            )
            .order_by(IapAppleNotification.created_at.asc())
        )
    )
    attached: list[IapAppleNotification] = []
    for row in rows:
        # Token check when present — never cross-account attach.
        got = (row.app_account_token or "").strip()
        if got:
            expected = apple_iap.app_account_token_for_user(user.id)
            if got.lower() != expected.lower():
                row.processing_state = "needs_reconciliation"
                row.last_error = "token_mismatch_on_attach"
                row.audit_meta = {
                    **(row.audit_meta or {}),
                    "policy": "quarantine_token_mismatch",
                }
                continue
        row.iap_purchase_id = purchase.id
        row.user_id = user.id
        if row.notification_type in _TAKEBACK_TYPES:
            if purchase.status == STATUS_BLOCKED and int(purchase.stars_credited or 0) == 0:
                row.processing_state = "applied"
                row.audit_meta = {
                    **(row.audit_meta or {}),
                    "policy": "attached_blocked_purchase",
                }
            elif purchase.status == STATUS_ACTIVE:
                # Purchase was credited; apply takeback now under caller's locks.
                _apply_takeback(db, row, user, purchase, kind=row.notification_type)
                if row.processing_state == "processing":
                    row.processing_state = "applied"
            else:
                row.processing_state = "applied"
                row.audit_meta = {
                    **(row.audit_meta or {}),
                    "policy": "attached_existing_status",
                    "status": purchase.status,
                }
        elif row.notification_type in _RESTORE_TYPES:
            if purchase.status in (STATUS_REFUNDED, STATUS_REVOKED):
                _apply_refund_reversed(db, row, user, purchase)
                if row.processing_state == "processing":
                    row.processing_state = "applied"
            elif int(purchase.stars_credited or 0) == 0:
                row.processing_state = "needs_reconciliation"
                row.audit_meta = {
                    **(row.audit_meta or {}),
                    "policy": "refund_reversed_on_never_credited",
                }
            else:
                row.processing_state = "needs_reconciliation"
                row.audit_meta = {
                    **(row.audit_meta or {}),
                    "policy": "refund_reversed_without_applied_takeback",
                }
        row.processed_at = datetime.now(UTC)
        attached.append(row)
    return attached


def _ensure_notification_receipt(
    db: Session, verified: apple_iap.VerifiedAppleNotification
) -> IapAppleNotification:
    """Insert+commit ASN receipt (or return existing). Survives later apply crashes."""
    existing = db.scalar(
        select(IapAppleNotification).where(
            IapAppleNotification.notification_uuid == verified.notification_uuid
        )
    )
    if existing is not None:
        _refresh_notification_fields(existing, verified)
        if db.is_modified(existing):
            db.commit()
            db.refresh(existing)
        return existing

    txn = verified.transaction
    row = IapAppleNotification(
        id=uuid.uuid4(),
        notification_uuid=verified.notification_uuid,
        notification_type=verified.notification_type,
        subtype=verified.subtype,
        environment=verified.environment,
        signed_date_ms=int(verified.signed_date)
        if verified.signed_date is not None
        else None,
        transaction_id=txn.transaction_id if txn else None,
        original_transaction_id=txn.original_transaction_id if txn else None,
        product_id=txn.product_id if txn else None,
        app_account_token=(txn.app_account_token if txn else None),
        processing_state="processing",
        processing_attempts=0,
        audit_meta={
            "signed_date": verified.signed_date,
            "has_transaction": txn is not None,
        },
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        again = db.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == verified.notification_uuid
            )
        )
        if again is None:
            raise
        _refresh_notification_fields(again, verified)
        if db.is_modified(again):
            db.commit()
            db.refresh(again)
        return again
    db.refresh(row)
    return row


def _refresh_notification_fields(
    row: IapAppleNotification, verified: apple_iap.VerifiedAppleNotification
) -> None:
    if row.notification_type in ("UNKNOWN", "") or not row.transaction_id:
        txn = verified.transaction
        row.notification_type = verified.notification_type
        row.subtype = verified.subtype
        row.environment = verified.environment
        row.signed_date_ms = (
            int(verified.signed_date) if verified.signed_date is not None else None
        )
        if txn is not None:
            row.transaction_id = txn.transaction_id
            row.original_transaction_id = txn.original_transaction_id
            row.product_id = txn.product_id
            row.app_account_token = txn.app_account_token


def _lock_notification_by_uuid(db: Session, notification_uuid: str) -> IapAppleNotification | None:
    return db.scalar(
        select(IapAppleNotification)
        .where(IapAppleNotification.notification_uuid == notification_uuid)
        .with_for_update()
    )


def _mark_notification_failed(db: Session, notification_uuid: str, error: str) -> None:
    """Durably mark a previously committed receipt as failed (Apple should retry)."""
    try:
        db.rollback()
    except Exception:  # noqa: BLE001
        pass
    row = _lock_notification_by_uuid(db, notification_uuid)
    if row is None:
        return
    if row.processing_state in _TERMINAL_OK:
        db.commit()
        return
    row.processing_state = "failed"
    row.last_error = error[:500]
    row.updated_at = datetime.now(UTC)
    db.commit()


def _apply_verified_notification(
    db: Session,
    row: IapAppleNotification,
    verified: apple_iap.VerifiedAppleNotification,
) -> None:
    ntype = verified.notification_type
    if ntype not in _HANDLED_TYPES:
        row.processing_state = "ignored"
        row.processed_at = datetime.now(UTC)
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "ignored_non_consumable_takeback",
        }
        return

    txn = verified.transaction
    if txn is None:
        # Durable failed — Apple may resend a complete payload; HTTP layer maps
        # failed→503 via post-commit check below when callers inspect state.
        row.processing_state = "failed"
        row.last_error = "missing_nested_transaction"
        row.processed_at = datetime.now(UTC)
        return

    purchase = _find_ios_purchase(db, transaction_id=txn.transaction_id)
    if purchase is None and txn.original_transaction_id:
        # Only fall back when original_transaction_id equals a known purchase txn.
        # For consumables original usually == transaction id; never fuzzy-match.
        purchase = _find_ios_purchase(db, transaction_id=txn.original_transaction_id)

    if purchase is None:
        if ntype in _RESTORE_TYPES:
            # REFUND_REVERSED before we know the purchase / takeback — park safely.
            row.processing_state = "unmatched"
            row.processed_at = datetime.now(UTC)
            row.audit_meta = {
                **(row.audit_meta or {}),
                "policy": "unmatched_refund_reversed_awaiting_purchase",
            }
            return
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

    locked_purchase = db.scalar(
        select(IapPurchase).where(IapPurchase.id == purchase.id).with_for_update()
    )
    if locked_purchase is None:
        row.processing_state = "failed"
        row.last_error = "purchase_missing_under_lock"
        return

    user = db.scalar(
        select(User).where(User.id == locked_purchase.user_id).with_for_update()
    )
    if user is None:
        row.processing_state = "failed"
        row.last_error = "user_missing"
        return

    expected = apple_iap.app_account_token_for_user(user.id)
    got = (txn.app_account_token or "").strip()
    if got and got.lower() != expected.lower():
        row.processing_state = "needs_reconciliation"
        row.last_error = "app_account_token_mismatch"
        row.processed_at = datetime.now(UTC)
        row.audit_meta = {
            **(row.audit_meta or {}),
            "policy": "quarantine_token_mismatch",
        }
        _log.warning(
            "apple_asn_token_mismatch purchase_id=%s type=%s",
            locked_purchase.id,
            ntype,
        )
        # Durable quarantine — 2xx (do not infinite-retry a contradictory signed event).
        return

    row.user_id = user.id
    row.iap_purchase_id = locked_purchase.id

    # Out-of-order: REFUND_REVERSED while purchase still active (no takeback yet).
    if ntype in _RESTORE_TYPES and locked_purchase.status == STATUS_ACTIVE:
        prior = _notification_adjustment(db, row.id)
        if prior is None and _clawable_remaining(locked_purchase) == int(
            locked_purchase.stars_credited or 0
        ):
            row.processing_state = "needs_reconciliation"
            row.processed_at = datetime.now(UTC)
            row.audit_meta = {
                **(row.audit_meta or {}),
                "policy": "refund_reversed_before_takeback",
            }
            return

    if ntype in _TAKEBACK_TYPES:
        _apply_takeback(db, row, user, locked_purchase, kind=ntype)
    else:
        _apply_refund_reversed(db, row, user, locked_purchase)

    if row.processing_state == "processing":
        row.processing_state = "applied"
    if row.processed_at is None:
        row.processed_at = datetime.now(UTC)


def _clawable_remaining(purchase: IapPurchase) -> int:
    """Stars still owed back to Apple for this purchase (supports multi-cycle refund)."""
    credited = max(0, int(purchase.stars_credited or 0))
    clawed = max(0, int(purchase.stars_clawed_back or 0))
    restored = max(0, int(purchase.stars_restored or 0))
    return max(0, credited + restored - clawed)


def _restorable_remaining(purchase: IapPurchase) -> int:
    clawed = max(0, int(purchase.stars_clawed_back or 0))
    restored = max(0, int(purchase.stars_restored or 0))
    return max(0, clawed - restored)


def _notification_adjustment(
    db: Session, notification_id: uuid.UUID
) -> IapStarsAdjustment | None:
    return db.scalar(
        select(IapStarsAdjustment).where(
            IapStarsAdjustment.notification_id == notification_id
        )
    )


def _apply_takeback(
    db: Session,
    row: IapAppleNotification,
    user: User,
    purchase: IapPurchase,
    *,
    kind: str,
) -> None:
    """REFUND / REVOKE — claw back remaining credited Stars (once per notification)."""
    existing_for_note = _notification_adjustment(db, row.id)
    if existing_for_note is not None:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "adjustment_already_for_notification"}
        return

    if purchase.status == STATUS_BLOCKED and int(purchase.stars_credited or 0) == 0:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "already_blocked"}
        return

    need = _clawable_remaining(purchase)
    if need <= 0:
        # Duplicate REFUND / REVOKE after full clawback — idempotent no-op.
        if purchase.status not in (STATUS_REFUNDED, STATUS_REVOKED, STATUS_BLOCKED):
            purchase.status = STATUS_REVOKED if kind == "REVOKE" else STATUS_REFUNDED
        row.audit_meta = {**(row.audit_meta or {}), "policy": "nothing_to_claw"}
        return

    from_balance, added_debt, balance_after, debt_after = ai_stars.apply_iap_clawback(
        db, user, stars_to_recover=need
    )
    purchase.stars_clawed_back = int(purchase.stars_clawed_back or 0) + need
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
        # Same notification_id won elsewhere — do not claw twice from this worker.
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
    if _notification_adjustment(db, row.id) is not None:
        row.audit_meta = {**(row.audit_meta or {}), "policy": "adjustment_already_for_notification"}
        return

    restorable = _restorable_remaining(purchase)
    if restorable <= 0:
        # Duplicate reversal or reversal without takeback.
        if int(purchase.stars_clawed_back or 0) == 0:
            row.processing_state = "needs_reconciliation"
            row.audit_meta = {
                **(row.audit_meta or {}),
                "policy": "refund_reversed_without_prior_takeback",
            }
            row.processed_at = datetime.now(UTC)
            return
        row.audit_meta = {**(row.audit_meta or {}), "policy": "nothing_to_restore"}
        return

    debt_reduced, balance_added, balance_after, debt_after = ai_stars.restore_iap_clawback(
        db, user, stars_to_restore=restorable
    )
    purchase.stars_restored = int(purchase.stars_restored or 0) + restorable
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
        restorable,
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
        "retryable": row.processing_state in _RETRYABLE
        and row.processing_state == "failed",
    }
