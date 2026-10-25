"""WEB-V4J Stage B: draft.v2 / saved_design.v2 fingerprint + reject-on-downgrade.

Offline maint-lineage suite. No FE Back UI, no migrations, no paid AI.
"""

from __future__ import annotations

import json

import pytest

from app.services.design_service import (
    STUDIO_DRAFT_V1,
    STUDIO_DRAFT_V2,
    _normalize_back_sentinel,
    _studio_content_fingerprint,
    _studio_downgrade_reason,
)
from tests.test_saved_design_isolation import _saved_payload
from tests.test_studio_draft_concurrency import _auth, _register, _studio_payload


def _stroke(stroke_id: str) -> dict:
    return {
        "id": stroke_id,
        "tool": "draw",
        "points": [1, 2, 0.5, 3, 4, 0.6],
        "color": "#1C1C1E",
        "size": 2,
        "opacity": 1,
    }


def _studio_v2_payload(
    client_revision: int,
    *,
    model: str = "female-straight",
    front_stroke_id: str | None = "front-1",
    back: dict | None = None,
    include_back_key: bool = True,
    active_side: str | None = "front",
    fills: list | None = None,
) -> dict:
    base = _studio_payload(client_revision, model=model, stroke_id=front_stroke_id, fills=fills)
    design_data = base["design_data"]
    design_data["schema"] = STUDIO_DRAFT_V2
    if active_side is not None:
        design_data["activeSide"] = active_side
    if include_back_key:
        design_data["back"] = back if back is not None else {"strokes": [], "fills": []}
    base["metadata"]["schema"] = STUDIO_DRAFT_V2
    return base


def _saved_v2_payload(save_request_id: str, *, with_back: bool = True) -> dict:
    payload = _saved_payload(save_request_id, title="Two-sided gown")
    payload["design_data"]["schema"] = "fashionrise.saved_design.v2"
    payload["metadata"]["envelope"] = "fashionrise.saved_design.v2"
    if with_back:
        payload["design_data"]["snapshot"]["back"] = {
            "strokes": [_stroke("back-s1")],
            "fills": [],
        }
        payload["design_data"]["snapshot"]["activeSide"] = "back"
    return payload


def test_fingerprint_absent_back_differs_from_empty_back():
    front = {
        "schema": STUDIO_DRAFT_V2,
        "strokes": [_stroke("a")],
        "fills": [],
        "model": "female-straight",
        "brush": {"sizeId": "thin"},
        "dimmed": False,
    }
    empty_back = {**front, "back": {"strokes": [], "fills": []}}
    assert "back" not in front
    assert _normalize_back_sentinel(front) is None
    assert _normalize_back_sentinel(empty_back) == {"strokes": [], "fills": []}
    assert _studio_content_fingerprint(front) != _studio_content_fingerprint(empty_back)


def test_fingerprint_includes_schema_and_active_side_and_back_only_edits():
    base = {
        "schema": STUDIO_DRAFT_V2,
        "strokes": [_stroke("front")],
        "fills": [],
        "model": "male-straight",
        "brush": {"sizeId": "thin"},
        "dimmed": False,
        "activeSide": "front",
        "back": {"strokes": [], "fills": []},
    }
    back_ink = {
        **base,
        "activeSide": "back",
        "back": {"strokes": [_stroke("back")], "fills": []},
    }
    assert _studio_content_fingerprint(base) != _studio_content_fingerprint(back_ink)
    v1 = {**base, "schema": STUDIO_DRAFT_V1}
    v1.pop("back", None)
    v1.pop("activeSide", None)
    assert _studio_content_fingerprint(base) != _studio_content_fingerprint(v1)


def test_downgrade_reason_codes():
    stored = {
        "schema": STUDIO_DRAFT_V2,
        "back": {"strokes": [_stroke("b")], "fills": []},
    }
    assert _studio_downgrade_reason(stored, {"schema": STUDIO_DRAFT_V1}) == "studio_schema_downgrade"
    assert _studio_downgrade_reason(stored, {"schema": STUDIO_DRAFT_V2}) == "back_stripped"
    assert (
        _studio_downgrade_reason(
            stored,
            {"schema": STUDIO_DRAFT_V2, "back": {"strokes": [], "fills": []}},
        )
        == "back_clear_requires_intent"
    )
    assert (
        _studio_downgrade_reason(
            stored,
            {"schema": STUDIO_DRAFT_V2, "back": {"strokes": [], "fills": []}},
            incoming_meta={"clearBackIntent": True},
        )
        is None
    )


