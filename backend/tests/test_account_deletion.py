"""In-app account deletion (App Store Guideline 5.1.1(v))."""

from __future__ import annotations

from sqlalchemy import select

from app.models.user import User
from app.models.user_profile import UserProfile
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_delete_account_requires_confirm(client, db_session):
    tokens = register_with_invite(
        client, db_session, email="del-confirm@example.com", username="del_confirm"
    )
    bad = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_auth(tokens),
        json={"confirm": "please"},
    )
    assert bad.status_code == 422


def test_delete_account_removes_user_and_blocks_me(client, db_session):
    tokens = register_with_invite(
        client, db_session, email="del-user@example.com", username="del_user"
    )
    me = client.get("/api/v1/auth/me", headers=_auth(tokens))
    assert me.status_code == 200
    user_id = me.json()["id"]

    deleted = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_auth(tokens),
        json={"confirm": "DELETE"},
    )
    assert deleted.status_code == 204, deleted.text

    gone = db_session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    assert gone is None
    profile = db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one_or_none()
    assert profile is None

    me_after = client.get("/api/v1/auth/me", headers=_auth(tokens))
    assert me_after.status_code == 401
