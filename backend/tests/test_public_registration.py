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
    """Product default: public registration without email verification / SMTP."""
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://fashionrise.app")
    get_settings.cache_clear()
    email_delivery.clear_captured_emails()
    email_verification.clear_resend_cooldowns()
    try:
        yield
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TESTING", "true")
        get_settings.cache_clear()
        email_delivery.clear_captured_emails()
        email_verification.clear_resend_cooldowns()


@pytest.fixture
def public_mode_verify(monkeypatch):
    """Optional future path: public + EMAIL_VERIFICATION_REQUIRED with capture mail."""
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@fashionrise.app")
    monkeypatch.setenv("PUBLIC_APP_URL", "https://fashionrise.app")
    get_settings.cache_clear()
    email_delivery.clear_captured_emails()
    email_verification.clear_resend_cooldowns()
    try:
        yield
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("TESTING", "true")
        get_settings.cache_clear()
        email_delivery.clear_captured_emails()
        email_verification.clear_resend_cooldowns()


def _token_from_captured(to_email: str) -> str:
    msgs = [m for m in email_delivery.captured_emails() if m.to_email == to_email]
    assert msgs, f"no captured email for {to_email}"
    body = msgs[-1].body_text
    # Fragment handoff — token must not appear in the query string.
    match = re.search(
        r"https://fashionrise\.app/verify-email#token=([^\s]+)",
        body,
    )
    assert match, body
    assert "?token=" not in body
    return match.group(1)


