"""Invite-only beta registration security tests."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import verify_password
from app.models.registration_invitation import RegistrationInvitation
from app.models.user import User
from app.services import invitation_service
from tests.auth_test_helpers import register_with_invite


def test_registration_disabled_by_default_gate(client, db_session, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    get_settings.cache_clear()
    try:
        created = invitation_service.create_invitation(db_session, email="gated@example.com")
        r = client.post(
            "/api/v1/auth/register",
            json={
                "email": "gated@example.com",
                "username": "gated_user",
                "password": "StrongPass123!",
                "invitation_code": created.plaintext_token,
            },
        )
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "forbidden"
    finally:
        monkeypatch.setenv("REGISTRATION_ENABLED", "true")
        get_settings.cache_clear()


def test_successful_invited_registration(client, db_session):
    tokens = register_with_invite(client, db_session, "newbeta@example.com", "newbeta")
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "newbeta@example.com"
    assert body["username"] == "newbeta"
    assert body["is_admin"] is False
    assert body["is_active"] is True


def test_register_without_invitation_code_rejected(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "noinvite@example.com",
            "username": "noinvite",
            "password": "StrongPass123!",
        },
    )
    assert r.status_code == 422


def test_invalid_invitation_rejected(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "badinvite@example.com",
            "username": "badinvite",
            "password": "StrongPass123!",
            "invitation_code": "this-is-not-a-real-invitation-token-xx",
        },
    )
    assert r.status_code == 403


def test_expired_invitation_rejected(client, db_session):
    created = invitation_service.create_invitation(db_session, email="expired@example.com", expires_in_hours=1)
    row = db_session.get(RegistrationInvitation, created.id)
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(row)
    db_session.commit()

    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "expired@example.com",
            "username": "expired_user",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert r.status_code == 403
    assert "expired" in r.json()["detail"]["message"].lower()


def test_revoked_invitation_rejected(client, db_session):
    created = invitation_service.create_invitation(db_session, email="revoked@example.com")
    invitation_service.revoke_invitation(db_session, created.id)
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "revoked@example.com",
            "username": "revoked_user",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert r.status_code == 403


def test_already_used_invitation_rejected(client, db_session):
    created = invitation_service.create_invitation(db_session, email="once@example.com")
    first = client.post(
        "/api/v1/auth/register",
        json={
            "email": "once@example.com",
            "username": "once_user",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/register",
        json={
            "email": "once2@example.com",
            "username": "once_user2",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert second.status_code == 403


def test_wrong_invited_email_rejected(client, db_session):
    created = invitation_service.create_invitation(db_session, email="invited@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "other@example.com",
            "username": "wrong_email_user",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert r.status_code == 403


def test_duplicate_email_and_username(client, db_session):
    register_with_invite(client, db_session, "dupe@example.com", "dupe_user")
    inv2 = invitation_service.create_invitation(db_session, email="dupe@example.com")
    email_conflict = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dupe@example.com",
            "username": "dupe_user_2",
            "password": "StrongPass123!",
            "invitation_code": inv2.plaintext_token,
        },
    )
    assert email_conflict.status_code == 409

    inv3 = invitation_service.create_invitation(db_session, email="dupe2@example.com")
    user_conflict = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dupe2@example.com",
            "username": "dupe_user",
            "password": "StrongPass123!",
            "invitation_code": inv3.plaintext_token,
        },
    )
    assert user_conflict.status_code == 409


def test_plaintext_token_not_stored(client, db_session):
    created = invitation_service.create_invitation(db_session, email="hashonly@example.com")
    row = db_session.get(RegistrationInvitation, created.id)
    assert row is not None
    assert created.plaintext_token not in (row.token_hash or "")
    assert row.token_hash == invitation_service.hash_invitation_token(created.plaintext_token)


def test_failed_account_creation_does_not_consume_invitation(db_session, monkeypatch):
    from app.core.security import hash_password
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    created = invitation_service.create_invitation(db_session, email="rollback@example.com")
    token = created.plaintext_token
    invite_id = created.id

    def boom(_password: str) -> str:
        raise RuntimeError("simulated hash failure")

    monkeypatch.setattr(auth_service, "hash_password", boom)
    try:
        with pytest.raises(RuntimeError):
            auth_service.register_user(
                db_session,
                UserRegister(
                    email="rollback@example.com",
                    username="rollback_user",
                    password="StrongPass123!",
                    invitation_code=token,
                ),
            )
    finally:
        monkeypatch.setattr(auth_service, "hash_password", hash_password)

    row = db_session.get(RegistrationInvitation, invite_id)
    assert row is not None
    assert row.redeemed_at is None
    assert invitation_service.invitation_status(row) == "pending"
    # Still redeemable: lock + validate succeeds for a follow-up register.
    locked = invitation_service.assert_invitation_redeemable(
        db_session, raw_token=token, email="rollback@example.com"
    )
    assert locked.id == invite_id


def test_existing_user_can_still_login(client, db_session):
    password = "StrongPass123!"
    register_with_invite(client, db_session, "loginok@example.com", "loginok", password)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "loginok@example.com", "password": password},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_invited_user_register_save_relogin_isolation_journey(client, db_session):
    """Product journey: invite → register → Studio save → logout → login → private designs."""
    password = "StrongPass123!"
    tokens = register_with_invite(
        client, db_session, "journey_a@example.com", "journey_a", password
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "journey_a@example.com"

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": "Journey look",
            "description": "kept across sessions",
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {
                "schema": "fashionrise.saved_design.v1",
                "snapshot": {
                    "schema": "fashionrise.studio.draft.v1",
                    "strokes": [],
                    "model": "female",
                    "customReferenceUrl": None,
                    "customReferenceKey": None,
                    "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
                    "dimmed": False,
                    "clientRevision": 1,
                    "updatedAt": "2026-10-20T00:00:00.000Z",
                },
            },
            "metadata": {"designKind": "saved_design"},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "journey_a@example.com", "password": password},
    )
    assert login.status_code == 200, login.text
    relogin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    mine = client.get("/api/v1/designs/my", headers=relogin_headers)
    assert mine.status_code == 200
    assert any(d["id"] == design_id for d in mine.json())

    reopen = client.get(f"/api/v1/designs/{design_id}", headers=relogin_headers)
    assert reopen.status_code == 200
    assert reopen.json()["title"] == "Journey look"

    other = register_with_invite(client, db_session, "journey_b@example.com", "journey_b")
    other_h = {"Authorization": f"Bearer {other['access_token']}"}
    other_list = client.get("/api/v1/designs/my", headers=other_h)
    assert other_list.status_code == 200
    assert all(d["id"] != design_id for d in other_list.json())
    other_get = client.get(f"/api/v1/designs/{design_id}", headers=other_h)
    assert other_get.status_code in (403, 404)


def test_username_charset_rejected(client, db_session):
    created = invitation_service.create_invitation(db_session, email="baduser@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "baduser@example.com",
            "username": "bad-user!",
            "password": "StrongPass123!",
            "invitation_code": created.plaintext_token,
        },
    )
    assert r.status_code == 422


def test_direct_register_cannot_bypass_invitation(client, db_session):
    # Even with registration enabled, omitting/forging invitation fails.
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bypass@example.com",
            "username": "bypass_user",
            "password": "StrongPass123!",
            "invitation_code": "x" * 32,
        },
    )
    assert r.status_code == 403


def test_private_design_isolation_across_invited_accounts(client, db_session):
    a = register_with_invite(client, db_session, "iso_a@example.com", "iso_a")
    b = register_with_invite(client, db_session, "iso_b@example.com", "iso_b")
    a_h = {"Authorization": f"Bearer {a['access_token']}"}
    b_h = {"Authorization": f"Bearer {b['access_token']}"}

    created = client.post(
        "/api/v1/designs",
        headers=a_h,
        json={
            "title": "A private look",
            "description": "secret",
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {
                "schema": "fashionrise.saved_design.v1",
                "snapshot": {
                    "schema": "fashionrise.studio.draft.v1",
                    "strokes": [],
                    "model": "female",
                    "customReferenceUrl": None,
                    "customReferenceKey": None,
                    "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
                    "dimmed": False,
                    "clientRevision": 1,
                    "updatedAt": "2026-10-20T00:00:00.000Z",
                },
            },
            "metadata": {"designKind": "saved_design"},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    mine = client.get("/api/v1/designs/my", headers=a_h)
    assert mine.status_code == 200
    assert any(d["id"] == design_id for d in mine.json())

    other_list = client.get("/api/v1/designs/my", headers=b_h)
    assert other_list.status_code == 200
    assert all(d["id"] != design_id for d in other_list.json())

    other_get = client.get(f"/api/v1/designs/{design_id}", headers=b_h)
    assert other_get.status_code in (403, 404)


def test_concurrent_invitation_redemption(engine):
    """Only one concurrent redeem succeeds for the same invitation token."""
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    try:
        created = invitation_service.create_invitation(setup, email="race@example.com", expires_in_hours=24)
        token = created.plaintext_token
        setup.commit()
    finally:
        setup.close()

    results: list[int] = []
    lock = threading.Lock()

    def attempt(username: str) -> None:
        from app.schemas.auth import UserRegister
        from app.services import auth_service

        db = Session()
        try:
            try:
                auth_service.register_user(
                    db,
                    UserRegister(
                        email="race@example.com",
                        username=username,
                        password="StrongPass123!",
                        invitation_code=token,
                    ),
                )
                code = 200
            except Exception as exc:  # noqa: BLE001 — map to status-like codes for assertion
                from app.core.errors import AppError, ConflictError, ForbiddenError

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
        f1 = pool.submit(attempt, "race_user_a")
        f2 = pool.submit(attempt, "race_user_b")
        f1.result()
        f2.result()

    assert results.count(200) == 1
    assert results.count(403) + results.count(409) >= 1

    from sqlalchemy import select

    verify = Session()
    try:
        users = list(verify.scalars(select(User).where(User.email == "race@example.com")).all())
        assert len(users) == 1
        assert users[0].is_admin is False
        assert verify_password("StrongPass123!", users[0].hashed_password)
        inv = verify.scalars(
            select(RegistrationInvitation).where(
                RegistrationInvitation.email_normalized == "race@example.com"
            )
        ).one()
        assert invitation_service.invitation_status(inv) == "redeemed"
    finally:
        verify.close()


def _status_code_from_exc(exc: BaseException) -> int:
    from app.core.errors import AppError, ConflictError, ForbiddenError

    if isinstance(exc, ForbiddenError):
        return 403
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, AppError):
        return exc.status_code
    return 500


def test_concurrent_different_invites_same_email_one_409(engine):
    """Two valid invites for the same email: one register wins, loser gets 409, loser invite stays pending."""
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    try:
        inv_a = invitation_service.create_invitation(setup, email="same_email@example.com")
        inv_b = invitation_service.create_invitation(setup, email="same_email@example.com")
        token_a, token_b = inv_a.plaintext_token, inv_b.plaintext_token
        id_a, id_b = inv_a.id, inv_b.id
        setup.commit()
    finally:
        setup.close()

    results: list[tuple[str, int]] = []
    lock = threading.Lock()

    def attempt(label: str, token: str, username: str) -> None:
        db = Session()
        try:
            try:
                auth_service.register_user(
                    db,
                    UserRegister(
                        email="same_email@example.com",
                        username=username,
                        password="StrongPass123!",
                        invitation_code=token,
                    ),
                )
                code = 200
            except Exception as exc:  # noqa: BLE001
                code = _status_code_from_exc(exc)
            with lock:
                results.append((label, code))
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(attempt, "a", token_a, "same_email_a")
        f2 = pool.submit(attempt, "b", token_b, "same_email_b")
        f1.result()
        f2.result()

    codes = [c for _, c in results]
    assert codes.count(200) == 1
    assert codes.count(409) == 1

    from sqlalchemy import select

    verify = Session()
    try:
        users = list(verify.scalars(select(User).where(User.email == "same_email@example.com")).all())
        assert len(users) == 1
        row_a = verify.get(RegistrationInvitation, id_a)
        row_b = verify.get(RegistrationInvitation, id_b)
        assert row_a is not None and row_b is not None
        statuses = {
            invitation_service.invitation_status(row_a),
            invitation_service.invitation_status(row_b),
        }
        assert "redeemed" in statuses
        assert "pending" in statuses
        # Loser invite must still be redeemable for a *different* email? No — email-bound.
        # It remains pending so operator can revoke or the invitee cannot use it for another email.
        pending = row_a if invitation_service.invitation_status(row_a) == "pending" else row_b
        assert pending.redeemed_at is None
        assert pending.revoked_at is None
    finally:
        verify.close()


def test_concurrent_different_invites_same_username_one_409(engine):
    """Different emails, same username: one wins, loser 409, loser invite remains pending."""
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    try:
        inv_a = invitation_service.create_invitation(setup, email="user_a_name@example.com")
        inv_b = invitation_service.create_invitation(setup, email="user_b_name@example.com")
        token_a, token_b = inv_a.plaintext_token, inv_b.plaintext_token
        id_a, id_b = inv_a.id, inv_b.id
        setup.commit()
    finally:
        setup.close()

    results: list[int] = []
    lock = threading.Lock()

    def attempt(email: str, token: str) -> None:
        db = Session()
        try:
            try:
                auth_service.register_user(
                    db,
                    UserRegister(
                        email=email,
                        username="shared_username",
                        password="StrongPass123!",
                        invitation_code=token,
                    ),
                )
                code = 200
            except Exception as exc:  # noqa: BLE001
                code = _status_code_from_exc(exc)
            with lock:
                results.append(code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(attempt, "user_a_name@example.com", token_a)
        f2 = pool.submit(attempt, "user_b_name@example.com", token_b)
        f1.result()
        f2.result()

    assert results.count(200) == 1
    assert results.count(409) == 1

    verify = Session()
    try:
        from sqlalchemy import select

        users = list(verify.scalars(select(User).where(User.username == "shared_username")).all())
        assert len(users) == 1
        row_a = verify.get(RegistrationInvitation, id_a)
        row_b = verify.get(RegistrationInvitation, id_b)
        statuses = sorted(
            [
                invitation_service.invitation_status(row_a),
                invitation_service.invitation_status(row_b),
            ]
        )
        assert statuses == ["pending", "redeemed"]
    finally:
        verify.close()


def test_revoke_wins_over_redeem(engine):
    """Deterministic ordering: revoke commits first; subsequent redeem is rejected."""
    from app.core.errors import ForbiddenError
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    try:
        created = invitation_service.create_invitation(setup, email="revoke_first@example.com")
        token = created.plaintext_token
        invite_id = created.id
        setup.commit()
    finally:
        setup.close()

    db_rev = Session()
    db_reg = Session()
    try:
        invitation_service.revoke_invitation(db_rev, invite_id)
        with pytest.raises(ForbiddenError):
            auth_service.register_user(
                db_reg,
                UserRegister(
                    email="revoke_first@example.com",
                    username="revoke_first_user",
                    password="StrongPass123!",
                    invitation_code=token,
                ),
            )
        row = db_rev.get(RegistrationInvitation, invite_id)
        assert invitation_service.invitation_status(row) == "revoked"
        assert row.redeemed_at is None
    finally:
        db_rev.close()
        db_reg.close()


def test_redeem_wins_over_revoke(engine):
    from app.core.errors import ConflictError
    from app.schemas.auth import UserRegister
    from app.services import auth_service

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    try:
        created = invitation_service.create_invitation(setup, email="redeem_first@example.com")
        token = created.plaintext_token
        invite_id = created.id
        setup.commit()
    finally:
        setup.close()

    db_reg = Session()
    db_rev = Session()
    try:
        auth_service.register_user(
            db_reg,
            UserRegister(
                email="redeem_first@example.com",
                username="redeem_first_user",
                password="StrongPass123!",
                invitation_code=token,
            ),
        )
        with pytest.raises(ConflictError, match="already redeemed"):
            invitation_service.revoke_invitation(db_rev, invite_id)
        row = db_reg.get(RegistrationInvitation, invite_id)
        assert invitation_service.invitation_status(row) == "redeemed"
        assert row.revoked_at is None
    finally:
        db_reg.close()
        db_rev.close()
