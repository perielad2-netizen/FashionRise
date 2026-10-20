"""WEB-V3A: saved-design envelopes coexist with the singleton Studio working draft.

Saved designs are ordinary private rows whose top-level design_data.schema is
"fashionrise.saved_design.v1" and whose metadata has no draftKind. These tests prove the
existing backend rules treat them as non-Studio rows: no reconciliation, no revision
checks, owner-private reads, and the working draft is never touched.
"""

from __future__ import annotations

from app.models.garment_design import GarmentDesign
from app.services.design_service import _is_studio_working_draft, find_studio_working_draft
from tests.test_studio_draft_concurrency import _auth, _register, _studio_payload


def _saved_payload(save_request_id: str, *, title: str = "Evening gown", nested_schema: str | None = None) -> dict:
    snapshot: dict = {
        "strokes": [
            {"id": "s1", "tool": "draw", "points": [1, 2, 0.5, 3, 4, 0.6], "color": "#1C1C1E", "size": 2, "opacity": 1}
        ],
        "model": "female",
        "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
        "dimmed": False,
    }
    if nested_schema:
        snapshot["schema"] = nested_schema
        snapshot["clientRevision"] = 99
    return {
        "title": title,
        "description": "Private FashionRise saved design",
        "garment_category": "studio",
        "template_id": None,
        "material_id": None,
        "color_palette_id": None,
        "design_data": {
            "schema": "fashionrise.saved_design.v1",
            "saveRequestId": save_request_id,
            "savedAt": "2026-10-20T10:00:00.000Z",
            "sourceRevision": 1,
            "snapshot": snapshot,
        },
        "metadata": {
            "designKind": "saved_design",
            "envelope": "fashionrise.saved_design.v1",
            "saveRequestId": save_request_id,
            "savedAt": "2026-10-20T10:00:00.000Z",
            "model": "female",
            "strokeCount": 1,
        },
        "visibility": "private",
        "status": "draft",
    }


def test_saved_designs_never_reconcile_with_the_working_draft(client, db_session):
    tokens = _register(client, "v3a_owner@example.com", "v3a_owner")
    headers = _auth(tokens["access_token"])

    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(3, stroke_id="w1"))
    assert draft.status_code == 201, draft.text
    draft_body = draft.json()

    first = client.post("/api/v1/designs", headers=headers, json=_saved_payload("req-1"))
    second = client.post("/api/v1/designs", headers=headers, json=_saved_payload("req-2", title="Coat"))
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    ids = {draft_body["id"], first.json()["id"], second.json()["id"]}
    assert len(ids) == 3

    # Saved rows are stored exactly as sent, not merged into the draft.
    assert first.json()["design_data"]["schema"] == "fashionrise.saved_design.v1"
    assert "draftKind" not in first.json()["metadata"]
    assert first.json()["visibility"] == "private"

    # Working draft is unchanged: same revision, same content.
    current = client.get(f"/api/v1/designs/{draft_body['id']}", headers=headers).json()
    assert current["design_data"] == draft_body["design_data"]
    assert current["design_data"]["clientRevision"] == 3

    mine = client.get("/api/v1/designs/my", headers=headers).json()
    studio_rows = [d for d in mine if d["metadata"].get("draftKind") == "studio_working_draft"]
    assert [d["id"] for d in studio_rows] == [draft_body["id"]]

    rows = db_session.query(GarmentDesign).filter(GarmentDesign.id.in_(list(ids))).all()
    flags = {str(r.id): _is_studio_working_draft(r) for r in rows}
    assert flags[draft_body["id"]] is True
    assert flags[first.json()["id"]] is False
    assert flags[second.json()["id"]] is False


def test_nested_snapshot_schema_is_ignored_by_singleton_detection(client, db_session):
    tokens = _register(client, "v3a_nested@example.com", "v3a_nested")
    headers = _auth(tokens["access_token"])
    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(2, stroke_id="w1")).json()

    nested = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_saved_payload("req-n", nested_schema="fashionrise.studio.draft.v1"),
    )
    assert nested.status_code == 201, nested.text
    assert nested.json()["id"] != draft["id"]

    from app.models.user import User

    user = db_session.query(User).filter(User.email == "v3a_nested@example.com").one()
    found = find_studio_working_draft(db_session, user)
    assert found is not None and str(found.id) == draft["id"]


def test_working_draft_rules_still_hold_after_saved_designs_exist(client):
    tokens = _register(client, "v3a_rules@example.com", "v3a_rules")
    headers = _auth(tokens["access_token"])
    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="w1")).json()
    client.post("/api/v1/designs", headers=headers, json=_saved_payload("req-a"))

    # Identical create retry still reconciles to the one draft.
    retry = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="w1"))
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == draft["id"]

    # Equal revision with different content is still a 409.
    clash = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="other"))
    assert clash.status_code == 409, clash.text

    # Studio PUT still requires expected_revision, and a stale token is still rejected.
    missing = client.put(f"/api/v1/designs/{draft['id']}", headers=headers, json=_studio_payload(2, stroke_id="w2"))
    assert missing.status_code == 409
    stale = client.put(
        f"/api/v1/designs/{draft['id']}",
        headers=headers,
        json={**_studio_payload(2, stroke_id="w2"), "expected_revision": 0},
    )
    assert stale.status_code == 409

    # Reopen = forward OCC write of saved content into the same singleton row.
    reopened = client.put(
        f"/api/v1/designs/{draft['id']}",
        headers=headers,
        json={**_studio_payload(2, model="male", stroke_id="s1"), "expected_revision": 1},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] == draft["id"]
    assert reopened.json()["design_data"]["clientRevision"] == 2

    # A lost-response retry of the same reopen write is rejected rather than applied twice.
    again = client.put(
        f"/api/v1/designs/{draft['id']}",
        headers=headers,
        json={**_studio_payload(2, model="male", stroke_id="s1"), "expected_revision": 1},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["payload"]["design"]["design_data"]["model"] == "male"

    mine = client.get("/api/v1/designs/my", headers=headers).json()
    assert len([d for d in mine if d["metadata"].get("draftKind") == "studio_working_draft"]) == 1
    assert len([d for d in mine if d["design_data"].get("schema") == "fashionrise.saved_design.v1"]) == 1


def test_saved_designs_are_owner_private(client):
    owner = _auth(_register(client, "v3a_a@example.com", "v3a_a")["access_token"])
    other = _auth(_register(client, "v3a_b@example.com", "v3a_b")["access_token"])
    saved = client.post("/api/v1/designs", headers=owner, json=_saved_payload("req-private")).json()

    assert client.get(f"/api/v1/designs/{saved['id']}", headers=other).status_code == 404
    assert all(d["id"] != saved["id"] for d in client.get("/api/v1/designs/my", headers=other).json())
    assert client.get(f"/api/v1/designs/{saved['id']}").status_code in (401, 403, 404)
    assert client.delete(f"/api/v1/designs/{saved['id']}", headers=other).status_code in (403, 404)
    assert client.get(f"/api/v1/designs/{saved['id']}", headers=owner).status_code == 200
