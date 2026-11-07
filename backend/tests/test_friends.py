"""Runway Friends — request / accept / list."""

from __future__ import annotations

from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_request_accept_lists_friend(client, db_session):
    peri = register_with_invite(client, db_session, "peri_friends@example.com", "PeriFriends")
    yaniv = register_with_invite(client, db_session, "yaniv_friends@example.com", "yanivFriends")

    req = client.post(
        "/api/v1/friends/request",
        headers=_auth(peri),
        json={"username": "yanivFriends"},
    )
    assert req.status_code == 201, req.text
    body = req.json()
    assert body["status"] == "pending"
    assert body["friend"]["username"] == "yanivFriends"
    friendship_id = body["id"]

    pending = client.get("/api/v1/friends/requests", headers=_auth(yaniv))
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    assert pending.json()[0]["friend"]["username"] == "PeriFriends"

    accepted = client.post(
        f"/api/v1/friends/{friendship_id}/accept",
        headers=_auth(yaniv),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    peri_friends = client.get("/api/v1/friends", headers=_auth(peri))
    yaniv_friends = client.get("/api/v1/friends", headers=_auth(yaniv))
    assert peri_friends.status_code == 200
    assert yaniv_friends.status_code == 200
    assert peri_friends.json()[0]["friend"]["username"] == "yanivFriends"
    assert yaniv_friends.json()[0]["friend"]["username"] == "PeriFriends"

    # Idempotent conflict when already friends.
    again = client.post(
        "/api/v1/friends/request",
        headers=_auth(peri),
        json={"username": "yanivFriends"},
    )
    assert again.status_code == 409


def test_cannot_friend_self(client, db_session):
    tokens = register_with_invite(client, db_session, "solo@example.com", "SoloFriend")
    res = client.post(
        "/api/v1/friends/request",
        headers=_auth(tokens),
        json={"username": "SoloFriend"},
    )
    assert res.status_code == 403
