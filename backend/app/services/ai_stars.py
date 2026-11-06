"""Per-user AI Stars wallet — spend gate for FashionRise AI features.

Phase 1: Magic (sketch_polish) costs ``AI_STARS_MAGIC_COST`` (default 10).
New accounts start with ``AI_STARS_STARTING_BALANCE`` (default 10) so the first
Magic is free. Owner emails in ``AI_STARS_UNLIMITED_EMAILS`` never debit.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.models.user import User

_log = logging.getLogger(__name__)


def starting_balance() -> int:
    return max(0, int(get_settings().ai_stars_starting_balance))


def magic_cost() -> int:
    return max(0, int(get_settings().ai_stars_magic_cost))


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
        # Owners keep a high display balance; debit path skips them anyway.
        user.ai_stars = max(user.ai_stars, 999_999)


def public_balance(user: User) -> dict[str, Any]:
    unlimited = user_has_unlimited_stars(user)
    return {
        "ai_stars": int(getattr(user, "ai_stars", 0) or 0),
        "ai_stars_unlimited": unlimited,
        "ai_stars_magic_cost": magic_cost(),
    }


def assert_can_spend_magic(db: Session, user: User) -> None:
    """Raise if the user cannot afford one Magic run. No-op for unlimited owners."""
    if user_has_unlimited_stars(user):
        return
    cost = magic_cost()
    if cost <= 0:
        return
    # Lock the user row so concurrent Magic enqueues cannot double-spend.
    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    if balance < cost:
        raise ForbiddenError(
            f"Not enough Stars for Magic (need {cost}, you have {balance}). "
            "Your first Magic uses your starter Stars."
        )


def debit_magic_stars(db: Session, user: User) -> int:
    """Debit Magic cost from the user wallet. Returns remaining balance.

    Call only when enqueueing a **new** Magic job (not idempotent replays).
    Unlimited owners are skipped. Must run inside the same transaction as job insert.
    """
    if user_has_unlimited_stars(user):
        return int(getattr(user, "ai_stars", 0) or 0)
    cost = magic_cost()
    if cost <= 0:
        return int(getattr(user, "ai_stars", 0) or 0)

    locked = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked is None:
        raise ForbiddenError("Account not found")
    balance = int(locked.ai_stars or 0)
    if balance < cost:
        raise ForbiddenError(
            f"Not enough Stars for Magic (need {cost}, you have {balance}). "
            "Your first Magic uses your starter Stars."
        )
    new_balance = balance - cost
    db.execute(update(User).where(User.id == locked.id).values(ai_stars=new_balance))
    locked.ai_stars = new_balance
    user.ai_stars = new_balance
    _log.info(
        "ai_stars_debited user_id=%s cost=%s remaining=%s feature=magic",
        user.id,
        cost,
        new_balance,
    )
    return new_balance