def test_old_fe_v1_create_over_stored_v2_returns_409_without_write(client, db_session):
    tokens = _register(client, db_session, "v4jb_create@example.com", "v4jb_create")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            3,
            front_stroke_id="f1",
            back={"strokes": [_stroke("b1")], "fills": []},
        ),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]
    server_before = created.json()["design_data"]

    # Old FE lost-response / stale create with v1 and lower revision — must 409, not 201.
    conflict = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="f1"),
    )
    assert conflict.status_code == 409, conflict.text
    detail = conflict.json()["detail"]
    assert detail["code"] == "conflict"
    assert detail["payload"]["reason"] == "studio_schema_downgrade"
    assert detail["payload"]["design"]["id"] == design_id

    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["design_data"] == server_before
    assert got.json()["design_data"]["back"]["strokes"][0]["id"] == "b1"


def test_old_fe_v1_update_over_stored_v2_returns_409_preserves_back(client, db_session):
    tokens = _register(client, db_session, "v4jb_put@example.com", "v4jb_put")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            2,
            front_stroke_id="f1",
            back={"strokes": [_stroke("keep-me")], "fills": []},
        ),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    stripped = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(3, stroke_id="f1"),
            "expected_revision": 2,
        },
    )
    assert stripped.status_code == 409, stripped.text
    assert stripped.json()["detail"]["payload"]["reason"] == "studio_schema_downgrade"

    got = client.get(f"/api/v1/designs/{design_id}", headers=headers).json()
    assert got["design_data"]["schema"] == STUDIO_DRAFT_V2
    assert got["design_data"]["back"]["strokes"][0]["id"] == "keep-me"
    assert got["design_data"]["clientRevision"] == 2


def test_back_only_update_changes_fingerprint_and_revision(client, db_session):
    tokens = _register(client, db_session, "v4jb_back@example.com", "v4jb_back")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            1,
            front_stroke_id="front-stable",
            back={"strokes": [], "fills": []},
            active_side="front",
        ),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]
    front_before = created.json()["design_data"]["strokes"]

    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                2,
                front_stroke_id="front-stable",
                back={"strokes": [_stroke("new-back")], "fills": []},
                active_side="back",
            ),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()["design_data"]
    assert body["clientRevision"] == 2
    assert body["activeSide"] == "back"
    assert body["back"]["strokes"][0]["id"] == "new-back"
    assert body["strokes"] == front_before


def test_identical_v2_create_and_put_retries_are_idempotent(client, db_session):
    tokens = _register(client, db_session, "v4jb_idem@example.com", "v4jb_idem")
    headers = _auth(tokens["access_token"])
    payload = _studio_v2_payload(
        4,
        front_stroke_id="f",
        back={"strokes": [_stroke("b")], "fills": []},
    )

    first = client.post("/api/v1/designs", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    design_id = first.json()["id"]

    retry_create = client.post("/api/v1/designs", headers=headers, json=payload)
    assert retry_create.status_code == 201, retry_create.text
    assert retry_create.json()["id"] == design_id

    retry_put = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={**payload, "expected_revision": 4},
    )
    assert retry_put.status_code == 200, retry_put.text
    assert retry_put.json()["design_data"]["clientRevision"] == 4
    assert retry_put.json()["design_data"]["back"]["strokes"][0]["id"] == "b"


def test_create_omitting_back_against_stored_back_is_rejected(client, db_session):
    tokens = _register(client, db_session, "v4jb_omit@example.com", "v4jb_omit")
    headers = _auth(tokens["access_token"])
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            5,
            back={"strokes": [_stroke("b")], "fills": []},
        ),
    )
    assert created.status_code == 201, created.text

    omit = _studio_v2_payload(6, include_back_key=False, active_side="front")
    conflict = client.post("/api/v1/designs", headers=headers, json=omit)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["reason"] == "back_stripped"


