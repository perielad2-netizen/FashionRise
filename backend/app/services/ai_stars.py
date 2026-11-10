"""Per-user AI Stars wallet — spend gate for FashionRise AI features.

Costs (defaults):
  magic=10, croquis=10, pdf=50, fabric=5
New accounts start with ``AI_STARS_STARTING_BALANCE`` (default 10).
Owner emails in ``AI_STARS_UNLIMITED_EMAILS`` never debit.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.models.user import User

_log = logging.getLogger(__name__)

Feature = Literal["magic", "croquis", "pdf", "fabric"]

_FEATURE_LABELS: dict[str, str] = {
    "magic": "Magic",
    "croquis": "Create Croquis",
    "pdf": "Create PDF",
    "fabric": "Create Fabric",
}


def starting_balance() -> int:
    return max(0, int(get_settings().ai_stars_starting_balance))


def feature_cost(feature: Feature | str) -> int:
    settings = get_settings()
    mapping = {
        "magic": int(settings.ai_stars_magic_cost),
        "croquis": int(settings.ai_stars_croquis_cost),
        "pdf": int(settings.ai_stars_pdf_cost),
        "fabric": int(settings.ai_stars_fabric_cost),
    }
    return max(0, mapping.get(str(feature), 0))


def magic_cost() -> int:
    return feature_cost("magic")


def cost_catalog() -> dict[str, int]:
    return {
        "magic": feature_cost("magic"),
        "croquis": feature_cost("croquis"),
        "pdf": feature_cost("pdf"),
        "fabric": feature_cost("fabric"),
    }


def _unlimited_emails() -> set[str]:
    raw = (get_settings().ai_stars_unlimited_emails or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def email_has_unlimited_stars(email: str) -> bool:
    return (email or "").strip().lower() in _unlimited_emails()


def user_has_unlimited_stars(user: User | Any) -> bool:
    if bool(getattr(user, "ai_stars_unlimited", False)):
        return True
    return email_has_unlimited_stars(str(getattr(user, "email", "") or ""))


def apply_new_user_stars(user: User) -> None:
    """Set starting wallet on a newly created User (before commit)."""
    user.ai_stars = starting_balance()
    user.ai_stars_unlimited = email_has_unlimited_stars(user.email or "")
    if user.ai_stars_unlimited:
        user.ai_stars = max(user.ai_stars, 999_999)


def public_balance(user: User) -> dict[str, Any]:
    unlimited = user_has_unlimited_stars(user)
    debt = int(getattr(user, "ai_stars_iap_debt", 0) or 0)
    return {
        "ai_stars": int(getattr(user, "ai_stars", 0) or 0),
        "ai_stars_unlimited": unlimited,
        "ai_stars_iap_debt": debt,
        "ai_stars_magic_cost": feature_cost("magic"),
        "ai_stars_costs": cost_catalog(),
    }


def assert_can_spend(db: Session, user: User, feature: Feature | str) -> None:
    """Raise if the user cannot afford ``feature``. No-op for unlimited owners."""
    if user_has_unlimited_stars(user):
        return
    cost = feature_cost(feature)
    if cost <= 0:
        return
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    if balance < cost:
        label = _FEATURE_LABELS.get(str(feature), str(feature))
        raise ForbiddenError(
            f"Not enough Stars for {label} (need {cost}, you have {balance}). "
            "Buy a Stars package when the shop opens, or use your starter Stars."
        )


def credit_stars(db: Session, user: User, amount: int, *, reason: str = "iap") -> int:
    """Credit Stars after verified purchase. Settles outstanding IAP refund debt first.

    Policy: ``ai_stars`` never goes negative. ``ai_stars_iap_debt`` tracks Stars Apple
    refunded that were already spent. New credits offset debt before increasing balance.
    Returns the new spendable balance (not including debt).
    """
    add = max(0, int(amount))
    if add <= 0:
        return int(getattr(user, "ai_stars", 0) or 0)
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    debt = max(0, int(getattr(locked, "ai_stars_iap_debt", 0) or 0))
    settle = min(debt, add)
    new_debt = debt - settle
    remainder = add - settle
    new_balance = int(locked.ai_stars or 0) + remainder
    db.execute(
        update(User)
        .where(User.id == locked.id)
        .values(ai_stars=new_balance, ai_stars_iap_debt=new_debt)
    )
    locked.ai_stars = new_balance
    locked.ai_stars_iap_debt = new_debt
    user.ai_stars = new_balance
    user.ai_stars_iap_debt = new_debt
    _log.info(
        "ai_stars_credited user_id=%s amount=%s settle_debt=%s remaining=%s debt=%s reason=%s",
        user.id,
        add,
        settle,
        new_balance,
        new_debt,
        reason,
    )
    return new_balance


def apply_iap_clawback(
    db: Session,
    user: User,
    *,
    stars_to_recover: int,
) -> tuple[int, int, int, int]:
    """Claw back Stars for a verified Apple refund/revoke without negative balances.

    Returns ``(from_balance, added_to_debt, balance_after, debt_after)``.

    Example: bought 500, spent 450, refund → claw 50 from balance, add 450 debt.
    Future credits settle debt before becoming spendable again.
    """
    need = max(0, int(stars_to_recover))
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    debt = max(0, int(getattr(locked, "ai_stars_iap_debt", 0) or 0))
    from_balance = min(balance, need)
    added_debt = need - from_balance
    new_balance = balance - from_balance
    new_debt = debt + added_debt
    db.execute(
        update(User)
        .where(User.id == locked.id)
        .values(ai_stars=new_balance, ai_stars_iap_debt=new_debt)
    )
    locked.ai_stars = new_balance
    locked.ai_stars_iap_debt = new_debt
    user.ai_stars = new_balance
    user.ai_stars_iap_debt = new_debt
    _log.info(
        "ai_stars_iap_clawback user_id=%s need=%s from_balance=%s debt_add=%s remaining=%s debt=%s",
        user.id,
        need,
        from_balance,
        added_debt,
        new_balance,
        new_debt,
    )
    return from_balance, added_debt, new_balance, new_debt


def restore_iap_clawback(
    db: Session,
    user: User,
    *,
    stars_to_restore: int,
) -> tuple[int, int, int, int]:
    """Restore Stars after verified REFUND_REVERSED (Apple reversed a prior refund).

    Settles outstanding debt first, then credits remainder to balance.
    Returns ``(debt_reduced, balance_added, balance_after, debt_after)``.
    Never invents Stars beyond ``stars_to_restore``.
    """
    restore = max(0, int(stars_to_restore))
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    debt = max(0, int(getattr(locked, "ai_stars_iap_debt", 0) or 0))
    debt_reduced = min(debt, restore)
    remainder = restore - debt_reduced
    new_debt = debt - debt_reduced
    new_balance = balance + remainder
    db.execute(
        update(User)
        .where(User.id == locked.id)
        .values(ai_stars=new_balance, ai_stars_iap_debt=new_debt)
    )
    locked.ai_stars = new_balance
    locked.ai_stars_iap_debt = new_debt
    user.ai_stars = new_balance
    user.ai_stars_iap_debt = new_debt
    _log.info(
        "ai_stars_iap_restore user_id=%s restore=%s debt_reduced=%s balance_add=%s remaining=%s debt=%s",
        user.id,
        restore,
        debt_reduced,
        remainder,
        new_balance,
        new_debt,
    )
    return debt_reduced, remainder, new_balance, new_debt


def debit_stars(db: Session, user: User, feature: Feature | str) -> int:
    """Debit feature cost. Returns remaining balance. Skip unlimited owners.

    Call only after AI work **succeeds** (not at enqueue, not on failure).
    Must run inside the same transaction as marking the job/run completed when possible.
    """
    if user_has_unlimited_stars(user):
        return int(getattr(user, "ai_stars", 0) or 0)
    cost = feature_cost(feature)
    if cost <= 0:
        return int(getattr(user, "ai_stars", 0) or 0)

    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    if balance < cost:
        label = _FEATURE_LABELS.get(str(feature), str(feature))
        raise ForbiddenError(
            f"Not enough Stars for {label} (need {cost}, you have {balance}). "
            "Buy a Stars package when the shop opens, or use your starter Stars."
        )
    new_balance = balance - cost
    db.execute(update(User).where(User.id == locked.id).values(ai_stars=new_balance))
    locked.ai_stars = new_balance
    user.ai_stars = new_balance
    _log.info(
        "ai_stars_debited user_id=%s cost=%s remaining=%s feature=%s",
        user.id,
        cost,
        new_balance,
        feature,
    )
    return new_balance


def assert_can_spend_magic(db: Session, user: User) -> None:
    assert_can_spend(db, user, "magic")


def debit_magic_stars(db: Session, user: User) -> int:
    return debit_stars(db, user, "magic")
