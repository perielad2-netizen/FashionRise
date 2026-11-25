"""Admin gate for FashionRise web console.

Access is username-allowlisted (same email/password login as the app).
``User.is_admin`` is also honored so operators can promote accounts in DB.

Security notes (PM audit):
- ``get_current_user`` already rejects inactive/missing accounts.
- Classification never grants admin privileges.
- Reserved usernames are blocked at registration (case-insensitive).
- Username is immutable via ProfileUpdate — allowlist cannot be claimed by rename.
- Prefer promoting via durable ``User.is_admin`` over relying solely on usernames;
  username allowlist remains for owner-designated accounts until a bounded
  identity-based remediation lands.

Financial mutations (Stars grants) use a separate fail-closed gate
(``require_financial_admin``) keyed by stable user UUID — not classification
and not username alone.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.models.user import User

# Owner-designated admin usernames (case-insensitive).
# DB account is PeriShilat; alias shilatperi kept for the spoken spelling.
ADMIN_USERNAMES: frozenset[str] = frozenset({"shilatperi", "perishilat", "yanivprbk"})


def normalize_username(username: str | None) -> str:
    return (username or "").strip().lower()


def is_reserved_admin_username(username: str | None) -> bool:
    """True when username (any case) matches a reserved admin allowlist entry."""
    return normalize_username(username) in ADMIN_USERNAMES


def user_is_admin(user: User) -> bool:
    if not bool(getattr(user, "is_active", True)):
        return False
    if bool(getattr(user, "is_admin", False)):
        return True
    return is_reserved_admin_username(getattr(user, "username", None))


def require_admin(user: User = Depends(get_current_user)) -> User:
    # get_current_user already enforces is_active; re-check for defense in depth.
    if not user.is_active or not user_is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def parse_financial_actor_ids() -> frozenset[uuid.UUID]:
    """Stable UUID allowlist for Stars grant mutations.

    Config: ``ADMIN_STARS_GRANT_ACTOR_IDS`` — comma-separated user UUIDs.
    Empty / invalid → empty set → fail closed (no financial grants).
    Classification and username alone never authorize financial mutations.
    """
    raw = (get_settings().admin_stars_grant_actor_ids or "").strip()
    if not raw:
        return frozenset()
    out: set[uuid.UUID] = set()
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            out.add(uuid.UUID(token))
        except ValueError:
            # Invalid tokens are ignored; remaining valid IDs still apply.
            continue
    return frozenset(out)


def user_can_grant_stars(user: User) -> bool:
    """Financial mutation gate: active admin AND stable UUID on the grant allowlist."""
    if not user.is_active or not user_is_admin(user):
        return False
    allowed = parse_financial_actor_ids()
    if not allowed:
        return False
    return user.id in allowed


def require_financial_admin(user: User = Depends(require_admin)) -> User:
    """Fail-closed gate for ADD-ONLY Stars grants.

    Must be an AdminUser **and** listed in ``ADMIN_STARS_GRANT_ACTOR_IDS``.
    Does not grant permission based on account_classification.
    """
    if not user_can_grant_stars(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Financial admin access required. "
                "Configure ADMIN_STARS_GRANT_ACTOR_IDS with this account's user UUID."
            ),
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
FinancialAdminUser = Annotated[User, Depends(require_financial_admin)]
