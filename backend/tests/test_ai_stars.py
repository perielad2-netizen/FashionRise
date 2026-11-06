"""AI Stars wallet — starting balance, Magic debit, owner unlimited."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.models.user import User
from app.services import ai_stars
from tests.auth_test_helpers import register_with_invite


@pytest.fixture()
def stars_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STARS_STARTING_BALANCE", "10")
    monkeypatch.setenv("AI_STARS_MAGIC_COST", "10")
    monkeypatch.setenv(
        "AI_STARS_UNLIMITED_EMAILS",
        "perielad@gmail.com,perielad2@gmail.com",
    )
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_new_user_starts_with_ten_stars(client, db_session, stars_env):
    tokens = register_with_invite(
        client, db_session, email="newbie@example.com", username="newbie_stars"
    )
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["ai_stars"] == 10
    assert body["ai_stars_unlimited"] is False


def test_owner_emails_unlimited(client, db_session, stars_env):
    tokens = register_with_invite(
        client, db_session, email="perielad@gmail.com", username="peri_owner"
    )
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["ai_stars_unlimited"] is True


def test_debit_magic_once_then_block(db_session, stars_env):
    user = User(
        email="spender@example.com",
        username="spender",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    remaining = ai_stars.debit_magic_stars(db_session, user)
    db_session.commit()
    assert remaining == 0

    with pytest.raises(ForbiddenError, match="Not enough Stars"):
        ai_stars.debit_magic_stars(db_session, user)


def test_unlimited_never_debits(db_session, stars_env):
    user = User(
        email="perielad2@gmail.com",
        username="peri2",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    before = user.ai_stars
    remaining = ai_stars.debit_magic_stars(db_session, user)
    db_session.commit()
    assert remaining == before
    assert user.ai_stars_unlimited is True
