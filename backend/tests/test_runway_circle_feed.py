"""Friends circle = one best look per friend; never the viewer's own looks."""

from __future__ import annotations

import uuid

from app.models.gallery_item import GalleryItem
from app.models.user import User
from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite
from tests.runway_publish_helpers import runway_publish_body
from tests.test_looks_api import _add_job, _auth, _store_image


def _publish(client, db_session, tokens, label: str) -> str:
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=label,
    )
    res = client.post(
        f"/api/v1/looks/{job.id}/publish",
        headers=_auth(tokens),
        json=runway_publish_body(),
    )
    assert res.status_code == 200, res.text
    return res.json()["runway_item_id"]


def test_circle_excludes_self_and_strangers(client, db_session):
    peri = register_with_invite(client, db_session, "circle_peri@example.com", "circlePeri")
    yaniv = register_with_invite(client, db_session, "circle_yaniv@example.com", "circleYaniv")
    stranger = register_with_invite(
        client, db_session, "circle_stranger@example.com", "circleStranger"
    )

    peri_user = db_session.query(User).filter(User.email == "circle_peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "circle_yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    peri_item = _publish(client, db_session, peri, "peri look")
    yaniv_item = _publish(client, db_session, yaniv, "yaniv look")
    stranger_item = _publish(client, db_session, stranger, "stranger look")

    circle = client.get("/api/v1/gallery?sort=circle", headers=_auth(peri))
    assert circle.status_code == 200, circle.text
    ids = {row["id"] for row in circle.json()}
    assert peri_item not in ids  # never show yourself in Friends circle
    assert yaniv_item in ids
    assert stranger_item not in ids

    top = client.get("/api/v1/gallery?sort=top10", headers=_auth(peri))
    assert top.status_code == 200, top.text
    assert len(top.json()) <= 10
    top_ids = {row["id"] for row in top.json()}
    assert stranger_item in top_ids or peri_item in top_ids or yaniv_item in top_ids


def test_circle_one_best_look_per_friend(client, db_session):
    peri = register_with_invite(client, db_session, "best_peri@example.com", "bestPeri")
    yaniv = register_with_invite(client, db_session, "best_yaniv@example.com", "bestYaniv")
    peri_user = db_session.query(User).filter(User.email == "best_peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "best_yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    weak = _publish(client, db_session, yaniv, "yaniv weak")
    strong = _publish(client, db_session, yaniv, "yaniv strong")
    # Boost the "strong" look so Worldwide-style ranking picks it.
    strong_row = db_session.get(GalleryItem, uuid.UUID(strong))
    assert strong_row is not None
    strong_row.likes_count = 12
    strong_row.rating_average = 9.0
    strong_row.rating_count = 3
    db_session.commit()

    circle = client.get("/api/v1/gallery?sort=circle", headers=_auth(peri))
    assert circle.status_code == 200, circle.text
    rows = circle.json()
    yaniv_rows = [r for r in rows if r["username"] == "bestYaniv"]
    assert len(yaniv_rows) == 1
    assert yaniv_rows[0]["id"] == strong
    assert weak not in {r["id"] for r in rows}
