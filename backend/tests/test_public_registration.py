"""Public email registration + verification + mode gates."""

from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.user import User
from app.services import email_delivery, email_verification
from tests.auth_test_helpers import register_with_invite


@pytest.fixture
def public_mode(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@fashionrise.app")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://fashionrise.app")
    get_settings.cache_clear()
    email_delivery.clear_captured_emails()
    email_verification.clear_resend_cooldowns()
    try:
        yield
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
        get_settings.cache_clear()
        email_delivery.clear_captured_emails()
        email_verification.clear_resend_cooldowns()


def _token_from_captured(to_email: str) -> str:
    msgs = [m for m in email_delivery.captured_emails() if m.to_email == to_email]
    assert msgs, f"no captured email for {to_email}"
    body = msgs[-1].body_text
    match = re.search(r"https://fashionrise\.app/verify-email\?token=([^\s]+)", body)
    assert match, body
    return match.group(1)


def test_registration_status_closed_by_default(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/auth/registration/status")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "closed"
        assert body["registration_available"] is False
        assert body["requires_invitation"] is False
    finally:
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_registration_status_invite_only(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "true")
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/auth/registration/status")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "invite_only"
        assert body["registration_available"] is True
        assert body["requires_invitation"] is True
        assert body["requires_email_verification"] is False
    finally:
        get_settings.cache_clear()


def test_public_mode_without_smtp_stays_closed(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    get_settings.cache_clear()
    try:
        status = client.get("/api/v1/auth/registration/status").json()
        assert status["configured_mode"] == "public"
        assert status["mode"] == "closed"
        assert status["registration_available"] is False
        assert status["prerequisite"]
        assert "SMTP_HOST" in status["prerequisite"]

        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "nosmtp@example.com",
                "username": "nosmtp_user",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 403
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_public_registration_success_and_verify(client, db_session, public_mode):
    status = client.get("/api/v1/auth/registration/status").json()
    assert status["mode"] == "public"
    assert status["requires_email_verification"] is True

    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Public.User@Example.com",
            "username": "public_user",
            "password": "StrongPass123!",
            "display_name": "Public User",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "verification_pending"
    assert body["access_token"] is None
    assert body["email"] == "public.user@example.com"

    user = db_session.scalar(select(User).where(User.email == "public.user@example.com"))
    assert user is not None
    assert user.email_verified is False
    assert user.is_admin is False
    assert user.ai_stars_unlimited is False
    assert user.ai_stars == get_settings().ai_stars_starting_balance

    # Unverified must not login or receive tokens.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "public.user@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 401
    assert "not verified" in login.json()["detail"]["message"].lower()

    raw = _token_from_captured("public.user@example.com")
    # Captured body must not be logged elsewhere; ensure token is single-use.
    verify = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert verify.status_code == 200, verify.text
    tokens = verify.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    db_session.refresh(user)
    assert user.email_verified is True

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "public.user@example.com"
    assert me.json()["is_admin"] is False

    reuse = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert reuse.status_code == 401

    # Password login works after verification.
    again = client.post(
        "/api/v1/auth/login",
        json={"email": "public.user@example.com", "password": "StrongPass123!"},
    )
    assert again.status_code == 200


def test_public_resend_verification(client, db_session, public_mode, monkeypatch):
    monkeypatch.setenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "resend@example.com",
            "username": "resend_user",
            "password": "StrongPass123!",
        },
    )
    assert len(email_delivery.captured_emails()) == 1
    first = _token_from_captured("resend@example.com")

    r = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "resend@example.com"},
    )
    assert r.status_code == 204
    assert len(email_delivery.captured_emails()) == 2
    second = _token_from_captured("resend@example.com")
    assert second != first

    # Old token invalidated.
    assert (
        client.post("/api/v1/auth/verify-email", json={"token": first}).status_code == 401
    )
    assert (
        client.post("/api/v1/auth/verify-email", json={"token": second}).status_code == 200
    )

    # Opaque success for unknown email.
    unknown = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "nobody@example.com"},
    )
    assert unknown.status_code == 204


def test_public_duplicate_email_and_username(client, public_mode):
    payload = {
        "email": "dup@example.com",
        "username": "dup_user",
        "password": "StrongPass123!",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 200
    email_clash = client.post(
        "/api/v1/auth/register",
        json={**payload, "username": "dup_user2"},
    )
    assert email_clash.status_code == 409
    assert "email" in email_clash.json()["detail"]["message"].lower()

    user_clash = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup2@example.com",
            "username": "dup_user",
            "password": "StrongPass123!",
        },
    )
    assert user_clash.status_code == 409
    assert "username" in user_clash.json()["detail"]["message"].lower()


def test_public_invalid_password_rejected(client, public_mode):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "short@example.com",
            "username": "short_pw",
            "password": "short",
        },
    )
    assert r.status_code == 422


def test_invite_only_mode_preserved(client, db_session, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    get_settings.cache_clear()
    try:
        # No invite → validation error (not silent public create).
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "needinvite@example.com",
                "username": "needinvite",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 422
        tokens = register_with_invite(
            client, db_session, "invitedok@example.com", "invitedok"
        )
        assert tokens["status"] == "authenticated"
        assert tokens["access_token"]
        user = db_session.scalar(
            select(User).where(User.email == "invitedok@example.com")
        )
        assert user is not None
        assert user.email_verified is True
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_closed_mode_preserved(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "closed")
    get_settings.cache_clear()
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "closed@example.com",
                "username": "closed_user",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 403
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_public_concurrent_duplicate_email(engine, public_mode):
    """Two parallel public registers for the same email → one winner, one 409."""
    from app.core.errors import AppError, ConflictError, ForbiddenError
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def worker(suffix: str) -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            try:
                auth_service.register_user(
                    db,
                    UserRegister(
                        email="race_public@example.com",
                        username=f"race_pub_{suffix}",
                        password="StrongPass123!",
                    ),
                )
                code = 200
            except Exception as exc:  # noqa: BLE001 — map to status-like codes
                if isinstance(exc, ForbiddenError):
                    code = 403
                elif isinstance(exc, ConflictError):
                    code = 409
                elif isinstance(exc, AppError):
                    code = exc.status_code
                else:
                    code = 500
            with lock:
                results.append(code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker, "a"), pool.submit(worker, "b")]
        for f in futs:
            f.result(timeout=30)

    assert results.count(200) == 1
    assert results.count(409) >= 1
    session = SessionLocal()
    try:
        users = list(
            session.scalars(
                select(User).where(User.email == "race_public@example.com")
            ).all()
        )
        assert len(users) == 1
        assert users[0].email_verified is False
        assert users[0].is_admin is False
        assert users[0].ai_stars_unlimited is False
    finally:
        session.close()


def test_public_does_not_require_invitation_code(client, public_mode):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "noinvitepublic@example.com",
            "username": "noinvitepublic",
            "password": "StrongPass123!",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "verification_pending"


def test_verify_url_does_not_embed_credentials(client, public_mode):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "safeurl@example.com",
            "username": "safeurl",
            "password": "StrongPass123!",
        },
    )
    msg = email_delivery.captured_emails()[-1]
    assert "StrongPass123!" not in msg.body_text
    parsed = urlparse(re.search(r"https://[^\s]+", msg.body_text).group(0))
    qs = parse_qs(parsed.query)
    assert "token" in qs
    assert "password" not in qs
