"""Live FastAPI + Postgres tests for Studio draft concurrency and reconcile."""

from __future__ import annotations


def _register(client, db_session, email: str, username: str, password: str = "StrongPass123!") -> dict:
    from tests.auth_test_helpers import register_with_invite

    return register_with_invite(client, db_session, email, username, password)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _solid_fill(fill_id: str = "f1", *, color: str = "#B91C1C") -> dict:
    return {
        "id": fill_id,
        "contour": [10, 10, 40, 10, 40, 50, 10, 50],
        "style": {"kind": "solid", "color": color},
        "seedX": 20,
        "seedY": 30,
    }


def _gradient_fill(fill_id: str = "g1") -> dict:
    return {
        "id": fill_id,
        "contour": [12, 12, 48, 12, 48, 60, 12, 60],
        "style": {
            "kind": "gradient",
            "gradientId": "rose-violet",
            "colors": ["#F472B6", "#7C3AED"],
            "angle": 135,
        },
        "seedX": 24,
        "seedY": 36,
    }


def _uploaded_fabric_fill(
    fill_id: str,
    asset_id: str,
    *,
    scale: float = 1.0,
) -> dict:
    return {
        "id": fill_id,
        "contour": [8, 8, 56, 8, 56, 72, 8, 72],
        "style": {"kind": "uploaded-fabric", "assetId": asset_id, "scale": scale},
        "seedX": 28,
        "seedY": 40,
    }


def _studio_payload(
    client_revision: int,
    *,
    model: str = "female",
    stroke_id: str | None = None,
    fills: list | None = None,
    include_fills_key: bool = True,
) -> dict:
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
    if include_fills_key:
        design_data["fills"] = fills if fills is not None else []
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


def test_fill_only_solid_update_advances_draft(client, db_session):
    """Fill-only edits must not be treated as identical to a strokes-only draft."""
    tokens = _register(client, db_session, "fill_solid@example.com", "fill_solid")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="s1", fills=[]),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]
    assert created.json()["design_data"].get("fills") in ([], None)

    solid = _solid_fill("fill-solid")
    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, stroke_id="s1", fills=[solid]),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["design_data"]["clientRevision"] == 2
    assert body["design_data"]["strokes"][0]["id"] == "s1"
    assert body["design_data"]["fills"] == [solid]

    reopened = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["design_data"]["fills"] == [solid]
    assert reopened.json()["design_data"]["clientRevision"] == 2


def test_fill_only_gradient_update_advances_draft(client, db_session):
    tokens = _register(client, db_session, "fill_grad@example.com", "fill_grad")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="ink", fills=[]),
    )
    design_id = created.json()["id"]
    gradient = _gradient_fill("fill-grad")

    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, stroke_id="ink", fills=[gradient]),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["design_data"]["fills"][0]["style"]["kind"] == "gradient"
    assert updated.json()["design_data"]["fills"][0]["style"]["colors"] == ["#F472B6", "#7C3AED"]


def test_fill_style_change_advances_draft(client, db_session):
    tokens = _register(client, db_session, "fill_restyle@example.com", "fill_restyle")
    headers = _auth(tokens["access_token"])

    first_fill = _solid_fill("region-a", color="#B91C1C")
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="s1", fills=[first_fill]),
    )
    design_id = created.json()["id"]

    restyled = _solid_fill("region-a", color="#166534")
    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, stroke_id="s1", fills=[restyled]),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["design_data"]["fills"][0]["style"]["color"] == "#166534"
    assert updated.json()["design_data"]["clientRevision"] == 2


def test_uploaded_fabric_fill_persists_asset_and_scale(client, db_session):
    from io import BytesIO

    from PIL import Image

    tokens = _register(client, db_session, "fill_fabric@example.com", "fill_fabric")
    headers = _auth(tokens["access_token"])

    img = Image.new("RGB", (64, 64), color=(180, 40, 90))
    buf = BytesIO()
    img.save(buf, format="PNG")
    upload = client.post(
        "/api/v1/fabrics",
        headers=headers,
        files={"file": ("swatch.png", buf.getvalue(), "image/png")},
        data={"name": "Hotfix swatch"},
    )
    assert upload.status_code == 201, upload.text
    asset_id = upload.json()["id"]

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="s1", fills=[]),
    )
    design_id = created.json()["id"]
    fabric_fill = _uploaded_fabric_fill("fabric-1", asset_id, scale=2.0)

    updated = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, stroke_id="s1", fills=[fabric_fill]),
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    saved_fill = updated.json()["design_data"]["fills"][0]
    assert saved_fill["style"]["kind"] == "uploaded-fabric"
    assert saved_fill["style"]["assetId"] == asset_id
    assert saved_fill["style"]["scale"] == 2.0

    reopened = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert reopened.json()["design_data"]["fills"][0]["style"]["assetId"] == asset_id
    assert reopened.json()["design_data"]["fills"][0]["style"]["scale"] == 2.0


