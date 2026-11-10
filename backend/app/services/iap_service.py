"""App Store / Play Store Stars purchases.

Apple and Google own checkout. We verify the signed transaction server-side, then
credit the Stars wallet. Phase A: Apple JWS verification via App Store Server
Library. Public purchasing stays default-OFF until refund/ASN (Phase B).
Android verification remains staged and unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.models.iap_purchase import IapPurchase
from app.models.user import User
from app.services import ai_stars, apple_iap

_log = logging.getLogger(__name__)

Platform = Literal["ios", "android"]

# Must match web-ui/src/services/native/iap.ts and store console product IDs.
# Launch prices in App Store Connect / Play Console: $5.99 / $16.99 / $49.99.
STARS_PRODUCTS: dict[str, int] = {
    "stars_50": 50,  # Starter — $5.99
    "stars_150": 150,  # Creator — $16.99
    "stars_500": 500,  # Studio — $49.99
}


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


def restore_placeholder() -> dict[str, Any]:
    """Client calls NativePurchases.restorePurchases(); re-confirm each txn via confirm."""
    return {
        "restored": 0,
        "note": (
            "Phase A: restore is a no-op. Phase B unfinished-txn recovery re-POSTs "
            "/shop/iap/confirm with each signed JWS when IAP_APPLE_CREDIT_ENABLED is on "
            "(distinct from IAP_APPLE_PURCHASING_ENABLED for starting new buys)."
        ),
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
    # (initiating new StoreKit buys). Both default OFF in Phase A.
    if not apple_iap.apple_credit_enabled():
        raise ServiceUnavailableError(
            "Apple Stars credit / transaction recovery is not enabled yet. "
            "Phase B (refunds / App Store Server Notifications) must land first."
        )

    if not apple_iap.apple_iap_configured():
        raise ServiceUnavailableError(
            "Apple IAP verification is not configured yet. "
            "Install Apple root certificates and set bundle / App Apple ID."
        )

    # Dev-only escape hatch — never production (gated above + settings validator).
    if settings.iap_allow_unverified_sandbox and settings.environment != "production":
        raise ServiceUnavailableError(
            "Unverified sandbox IAP credit is disabled for Apple Phase A. "
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

    stars = STARS_PRODUCTS[verified.product_id] * max(1, verified.quantity)
    return _persist_credit(
        db,
        user,
        platform="ios",
        product_id=verified.product_id,
        transaction_id=verified.transaction_id,
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
    """Android path unchanged (staged). Phase A does not modify Play Billing."""
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
            "Unverified sandbox IAP credit is disabled while Apple Phase A is in progress."
        )

    if not (settings.iap_google_service_account_json or "").strip():
        raise ServiceUnavailableError("Google Play service account not configured")
    if not (purchase_token or "").strip():
        raise ForbiddenError("Missing Google purchase token")
    raise ServiceUnavailableError(
        "Google Play purchase verification is staged — configure Play Developer API next."
    )


def _persist_credit(
    db: Session,
    user: User,
    *,
    platform: str,
    product_id: str,
    transaction_id: str,
    stars: int,
) -> dict[str, Any]:
    existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
    if existing is not None:
        return _idempotent_or_conflict(db, user, existing)

    row = IapPurchase(
        user_id=user.id,
        platform=platform,
        product_id=product_id,
        transaction_id=transaction_id,
        stars_credited=stars,
    )
    db.add(row)
    try:
        # Flush to surface unique violations before wallet credit when possible.
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
        if existing is None:
            raise
        return _idempotent_or_conflict(db, user, existing)

    try:
        balance = ai_stars.credit_stars(db, user, stars, reason=f"iap:{platform}:{product_id}")
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _find_purchase(db, platform=platform, transaction_id=transaction_id)
        if existing is None:
            raise
        return _idempotent_or_conflict(db, user, existing)

    # Refresh user balance after commit
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
        "stars_credited": stars,
        "already_processed": False,
        "ai_stars": balance,
        "product_id": product_id,
        "transaction_id": transaction_id,
    }


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
    # Ensure we see committed balance
    locked = db.scalar(select(User).where(User.id == user.id))
    if locked is not None:
        balance = int(getattr(locked, "ai_stars", 0) or 0)
    return {
        "stars_credited": 0,
        "already_processed": True,
        "ai_stars": balance,
        "product_id": existing.product_id,
        "transaction_id": existing.transaction_id,
    }
