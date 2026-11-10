"""Stars shop — packages catalog + cart + store IAP confirm + Apple ASN V2."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services import apple_asn, iap_service, stars_shop

router = APIRouter()


class CartItemBody(BaseModel):
    package_sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=0, le=20)


class IapConfirmBody(BaseModel):
    platform: Literal["ios", "android"]
    product_id: str = Field(min_length=1, max_length=128)
    transaction_id: str | None = Field(default=None, max_length=255)
    purchase_token: str | None = None
    receipt: str | None = None
    jws: str | None = None


class AppleAsnBody(BaseModel):
    """App Store Server Notifications V2 envelope (Apple field name: signedPayload)."""

    signedPayload: str = Field(min_length=1, max_length=apple_asn.MAX_SIGNED_PAYLOAD_CHARS)


@router.get("/packages")
@limiter.limit("60/minute")
def list_star_packages(request: Request) -> dict[str, Any]:
    """Public catalog of Stars packages (purchase may still be disabled)."""
    _ = request.url
    return {"packages": stars_shop.list_packages()}


@router.get("/cart")
@limiter.limit("60/minute")
def get_cart(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = request.url
    cart = stars_shop.get_or_create_open_cart(db, user)
    return stars_shop.cart_payload(cart)


@router.put("/cart/items")
@limiter.limit("60/minute")
def put_cart_item(
    request: Request,
    body: CartItemBody,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = request.url
    cart = stars_shop.set_cart_item(
        db, user, sku=body.package_sku, quantity=body.quantity
    )
    return stars_shop.cart_payload(cart)


@router.delete("/cart")
@limiter.limit("30/minute")
def clear_cart(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = request.url
    cart = stars_shop.clear_cart(db, user)
    return stars_shop.cart_payload(cart)


@router.post("/cart/checkout")
@limiter.limit("20/minute")
def checkout_cart(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reserved — web card checkout stays off; store apps use /shop/iap/confirm."""
    _ = request.url
    return stars_shop.checkout_cart(db, user)


@router.get("/iap/app-account-token")
@limiter.limit("60/minute")
def get_iap_app_account_token(
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    """Opaque StoreKit appAccountToken UUID for the signed-in account."""
    _ = request.url
    return iap_service.app_account_token_payload(user)


@router.get("/iap/apple/status")
@limiter.limit("60/minute")
def get_apple_iap_status(request: Request) -> dict[str, Any]:
    """Native shop gate/config status (no auth; no secrets)."""
    _ = request.url
    return iap_service.apple_shop_status()


@router.post("/iap/confirm")
@limiter.limit("30/minute")
def confirm_iap_purchase(
    request: Request,
    body: IapConfirmBody,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Confirm an Apple/Google IAP and credit Stars (idempotent)."""
    _ = request.url
    return iap_service.confirm_purchase(
        db,
        user,
        platform=body.platform,
        product_id=body.product_id,
        transaction_id=body.transaction_id,
        purchase_token=body.purchase_token,
        receipt=body.receipt,
        jws=body.jws,
    )


@router.post("/iap/restore")
@limiter.limit("20/minute")
def restore_iap_purchases(
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    _ = request.url
    _ = user
    return iap_service.restore_placeholder()


@router.post("/iap/apple/notifications")
@limiter.limit("120/minute")
def apple_iap_notifications(
    request: Request,
    body: AppleAsnBody,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """App Store Server Notifications V2 webhook.

    No FashionRise user session. Authenticated solely by Apple JWS verification.
    Invalid signatures → 403. Transient processing errors → 503 so Apple retries.
    """
    _ = request.url
    try:
        return apple_asn.process_apple_notification(db, signed_payload=body.signedPayload)
    except (ValidationAppError, ForbiddenError, ServiceUnavailableError):
        raise
    except Exception:
        # Transient — Apple retries on non-2xx.
        raise ServiceUnavailableError("Apple notification processing temporarily unavailable")
