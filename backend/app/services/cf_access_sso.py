"""Cloudflare Access → FashionRise session (optional seamless login).

Verifies ``Cf-Access-Jwt-Assertion`` (signature / iss / aud / exp) then maps the
verified email claim to an **existing** FashionRise user. Never auto-provisions.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.cloudflare_access import (
    CloudflareAccessError,
    JwksClient,
    extract_and_verify_assertion,
    jwks_url_for_team,
)
from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError, ValidationAppError
from app.models.user import User
from app.services import auth_service

_log = logging.getLogger(__name__)
_jwks: JwksClient | None = None


def sso_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.cf_access_sso_login
        and (settings.cf_access_team_domain or "").strip()
        and (settings.cf_access_aud or "").strip()
    )


def _jwks_client() -> JwksClient:
    global _jwks
    settings = get_settings()
    url = jwks_url_for_team(settings.cf_access_team_domain.strip())
    if _jwks is None or getattr(_jwks, "_jwks_url", None) != url:
        _jwks = JwksClient(jwks_url=url)
    return _jwks


async def login_with_access_assertion(db: Session, request: Request) -> dict[str, Any]:
    """Issue FashionRise tokens for the existing user matching verified Access email."""
    if not sso_configured():
        raise ValidationAppError("Cloudflare Access SSO login is not enabled")

    settings = get_settings()
    try:
        claims = await extract_and_verify_assertion(
            request.headers,
            team_domain=settings.cf_access_team_domain.strip(),
            audience=settings.cf_access_aud.strip(),
            jwks_client=_jwks_client(),
        )
    except CloudflareAccessError as exc:
        _log.warning("cf_access_sso_denied code=%s", exc.code)
        raise UnauthorizedError("Cloudflare Access identity could not be verified") from exc

    email = (claims.email or "").strip().lower()
    if not email or "@" not in email:
        raise UnauthorizedError("Cloudflare Access token is missing a verified email")

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        # Do not create accounts — owner data stays bound to existing user rows.
        raise ForbiddenError(
            "No FashionRise account matches this Cloudflare Access identity. "
            "Sign in with your existing FashionRise credentials once, or ask the operator "
            "to link this Access email to your account."
        )
    if not user.is_active:
        raise UnauthorizedError("Account disabled")

    access, refresh = auth_service.issue_tokens(db, user)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
        "auth_via": "cloudflare_access",
    }
