"""Create, send, and redeem email ownership verification tokens."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import UnauthorizedError, ValidationAppError
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User
from app.services import email_delivery

_log = logging.getLogger(__name__)

# In-process last-resend timestamps keyed by normalized email (abuse soft-limit).
_LAST_RESEND_AT: dict[str, float] = {}


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_resend_cooldowns() -> None:
    _LAST_RESEND_AT.clear()


def mint_and_send_verification(db: Session, user: User) -> None:
    """Invalidate prior unused tokens, mint a new one, and send the email."""
    settings = get_settings()
    now = _now()
    # Expire outstanding unused tokens for this user (single active challenge).
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw = secrets.token_urlsafe(32)
    digest = _hash_token(raw)
    ttl = max(5, int(settings.email_verification_token_ttl_minutes))
    row = EmailVerificationToken(
        user_id=user.id,
        token_hash=digest,
        expires_at=now + timedelta(minutes=ttl),
    )
    db.add(row)
    db.flush()

    app_url = (settings.public_app_url or "https://fashionrise.app").rstrip("/")
    # Token only in query for the SPA verify page — never logged here.
    verify_url = f"{app_url}/verify-email?token={quote(raw, safe='')}"
    email_delivery.send_verification_email(to_email=user.email, verify_url=verify_url)
    _log.info("email_verification_sent user_id=%s", user.id)


def verify_email_token(db: Session, raw_token: str) -> User:
    raw = (raw_token or "").strip()
    if len(raw) < 16 or len(raw) > 200:
        raise ValidationAppError("Invalid verification link")

    digest = _hash_token(raw)
    row = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == digest)
    )
    if row is None:
        raise UnauthorizedError("Invalid or expired verification link")
    if row.used_at is not None:
        raise UnauthorizedError("Verification link already used")
    exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if exp < _now():
        raise UnauthorizedError("Verification link expired")

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account unavailable")

    row.used_at = _now()
    user.email_verified = True
    db.add(row)
    db.add(user)
    # Invalidate any other outstanding tokens for this user.
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != row.id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=_now())
    )
    db.commit()
    db.refresh(user)
    _log.info("email_verified user_id=%s", user.id)
    return user


def resend_verification(db: Session, email: str) -> None:
    """Resend verification for an unverified account.

    Always succeeds from the caller's perspective when the email format is valid —
    do not reveal whether the account exists.
    """
    from app.services import invitation_service

    email_norm = invitation_service.normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValidationAppError("Enter a valid email address")

    settings = get_settings()
    cooldown = max(0, int(settings.email_verification_resend_cooldown_seconds))
    import time

    now_ts = time.time()
    last = _LAST_RESEND_AT.get(email_norm)
    if last is not None and cooldown > 0 and (now_ts - last) < cooldown:
        # Soft cooldown — same opaque success response.
        _log.info("email_verification_resend_cooldown email_present=1")
        return

    user = db.scalar(select(User).where(User.email == email_norm))
    if user is None or user.email_verified or not user.is_active:
        _LAST_RESEND_AT[email_norm] = now_ts
        return

    try:
        mint_and_send_verification(db, user)
        db.commit()
    except Exception:
        db.rollback()
        raise
    _LAST_RESEND_AT[email_norm] = now_ts
