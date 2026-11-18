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


def test_search_contains_and_reject(client, db_session):
    peri = register_with_invite(client, db_session, "peri_search@example.com", "PeriSearch")
    maya = register_with_invite(client, db_session, "maya_rose@example.com", "MayaRose")

    hits = client.get("/api/v1/friends/search", headers=_auth(peri), params={"q": "maya"})
    assert hits.status_code == 200, hits.text
    body = hits.json()
    assert len(body) == 1
    assert body[0]["user"]["username"] == "MayaRose"
    assert body[0]["relationship"] == "none"

    req = client.post(
        "/api/v1/friends/request",
        headers=_auth(peri),
        json={"user_id": body[0]["user"]["user_id"]},
    )
    assert req.status_code == 201, req.text
    friendship_id = req.json()["id"]

    pending_out = client.get(
        "/api/v1/friends/search", headers=_auth(peri), params={"q": "Maya"}
    )
    assert pending_out.status_code == 200
    assert pending_out.json()[0]["relationship"] == "pending_out"

    pending = client.get("/api/v1/friends/requests", headers=_auth(maya))
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    assert pending.json()[0]["friend"]["username"] == "PeriSearch"

    rejected = client.post(
        f"/api/v1/friends/{friendship_id}/reject",
        headers=_auth(maya),
    )
    assert rejected.status_code == 204, rejected.text

    after = client.get("/api/v1/friends/requests", headers=_auth(maya))
    assert after.json() == []

    # Requester cannot reject their own outbound request.
    again = client.post(
        "/api/v1/friends/request",
        headers=_auth(peri),
        json={"username": "MayaRose"},
    )
    assert again.status_code == 201
    bad = client.post(
        f"/api/v1/friends/{again.json()['id']}/reject",
        headers=_auth(peri),
    )
    assert bad.status_code == 403
