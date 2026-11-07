"""Runway like + score: list feeds expose liked_by_me / my_score."""

from __future__ import annotations

import uuid

from app.models.user import User
from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _add_job, _auth, _store_image


def test_circle_feed_includes_like_and_score_flags(client, db_session):
    peri = register_with_invite(client, db_session, "score_peri@example.com", "scorePeri")
    yaniv = register_with_invite(client, db_session, "score_yaniv@example.com", "scoreYaniv")

    peri_user = db_session.query(User).filter(User.email == "score_peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "score_yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    me = client.get("/api/v1/auth/me", headers=_auth(yaniv)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="yaniv scored look",
    )
    published = client.post(f"/api/v1/looks/{job.id}/publish", headers=_auth(yaniv))
    assert published.status_code == 200, published.text
    item_id = published.json()["runway_item_id"]

    like = client.post(f"/api/v1/gallery/{item_id}/like", headers=_auth(peri))
    assert like.status_code == 204, like.text

    rate = client.post(
        "/api/v1/ratings",
        headers=_auth(peri),
        json={"gallery_item_id": item_id, "score": 8},
    )
    assert rate.status_code == 200, rate.text

    circle = client.get("/api/v1/gallery?sort=circle", headers=_auth(peri))
    assert circle.status_code == 200, circle.text
    row = next(r for r in circle.json() if r["id"] == item_id)
    assert row["liked_by_me"] is True
    assert row["my_score"] == 8
    assert row["likes_count"] >= 1
    assert row["rating_average"] is not None
    assert float(row["rating_average"]) == 8.0

    top = client.get("/api/v1/gallery?sort=top10", headers=_auth(peri))
    assert top.status_code == 200, top.text
    top_row = next(r for r in top.json() if r["id"] == item_id)
    assert top_row["liked_by_me"] is True
    assert top_row["my_score"] == 8
