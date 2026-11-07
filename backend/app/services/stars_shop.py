"""Stars shop catalog + cart (checkout disabled until payments ship)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ValidationAppError
from app.models.star_cart import StarCart, StarCartItem
from app.models.user import User


@dataclass(frozen=True)
class StarPackage:
    sku: str
    name: str
    stars: int
    price_usd_cents: int
    """Current sell price (cents). Store IAP price is set in Apple/Google consoles to match."""
    list_price_usd_cents: int
    """Compare-at / was price for UI (cents)."""
    description: str
    # Purchases are listed but not sellable until store IAP / checkout is enabled.
    available: bool = False


# Catalog aligned with App Store / Play Store IAP product IDs.
# Launch prices (set the same amounts in App Store Connect / Play Console).
STAR_PACKAGES: tuple[StarPackage, ...] = (
    StarPackage(
        sku="stars_50",
        name="Starter",
        stars=50,
        price_usd_cents=599,
        list_price_usd_cents=599,
        description="50 Stars — ~11.98¢ / Star.",
        available=False,
    ),
    StarPackage(
        sku="stars_150",
        name="Creator",
        stars=150,
        price_usd_cents=1699,
        list_price_usd_cents=1699,
        description="150 Stars — ~11.33¢ / Star.",
        available=False,
    ),
    StarPackage(
        sku="stars_500",
        name="Studio",
        stars=500,
        price_usd_cents=4999,
        list_price_usd_cents=4999,
        description="500 Stars — 10.00¢ / Star.",
        available=False,
    ),
)


def list_packages() -> list[dict[str, Any]]:
    checkout = bool(get_settings().stars_shop_checkout_enabled)
    out: list[dict[str, Any]] = []
    for pkg in STAR_PACKAGES:
        out.append(
            {
                "sku": pkg.sku,
                "name": pkg.name,
                "stars": pkg.stars,
                "price_usd_cents": pkg.price_usd_cents,
                "list_price_usd_cents": pkg.list_price_usd_cents,
                "cents_per_star": round(pkg.price_usd_cents / pkg.stars, 2) if pkg.stars else None,
                "description": pkg.description,
                "available": bool(pkg.available and checkout),
            }
        )
    return out


def package_by_sku(sku: str) -> StarPackage | None:
    key = (sku or "").strip().lower()
    for pkg in STAR_PACKAGES:
        if pkg.sku == key:
            return pkg
    return None


def get_or_create_open_cart(db: Session, user: User) -> StarCart:
    cart = db.scalar(
        select(StarCart)
        .where(StarCart.user_id == user.id, StarCart.status == "open")
        .options(selectinload(StarCart.items))
        .order_by(StarCart.created_at.desc())
    )
    if cart is not None:
        return cart
    cart = StarCart(id=uuid.uuid4(), user_id=user.id, status="open")
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return db.scalar(
        select(StarCart)
        .where(StarCart.id == cart.id)
        .options(selectinload(StarCart.items))
    )  # type: ignore[return-value]


def cart_payload(cart: StarCart) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    stars_total = 0
    price_total = 0
    for row in cart.items or []:
        pkg = package_by_sku(row.package_sku)
        qty = max(0, int(row.quantity or 0))
        if pkg is None or qty <= 0:
            continue
        line_stars = pkg.stars * qty
        line_price = pkg.price_usd_cents * qty
        stars_total += line_stars
        price_total += line_price
        items.append(
            {
                "package_sku": pkg.sku,
                "name": pkg.name,
                "quantity": qty,
                "stars_each": pkg.stars,
                "stars_line": line_stars,
                "price_usd_cents_each": pkg.price_usd_cents,
                "price_usd_cents_line": line_price,
                "available": pkg.available and bool(get_settings().stars_shop_checkout_enabled),
            }
        )
    return {
        "id": str(cart.id),
        "status": cart.status,
        "items": items,
        "stars_total": stars_total,
        "price_usd_cents_total": price_total,
        "checkout_enabled": bool(get_settings().stars_shop_checkout_enabled),
        "checkout_note": (
            None
            if get_settings().stars_shop_checkout_enabled
            else "Purchases are not available yet — cart infrastructure only."
        ),
    }


def set_cart_item(db: Session, user: User, *, sku: str, quantity: int) -> StarCart:
    pkg = package_by_sku(sku)
    if pkg is None:
        raise ValidationAppError("Unknown Stars package")
    qty = int(quantity)
    if qty < 0:
        raise ValidationAppError("Quantity must be zero or more")
    if qty > 20:
        raise ValidationAppError("Quantity too large")

    cart = get_or_create_open_cart(db, user)
    existing = next((i for i in (cart.items or []) if i.package_sku == pkg.sku), None)
    if qty == 0:
        if existing is not None:
            db.delete(existing)
            db.commit()
    else:
        if existing is None:
            db.add(
                StarCartItem(
                    id=uuid.uuid4(),
                    cart_id=cart.id,
                    package_sku=pkg.sku,
                    quantity=qty,
                )
            )
        else:
            existing.quantity = qty
        db.commit()
    return get_or_create_open_cart(db, user)


def clear_cart(db: Session, user: User) -> StarCart:
    cart = get_or_create_open_cart(db, user)
    for item in list(cart.items or []):
        db.delete(item)
    db.commit()
    return get_or_create_open_cart(db, user)


def checkout_cart(db: Session, user: User) -> dict[str, Any]:
    """Reserved for payments — currently always refused."""
    cart = get_or_create_open_cart(db, user)
    payload = cart_payload(cart)
    if not get_settings().stars_shop_checkout_enabled:
        raise ForbiddenError(
            "Stars purchases are not available yet. Your cart is saved for when checkout opens."
        )
    if not payload["items"]:
        raise ValidationAppError("Cart is empty")
    # Future: payment provider + credit ai_stars, mark cart checked_out.
    raise ForbiddenError("Stars checkout is not wired yet")
