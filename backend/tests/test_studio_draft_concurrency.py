"""Live FastAPI + Postgres tests for Studio draft concurrency and reconcile."""

from __future__ import annotations


def _register(client, db_session, email: str, username: str, password: str = "StrongPass123!") -> dict:
    from tests.auth_test_helpers import register_with_invite

    return register_with_invite(client, db_session, email, username, password)


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


def test_stale_expected_revision_returns_409_and_preserves_server_copy(client, db_session):
    tokens = _register(client, db_session, "studio_a@example.com", "studio_a")
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


def test_update_without_expected_revision_remains_compatible(client, db_session):
    tokens = _register(client, db_session, "legacy@example.com", "legacy_user")
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


def test_duplicate_studio_create_same_content_is_idempotent(client, db_session):
    tokens = _register(client, db_session, "recon@example.com", "recon_user")
    headers = _auth(tokens["access_token"])

    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="a"))
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    # Lost-response retry with the same content must not create a second working draft.
    second = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="a"),
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
    assert studio[0]["design_data"]["strokes"][0]["id"] == "a"


def test_concurrent_create_different_content_preserves_existing(client, db_session):
    """Higher-rev create must not overwrite another device's draft (WEB-V3A reopen race)."""
    tokens = _register(client, db_session, "create_race@example.com", "create_race")
    headers = _auth(tokens["access_token"])

    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="device-b"))
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]

    conflict = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(2, model="male", stroke_id="device-a-open"),
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["design"]["id"] == first_id

    got = client.get(f"/api/v1/designs/{first_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["design_data"]["clientRevision"] == 1
    assert got.json()["design_data"]["strokes"][0]["id"] == "device-b"


def test_stale_create_retry_does_not_clobber_newer_revision(client, db_session):
    tokens = _register(client, db_session, "stale_create@example.com", "stale_create")
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


def test_matching_expected_revision_allows_update(client, db_session):
    tokens = _register(client, db_session, "ok_rev@example.com", "ok_rev")
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


def test_studio_put_requires_expected_revision(client, db_session):
    tokens = _register(client, db_session, "need_rev@example.com", "need_rev")
    headers = _auth(tokens["access_token"])

    created = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="s1"))
    design_id = created.json()["id"]

    missing = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json=_studio_payload(2, model="male", stroke_id="s2"),
    )
    assert missing.status_code == 409, missing.text
    assert missing.json()["detail"]["code"] == "conflict"


def test_studio_put_rejects_nonadvancing_revision_with_new_content(client, db_session):
    tokens = _register(client, db_session, "nonadv@example.com", "nonadv")
    headers = _auth(tokens["access_token"])

    created = client.post("/api/v1/designs", headers=headers, json=_studio_payload(1, stroke_id="s1"))
    design_id = created.json()["id"]

    bad = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(1, model="blank", stroke_id="changed"),
            "expected_revision": 1,
        },
    )
    assert bad.status_code == 409, bad.text
    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.json()["design_data"]["strokes"][0]["id"] == "s1"


def test_equal_revision_different_content_create_returns_409(client, db_session):
    tokens = _register(client, db_session, "eqrev@example.com", "eqrev")
    headers = _auth(tokens["access_token"])

    first = client.post("/api/v1/designs", headers=headers, json=_studio_payload(3, stroke_id="a"))
    assert first.status_code == 201, first.text
    design_id = first.json()["id"]

    conflict = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(3, model="blank", stroke_id="b"),
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["design"]["id"] == design_id

    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.json()["design_data"]["strokes"][0]["id"] == "a"


def test_identical_create_retry_is_idempotent(client, db_session):
    tokens = _register(client, db_session, "idem@example.com", "idem")
    headers = _auth(tokens["access_token"])
    payload = _studio_payload(2, model="male", stroke_id="same")

    first = client.post("/api/v1/designs", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/designs", headers=headers, json=payload)
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["design_data"]["strokes"][0]["id"] == "same"

    mine = client.get("/api/v1/designs/my", headers=headers)
    studio = [
        d
        for d in mine.json()
        if d.get("metadata", {}).get("draftKind") == "studio_working_draft"
        or (d.get("design_data") or {}).get("schema") == "fashionrise.studio.draft.v1"
    ]
    assert len(studio) == 1


def test_concurrent_studio_creates_single_draft(engine):
    """Real Postgres advisory-lock coverage: parallel creates cannot insert duplicates."""
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
    email = f"concurrent_{uuid.uuid4().hex[:8]}@example.com"
    username = f"cuser_{uuid.uuid4().hex[:8]}"

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
        title="Studio working draft",
        description="concurrent",
        garment_category="studio",
        design_data={
            "schema": "fashionrise.studio.draft.v1",
            "strokes": [
                {
                    "id": "shared",
                    "tool": "draw",
                    "points": [1, 2, 0.5],
                    "color": "#1C1C1E",
                    "size": 2,
                    "opacity": 1,
                }
            ],
            "model": "female",
            "customReferenceUrl": None,
            "customReferenceKey": None,
            "brush": {"sizeId": "thin", "opacity": 1, "color": "#1C1C1E"},
            "dimmed": False,
            "clientRevision": 1,
            "updatedAt": "2026-10-19T00:00:00.000Z",
        },
        metadata={
            "draftKind": "studio_working_draft",
            "schema": "fashionrise.studio.draft.v1",
            "clientRevision": 1,
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
                existing = design_service.find_studio_working_draft(session, u)
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
        studio = [r for r in rows if design_service._is_studio_working_draft(r)]
        assert len(studio) == 1
        for r in rows:
            verify.delete(r)
        u = verify.get(User, user_id)
        if u:
            verify.delete(u)
        verify.commit()
    finally:
        verify.close()
