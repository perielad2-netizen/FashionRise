"""Share saved design with accepted friend — copy + fabric/model grants."""

from __future__ import annotations

import uuid

from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _save_design(client, tokens, *, title: str = "Shared look") -> dict:
    save_id = str(uuid.uuid4())
    body = {
        "title": title,
        "garment_category": "dress",
        "visibility": "private",
        "status": "draft",
        "metadata": {
            "designKind": "saved_design",
            "envelope": True,
            "saveRequestId": save_id,
        },
        "design_data": {
            "schema": "fashionrise.saved_design.v2",
            "saveRequestId": save_id,
            "savedAt": "2026-11-22T00:00:00Z",
            "sourceRevision": 1,
            "snapshot": {
                "strokes": [],
                "fills": [],
                "model": "female",
                "brush": {"size": 8, "opacity": 1, "color": "#111111"},
                "dimmed": False,
                "activeSide": "front",
                "back": {"strokes": [], "fills": []},
                "personalCroquisId": None,
                "personalCroquisVersion": None,
            },
        },
    }
    res = client.post("/api/v1/designs", headers=_auth(tokens), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_share_design_with_friend_copies_and_grants(client, db_session):
    peri = register_with_invite(client, db_session, "peri_share@example.com", "PeriShare")
    yaniv = register_with_invite(client, db_session, "yaniv_share@example.com", "YanivShare")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriShare").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivShare").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    # Peri uploads a fabric so share grants it.
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(200, 40, 120)).save(buf, format="PNG")
    buf.seek(0)
    up = client.post(
        "/api/v1/fabrics",
        headers=_auth(peri),
        files={"file": ("tile.png", buf.getvalue(), "image/png")},
        data={"name": "Share Denim"},
    )
    assert up.status_code == 201, up.text
    fabric_id = up.json()["id"]

    design = _save_design(client, peri, title="Collab dress")
    share = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id), "note": "Your turn"},
    )
    assert share.status_code == 201, share.text
    payload = share.json()
    assert payload["received_design"]["user_id"] == str(yaniv_user.id)
    assert payload["transfer"]["fabrics_granted"] >= 1
    assert "From PeriShare:" in payload["received_design"]["title"]
    meta = payload["received_design"]["metadata"]
    assert meta["receivedViaShare"] is True
    assert meta["sharedFromUsername"] == "PeriShare"

    # Friend sees the design in My Designs and can load Peri's fabric image.
    mine = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    assert mine.status_code == 200
    ids = {row["id"] for row in mine.json()}
    assert payload["received_design"]["id"] in ids

    fabrics = client.get("/api/v1/fabrics", headers=_auth(yaniv))
    assert fabrics.status_code == 200
    fabric_ids = {row["id"] for row in fabrics.json()}
    assert fabric_id in fabric_ids

    img = client.get(f"/api/v1/fabrics/{fabric_id}/image", headers=_auth(yaniv))
    assert img.status_code == 200, img.text
    assert img.headers.get("content-type", "").startswith("image/")


def test_share_requires_accepted_friend(client, db_session):
    peri = register_with_invite(client, db_session, "peri_nofriend@example.com", "PeriNoFriend")
    stranger = register_with_invite(client, db_session, "stranger_share@example.com", "StrangerShare")
    from app.models.user import User

    stranger_user = db_session.query(User).filter(User.username == "StrangerShare").one()
    design = _save_design(client, peri)
    res = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(stranger_user.id)},
    )
    assert res.status_code == 403


def test_share_back_and_forth(client, db_session):
    peri = register_with_invite(client, db_session, "peri_ping@example.com", "PeriPing")
    yaniv = register_with_invite(client, db_session, "yaniv_pong@example.com", "YanivPong")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriPing").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivPong").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="Ping")
    first = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    assert first.status_code == 201, first.text
    received_id = first.json()["received_design"]["id"]

    back = client.post(
        f"/api/v1/designs/{received_id}/share",
        headers=_auth(yaniv),
        json={"friend_user_id": str(peri_user.id), "note": "Back to you"},
    )
    assert back.status_code == 201, back.text
    assert back.json()["received_design"]["user_id"] == str(peri_user.id)
    assert "From YanivPong:" in back.json()["received_design"]["title"]
