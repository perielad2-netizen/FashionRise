"""Admin gate for FashionRise web console.

Access is username-allowlisted (same email/password login as the app).
``User.is_admin`` is also honored so operators can promote accounts in DB.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.models.user import User

# Owner-designated admin usernames (case-insensitive).
# DB account is PeriShilat; alias shilatperi kept for the spoken spelling.
ADMIN_USERNAMES: frozenset[str] = frozenset({"shilatperi", "perishilat", "yanivprbk"})


def user_is_admin(user: User) -> bool:
    if bool(getattr(user, "is_admin", False)):
        return True
    name = (getattr(user, "username", None) or "").strip().lower()
    return name in ADMIN_USERNAMES


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user_is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