def test_malformed_back_rejected_with_422(client, db_session):
    tokens = _register(client, db_session, "v4jb_bad@example.com", "v4jb_bad")
    headers = _auth(tokens["access_token"])
    bad = _studio_v2_payload(1, back="not-an-object")  # type: ignore[arg-type]
    resp = client.post("/api/v1/designs", headers=headers, json=bad)
    assert resp.status_code == 422, resp.text


def test_v1_with_back_key_rejected(client, db_session):
    tokens = _register(client, db_session, "v4jb_v1back@example.com", "v4jb_v1back")
    headers = _auth(tokens["access_token"])
    payload = _studio_payload(1, stroke_id="x")
    payload["design_data"]["back"] = {"strokes": [], "fills": []}
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_studio_sides_capability_guard(client, db_session):
    tokens = _register(client, db_session, "v4jb_cap@example.com", "v4jb_cap")
    headers = _auth(tokens["access_token"])
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(1, back={"strokes": [_stroke("b")], "fills": []}),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    payload = _studio_v2_payload(
        2,
        back={"strokes": [_stroke("b2")], "fills": []},
    )
    payload["metadata"]["studioSides"] = 1
    resp = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={**payload, "expected_revision": 1},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["payload"]["reason"] == "studio_sides_insufficient"


def test_saved_design_v2_create_idempotent_and_immutable(client, db_session):
    tokens = _register(client, db_session, "v4jb_saved@example.com", "v4jb_saved")
    headers = _auth(tokens["access_token"])

    # Working draft may coexist.
    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="w"))
    assert draft.status_code == 201, draft.text

    first = client.post("/api/v1/designs", headers=headers, json=_saved_v2_payload("save-req-1"))
    assert first.status_code == 201, first.text
    saved_id = first.json()["id"]
    assert first.json()["design_data"]["schema"] == "fashionrise.saved_design.v2"
    assert first.json()["design_data"]["snapshot"]["back"]["strokes"][0]["id"] == "back-s1"

    retry = client.post("/api/v1/designs", headers=headers, json=_saved_v2_payload("save-req-1"))
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == saved_id

    # Downgrade rewrite rejected.
    v1_rewrite = _saved_payload("save-req-1")
    conflict = client.put(
        f"/api/v1/designs/{saved_id}",
        headers=headers,
        json=v1_rewrite,
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["reason"] in {
        "saved_schema_downgrade",
        "back_stripped",
    }

    got = client.get(f"/api/v1/designs/{saved_id}", headers=headers).json()
    assert got["design_data"]["schema"] == "fashionrise.saved_design.v2"
    assert got["design_data"]["snapshot"]["back"]["strokes"][0]["id"] == "back-s1"


def test_saved_design_v2_malformed_back_rejected(client, db_session):
    tokens = _register(client, db_session, "v4jb_saved_bad@example.com", "v4jb_saved_bad")
    headers = _auth(tokens["access_token"])
    payload = _saved_v2_payload("bad-back")
    payload["design_data"]["snapshot"]["back"] = ["nope"]
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_saved_design_owner_isolation_still_holds(client, db_session):
    owner = _register(client, db_session, "v4jb_own@example.com", "v4jb_own")
    other = _register(client, db_session, "v4jb_oth@example.com", "v4jb_oth")
    owner_h = _auth(owner["access_token"])
    other_h = _auth(other["access_token"])

    saved = client.post("/api/v1/designs", headers=owner_h, json=_saved_v2_payload("priv-1"))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]

    denied = client.get(f"/api/v1/designs/{saved_id}", headers=other_h)
    assert denied.status_code == 404, denied.text


def test_v1_behavior_unchanged_for_front_only_drafts(client, db_session):
    tokens = _register(client, db_session, "v4jb_v1ok@example.com", "v4jb_v1ok")
    headers = _auth(tokens["access_token"])
    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="a"))
    assert first.status_code == 201, first.text
    design_id = first.json()["id"]
    retry = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="a"))
    assert retry.status_code == 201
    assert retry.json()["id"] == design_id
    advanced = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={**_studio_payload(2, stroke_id="b"), "expected_revision": 1},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["design_data"]["schema"] == STUDIO_DRAFT_V1


