"""Forgot-password email recovery."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services import email_delivery, password_reset
from tests.auth_test_helpers import register_with_invite


@pytest.fixture
def reset_enabled(monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_ENABLED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@fashionrise.app")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://fashionrise.app")
    monkeypatch.setenv("PASSWORD_RESET_REQUEST_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()
    email_delivery.clear_captured_emails()
    try:
        yield
    finally:
        monkeypatch.delenv("PASSWORD_RESET_ENABLED", raising=False)
        monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TESTING", "true")
        get_settings.cache_clear()
        email_delivery.clear_captured_emails()


def _token_from_captured(to_email: str) -> str:
    msgs = [m for m in email_delivery.captured_emails() if m.to_email == to_email]
    assert msgs, f"no captured email for {to_email}"
    body = msgs[-1].body_text
    match = re.search(
        r"https://fashionrise\.app/reset-password#token=([^\s]+)",
        body,
    )
    assert match, body
    return match.group(1)


def test_schema_029_password_reset_table(engine):
    from sqlalchemy import inspect

    insp = inspect(engine)
    assert "password_reset_tokens" in insp.get_table_names()
    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "password_reset_last_sent_at" in user_cols


def test_status_disabled_by_default(client):
    get_settings.cache_clear()
    res = client.get("/api/v1/auth/password-reset/status")
    assert res.status_code == 200
    body = res.json()
    assert body["password_reset_available"] is False
    assert body["password_reset_enabled"] is False


def test_status_available_when_enabled(client, reset_enabled):
    res = client.get("/api/v1/auth/password-reset/status")
    assert res.status_code == 200
    body = res.json()
    assert body["password_reset_available"] is True
    assert body["email_delivery_configured"] is True


def test_forgot_password_opaque_and_resets(client, db_session, reset_enabled):
    register_with_invite(
        client,
        db_session,
        email="reset_me@example.com",
        username="reset_me",
        password="oldpass12",
    )
    # Unknown email still 204
    unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert unknown.status_code == 204
    assert email_delivery.captured_emails() == []

    known = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset_me@example.com"},
    )
    assert known.status_code == 204
    raw = _token_from_captured("reset_me@example.com")

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset_me@example.com", "password": "newpass99"},
    )
    assert bad_login.status_code == 401

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "newpass99"},
    )
    assert reset.status_code == 200
    tokens = reset.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    # Single-use
    reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "another99"},
    )
    assert reuse.status_code == 401

    ok_login = client.post(
        "/api/v1/auth/login",
        json={"email": "reset_me@example.com", "password": "newpass99"},
    )
    assert ok_login.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "reset_me@example.com"))
    assert user is not None
    assert verify_password("newpass99", user.hashed_password)
    assert user.email_verified is True


def test_forgot_password_unavailable_without_flag(client, monkeypatch):
    monkeypatch.setenv("PASSWORD_RESET_ENABLED", "false")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    get_settings.cache_clear()
    res = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "anyone@example.com"},
    )
    assert res.status_code == 503


def test_build_reset_url_uses_fragment(reset_enabled):
    url = password_reset.build_reset_url("abcDEF0123456789xyz")
    assert url.startswith("https://fashionrise.app/reset-password#token=")
    assert "?" not in url.split("#", 1)[0]


def test_opening_link_does_not_redeem(client, db_session, reset_enabled):
    """GET/status and forgot alone never consume a minted token — only POST reset does."""
    register_with_invite(
        client,
        db_session,
        email="hold_token@example.com",
        username="hold_token",
        password="oldpass12",
    )
    assert (
        client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "hold_token@example.com"},
        ).status_code
        == 204
    )
    raw = _token_from_captured("hold_token@example.com")
    # Probing status / invalid methods must not burn the token.
    assert client.get("/api/v1/auth/password-reset/status").status_code == 200
    assert client.get("/api/v1/auth/reset-password").status_code == 405
    first = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "freshpass1"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "freshpass2"},
    )
    assert second.status_code == 401


def test_expired_and_invalid_tokens_rejected(client, db_session, reset_enabled):
    from datetime import UTC, datetime, timedelta

    from app.models.password_reset_token import PasswordResetToken

    register_with_invite(
        client,
        db_session,
        email="expire_me@example.com",
        username="expire_me",
        password="oldpass12",
    )
    assert (
        client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "expire_me@example.com"},
        ).status_code
        == 204
    )
    raw = _token_from_captured("expire_me@example.com")
    row = db_session.scalar(select(PasswordResetToken).limit(1))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(row)
    db_session.commit()

    expired = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "password": "newpass99"},
    )
    assert expired.status_code == 401

    invalid = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "zzzzzzzzzzzzzzzzzzzz", "password": "newpass99"},
    )
    assert invalid.status_code == 401