def test_schema_028_email_verification_columns(engine):
    """create_all / migration 028 surface: verified flag, resend throttle, token table."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "email_verified" in user_cols
    assert "email_verification_last_sent_at" in user_cols
    assert "email_verification_tokens" in insp.get_table_names()
    token_cols = {c["name"] for c in insp.get_columns("email_verification_tokens")}
    assert {"token_hash", "used_at", "expires_at", "user_id"} <= token_cols


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


def test_public_mode_without_smtp_works_when_verification_off(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    get_settings.cache_clear()
    try:
        status = client.get("/api/v1/auth/registration/status").json()
        assert status["configured_mode"] == "public"
        assert status["mode"] == "public"
        assert status["registration_available"] is True
        assert status["requires_email_verification"] is False
        assert status["prerequisite"] is None

        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "nosmtp@example.com",
                "username": "nosmtp_user",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "authenticated"
        assert body["access_token"]
        assert body["refresh_token"]
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_public_mode_with_verification_requires_smtp(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
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
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "needsmtp@example.com",
                "username": "needsmtp",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 403
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_public_registration_immediate_session(client, db_session, public_mode):
    status = client.get("/api/v1/auth/registration/status").json()
    assert status["mode"] == "public"
    assert status["requires_email_verification"] is False

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
    assert body["status"] == "authenticated"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["email"] == "public.user@example.com"
    assert email_delivery.captured_emails() == []

    user = db_session.scalar(select(User).where(User.email == "public.user@example.com"))
    assert user is not None
    assert user.email_verified is True
    assert user.is_admin is False
    assert user.ai_stars_unlimited is False
    assert user.ai_stars == get_settings().ai_stars_starting_balance

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "public.user@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "public.user@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_public_registration_success_and_verify(client, db_session, public_mode_verify):
    status = client.get("/api/v1/auth/registration/status").json()
    assert status["mode"] == "public"
    assert status["requires_email_verification"] is True

    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Verify.User@Example.com",
            "username": "verify_user",
            "password": "StrongPass123!",
            "display_name": "Verify User",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "verification_pending"
    assert body["access_token"] is None
    assert body["email"] == "verify.user@example.com"

    user = db_session.scalar(select(User).where(User.email == "verify.user@example.com"))
    assert user is not None
    assert user.email_verified is False
    assert user.is_admin is False
    assert user.ai_stars_unlimited is False
    assert user.ai_stars == get_settings().ai_stars_starting_balance

    # Unverified must not login or receive tokens when verification is required.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "verify.user@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 401
    assert "not verified" in login.json()["detail"]["message"].lower()

    raw = _token_from_captured("verify.user@example.com")
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
    assert me.json()["email"] == "verify.user@example.com"
    assert me.json()["is_admin"] is False

    reuse = client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert reuse.status_code == 401

    # Password login works after verification.
    again = client.post(
        "/api/v1/auth/login",
        json={"email": "verify.user@example.com", "password": "StrongPass123!"},
    )
    assert again.status_code == 200


def test_public_resend_verification(client, db_session, public_mode_verify, monkeypatch):
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
        assert users[0].email_verified is True
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
    assert r.json()["status"] == "authenticated"
    assert r.json()["access_token"]


def test_verify_url_uses_fragment_not_query(client, public_mode_verify):
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
    url = re.search(r"https://[^\s]+", msg.body_text).group(0)
    parsed = urlparse(url)
    assert parsed.path.endswith("/verify-email")
    assert parse_qs(parsed.query) == {}
    frag = parse_qs(parsed.fragment)
    assert "token" in frag
    assert "password" not in frag
    assert "Opening the page alone does not verify" in msg.body_text


def test_concurrent_verification_token_redemption(engine, public_mode_verify):
    """Exactly one concurrent redemption of the same token may authenticate."""
    from app.core.errors import AppError, UnauthorizedError, ValidationAppError
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    setup = SessionLocal()
    try:
        auth_service.register_user(
            setup,
            UserRegister(
                email="race_verify@example.com",
                username="race_verify",
                password="StrongPass123!",
            ),
        )
    finally:
        setup.close()
    raw = _token_from_captured("race_verify@example.com")
    barrier = threading.Barrier(2)
    results: list[int] = []
    lock = threading.Lock()

    def worker() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            try:
                user = email_verification.verify_email_token(db, raw)
                access, refresh = auth_service.issue_tokens(db, user)
                assert access and refresh
                code = 200
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, UnauthorizedError):
                    code = 401
                elif isinstance(exc, ValidationAppError):
                    code = 422
                elif isinstance(exc, AppError):
                    code = exc.status_code
                else:
                    code = 500
            with lock:
                results.append(code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker), pool.submit(worker)]
        for f in futs:
            f.result(timeout=30)

    assert results.count(200) == 1
    assert results.count(401) == 1
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == "race_verify@example.com"))
        assert user is not None
        assert user.email_verified is True
        assert user.is_admin is False
    finally:
        session.close()


def test_concurrent_verify_versus_resend(engine, public_mode_verify, monkeypatch):
    """User→token lock order: verify vs resend must not deadlock; exactly one redeem path."""
    from app.core.errors import UnauthorizedError
    from app.models.email_verification_token import EmailVerificationToken
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    monkeypatch.setenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    setup = SessionLocal()
    try:
        auth_service.register_user(
            setup,
            UserRegister(
                email="race_vr@example.com",
                username="race_vr",
                password="StrongPass123!",
            ),
        )
        user = setup.scalar(select(User).where(User.email == "race_vr@example.com"))
        assert user is not None
        user.email_verification_last_sent_at = None
        setup.add(user)
        setup.commit()
    finally:
        setup.close()

    old_token = _token_from_captured("race_vr@example.com")
    email_delivery.clear_captured_emails()
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def do_verify() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            try:
                user = email_verification.verify_email_token(db, old_token)
                # Tokens only after successful verification — never auto-auth on open.
                auth_service.issue_tokens(db, user)
                label = "verify_ok"
            except UnauthorizedError:
                label = "verify_rejected"
            except Exception as exc:  # noqa: BLE001
                label = f"verify_err:{type(exc).__name__}"
            with lock:
                outcomes.append(label)
        finally:
            db.close()

    def do_resend() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            try:
                email_verification.resend_verification(db, "race_vr@example.com")
                label = "resend_done"
            except Exception as exc:  # noqa: BLE001
                label = f"resend_err:{type(exc).__name__}"
            with lock:
                outcomes.append(label)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(do_verify), pool.submit(do_resend)]
        for f in futs:
            f.result(timeout=30)

    assert len(outcomes) == 2, outcomes
    assert not any(o.startswith(("verify_err", "resend_err")) for o in outcomes), outcomes
    assert "resend_done" in outcomes
    assert ("verify_ok" in outcomes) ^ ("verify_rejected" in outcomes)

    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == "race_vr@example.com"))
        assert user is not None
        assert user.is_admin is False
        unused = list(
            session.scalars(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.used_at.is_(None),
                )
            ).all()
        )
        if "verify_ok" in outcomes:
            # Verification won: account verified; resend is a verified no-op (no new mail).
            assert user.email_verified is True
            assert unused == []
            assert email_delivery.captured_emails() == []
            reuse = SessionLocal()
            try:
                with pytest.raises(UnauthorizedError):
                    email_verification.verify_email_token(reuse, old_token)
            finally:
                reuse.close()
        else:
            # Resend won: old token invalidated; replacement can be verified once.
            assert user.email_verified is False
            assert len(email_delivery.captured_emails()) == 1
            new_raw = _token_from_captured("race_vr@example.com")
            assert new_raw != old_token
            verified = email_verification.verify_email_token(session, new_raw)
            assert verified.email_verified is True
    finally:
        session.close()


def test_concurrent_resend_does_not_stampede(engine, public_mode_verify, monkeypatch):
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    monkeypatch.setenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "120")
    get_settings.cache_clear()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    setup = SessionLocal()
    try:
        auth_service.register_user(
            setup,
            UserRegister(
                email="race_resend@example.com",
                username="race_resend",
                password="StrongPass123!",
            ),
        )
        user = setup.scalar(select(User).where(User.email == "race_resend@example.com"))
        assert user is not None
        # Clear throttle so both workers attempt a send; FOR UPDATE serializes them.
        user.email_verification_last_sent_at = None
        setup.add(user)
        setup.commit()
    finally:
        setup.close()
    email_delivery.clear_captured_emails()
    barrier = threading.Barrier(2)

    def worker() -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=10)
            email_verification.resend_verification(db, "race_resend@example.com")
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker), pool.submit(worker)]
        for f in futs:
            f.result(timeout=30)

    # One winner sends; the other hits persistent cooldown under FOR UPDATE.
    assert len(email_delivery.captured_emails()) == 1


def test_capture_backend_rejected_outside_tests(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "false")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
    monkeypatch.setenv("CORS_ORIGINS", "https://fashionrise.app")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.testing is False
        assert s.email_delivery_configured() is False
        assert s.effective_registration_mode() == "closed"
        assert s.registration_public_prerequisite()
        assert "capture" in (s.registration_public_prerequisite() or "").lower()
        from app.core.errors import ServiceUnavailableError

        with pytest.raises(ServiceUnavailableError):
            email_delivery.send_email(
                to_email="x@example.com",
                subject="nope",
                body_text="nope",
            )
    finally:
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        get_settings.cache_clear()


def test_capture_rejected_when_testing_true_but_environment_production(client, monkeypatch):
    """PM guard: capture must not satisfy verification-required public mode in production."""
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
    monkeypatch.setenv("CORS_ORIGINS", "https://fashionrise.app")
    get_settings.cache_clear()
    email_delivery.clear_captured_emails()
    try:
        s = get_settings()
        assert s.testing is True
        assert s.environment == "production"
        assert s.email_delivery_configured() is False
        assert s.effective_registration_mode() == "closed"
        assert "production" in (s.registration_public_prerequisite() or "").lower()

        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "capprod@example.com",
                "username": "capprod",
                "password": "StrongPass123!",
            },
        )
        assert r.status_code == 403
        assert email_delivery.captured_emails() == []

        from app.core.errors import ServiceUnavailableError

        with pytest.raises(ServiceUnavailableError):
            email_delivery.send_email(
                to_email="capprod@example.com",
                subject="nope",
                body_text="nope",
            )
        assert email_delivery.captured_emails() == []
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setenv("ENVIRONMENT", "production")
        get_settings.cache_clear()
        email_delivery.clear_captured_emails()


def test_authenticated_smtp_without_tls_rejected(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "public")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@fashionrise.app")
    monkeypatch.setenv("SMTP_USERNAME", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    monkeypatch.setenv("SMTP_PORT", "587")
    get_settings.cache_clear()
    try:
        s = get_settings()
        assert s.email_delivery_configured() is False
        assert "encrypted" in (s.registration_public_prerequisite() or "").lower()
    finally:
        monkeypatch.delenv("REGISTRATION_MODE", raising=False)
        monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
        monkeypatch.delenv("SMTP_USERNAME", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)
        monkeypatch.setenv("SMTP_USE_TLS", "true")
        get_settings.cache_clear()


def test_smtp_failure_after_commit_leaves_recoverable_account(
    client, db_session, public_mode_verify, monkeypatch
):
    """If delivery fails after commit, the user can resend — no stranded credentials."""
    from app.core.errors import ServiceUnavailableError

    calls = {"n": 0}
    real_send = email_verification.send_verification_for_raw_token

    def flaky_send(*, to_email: str, raw_token: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ServiceUnavailableError("Unable to send verification email right now")
        return real_send(to_email=to_email, raw_token=raw_token)

    monkeypatch.setattr(
        email_verification,
        "send_verification_for_raw_token",
        flaky_send,
    )
    monkeypatch.setenv("EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS", "0")
    get_settings.cache_clear()

    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "deferred@example.com",
            "username": "deferred_user",
            "password": "StrongPass123!",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "verification_pending"
    assert "could not be sent" in (r.json().get("message") or "").lower()

    user = db_session.scalar(select(User).where(User.email == "deferred@example.com"))
    assert user is not None
    assert user.email_verified is False
    # Password login still blocked until verify.
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "deferred@example.com", "password": "StrongPass123!"},
        ).status_code
        == 401
    )

    # Resend recovers delivery.
    assert (
        client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "deferred@example.com"},
        ).status_code
        == 204
    )
    raw = _token_from_captured("deferred@example.com")
    assert client.post("/api/v1/auth/verify-email", json={"token": raw}).status_code == 200


def test_registration_rate_limit_keys_on_trusted_visitor_ip(monkeypatch):
    """Abuse controls must key on Nginx-overwritten X-Real-IP when trust is on;
    forged headers must not bypass when trust is off.
    """
    from types import SimpleNamespace

    from starlette.datastructures import Headers

    from app.core import rate_limit

    def _req(host: str, headers: list[tuple[str, str]]):
        raw = [(k.lower().encode(), v.encode()) for k, v in headers]
        return SimpleNamespace(
            client=SimpleNamespace(host=host, port=443),
            headers=Headers(raw=raw),
        )

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    forged = _req(
        "127.0.0.1",
        [("x-real-ip", "198.51.100.66"), ("x-forwarded-for", "198.51.100.66")],
    )
    assert rate_limit.client_ip_key(forged) == "127.0.0.1"

    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    trusted = _req("127.0.0.1", [("x-real-ip", "198.51.100.66")])
    assert rate_limit.client_ip_key(trusted) == "198.51.100.66"

    # Duplicate / untrusted chain fails closed to the ASGI peer.
    dup = _req(
        "127.0.0.1",
        [("x-real-ip", "198.51.100.66"), ("x-real-ip", "203.0.113.10")],
    )
    assert rate_limit.client_ip_key(dup) == "127.0.0.1"