def test_upgrade_v1_to_v2_via_put_allowed(client, db_session):
    tokens = _register(client, db_session, "v4jb_up@example.com", "v4jb_up")
    headers = _auth(tokens["access_token"])
    created = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="f"))
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    upgraded = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                2,
                front_stroke_id="f",
                back={"strokes": [], "fills": []},
            ),
            "expected_revision": 1,
        },
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["design_data"]["schema"] == STUDIO_DRAFT_V2
    assert upgraded.json()["design_data"]["back"] == {"strokes": [], "fills": []}


def test_stale_create_downgrade_never_silent_success(client, db_session):
    """Regression: incoming_rev < current_rev used to return 201 existing; must 409 on downgrade."""
    tokens = _register(client, db_session, "v4jb_stale@example.com", "v4jb_stale")
    headers = _auth(tokens["access_token"])
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(9, back={"strokes": [_stroke("secret")], "fills": []}),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    stale_v1 = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="x"))
    assert stale_v1.status_code == 409, stale_v1.text
    assert stale_v1.json()["detail"]["payload"]["reason"] == "studio_schema_downgrade"
    got = client.get(f"/api/v1/designs/{design_id}", headers=headers).json()
    assert got["design_data"]["back"]["strokes"][0]["id"] == "secret"


def test_emptying_back_without_intent_rejected(client, db_session):
    tokens = _register(client, db_session, "v4jb_clear@example.com", "v4jb_clear")
    headers = _auth(tokens["access_token"])
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            1,
            front_stroke_id="f",
            back={"strokes": [_stroke("keep")], "fills": []},
        ),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    accidental = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                2,
                front_stroke_id="f",
                back={"strokes": [], "fills": []},
            ),
            "expected_revision": 1,
        },
    )
    assert accidental.status_code == 409, accidental.text
    assert accidental.json()["detail"]["payload"]["reason"] == "back_clear_requires_intent"
    assert (
        client.get(f"/api/v1/designs/{design_id}", headers=headers).json()["design_data"]["back"][
            "strokes"
        ][0]["id"]
        == "keep"
    )

    payload = _studio_v2_payload(
        2,
        front_stroke_id="f",
        back={"strokes": [], "fills": []},
    )
    payload["metadata"]["clearBackIntent"] = True
    cleared = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={**payload, "expected_revision": 1},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["design_data"]["back"] == {"strokes": [], "fills": []}
    assert cleared.json()["design_data"]["clientRevision"] == 2


def test_two_tab_conflict_preserves_full_v2_document(client, db_session):
    tokens = _register(client, db_session, "v4jb_tabs@example.com", "v4jb_tabs")
    headers = _auth(tokens["access_token"])
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_v2_payload(
            1,
            front_stroke_id="front-a",
            back={"strokes": [_stroke("back-a")], "fills": []},
        ),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    tab_b = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                2,
                front_stroke_id="front-b",
                back={"strokes": [_stroke("back-b")], "fills": []},
            ),
            "expected_revision": 1,
        },
    )
    assert tab_b.status_code == 200, tab_b.text

    tab_a_stale = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                3,
                front_stroke_id="front-stale",
                back={"strokes": [_stroke("back-stale")], "fills": []},
            ),
            "expected_revision": 1,
        },
    )
    assert tab_a_stale.status_code == 409, tab_a_stale.text
    server = client.get(f"/api/v1/designs/{design_id}", headers=headers).json()["design_data"]
    assert server["clientRevision"] == 2
    assert server["strokes"][0]["id"] == "front-b"
    assert server["back"]["strokes"][0]["id"] == "back-b"


def test_fingerprint_json_stable_sort_keys():
    data = {
        "schema": STUDIO_DRAFT_V2,
        "dimmed": False,
        "model": "female-straight",
        "strokes": [],
        "fills": [],
        "brush": {"color": "#1C1C1E", "sizeId": "thin", "opacity": 1},
        "activeSide": "back",
        "back": {"fills": [], "strokes": [_stroke("z")]},
    }
    a = _studio_content_fingerprint(data)
    b = _studio_content_fingerprint(data)
    assert a == b
    parsed = json.loads(a)
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert parsed["back"]["strokes"][0]["id"] == "z"


