"""App Store / Play Store Stars purchases.

Apple and Google own checkout. We verify the signed transaction server-side, then
credit the Stars wallet. Phase B adds ASN V2 refund/revoke handling and native
shop recovery. Public purchasing and credit stay default-OFF.
Android verification remains staged and unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.models.iap_purchase import (
    STATUS_ACTIVE,
    STATUS_BLOCKED,
    STATUS_REFUND_REVERSED,
    STATUS_REFUNDED,
    STATUS_REVOKED,
    IapPurchase,
)
from app.models.user import User
from app.services import ai_stars, apple_asn, apple_iap

_log = logging.getLogger(__name__)

Platform = Literal["ios", "android"]

# Must match web-ui/src/services/native/iap.ts and store console product IDs.
# Launch prices in App Store Connect / Play Console: $5.99 / $16.99 / $49.99.
STARS_PRODUCTS: dict[str, int] = {
    "stars_50": 50,  # Starter — $5.99
    "stars_150": 150,  # Creator — $16.99
    "stars_500": 500,  # Studio — $49.99
}

_TAKEBACK_STATUSES = frozenset({STATUS_BLOCKED, STATUS_REFUNDED, STATUS_REVOKED})


def iap_verification_ready(*, platform: str | None = None) -> bool:
    """Whether confirm can attempt verification for a platform (not the public enable gate)."""
    s = get_settings()
    # Production can never treat unverified sandbox as "ready".
    if s.iap_allow_unverified_sandbox and s.environment != "production":
        return True
    plat = (platform or "").strip().lower()
    if plat == "ios" or plat == "":
        if apple_iap.apple_iap_configured():
            return True
    if plat in ("android", ""):
        if (s.iap_google_service_account_json or "").strip():
            return True
    return False


def app_account_token_payload(user: User) -> dict[str, str]:
    """Opaque StoreKit appAccountToken for the signed-in user (Phase A helper)."""
    return {"app_account_token": apple_iap.app_account_token_for_user(user.id)}


def apple_shop_status(user: User | None = None) -> dict[str, Any]:
    """Native shop readiness (gates + configuration). No secrets.

    When ``user`` is a designated sandbox tester, purchasing/credit flip on for
    that session even while public gates stay OFF.
    """
    return {
        "platform": "ios",
        "purchasing_enabled": apple_iap.apple_purchasing_enabled_for(user),
        "credit_enabled": apple_iap.apple_credit_enabled_for(user),
        "verification_configured": apple_iap.apple_iap_configured(),
        "sandbox_tester": bool(
            user is not None and apple_iap.email_is_apple_sandbox_tester(user.email)
        ),
        "products": [
            {"product_id": pid, "stars": stars} for pid, stars in STARS_PRODUCTS.items()
        ],
    }


def confirm_purchase(
    db: Session,
    user: User,
    *,
    platform: str,
    product_id: str,
    transaction_id: str | None,
    purchase_token: str | None = None,
    receipt: str | None = None,
    jws: str | None = None,
) -> dict[str, Any]:
    plat = (platform or "").strip().lower()
    if plat not in ("ios", "android"):
        raise ValidationAppError("platform must be ios or android")

    client_pid = (product_id or "").strip()
    # Client product_id is advisory for early validation only — never used for Stars.
    if client_pid and client_pid not in STARS_PRODUCTS:
        raise ValidationAppError("Unknown Stars product")

    if plat == "ios":
        return _confirm_apple(
            db,
            user,
            client_product_id=client_pid,
            client_transaction_id=(transaction_id or "").strip() or None,
            jws=jws,
            receipt=receipt,
        )

    return _confirm_android_staged(
        db,
        user,
        product_id=client_pid,
        transaction_id=transaction_id,
        purchase_token=purchase_token,
    )


def restore_placeholder(user: User | None = None) -> dict[str, Any]:
    """Client re-confirms unfinished StoreKit txns via /shop/iap/confirm (credit gate)."""
    return {
        "restored": 0,
        "note": (
            "Native recovery re-POSTs /shop/iap/confirm with each signed JWS when "
            "credit is enabled globally or for a sandbox-tester account. This endpoint "
            "acknowledges the restore handshake only — Stars come solely from verified confirm."
        ),
        "credit_enabled": apple_iap.apple_credit_enabled_for(user),
        "purchasing_enabled": apple_iap.apple_purchasing_enabled_for(user),
    }


def _confirm_apple(
    db: Session,
    user: User,
    *,
    client_product_id: str,
    client_transaction_id: str | None,
    jws: str | None,
    receipt: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.iap_allow_unverified_sandbox and settings.environment == "production":
        # Belt-and-suspenders (also coerced off in Settings).
        raise ServiceUnavailableError("Unverified IAP sandbox credit is forbidden in production")

    # Credit/reconcile gate (completed Apple txns). Distinct from purchasing_enabled
    # (initiating new StoreKit buys). Both default OFF for the public; designated
    # sandbox-tester emails may confirm while public gates stay OFF.
    if not apple_iap.apple_credit_enabled_for(user):
        raise ServiceUnavailableError(
            "Apple Stars credit / transaction recovery is not enabled yet. "
            "ASN refund handling must be live before the credit gate is turned on."
        )

    if not apple_iap.apple_iap_configured():
        raise ServiceUnavailableError(
            "Apple IAP verification is not configured yet. "
            "Install Apple root certificates and set bundle / App Apple ID."
        )

    # Dev-only escape hatch — never production (gated above + settings validator).
    if settings.iap_allow_unverified_sandbox and settings.environment != "production":
        raise ServiceUnavailableError(
            "Unverified sandbox IAP credit is disabled for Apple. "
            "Send a real signed transaction JWS (StoreKit sandbox) instead."
        )

    if not (jws or "").strip():
        # Legacy shared-secret verifyReceipt path intentionally not used.
        if (receipt or "").strip() and (settings.iap_apple_shared_secret or "").strip():
            raise ServiceUnavailableError(
                "Legacy Apple shared-secret receipt verification is not supported. "
                "Send StoreKit 2 jwsRepresentation for App Store Server Library verification."
            )
        raise ValidationAppError("Apple transaction JWS (jwsRepresentation) is required")

    verified = apple_iap.verify_signed_transaction_jws(jws or "")

    if verified.product_id not in STARS_PRODUCTS:
        raise ValidationAppError("Unknown Stars product on verified Apple transaction")

    if client_product_id and client_product_id != verified.product_id:
        raise ForbiddenError("Client product id does not match verified Apple product")

    if client_transaction_id and client_transaction_id != verified.transaction_id:
        raise ForbiddenError("Client transaction id does not match verified Apple transaction")

    _assert_app_account_token_owns_transaction(user, verified)

    # Shared with ASN: serialize confirm vs refund before any wallet mutation.
    apple_asn.lock_apple_transaction(db, verified.transaction_id)

    # Reload authoritative purchase after the lock (never trust pre-lock state).
    existing = _find_purchase(
        db, platform="ios", transaction_id=verified.transaction_id
    )
    if existing is not None:
        return _idempotent_or_conflict(db, user, existing)

    # Any durable REFUND/REVOKE for this txn blocks first-time credit.
    pending_takeback = apple_asn.pending_takeback_for_transaction(
        db, transaction_id=verified.transaction_id
    )
    if pending_takeback is not None:
        return _persist_blocked_after_prior_refund(
            db,
            user,
            verified=verified,
            notification=pending_takeback,
        )

    stars = STARS_PRODUCTS[verified.product_id] * max(1, verified.quantity)
    return _persist_credit(
        db,
        user,
        platform="ios",
        product_id=verified.product_id,
        transaction_id=verified.transaction_id,
        original_transaction_id=verified.original_transaction_id,
        environment=verified.environment,
        stars=stars,
    )


def _assert_app_account_token_owns_transaction(user: User, verified: apple_iap.VerifiedAppleTransaction) -> None:
    """Require cryptographically verified appAccountToken == this account (no missing bypass)."""
    expected_token = apple_iap.app_account_token_for_user(user.id)
    got = (verified.app_account_token or "").strip()
    if not got:
        raise ForbiddenError(
            "Apple appAccountToken is required on Stars purchases and must match this account"
        )
    if got.lower() != expected_token.lower():
        raise ForbiddenError("Apple appAccountToken does not match this account")


def _confirm_android_staged(
    db: Session,
    user: User,
    *,
    product_id: str,
    transaction_id: str | None,
    purchase_token: str | None,
) -> dict[str, Any]:
    """Android path unchanged (staged). Phase B does not modify Play Billing."""
    _ = db
    _ = user
    pid = (product_id or "").strip()
    if pid not in STARS_PRODUCTS:
        raise ValidationAppError("Unknown Stars product")
    txn = (transaction_id or purchase_token or "").strip()
    if not txn:
        raise ValidationAppError("transaction_id is required")

    settings = get_settings()
    if settings.iap_allow_unverified_sandbox and settings.environment != "production":
        raise ServiceUnavailableError(
            "Unverified sandbox IAP credit is disabled while Apple IAP is the active path."
        )

    if not (settings.iap_google_service_account_json or "").strip():
        raise ServiceUnavailableError("Google Play service account not configured")
    if not (purchase_token or "").strip():
        raise ForbiddenError("Missing Google purchase token")
    raise ServiceUnavailableError(
        "Google Play purchase verification is staged — configure Play Developer API next."
    )


def _persist_blocked_after_prior_refund(
    db: Session,
    user: User,
    *,
    verified: apple_iap.VerifiedAppleTransaction,
    notification: Any,
) -> dict[str, Any]:
    """Refund/revoke ASN beat confirm — create blocked row, zero Stars credit.

    Caller holds ``lock_apple_transaction``. Uses a savepoint so an IntegrityError
    does not release the advisory lock via full rollback.
    """
    existing = _find_purchase(db, platform="ios", transaction_id=verified.transaction_id)
    if existing is not None:
        return _idempotent_or_conflict(db, user, existing)

    stars = STARS_PRODUCTS.get(verified.product_id, 0) * max(1, verified.quantity)
    row = IapPurchase(
        user_id=user.id,
        platform="ios",
        product_id=verified.product_id,
        transaction_id=verified.transaction_id,
        original_transaction_id=verified.original_transaction_id,
        environment=verified.environment,
        status=STATUS_BLOCKED,
        stars_credited=0,
        stars_clawed_back=0,
        stars_restored=0,
    )
    try:
        _flush_purchase_row(db, row)
    except IntegrityError:
        if not hasattr(db, "begin_nested"):
            db.rollback()
        existing = _find_purchase(
            db, platform="ios", transaction_id=verified.transaction_id
        )
        if existing is None:
            raise
        return _idempotent_or_conflict(db, user, existing)

    # Lock user after purchase insert (lock order: advisory → purchase → user).
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise ForbiddenError("Account not found")

    try:
        notification.iap_purchase_id = row.id
        notification.user_id = user.id
        if notification.processing_state in (
            "unmatched",
            "failed",
            "processing",
            "needs_reconciliation",
        ):
            notification.processing_state = "applied"
        notification.audit_meta = {
            **(notification.audit_meta or {}),
            "policy": "blocked_on_confirm_after_prior_takeback",
            "would_have_credited": stars,
        }
        apple_asn.attach_unmatched_takebacks_to_purchase(
            db, purchase=row, user=locked_user
        )
    except Exception:  # noqa: BLE001
        _log.exception("apple_asn_attach_blocked_failed")

    db.commit()
    db.refresh(user)
    _log.info(
        "iap_blocked_prior_refund user_id=%s product=%s txn_suffix=%s",
        user.id,
        verified.product_id,
        verified.transaction_id[-12:],
    )
    return {
        "stars_credited": 0,
        "already_processed": True,
        "blocked": True,
        "reason": "apple_refund_or_revoke_recorded",
        "ai_stars": int(getattr(user, "ai_stars", 0) or 0),
        "product_id": verified.product_id,
        "transaction_id": verified.transaction_id,
    }


def _persist_credit(
    db: Session,
    user: User,
    *,
    platform: str,
    product_id: str,
    transaction_id: str,
    stars: int,
    original_transaction_id: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """Insert purchase + credit under caller's advisory lock (iOS) / uniqueness.

    Uses savepoints so IntegrityError recovery does not drop advisory locks.
    """
    existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
    if existing is not None:
        return _idempotent_or_conflict(db, user, existing)

    row = IapPurchase(
        user_id=user.id,
        platform=platform,
        product_id=product_id,
        transaction_id=transaction_id,
        original_transaction_id=original_transaction_id or transaction_id,
        environment=environment,
        status=STATUS_ACTIVE,
        stars_credited=stars,
        stars_clawed_back=0,
        stars_restored=0,
    )
    try:
        _flush_purchase_row(db, row)
    except IntegrityError:
        if not hasattr(db, "begin_nested"):
            db.rollback()
        existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
        if existing is None:
            raise
        return _idempotent_or_conflict(db, user, existing)

    try:
        balance = ai_stars.credit_stars(
            db, user, stars, reason=f"iap:{platform}:{product_id}"
        )
        if platform == "ios":
            apple_asn.attach_unmatched_takebacks_to_purchase(
                db, purchase=row, user=user
            )
            db.refresh(row)
            if row.status in _TAKEBACK_STATUSES and int(row.stars_credited or 0) > 0:
                balance = int(getattr(user, "ai_stars", 0) or 0)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
        if existing is None:
            raise
        return _idempotent_or_conflict(db, user, existing)

    db.refresh(user)
    _log.info(
        "iap_confirmed user_id=%s platform=%s product=%s stars=%s txn_suffix=%s",
        user.id,
        platform,
        product_id,
        stars,
        transaction_id[-12:],
    )
    return {
        "stars_credited": stars if row.status == STATUS_ACTIVE else 0,
        "already_processed": False,
        "blocked": row.status in _TAKEBACK_STATUSES,
        "status": row.status,
        "ai_stars": int(getattr(user, "ai_stars", 0) or balance),
        "ai_stars_iap_debt": int(getattr(user, "ai_stars_iap_debt", 0) or 0),
        "product_id": product_id,
        "transaction_id": transaction_id,
    }


def _flush_purchase_row(db: Session, row: IapPurchase) -> None:
    """Flush a new purchase row; prefer savepoint when the session supports it."""
    if hasattr(db, "begin_nested"):
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            return
        except AttributeError:
            pass
    db.add(row)
    db.flush()


def _find_purchase(db: Session, *, platform: str, transaction_id: str) -> IapPurchase | None:
    return db.scalar(
        select(IapPurchase).where(
            IapPurchase.platform == platform,
            IapPurchase.transaction_id == transaction_id,
        )
    )


def _idempotent_or_conflict(db: Session, user: User, existing: IapPurchase) -> dict[str, Any]:
    if existing.user_id != user.id:
        raise ConflictError("This purchase is already linked to another account")
    balance = int(getattr(user, "ai_stars", 0) or 0)
    debt = int(getattr(user, "ai_stars_iap_debt", 0) or 0)
    # Ensure we see committed balance
    locked = db.scalar(select(User).where(User.id == user.id))
    if locked is not None:
        balance = int(getattr(locked, "ai_stars", 0) or 0)
        debt = int(getattr(locked, "ai_stars_iap_debt", 0) or 0)

    status = str(getattr(existing, "status", STATUS_ACTIVE) or STATUS_ACTIVE)
    credited = int(getattr(existing, "stars_credited", 0) or 0)
    blocked = status in _TAKEBACK_STATUSES and credited == 0
    already_takeback = status in (STATUS_REFUNDED, STATUS_REVOKED, STATUS_BLOCKED)
    return {
        "stars_credited": 0,
        "already_processed": True,
        "blocked": blocked or already_takeback,
        "status": status,
        "ai_stars": balance,
        "ai_stars_iap_debt": debt,
        "product_id": existing.product_id,
        "transaction_id": existing.transaction_id,
        "refund_reversed": status == STATUS_REFUND_REVERSED,
    }
