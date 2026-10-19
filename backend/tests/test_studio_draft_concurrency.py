"""Live FastAPI + Postgres tests for Studio draft concurrency and reconcile."""

from __future__ import annotations


def _register(client, email: str, username: str, password: str = "StrongPass123!") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password, "display_name": username},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _studio_payload(client_revision: int, *, model: str = "female", stroke_id: str | None = None) -> dict:
    strokes = []
    if stroke_id:
        strokes.append(
            {
                "id": stroke_id,
                "tool": "draw",
                "points": [1, 2, 0.5, 3, 4, 0.6],
                "color": "#1C1C1E",
                "size": 2,
                "opacity": 1,
            }
        )
    design_data = {
        "schema": "fashionrise.studio.draft.v1",
        "strokes": strokes,
        "model": model,
        "customReferenceUrl": None,
        "customReferenceKey": None,
        "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
        "dimmed": False,
        "clientRevision": client_revision,
        "updatedAt": "2026-10-19T00:00:00.000Z",
    }
    return {
        "title": "Studio working draft",
        "description": "Private FashionRise Creator Studio draft",
        "garment_category": "studio",
        "template_id": None,
        "material_id": None,
        "color_palette_id": None,
        "design_data": design_data,
        "metadata": {
            "draftKind": "studio_working_draft",
            "schema": "fashionrise.studio.draft.v1",
            "clientRevision": client_revision,
            "updatedAt": design_data["updatedAt"],
        },
        "visibility": "private",
        "status": "draft",
    }


def test_stale_expected_revision_returns_409_and_preserves_server_copy(client):
    tokens = _register(client, "studio_a@example.com", "studio_a")
    headers = _auth(tokens["access_token"])

    created = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="s1"))
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    # Tab B advances the draft.
    ok = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, model="male", stroke_id="s2"),
            "expected_revision": 1,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["design_data"]["clientRevision"] == 2
    assert ok.json()["design_data"]["model"] == "male"

    # Tab A retries with stale expected_revision=1 — must 409, not overwrite.
    stale = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(3, model="blank", stroke_id="s-stale"),
            "expected_revision": 1,
        },
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["code"] == "conflict"
    assert detail["payload"]["expected_revision"] == 1
    assert detail["payload"]["current_revision"] == 2
    assert detail["payload"]["design"]["design_data"]["model"] == "male"
    assert detail["payload"]["design"]["design_data"]["strokes"][0]["id"] == "s2"

    # Server copy unchanged.
    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["design_data"]["clientRevision"] == 2
    assert got.json()["design_data"]["model"] == "male"


def test_update_without_expected_revision_remains_compatible(client):
    tokens = _register(client, "legacy@example.com", "legacy_user")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": "Legacy look",
            "description": None,
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {"neckline": "V"},
            "metadata": {"source": "pytest"},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={"design_data": {"neckline": "Boat"}, "title": "Legacy look v2"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["design_data"]["neckline"] == "Boat"
    assert updated.json()["title"] == "Legacy look v2"


def test_duplicate_studio_create_reconciles_to_one_draft(client):
    tokens = _register(client, "recon@example.com", "recon_user")
    headers = _auth(tokens["access_token"])

    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="a"))
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    # Simulate lost response retry: second POST must not create a second working draft.
    second = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(2, model="male", stroke_id="b"),
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first_id

    mine = client.get("/api/v1/designs/my", headers=headers)
    assert mine.status_code == 200
    studio = [
        d
        for d in mine.json()
        if d.get("metadata", {}).get("draftKind") == "studio_working_draft"
        or (d.get("design_data") or {}).get("schema") == "fashionrise.studio.draft.v1"
    ]
    assert len(studio) == 1
    assert studio[0]["design_data"]["clientRevision"] == 2
    assert studio[0]["design_data"]["strokes"][0]["id"] == "b"


def test_stale_create_retry_does_not_clobber_newer_revision(client):
    tokens = _register(client, "stale_create@example.com", "stale_create")
    headers = _auth(tokens["access_token"])

    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="a"))
    assert first.status_code == 201, first.text
    design_id = first.json()["id"]

    advanced = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(5, model="blank", stroke_id="newer"),
            "expected_revision": 1,
        },
    )
    assert advanced.status_code == 200, advanced.text

    # Lost older create retry with revision 2 must not overwrite revision 5.
    retry = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(2, model="female", stroke_id="stale"),
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == design_id
    assert retry.json()["design_data"]["clientRevision"] == 5
    assert retry.json()["design_data"]["strokes"][0]["id"] == "newer"


def test_matching_expected_revision_allows_update(client):
    tokens = _register(client, "ok_rev@example.com", "ok_rev")
    headers = _auth(tokens["access_token"])

    created = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="s1"))
    design_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, model="male", stroke_id="s2"),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["design_data"]["clientRevision"] == 2
