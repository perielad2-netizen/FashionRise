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


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clear_resend_cooldowns() -> None:
    """No-op retained for tests that cleared the former in-process map."""
    return None


def build_verify_url(raw_token: str) -> str:
    """SPA handoff via URL fragment so the token never hits server access logs."""
    settings = get_settings()
    app_url = (settings.public_app_url or "https://fashionrise.app").rstrip("/")
    # Fragment is not sent to Nginx/API. SPA reads hash, clears history, POSTs body.
    return f"{app_url}/verify-email#token={quote(raw_token, safe='')}"


def mint_verification_token(db: Session, user: User) -> str:
    """Invalidate prior unused tokens and mint a new one. Returns plaintext once.

    Caller must commit (or flush) before sending email. Does not send mail.
    """
    settings = get_settings()
    now = _now()
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
    user.email_verification_last_sent_at = now
    db.add(user)
    db.flush()
    return raw


def send_verification_for_raw_token(*, to_email: str, raw_token: str) -> None:
    email_delivery.send_verification_email(
        to_email=to_email,
        verify_url=build_verify_url(raw_token),
    )
    _log.info("email_verification_sent")


def mint_and_send_verification(db: Session, user: User) -> str:
    """Mint token (flush) and send email. Prefer commit-then-send at call sites."""
    raw = mint_verification_token(db, user)
    send_verification_for_raw_token(to_email=user.email, raw_token=raw)
    return raw


def verify_email_token(db: Session, raw_token: str) -> User:
    """Atomically redeem a single-use token (conditional UPDATE … WHERE used_at IS NULL)."""
    raw = (raw_token or "").strip()
    if len(raw) < 16 or len(raw) > 200:
        raise ValidationAppError("Invalid verification link")

    digest = _hash_token(raw)
    now = _now()

    # Atomic claim — concurrent redemptions: exactly one UPDATE wins.
    claimed = db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash == digest,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at >= now,
        )
        .values(used_at=now)
        .returning(
            EmailVerificationToken.id,
            EmailVerificationToken.user_id,
        )
    ).first()

    if claimed is None:
        existing = db.scalar(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == digest)
        )
        if existing is None:
            raise UnauthorizedError("Invalid or expired verification link")
        if existing.used_at is not None:
            raise UnauthorizedError("Verification link already used")
        raise UnauthorizedError("Verification link expired")

    token_id, user_id = claimed
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None or not user.is_active:
        raise UnauthorizedError("Account unavailable")

    user.email_verified = True
    db.add(user)
    # Invalidate any other outstanding tokens for this user.
    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != token_id,
            EmailVerificationToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()
    db.refresh(user)
    _log.info("email_verified user_id=%s", user.id)
    return user


def resend_verification(db: Session, email: str) -> None:
    """Resend verification for an unverified account.

    Persistent cooldown uses ``users.email_verification_last_sent_at`` under
    ``SELECT … FOR UPDATE`` so concurrent resends cannot stampede.
    Always returns success when the email format is valid (no account oracle).
    """
    from app.services import invitation_service

    email_norm = invitation_service.normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValidationAppError("Enter a valid email address")

    settings = get_settings()
    cooldown = max(0, int(settings.email_verification_resend_cooldown_seconds))
    now = _now()

    user = db.scalar(
        select(User).where(User.email == email_norm).with_for_update()
    )
    if user is None or user.email_verified or not user.is_active:
        # Opaque success — do not reveal account existence.
        db.commit()
        return

    last = user.email_verification_last_sent_at
    if last is not None and cooldown > 0:
        last_aware = last if last.tzinfo else last.replace(tzinfo=UTC)
        if (now - last_aware).total_seconds() < cooldown:
            _log.info("email_verification_resend_cooldown")
            db.commit()
            return

    # Reserve the cooldown slot under the row lock before releasing the transaction.
    raw = mint_verification_token(db, user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Send after commit so a delivery failure does not roll back the token / cooldown.
    try:
        send_verification_for_raw_token(to_email=user.email, raw_token=raw)
    except Exception:
        # Account + token remain; caller gets opaque 204. User can retry after cooldown.
        _log.warning("email_verification_resend_delivery_failed")
        return