@pytest.mark.parametrize(
    "active_side",
    ["sideways", 1, None],
)
def test_invalid_active_side_rejected(client, db_session, active_side):
    tokens = _register(
        client,
        db_session,
        f"v4jb_side_{active_side}@example.com",
        f"v4jb_side_{str(active_side)[:8]}",
    )
    headers = _auth(tokens["access_token"])
    payload = _studio_v2_payload(1, active_side="front")
    if active_side is None:
        payload["design_data"]["activeSide"] = None
    else:
        payload["design_data"]["activeSide"] = active_side
    # None is invalid when key present with non front/back value; missing key is OK.
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_unknown_studio_schema_family_rejected_without_metadata(client, db_session):
    tokens = _register(client, db_session, "v4jb_v3@example.com", "v4jb_v3")
    headers = _auth(tokens["access_token"])
    payload = {
        "title": "Unknown schema",
        "description": None,
        "garment_category": "studio",
        "template_id": None,
        "material_id": None,
        "color_palette_id": None,
        "design_data": {
            "schema": "fashionrise.studio.draft.v3",
            "strokes": [],
            "model": "female",
        },
        "metadata": {},
        "visibility": "private",
        "status": "draft",
    }
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_unknown_saved_schema_family_rejected_without_metadata(client, db_session):
    tokens = _register(client, db_session, "v4jb_sv3@example.com", "v4jb_sv3")
    headers = _auth(tokens["access_token"])
    payload = _saved_v2_payload("req-v3")
    payload["design_data"]["schema"] = "fashionrise.saved_design.v3"
    payload["metadata"] = {}
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_saved_design_kind_switch_to_studio_rejected(client, db_session):
    from app.models.garment_design import GarmentDesign
    from app.services.design_service import _is_studio_working_draft, find_studio_working_draft
    from app.models.user import User

    tokens = _register(client, db_session, "v4jb_kind@example.com", "v4jb_kind")
    headers = _auth(tokens["access_token"])

    draft = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="w"))
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    saved = client.post("/api/v1/designs", headers=headers, json=_saved_v2_payload("kind-1"))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]
    before = client.get(f"/api/v1/designs/{saved_id}", headers=headers).json()

    hijack = client.put(
        f"/api/v1/designs/{saved_id}",
        headers=headers,
        json={
            **_studio_v2_payload(
                0,
                front_stroke_id="hijack",
                back={"strokes": [_stroke("x")], "fills": []},
            ),
            "expected_revision": 0,
        },
    )
    assert hijack.status_code == 409, hijack.text
    assert hijack.json()["detail"]["payload"]["reason"] == "saved_kind_conversion"

    meta_only = client.put(
        f"/api/v1/designs/{saved_id}",
        headers=headers,
        json={
            "metadata": {
                "draftKind": "studio_working_draft",
                "schema": STUDIO_DRAFT_V2,
                "clientRevision": 0,
            }
        },
    )
    assert meta_only.status_code == 409, meta_only.text
    assert meta_only.json()["detail"]["payload"]["reason"] == "saved_kind_conversion"

    after = client.get(f"/api/v1/designs/{saved_id}", headers=headers).json()
    assert after["design_data"] == before["design_data"]
    assert after["metadata"] == before["metadata"]
    assert after["design_data"]["schema"] == "fashionrise.saved_design.v2"

    user = db_session.query(User).filter(User.email == "v4jb_kind@example.com").one()
    found = find_studio_working_draft(db_session, user)
    assert found is not None and str(found.id) == draft_id
    row = db_session.get(GarmentDesign, saved_id)
    assert row is not None
    assert _is_studio_working_draft(row) is False


