"""Create, send, and redeem forgot-password tokens."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError, UnauthorizedError, ValidationAppError
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services import email_delivery

_log = logging.getLogger(__name__)

# Lock order (mandatory): users row FOR UPDATE, then password_reset_tokens.


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_password(plain: str) -> str:
    return (plain or "").strip()


def status_payload() -> dict:
    settings = get_settings()
    available = settings.password_reset_available()
    return {
        "password_reset_available": available,
        "password_reset_enabled": bool(settings.password_reset_enabled),
        "email_delivery_configured": settings.email_delivery_configured(),
        "prerequisite": settings.password_reset_prerequisite(),
        "note": (
            "When available, POST /auth/forgot-password emails a single-use link "
            "to /reset-password#token=… (HTTPS). Works for web, iOS, and Android."
            if available
            else "Forgot-password is disabled until PASSWORD_RESET_ENABLED=true and SMTP is configured."
        ),
    }


def build_reset_url(raw_token: str) -> str:
    """SPA handoff via URL fragment so the token never hits server access logs."""
    settings = get_settings()
    app_url = (settings.public_app_url or "https://fashionrise.app").rstrip("/")
    return f"{app_url}/reset-password#token={quote(raw_token, safe='')}"


def mint_reset_token(db: Session, user: User) -> str:
    """Invalidate prior unused tokens and mint a new one. Returns plaintext once.

    Caller must already hold ``User`` ``FOR UPDATE``. Does not send mail.
    """
    settings = get_settings()
    now = _now()
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw = secrets.token_urlsafe(32)
    digest = _hash_token(raw)
    ttl = max(5, int(settings.password_reset_token_ttl_minutes))
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=digest,
        expires_at=now + timedelta(minutes=ttl),
    )
    db.add(row)
    user.password_reset_last_sent_at = now
    db.add(user)
    db.flush()
    return raw


def send_reset_for_raw_token(*, to_email: str, raw_token: str) -> None:
    email_delivery.send_password_reset_email(
        to_email=to_email,
        reset_url=build_reset_url(raw_token),
    )
    _log.info("password_reset_email_sent")


def request_password_reset(db: Session, email: str) -> None:
    """Request a reset email. Always opaque success when email format is valid.

    Lock order: ``User`` ``FOR UPDATE``, then token mint. Does not reveal whether
    the account exists. No-ops (still opaque) when the feature is unavailable,
    the account is inactive, or delivery fails after commit.
    """
    from app.services import invitation_service

    email_norm = invitation_service.normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValidationAppError("Enter a valid email address")

    settings = get_settings()
    if not settings.password_reset_available():
        # Fail closed for operators who hit the API before activation — do not mint tokens.
        raise ServiceUnavailableError(
            settings.password_reset_prerequisite()
            or "Password reset is not available"
        )

    cooldown = max(0, int(settings.password_reset_request_cooldown_seconds))
    now = _now()

    user = db.scalar(select(User).where(User.email == email_norm).with_for_update())
    if user is None or not user.is_active:
        db.commit()
        return

    last = user.password_reset_last_sent_at
    if last is not None and cooldown > 0:
        last_aware = last if last.tzinfo else last.replace(tzinfo=UTC)
        if (now - last_aware).total_seconds() < cooldown:
            _log.info("password_reset_request_cooldown")
            db.commit()
            return

    raw = mint_reset_token(db, user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        send_reset_for_raw_token(to_email=user.email, raw_token=raw)
    except Exception:  # noqa: BLE001 — delivery failure must not undo committed token
        _log.warning("password_reset_delivery_failed")
        return


def reset_password_with_token(db: Session, raw_token: str, new_password: str) -> User:
    """Redeem a single-use reset token and set a new password.

    Lock order: resolve token → lock user → atomic claim → update password.
    Caller issues tokens / revokes sessions after this returns (commit already done).
    """
    settings = get_settings()
    if not settings.password_reset_available():
        raise ServiceUnavailableError(
            settings.password_reset_prerequisite()
            or "Password reset is not available"
        )

    raw = (raw_token or "").strip()
    if len(raw) < 16 or len(raw) > 200:
        raise ValidationAppError("Invalid reset link")

    password = _normalize_password(new_password)
    if len(password) < 8 or len(password) > 128:
        raise ValidationAppError("Password must be 8–128 characters")

    digest = _hash_token(raw)
    now = _now()

    probe = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == digest)
    )
    if probe is None:
        raise UnauthorizedError("Invalid or expired reset link")

    user = db.scalar(select(User).where(User.id == probe.user_id).with_for_update())
    if user is None or not user.is_active:
        raise UnauthorizedError("Account unavailable")

    claimed = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == digest,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at >= now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.id)
    ).first()

    if claimed is None:
        row = db.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == digest)
        )
        if row is None:
            raise UnauthorizedError("Invalid or expired reset link")
        if row.used_at is not None:
            raise UnauthorizedError("Reset link already used")
        raise UnauthorizedError("Reset link expired")

    token_id = claimed[0]
    user.hashed_password = hash_password(password)
    # Proving inbox ownership — mark verified so login is not blocked by verify gate.
    user.email_verified = True
    db.add(user)
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != token_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()
    db.refresh(user)
    _log.info("password_reset_completed user_id=%s", user.id)
    return user
