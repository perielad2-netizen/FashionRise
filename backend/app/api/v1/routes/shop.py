"""Stars shop — packages catalog + cart + store IAP confirm."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services import iap_service, stars_shop

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
