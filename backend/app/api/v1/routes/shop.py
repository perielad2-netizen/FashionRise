"""Stars shop — packages catalog + cart (checkout not live)."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.services import stars_shop

router = APIRouter()


class CartItemBody(BaseModel):
    package_sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=0, le=20)


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
    """Reserved — currently always refused until payments are enabled."""
    _ = request.url
    return stars_shop.checkout_cart(db, user)
