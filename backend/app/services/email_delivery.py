"""Outbound email delivery for ownership verification.

Uses stdlib SMTP when configured. Capture backend stores messages in-memory for tests.
Never log passwords, raw verification tokens, or SMTP credentials.
"""

from __future__ import annotations

import logging
import smtplib
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
            "Email delivery is not configured (SMTP_HOST and SMTP_FROM_EMAIL required)"
        )

    msg = _build_message(to_email=to_email, subject=subject, body_text=body_text)
    host = settings.smtp_host.strip()
    port = int(settings.smtp_port)
    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                user = (settings.smtp_username or "").strip()
                if user:
                    smtp.login(user, settings.smtp_password or "")
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                user = (settings.smtp_username or "").strip()
                if user:
                    smtp.login(user, settings.smtp_password or "")
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
        "Confirm your email address to finish creating your account:\n"
        f"{verify_url}\n\n"
        "This link expires soon and can be used only once. "
        "If you did not create a FashionRise account, you can ignore this message.\n"
    )
    # Meta must never include the raw token — only a non-sensitive kind tag.
    send_email(to_email=to_email, subject=subject, body_text=body, meta={"kind": "email_verification"})
