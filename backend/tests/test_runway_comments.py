"""Runway comments: list + post with author username."""

from __future__ import annotations

import uuid

from app.models.user import User
from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _add_job, _auth, _store_image


def test_circle_look_comments_include_username(client, db_session):
    peri = register_with_invite(client, db_session, "cmt_peri@example.com", "cmtPeri")
    yaniv = register_with_invite(client, db_session, "cmt_yaniv@example.com", "cmtYaniv")

    peri_user = db_session.query(User).filter(User.email == "cmt_peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "cmt_yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    me = client.get("/api/v1/auth/me", headers=_auth(yaniv)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="comment look",
    )
    published = client.post(f"/api/v1/looks/{job.id}/publish", headers=_auth(yaniv))
    assert published.status_code == 200, published.text
    item_id = published.json()["runway_item_id"]

    empty = client.get(f"/api/v1/gallery/{item_id}/comments", headers=_auth(peri))
    assert empty.status_code == 200, empty.text
    assert empty.json() == []

    posted = client.post(
        f"/api/v1/gallery/{item_id}/comments",
        headers=_auth(peri),
        json={"body": "  Love the drape  "},
    )
    assert posted.status_code == 201, posted.text
    body = posted.json()
    assert body["body"] == "Love the drape"
    assert body["username"] == "cmtPeri"
    assert str(body["user_id"]) == str(peri_user.id)

    listed = client.get(f"/api/v1/gallery/{item_id}/comments", headers=_auth(yaniv))
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["username"] == "cmtPeri"
    assert rows[0]["body"] == "Love the drape"
