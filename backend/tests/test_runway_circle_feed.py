"""Runway circle feed = friends + own looks; top10 is global highlight."""

from __future__ import annotations

import uuid

from app.models.user import User
from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _add_job, _auth, _store_image


def test_circle_hides_strangers_and_top10_is_global(client, db_session):
    peri = register_with_invite(client, db_session, "circle_peri@example.com", "circlePeri")
    yaniv = register_with_invite(client, db_session, "circle_yaniv@example.com", "circleYaniv")
    stranger = register_with_invite(
        client, db_session, "circle_stranger@example.com", "circleStranger"
    )

    peri_user = db_session.query(User).filter(User.email == "circle_peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "circle_yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    def publish(tokens, label: str) -> str:
        me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
        job = _add_job(
            db_session,
            user_id=uuid.UUID(me["id"]),
            image_url=_store_image(),
            summary=label,
        )
        res = client.post(f"/api/v1/looks/{job.id}/publish", headers=_auth(tokens))
        assert res.status_code == 200, res.text
        return res.json()["runway_item_id"]

    peri_item = publish(peri, "peri look")
    yaniv_item = publish(yaniv, "yaniv look")
    stranger_item = publish(stranger, "stranger look")

    circle = client.get("/api/v1/gallery?sort=circle", headers=_auth(peri))
    assert circle.status_code == 200, circle.text
    ids = {row["id"] for row in circle.json()}
    assert peri_item in ids
    assert yaniv_item in ids
    assert stranger_item not in ids

    top = client.get("/api/v1/gallery?sort=top10", headers=_auth(peri))
    assert top.status_code == 200, top.text
    assert len(top.json()) <= 10
    top_ids = {row["id"] for row in top.json()}
    assert stranger_item in top_ids or peri_item in top_ids or yaniv_item in top_ids
