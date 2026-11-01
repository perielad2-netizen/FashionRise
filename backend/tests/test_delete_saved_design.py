"""WEB-V3B / Issue #17: saved-only owner delete for fashionrise.saved_design.v1/v2.

Protects the Studio working draft and cross-account isolation. Generic
DELETE /designs/{id} remains available for other consumers.
"""

from __future__ import annotations

import uuid

from app.models.garment_design import GarmentDesign
from app.services.design_service import _is_studio_working_draft
from tests.test_saved_design_isolation import _saved_payload
from tests.test_studio_draft_concurrency import _auth, _register, _studio_payload
from tests.test_studio_draft_v2_persistence import _saved_v2_payload


def test_owner_can_delete_saved_v1_and_v2(client, db_session):
    tokens = _register(client, db_session, "del_owner@example.com", "del_owner")
    headers = _auth(tokens["access_token"])

    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="w1"))
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    v1 = client.post("/api/v1/designs", headers=headers, json=_saved_payload("del-v1", title="V1 gown"))
    v2 = client.post("/api/v1/designs", headers=headers, json=_saved_v2_payload("del-v2"))
    assert v1.status_code == 201, v1.text
    assert v2.status_code == 201, v2.text
    v1_id = v1.json()["id"]
    v2_id = v2.json()["id"]

    assert client.delete(f"/api/v1/designs/saved/{v1_id}", headers=headers).status_code == 204
    assert client.delete(f"/api/v1/designs/saved/{v2_id}", headers=headers).status_code == 204

    assert client.get(f"/api/v1/designs/{v1_id}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/designs/{v2_id}", headers=headers).status_code == 404

    # Working draft untouched
    still = client.get(f"/api/v1/designs/{draft_id}", headers=headers)
    assert still.status_code == 200
    assert still.json()["design_data"]["clientRevision"] == 1
    row = db_session.get(GarmentDesign, uuid.UUID(draft_id))
    assert row is not None
    assert _is_studio_working_draft(row) is True

    mine = client.get("/api/v1/designs/my", headers=headers).json()
    ids = {d["id"] for d in mine}
    assert draft_id in ids
    assert v1_id not in ids
    assert v2_id not in ids


def test_cross_account_cannot_delete_saved_design(client, db_session):
    owner = _register(client, db_session, "del_owner2@example.com", "del_owner2")
    other = _register(client, db_session, "del_other@example.com", "del_other")
    owner_h = _auth(owner["access_token"])
    other_h = _auth(other["access_token"])

    saved = client.post("/api/v1/designs", headers=owner_h, json=_saved_payload("del-xuser"))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]

    resp = client.delete(f"/api/v1/designs/saved/{saved_id}", headers=other_h)
    assert resp.status_code == 404

    assert client.get(f"/api/v1/designs/{saved_id}", headers=owner_h).status_code == 200


def test_working_draft_cannot_be_deleted_via_saved_route(client, db_session):
    tokens = _register(client, db_session, "del_draft@example.com", "del_draft")
    headers = _auth(tokens["access_token"])

    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(2, stroke_id="w1"))
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    resp = client.delete(f"/api/v1/designs/saved/{draft_id}", headers=headers)
    assert resp.status_code == 422
    assert "saved_design" in resp.json()["detail"]["message"]

    assert client.get(f"/api/v1/designs/{draft_id}", headers=headers).status_code == 200


def test_nonexistent_saved_delete_is_404(client, db_session):
    tokens = _register(client, db_session, "del_missing@example.com", "del_missing")
    headers = _auth(tokens["access_token"])
    missing = uuid.uuid4()
    assert client.delete(f"/api/v1/designs/saved/{missing}", headers=headers).status_code == 404


def test_unknown_schema_and_damaged_rows_rejected(client, db_session):
    tokens = _register(client, db_session, "del_damaged@example.com", "del_damaged")
    headers = _auth(tokens["access_token"])
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]

    # Unknown saved family version (not creatable via API) — insert damaged row directly.
    unknown = GarmentDesign(
        user_id=uuid.UUID(user_id),
        title="Future schema",
        description="",
        garment_category="studio",
        design_data={
            "schema": "fashionrise.saved_design.v9",
            "saveRequestId": "bad-v9",
            "savedAt": "2026-10-26T00:00:00.000Z",
            "sourceRevision": 1,
            "snapshot": {"strokes": [], "model": "female", "brush": {}, "dimmed": False},
        },
        metadata_={"designKind": "saved_design", "envelope": "fashionrise.saved_design.v9"},
        visibility="private",
        status="draft",
    )
    # Generic design without saved schema
    generic = GarmentDesign(
        user_id=uuid.UUID(user_id),
        title="Legacy look",
        description="",
        garment_category="dress",
        design_data={"colors": ["#fff"]},
        metadata_={},
        visibility="private",
        status="draft",
    )
    # Ambiguous: saved Kind marker but studio schema
    ambiguous = GarmentDesign(
        user_id=uuid.UUID(user_id),
        title="Ambiguous",
        description="",
        garment_category="studio",
        design_data={
            "schema": "fashionrise.studio.draft.v1",
            "clientRevision": 1,
            "strokes": [],
            "model": "female",
            "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
            "dimmed": False,
        },
        metadata_={"designKind": "saved_design", "draftKind": "studio_working_draft"},
        visibility="private",
        status="draft",
    )
    db_session.add_all([unknown, generic, ambiguous])
    db_session.commit()

    for row in (unknown, generic, ambiguous):
        resp = client.delete(f"/api/v1/designs/saved/{row.id}", headers=headers)
        assert resp.status_code == 422, (row.title, resp.text)
        assert db_session.get(GarmentDesign, row.id) is not None


def test_generic_delete_still_works_for_owner(client, db_session):
    """Preserve generic API consumers — DELETE /designs/{id} unchanged."""
    tokens = _register(client, db_session, "del_generic@example.com", "del_generic")
    headers = _auth(tokens["access_token"])
    saved = client.post("/api/v1/designs", headers=headers, json=_saved_payload("del-generic"))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]
    assert client.delete(f"/api/v1/designs/{saved_id}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/designs/{saved_id}", headers=headers).status_code == 404


def test_delete_one_saved_leaves_siblings(client, db_session):
    tokens = _register(client, db_session, "del_sib@example.com", "del_sib")
    headers = _auth(tokens["access_token"])
    a = client.post("/api/v1/designs", headers=headers, json=_saved_payload("sib-a", title="Keep"))
    b = client.post("/api/v1/designs", headers=headers, json=_saved_payload("sib-b", title="Drop"))
    assert a.status_code == 201 and b.status_code == 201
    keep_id, drop_id = a.json()["id"], b.json()["id"]

    assert client.delete(f"/api/v1/designs/saved/{drop_id}", headers=headers).status_code == 204
    mine = client.get("/api/v1/designs/my", headers=headers).json()
    ids = {d["id"] for d in mine}
    assert keep_id in ids
    assert drop_id not in ids
