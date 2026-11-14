"""V2-0014 / V2-0015 / V2-0018 / V2-0019 / V2-0020 — Batch A synthetic regressions.

Uses only synthetic fixtures. Never mutates real user designs.
"""

from __future__ import annotations

from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth
from tests.test_saved_design_isolation import _saved_payload


SQLISH = "SELECT * FROM users; DROP TABLE garment_designs;--"


def test_v2_0018_design_title_stores_sql_like_text_literally(client, db_session):
    tokens = register_with_invite(client, db_session, "qa.v2.title@example.com", "qaTitle")
    headers = _auth(tokens)
    payload = _saved_payload("qa-v2-0018-req-1", title=SQLISH)
    created = client.post("/api/v1/designs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["title"] == SQLISH

    listed = client.get("/api/v1/designs/my", headers=headers)
    assert listed.status_code == 200, listed.text
    titles = [row["title"] for row in listed.json()]
    assert SQLISH in titles


def test_v2_0014_0015_distinct_titles_and_no_title_overwrite(client, db_session):
    """Same display title must not collapse rows; each saveRequestId is its own design."""
    tokens = register_with_invite(client, db_session, "qa.v2.names@example.com", "qaNames")
    headers = _auth(tokens)

    first = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_saved_payload("qa-v2-name-req-a", title="Evening look"),
    )
    second = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_saved_payload("qa-v2-name-req-b", title="Evening look"),
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["title"] == "Evening look"
    assert second.json()["title"] == "Evening look"

    # Idempotent replay of the first request returns the same row, not a new overwrite of second.
    replay = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_saved_payload("qa-v2-name-req-a", title="Evening look"),
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["id"] != second.json()["id"]


def test_v2_0019_runway_comment_stores_sql_like_text_literally(client, db_session):
    owner = register_with_invite(client, db_session, "qa.v2.owner@example.com", "qaOwner")
    friend = register_with_invite(client, db_session, "qa.v2.friend@example.com", "qaFriend")
    from app.models.user import User
    from app.services.friendship_service import ensure_accepted_friends
    from tests.test_looks_api import _add_job, _store_image
    import uuid

    owner_user = db_session.query(User).filter(User.email == "qa.v2.owner@example.com").one()
    friend_user = db_session.query(User).filter(User.email == "qa.v2.friend@example.com").one()
    ensure_accepted_friends(db_session, owner_user, friend_user)

    me = client.get("/api/v1/auth/me", headers=_auth(owner)).json()
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image(), summary="qa")
    from tests.runway_publish_helpers import runway_publish_body

    published = client.post(
        f"/api/v1/looks/{job.id}/publish",
        headers=_auth(owner),
        json=runway_publish_body(),
    )
    assert published.status_code == 200, published.text
    item_id = published.json()["runway_item_id"]

    commented = client.post(
        f"/api/v1/gallery/{item_id}/comments",
        headers=_auth(friend),
        json={"body": SQLISH},
    )
    assert commented.status_code == 201, commented.text
    assert commented.json()["body"] == SQLISH

    listed = client.get(f"/api/v1/gallery/{item_id}/comments", headers=_auth(friend))
    assert listed.status_code == 200, listed.text
    assert any(row.get("body") == SQLISH for row in listed.json())


def test_v2_0020_friend_lookup_treats_sql_like_username_literally(client, db_session):
    tokens = register_with_invite(client, db_session, "qa.v2.search@example.com", "qaSearch")
    # Exact username match only — SQL string must not match or error.
    res = client.post(
        "/api/v1/friends/request",
        headers=_auth(tokens),
        json={"username": SQLISH},
    )
    assert res.status_code == 404, res.text
    # Server must not 500 or leak SQL errors.
    assert "Traceback" not in res.text
    assert "psycopg" not in res.text.lower()
