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
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
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


AdminUser = Annotated[User, Depends(require_admin)]