def test_saved_design_title_update_keeps_snapshot(client, db_session):
    tokens = _register(client, db_session, "v4jb_title@example.com", "v4jb_title")
    headers = _auth(tokens["access_token"])
    saved = client.post("/api/v1/designs", headers=headers, json=_saved_v2_payload("title-1"))
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]
    before = saved.json()["design_data"]

    renamed = client.put(
        f"/api/v1/designs/{saved_id}",
        headers=headers,
        json={"title": "Renamed gown"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Renamed gown"
    assert renamed.json()["design_data"] == before
    assert renamed.json()["metadata"]["designKind"] == "saved_design"


def test_saved_retry_different_source_revision_conflicts(client, db_session):
    tokens = _register(client, db_session, "v4jb_src@example.com", "v4jb_src")
    headers = _auth(tokens["access_token"])
    first = _saved_v2_payload("src-1")
    first["design_data"]["sourceRevision"] = 1
    created = client.post("/api/v1/designs", headers=headers, json=first)
    assert created.status_code == 201, created.text
    saved_id = created.json()["id"]

    changed = _saved_v2_payload("src-1")
    changed["design_data"]["sourceRevision"] = 99
    conflict = client.post("/api/v1/designs", headers=headers, json=changed)
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["reason"] == "saved_request_conflict"
    got = client.get(f"/api/v1/designs/{saved_id}", headers=headers).json()
    assert got["design_data"]["sourceRevision"] == 1


def test_saved_unknown_back_key_rejected(client, db_session):
    tokens = _register(client, db_session, "v4jb_bkey@example.com", "v4jb_bkey")
    headers = _auth(tokens["access_token"])
    payload = _saved_v2_payload("bkey-1")
    payload["design_data"]["snapshot"]["back"]["extra"] = "nope"
    resp = client.post("/api/v1/designs", headers=headers, json=payload)
    assert resp.status_code == 422, resp.text


def test_concurrent_saved_creates_single_row(engine):
    """Real Postgres advisory-lock coverage for saved saveRequestId reconcile."""
    import uuid
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import ConflictError
    from app.core.security import hash_password
    from app.models.garment_design import GarmentDesign
    from app.models.user import User
    from app.schemas.design import DesignCreate
    from app.services import design_service

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    email = f"saved_conc_{uuid.uuid4().hex[:8]}@example.com"
    username = f"sconc_{uuid.uuid4().hex[:8]}"

    bootstrap = SessionLocal()
    try:
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            is_admin=False,
        )
        bootstrap.add(user)
        bootstrap.commit()
        bootstrap.refresh(user)
        user_id = user.id
    finally:
        bootstrap.close()

    identical = DesignCreate(
        title="Two-sided gown",
        description="concurrent saved",
        garment_category="studio",
        design_data={
            "schema": "fashionrise.saved_design.v2",
            "saveRequestId": "concurrent-save-1",
            "savedAt": "2026-10-25T12:00:00.000Z",
            "sourceRevision": 1,
            "snapshot": {
                "strokes": [_stroke("front")],
                "fills": [],
                "model": "female-straight",
                "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
                "dimmed": False,
                "activeSide": "back",
                "back": {"strokes": [_stroke("back")], "fills": []},
            },
        },
        metadata={
            "designKind": "saved_design",
            "envelope": "fashionrise.saved_design.v2",
            "saveRequestId": "concurrent-save-1",
            "savedAt": "2026-10-25T12:00:00.000Z",
            "model": "female-straight",
            "strokeCount": 1,
        },
        visibility="private",
        status="draft",
    )

    def worker(_: int) -> str:
        session = SessionLocal()
        try:
            u = session.get(User, user_id)
            assert u is not None
            try:
                d = design_service.create_design(session, u, identical)
                return str(d.id)
            except ConflictError:
                existing = design_service.find_saved_design_by_request_id(
                    session, u, "concurrent-save-1"
                )
                assert existing is not None
                return str(existing.id)
        finally:
            session.close()

    ids: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(8)]
        for fut in as_completed(futures):
            ids.append(fut.result())

    assert len(set(ids)) == 1

    verify = SessionLocal()
    try:
        rows = list(
            verify.scalars(select(GarmentDesign).where(GarmentDesign.user_id == user_id)).all()
        )
        saved = [r for r in rows if design_service._is_saved_design_row(r)]
        assert len(saved) == 1
        for r in rows:
            verify.delete(r)
        u = verify.get(User, user_id)
        if u:
            verify.delete(u)
        verify.commit()
    finally:
        verify.close()
