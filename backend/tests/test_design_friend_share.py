"""Share saved design with accepted friend — pending approval then copy + grants."""

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
            "envelope": "fashionrise.saved_design.v2",
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


def test_share_requires_accept_before_my_designs(client, db_session):
    peri = register_with_invite(client, db_session, "peri_share@example.com", "PeriShare")
    yaniv = register_with_invite(client, db_session, "yaniv_share@example.com", "YanivShare")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriShare").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivShare").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

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
    assert payload["received_design"] is None
    assert payload["transfer"]["status"] == "pending"
    transfer_id = payload["transfer"]["id"]

    # Not in My Designs until accepted.
    mine_before = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    assert mine_before.status_code == 200
    assert all("Collab dress" not in (row.get("title") or "") for row in mine_before.json())

    # Fabric not granted yet.
    fabrics_before = client.get("/api/v1/fabrics", headers=_auth(yaniv))
    assert fabric_id not in {row["id"] for row in fabrics_before.json()}

    inbox = client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv))
    assert inbox.status_code == 200, inbox.text
    assert len(inbox.json()) == 1
    assert inbox.json()[0]["id"] == transfer_id
    assert inbox.json()[0]["from_username"] == "PeriShare"

    accepted = client.post(
        f"/api/v1/designs/shares/{transfer_id}/accept",
        headers=_auth(yaniv),
    )
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    assert accepted_body["transfer"]["status"] == "accepted"
    assert accepted_body["received_design"]["user_id"] == str(yaniv_user.id)
    assert "From PeriShare:" in accepted_body["received_design"]["title"]
    assert accepted_body["transfer"]["fabrics_granted"] >= 1

    mine = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    ids = {row["id"] for row in mine.json()}
    assert accepted_body["received_design"]["id"] in ids

    fabrics = client.get("/api/v1/fabrics", headers=_auth(yaniv))
    assert fabric_id in {row["id"] for row in fabrics.json()}
    img = client.get(f"/api/v1/fabrics/{fabric_id}/image", headers=_auth(yaniv))
    assert img.status_code == 200, img.text

    empty = client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv))
    assert empty.json() == []


def test_share_reject_keeps_out_of_my_designs(client, db_session):
    peri = register_with_invite(client, db_session, "peri_reject@example.com", "PeriReject")
    yaniv = register_with_invite(client, db_session, "yaniv_reject@example.com", "YanivReject")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriReject").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivReject").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="No thanks")
    share = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    transfer_id = share.json()["transfer"]["id"]
    rejected = client.post(
        f"/api/v1/designs/shares/{transfer_id}/reject",
        headers=_auth(yaniv),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    mine = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    assert all("No thanks" not in (row.get("title") or "") for row in mine.json())
    assert client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv)).json() == []


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


def test_share_back_and_forth_with_approval(client, db_session):
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
    tid = first.json()["transfer"]["id"]
    accepted = client.post(f"/api/v1/designs/shares/{tid}/accept", headers=_auth(yaniv))
    assert accepted.status_code == 200, accepted.text
    received_id = accepted.json()["received_design"]["id"]

    back = client.post(
        f"/api/v1/designs/{received_id}/share",
        headers=_auth(yaniv),
        json={"friend_user_id": str(peri_user.id), "note": "Back to you"},
    )
    assert back.status_code == 201, back.text
    assert back.json()["transfer"]["status"] == "pending"
    back_id = back.json()["transfer"]["id"]
    peri_accept = client.post(f"/api/v1/designs/shares/{back_id}/accept", headers=_auth(peri))
    assert peri_accept.status_code == 200, peri_accept.text
    assert peri_accept.json()["received_design"]["user_id"] == str(peri_user.id)
    assert "From YanivPong:" in peri_accept.json()["received_design"]["title"]


def test_recipient_can_delete_copy_without_touching_source(client, db_session):
    """Recipient deletes their copy only; sender's original stays."""
    peri = register_with_invite(client, db_session, "peri_delcopy@example.com", "PeriDelCopy")
    yaniv = register_with_invite(client, db_session, "yaniv_delcopy@example.com", "YanivDelCopy")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriDelCopy").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivDelCopy").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="Keep mine")
    source_id = design["id"]
    share = client.post(
        f"/api/v1/designs/{source_id}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    assert share.status_code == 201, share.text
    tid = share.json()["transfer"]["id"]
    accepted = client.post(f"/api/v1/designs/shares/{tid}/accept", headers=_auth(yaniv))
    assert accepted.status_code == 200, accepted.text
    copy_id = accepted.json()["received_design"]["id"]
    assert accepted.json()["received_design"]["metadata"]["envelope"] == "fashionrise.saved_design.v2"
    assert accepted.json()["received_design"]["metadata"]["receivedViaShare"] is True

    deleted = client.delete(f"/api/v1/designs/saved/{copy_id}", headers=_auth(yaniv))
    assert deleted.status_code == 204, deleted.text

    assert client.get(f"/api/v1/designs/{copy_id}", headers=_auth(yaniv)).status_code == 404
    still = client.get(f"/api/v1/designs/{source_id}", headers=_auth(peri))
    assert still.status_code == 200, still.text
    assert still.json()["title"] == "Keep mine"


def test_legacy_boolean_envelope_share_copy_can_be_deleted(client, db_session):
    """Early share copies wrote metadata.envelope=True; delete must still work."""
    from app.models.garment_design import GarmentDesign
    from app.services.design_service import SAVED_DESIGN_V2

    peri = register_with_invite(client, db_session, "peri_legacy@example.com", "PeriLegacy")
    headers = _auth(peri)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    save_id = str(uuid.uuid4())
    row = GarmentDesign(
        user_id=uuid.UUID(me["id"]),
        title="Legacy share copy",
        garment_category="dress",
        visibility="private",
        status="draft",
        metadata_={
            "designKind": "saved_design",
            "envelope": True,
            "receivedViaShare": True,
            "saveRequestId": save_id,
        },
        design_data={
            "schema": SAVED_DESIGN_V2,
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
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    deleted = client.delete(f"/api/v1/designs/saved/{row.id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/designs/{row.id}", headers=headers).status_code == 404
