"""App Store / Play Store Stars purchases.

Apple and Google own checkout. We verify the receipt/token server-side, then credit
the Stars wallet. Verification stays fail-closed until store credentials are configured.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.models.iap_purchase import IapPurchase
from app.models.user import User
from app.services import ai_stars

_log = logging.getLogger(__name__)

Platform = Literal["ios", "android"]

# Must match web-ui/src/services/native/iap.ts and store console product IDs.
# Prices are set in App Store Connect / Play Console (Starter $4.99, Creator $12.99, Studio $34.99).
STARS_PRODUCTS: dict[str, int] = {
    "stars_50": 50,  # Starter
    "stars_150": 150,  # Creator
    "stars_500": 500,  # Studio
}


def iap_verification_ready() -> bool:
    s = get_settings()
    return bool(
        (s.iap_apple_shared_secret or "").strip()
        or (s.iap_google_service_account_json or "").strip()
        or s.iap_allow_unverified_sandbox
    )


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
    pid = (product_id or "").strip()
    if pid not in STARS_PRODUCTS:
        raise ValidationAppError("Unknown Stars product")
    txn = (transaction_id or purchase_token or "").strip()
    if not txn:
        raise ValidationAppError("transaction_id is required")

    if not iap_verification_ready():
        raise ServiceUnavailableError(
            "Store purchase verification is not configured yet. "
            "Add Apple/Google IAP credentials on the server, then retry."
        )

    existing = db.scalar(
        select(IapPurchase).where(
            IapPurchase.platform == plat,
            IapPurchase.transaction_id == txn,
        )
    )
    if existing is not None:
        if existing.user_id != user.id:
            raise ConflictError("This purchase is already linked to another account")
        return {
            "stars_credited": 0,
            "already_processed": True,
            "ai_stars": int(getattr(user, "ai_stars", 0) or 0),
        }

    _verify_with_store(
        platform=plat,  # type: ignore[arg-type]
        product_id=pid,
        transaction_id=txn,
        purchase_token=purchase_token,
        receipt=receipt,
        jws=jws,
    )

    stars = STARS_PRODUCTS[pid]
    row = IapPurchase(
        user_id=user.id,
        platform=plat,
        product_id=pid,
        transaction_id=txn,
        stars_credited=stars,
    )
    db.add(row)
    balance = ai_stars.credit_stars(db, user, stars, reason=f"iap:{plat}:{pid}")
    db.commit()
    _log.info(
        "iap_confirmed user_id=%s platform=%s product=%s stars=%s",
        user.id,
        plat,
        pid,
        stars,
    )
    return {
        "stars_credited": stars,
        "already_processed": False,
        "ai_stars": balance,
    }


def restore_placeholder() -> dict[str, Any]:
    """Client calls NativePurchases.restorePurchases(); re-confirm each txn via confirm."""
    return {"restored": 0, "note": "Re-run confirm for each restored transaction from the client."}


def _verify_with_store(
    *,
    platform: Platform,
    product_id: str,
    transaction_id: str,
    purchase_token: str | None,
    receipt: str | None,
    jws: str | None,
) -> None:
    settings = get_settings()
    if settings.iap_allow_unverified_sandbox and settings.environment != "production":
        _log.warning(
            "iap_sandbox_unverified platform=%s product=%s txn=%s",
            platform,
            product_id,
            transaction_id[-12:],
        )
        return

    # Production path: wire Apple verifyReceipt / App Store Server API + Google Play Developer API.
    # Until credentials + verifier land, refuse so we never credit unverified Stars in prod.
    if platform == "ios":
        if not (settings.iap_apple_shared_secret or "").strip() and not (jws or receipt):
            raise ForbiddenError("Missing Apple receipt for verification")
        if not (settings.iap_apple_shared_secret or "").strip():
            raise ServiceUnavailableError("Apple IAP shared secret not configured")
        # Placeholder — full Apple verification lands with App Store Connect setup.
        raise ServiceUnavailableError(
            "Apple receipt verification is staged — configure App Store Server API next."
        )

    if not (settings.iap_google_service_account_json or "").strip():
        raise ServiceUnavailableError("Google Play service account not configured")
    if not (purchase_token or "").strip():
        raise ForbiddenError("Missing Google purchase token")
    raise ServiceUnavailableError(
        "Google Play purchase verification is staged — configure Play Developer API next."
    )
