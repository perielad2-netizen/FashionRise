import uuid


def _register(client, email: str, username: str, password: str = "StrongPass123!") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password, "display_name": username},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_end_to_end_user_social_design_flow(client):
    # Two users for social interactions.
    a_tokens = _register(client, "a@example.com", "user_a")
    b_tokens = _register(client, "b@example.com", "user_b")
    a_headers = _auth_header(a_tokens["access_token"])
    b_headers = _auth_header(b_tokens["access_token"])

    # Auth / me
    me_a = client.get("/api/v1/auth/me", headers=a_headers)
    me_b = client.get("/api/v1/auth/me", headers=b_headers)
    assert me_a.status_code == 200 and me_b.status_code == 200
    a_user_id = me_a.json()["id"]
    b_user_id = me_b.json()["id"]
    assert a_user_id != b_user_id

    # Profile follow status starts false.
    fs0 = client.get(f"/api/v1/profiles/{a_user_id}/follow-status", headers=b_headers)
    assert fs0.status_code == 200
    assert fs0.json()["following"] is False

    p0 = client.get("/api/v1/profiles/me", headers=a_headers)
    assert p0.status_code == 200
    rep0 = p0.json()["reputation_score"]
    assert p0.json()["reputation_tier"] in {"newcomer", "rising", "established", "icon"}

    # Design create by A.
    create_design = client.post(
        "/api/v1/designs",
        headers=a_headers,
        json={
            "title": "Flow look",
            "description": "flow test",
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {"neckline": "VNeck", "sleeve": "Long"},
            "metadata": {"source": "pytest"},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert create_design.status_code == 201, create_design.text
    design_id = create_design.json()["id"]

    # Revisions create/list/get.
    rev_create = client.post(
        f"/api/v1/designs/{design_id}/revisions",
        headers=a_headers,
        json={"design_data": {"neckline": "BoatNeck", "sleeve": "Short"}, "notes": "fit tweak"},
    )
    assert rev_create.status_code == 201, rev_create.text
    rev_num = rev_create.json()["revision_number"]
    assert rev_num >= 1

    rev_list = client.get(f"/api/v1/designs/{design_id}/revisions", headers=a_headers)
    assert rev_list.status_code == 200
    assert len(rev_list.json()) >= 1

    rev_get = client.get(f"/api/v1/designs/{design_id}/revisions/{rev_num}", headers=a_headers)
    assert rev_get.status_code == 200
    assert rev_get.json()["design_data"]["neckline"] == "BoatNeck"

    # Handoff includes new revision summary / export hints.
    handoff = client.get(f"/api/v1/designs/{design_id}/handoff", headers=a_headers)
    assert handoff.status_code == 200
    manifest = handoff.json()
    assert manifest["export_kind"] == "fashionrise.handoff.manifest_v1"
    assert "revision_summary" in manifest
    assert "export_hints" in manifest

    handoff_spec = client.get(
        f"/api/v1/designs/{design_id}/handoff?export_kind=spec_sheet_v1",
        headers=a_headers,
    )
    assert handoff_spec.status_code == 200
    spec = handoff_spec.json()
    assert spec["export_kind"] == "fashionrise.handoff.spec_sheet_v1"
    assert "style_recipe" in spec
    assert "revision_summary" in spec

    handoff_pdf = client.get(
        f"/api/v1/designs/{design_id}/handoff?export_kind=spec_sheet_pdf",
        headers=a_headers,
    )
    assert handoff_pdf.status_code == 200, handoff_pdf.text
    pdf_payload = handoff_pdf.json()
    assert pdf_payload["export_kind"] == "fashionrise.handoff.spec_sheet_pdf_v1"
    assert pdf_payload["export"]["export_type"] == "spec_sheet_pdf"
    assert pdf_payload["export"]["file_url"]
    assert pdf_payload["export"]["file_url"].endswith(".pdf")
    ex_list = client.get(f"/api/v1/exports/design/{design_id}", headers=a_headers)
    assert ex_list.status_code == 200
    assert any(e["export_type"] == "spec_sheet_pdf" for e in ex_list.json())

    # Publish to gallery.
    publish = client.post(
        "/api/v1/gallery",
        headers=a_headers,
        json={
            "design_id": design_id,
            "title": "Flow gallery look",
            "image_url": "https://example.com/preview.png",
            "visibility": "public",
        },
    )
    assert publish.status_code == 200, publish.text
    gallery_item_id = publish.json()["id"]

    # Gallery read paths.
    g_feed = client.get("/api/v1/gallery?sort=newest")
    assert g_feed.status_code == 200
    assert any(i["id"] == gallery_item_id for i in g_feed.json())

    g_user = client.get(f"/api/v1/gallery/user/{a_user_id}")
    assert g_user.status_code == 200
    assert any(i["id"] == gallery_item_id for i in g_user.json())

    # B follows A, then following feed includes A's item.
    follow = client.post(f"/api/v1/profiles/{a_user_id}/follow", headers=b_headers)
    assert follow.status_code == 204, follow.text

    fs1 = client.get(f"/api/v1/profiles/{a_user_id}/follow-status", headers=b_headers)
    assert fs1.status_code == 200
    assert fs1.json()["following"] is True

    following_ids = client.get("/api/v1/profiles/me/following-ids", headers=b_headers)
    assert following_ids.status_code == 200
    assert str(uuid.UUID(a_user_id)) in [str(uuid.UUID(x)) for x in following_ids.json()]

    follow_feed = client.get("/api/v1/gallery?sort=following", headers=b_headers)
    assert follow_feed.status_code == 200
    assert any(i["id"] == gallery_item_id for i in follow_feed.json())

    # B likes/comments/rates item.
    like = client.post(f"/api/v1/gallery/{gallery_item_id}/like", headers=b_headers)
    assert like.status_code == 204

    comment = client.post(
        f"/api/v1/gallery/{gallery_item_id}/comments",
        headers=b_headers,
        json={"body": "Nice drape"},
    )
    assert comment.status_code == 201, comment.text

    rate = client.post(
        "/api/v1/ratings",
        headers=b_headers,
        json={"gallery_item_id": gallery_item_id, "score": 9},
    )
    assert rate.status_code == 200, rate.text
    assert rate.json()["score"] == 9

    ratings = client.get(f"/api/v1/ratings/gallery/{gallery_item_id}")
    assert ratings.status_code == 200
    assert any(r["user_id"] == b_user_id for r in ratings.json())

    # Detail with B token should report liked_by_me=true.
    detail = client.get(f"/api/v1/gallery/{gallery_item_id}", headers=b_headers)
    assert detail.status_code == 200
    assert detail.json()["liked_by_me"] is True

    p1 = client.get("/api/v1/profiles/me", headers=a_headers)
    assert p1.status_code == 200
    assert p1.json()["published_count"] >= 1
    assert p1.json()["followers_count"] >= 1
    assert p1.json()["likes_received_count"] >= 1
    assert p1.json()["rating_count"] >= 1
    assert p1.json()["reputation_score"] >= rep0


def test_following_feed_requires_auth(client):
    r = client.get("/api/v1/gallery?sort=following")
    assert r.status_code == 401
    detail = r.json()["detail"]
    assert detail["code"] == "unauthorized"


def test_auth_refresh_and_logout_flow(client):
    tokens = _register(client, "authflow@example.com", "auth_flow_user")
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    me = client.get("/api/v1/auth/me", headers=_auth_header(access))
    assert me.status_code == 200

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    assert new_tokens["refresh_token"] != refresh

    logout = client.post("/api/v1/auth/logout", headers=_auth_header(new_tokens["access_token"]))
    assert logout.status_code == 204

    refresh_after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert refresh_after_logout.status_code == 401
