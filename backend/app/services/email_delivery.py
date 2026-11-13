"""Outbound email delivery for ownership verification.

Uses stdlib SMTP when configured. Capture backend stores messages in-memory for tests.
Never log passwords, raw verification tokens, or SMTP credentials.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

_log = logging.getLogger(__name__)

# Test / capture sink — cleared explicitly in tests. Not a production store.
_CAPTURED: list[CapturedEmail] = []


@dataclass(frozen=True)
class CapturedEmail:
    to_email: str
    subject: str
    body_text: str
    meta: dict[str, Any] = field(default_factory=dict)


def clear_captured_emails() -> None:
    _CAPTURED.clear()


def captured_emails() -> list[CapturedEmail]:
    return list(_CAPTURED)


def _build_message(*, to_email: str, subject: str, body_text: str) -> EmailMessage:
    settings = get_settings()
    msg = EmailMessage()
    from_email = (settings.smtp_from_email or "").strip()
    from_name = (settings.smtp_from_name or "FashionRise").strip()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
    msg["To"] = to_email
    msg.set_content(body_text)
    return msg


def send_email(*, to_email: str, subject: str, body_text: str, meta: dict[str, Any] | None = None) -> None:
    """Send a plain-text email. Raises ServiceUnavailableError if delivery cannot proceed."""
    settings = get_settings()
    backend = (settings.email_delivery_backend or "smtp").strip().lower()
    if backend == "capture":
        # Require TESTING=true and a non-production ENVIRONMENT.
        if not settings.testing or settings.environment == "production":
            raise ServiceUnavailableError(
                "EMAIL_DELIVERY_BACKEND=capture requires TESTING=true and "
                "ENVIRONMENT other than production"
            )
        _CAPTURED.append(
            CapturedEmail(
                to_email=to_email,
                subject=subject,
                body_text=body_text,
                meta=dict(meta or {}),
            )
        )
        _log.info("email_captured to=%s subject=%s", to_email, subject)
        return

    if not settings.email_delivery_configured():
        raise ServiceUnavailableError(
            settings.registration_public_prerequisite()
            or "Email delivery is not configured (SMTP_HOST and SMTP_FROM_EMAIL required)"
        )

    msg = _build_message(to_email=to_email, subject=subject, body_text=body_text)
    host = settings.smtp_host.strip()
    port = int(settings.smtp_port)
    user = (settings.smtp_username or "").strip()
    password = settings.smtp_password or ""

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        elif settings.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            # Unauthenticated plaintext only (local relays). Auth without TLS is refused above.
            if user:
                raise ServiceUnavailableError(
                    "Authenticated SMTP requires SMTP_USE_TLS=true or port 465"
                )
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.send_message(msg)
    except OSError as exc:
        _log.warning("smtp_send_failed to=%s err=%s", to_email, type(exc).__name__)
        raise ServiceUnavailableError("Unable to send verification email right now") from exc
    except smtplib.SMTPException as exc:
        _log.warning("smtp_send_failed to=%s err=%s", to_email, type(exc).__name__)
        raise ServiceUnavailableError("Unable to send verification email right now") from exc

    _log.info("email_sent to=%s subject=%s", to_email, subject)


def send_verification_email(*, to_email: str, verify_url: str) -> None:
    subject = "Verify your FashionRise account"
    body = (
        "Welcome to FashionRise.\n\n"
        "Open this link, then confirm on the page to finish creating your account:\n"
        f"{verify_url}\n\n"
        "The link expires soon and can be used only once. "
        "Opening the page alone does not verify your email — you must confirm in the app. "
        "If you did not create a FashionRise account, you can ignore this message.\n"
    )
    # Meta must never include the raw token — only a non-sensitive kind tag.
    send_email(to_email=to_email, subject=subject, body_text=body, meta={"kind": "email_verification"})


def send_password_reset_email(*, to_email: str, reset_url: str) -> None:
    subject = "Reset your FashionRise password"
    body = (
        "We received a request to reset your FashionRise password.\n\n"
        "Open this link, then choose a new password on the page:\n"
        f"{reset_url}\n\n"
        "The link expires soon and can be used only once. "
        "Opening the page alone does not change your password — you must submit a new one. "
        "If you did not request a reset, you can ignore this message.\n"
    )
    send_email(to_email=to_email, subject=subject, body_text=body, meta={"kind": "password_reset"})