def test_identical_fill_retry_is_idempotent(client, db_session):
    tokens = _register(client, db_session, "fill_idem@example.com", "fill_idem")
    headers = _auth(tokens["access_token"])
    fills = [_solid_fill("same-fill")]
    payload = _studio_payload(3, stroke_id="s1", fills=fills)

    created = client.post("/api/v1/designs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]

    retry = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={**payload, "expected_revision": 3},
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == design_id
    assert retry.json()["design_data"]["clientRevision"] == 3
    assert retry.json()["design_data"]["fills"] == fills


def test_missing_fills_and_empty_fills_are_compatible(client, db_session):
    tokens = _register(client, db_session, "fill_legacy@example.com", "fill_legacy")
    headers = _auth(tokens["access_token"])

    # Older drafts omit the fills key entirely.
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="legacy", include_fills_key=False),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]
    assert "fills" not in created.json()["design_data"]

    # Empty fills[] with same strokes/model must remain an idempotent retry.
    empty_retry = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(1, stroke_id="legacy", fills=[]),
            "expected_revision": 1,
        },
    )
    assert empty_retry.status_code == 200, empty_retry.text
    assert empty_retry.json()["design_data"]["clientRevision"] == 1
    assert empty_retry.json()["design_data"]["strokes"][0]["id"] == "legacy"


def test_stale_revision_still_409_when_fills_differ(client, db_session):
    tokens = _register(client, db_session, "fill_409@example.com", "fill_409")
    headers = _auth(tokens["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="s1", fills=[_solid_fill("a")]),
    )
    design_id = created.json()["id"]

    advanced = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(2, stroke_id="s1", fills=[_solid_fill("b", color="#0F766E")]),
            "expected_revision": 1,
        },
    )
    assert advanced.status_code == 200, advanced.text

    stale = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(3, stroke_id="s1", fills=[_solid_fill("stale")]),
            "expected_revision": 1,
        },
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["code"] == "conflict"
    assert detail["payload"]["current_revision"] == 2
    assert detail["payload"]["design"]["design_data"]["fills"][0]["id"] == "b"

    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.json()["design_data"]["fills"][0]["id"] == "b"


def test_keep_this_device_recovery_persists_local_fills(client, db_session):
    """Simulate Keep-this-device: rebase above seen server rev, then OCC PUT with fills."""
    tokens = _register(client, db_session, "fill_keep@example.com", "fill_keep")
    headers = _auth(tokens["access_token"])

    # Cloud draft has strokes only (what fingerprint omission previously "kept").
    created = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="device-cloud", fills=[]),
    )
    assert created.status_code == 201, created.text
    design_id = created.json()["id"]
    server_revision = created.json()["design_data"]["clientRevision"]
    assert server_revision == 1

    # Local device has fills; Keep-this-device rebases to serverRevision + 1.
    local_fills = [_solid_fill("local-keep"), _gradient_fill("local-grad")]
    rebased_revision = server_revision + 1
    keep = client.put(
        f"/api/v1/designs/{design_id}",
        headers=headers,
        json={
            **_studio_payload(
                rebased_revision,
                stroke_id="device-cloud",
                fills=local_fills,
            ),
            "expected_revision": server_revision,
        },
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["design_data"]["clientRevision"] == rebased_revision
    assert keep.json()["design_data"]["fills"] == local_fills

    reopened = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["design_data"]["fills"] == local_fills
    assert reopened.json()["design_data"]["strokes"][0]["id"] == "device-cloud"


def test_fill_update_no_cross_account_access(client, db_session):
    owner = _register(client, db_session, "fill_owner@example.com", "fill_owner")
    other = _register(client, db_session, "fill_other@example.com", "fill_other")
    owner_headers = _auth(owner["access_token"])
    other_headers = _auth(other["access_token"])

    created = client.post(
        "/api/v1/designs",
        headers=owner_headers,
        json=_studio_payload(1, stroke_id="private", fills=[_solid_fill("own")]),
    )
    design_id = created.json()["id"]

    denied_get = client.get(f"/api/v1/designs/{design_id}", headers=other_headers)
    assert denied_get.status_code in (403, 404)

    denied_put = client.put(
        f"/api/v1/designs/{design_id}",
        headers=other_headers,
        json={
            **_studio_payload(2, stroke_id="hijack", fills=[_solid_fill("stolen")]),
            "expected_revision": 1,
        },
    )
    assert denied_put.status_code in (403, 404)

    intact = client.get(f"/api/v1/designs/{design_id}", headers=owner_headers)
    assert intact.status_code == 200
    assert intact.json()["design_data"]["fills"][0]["id"] == "own"
    assert intact.json()["design_data"]["strokes"][0]["id"] == "private"


def test_create_reconcile_detects_fill_only_difference(client, db_session):
    """POST reconcile must not treat fill-only differences as identical content."""
    tokens = _register(client, db_session, "fill_create@example.com", "fill_create")
    headers = _auth(tokens["access_token"])

    first = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(1, stroke_id="base", fills=[]),
    )
    assert first.status_code == 201, first.text
    design_id = first.json()["id"]

    conflict = client.post(
        "/api/v1/designs",
        headers=headers,
        json=_studio_payload(2, stroke_id="base", fills=[_solid_fill("post-fill")]),
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["payload"]["design"]["id"] == design_id

    got = client.get(f"/api/v1/designs/{design_id}", headers=headers)
    assert got.json()["design_data"].get("fills") in ([], None)
    assert got.json()["design_data"]["clientRevision"] == 1
