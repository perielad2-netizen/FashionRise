import base64


def _register(client, email: str, username: str, password: str = "StrongPass123!") -> dict:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password, "display_name": username},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_catalog_endpoints_and_ai_upload_export_flow(client):
    tokens = _register(client, "surface@example.com", "surface_user")
    headers = _auth_header(tokens["access_token"])

    # Catalog endpoints should respond even when lists are empty.
    mats = client.get("/api/v1/materials")
    tpls = client.get("/api/v1/templates")
    pals = client.get("/api/v1/palettes")
    assert mats.status_code == 200
    assert tpls.status_code == 200
    assert pals.status_code == 200
    if mats.json():
        m0 = mats.json()[0]
        m_detail = client.get(f"/api/v1/materials/{m0['id']}")
        assert m_detail.status_code == 200
    if tpls.json():
        t0 = tpls.json()[0]
        t_detail = client.get(f"/api/v1/templates/{t0['id']}")
        assert t_detail.status_code == 200

    # Build one design for export flow ownership checks.
    d = client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": "Surface look",
            "description": "surface flow",
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {"neckline": "VNeck"},
            "metadata": {},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert d.status_code == 201, d.text
    design_id = d.json()["id"]

    # AI routes (queue + fetch).
    ai_clean = client.post("/api/v1/ai/sketch/clean", headers=headers, json={"design_id": design_id, "input_data": {}})
    assert ai_clean.status_code == 201, ai_clean.text
    clean_job_id = ai_clean.json()["id"]
    assert ai_clean.json()["job_type"] == "sketch_clean"

    ai_polish = client.post("/api/v1/ai/sketch/polish", headers=headers, json={"design_id": design_id, "input_data": {}})
    assert ai_polish.status_code == 201, ai_polish.text
    assert ai_polish.json()["job_type"] == "sketch_polish"

    ai_style = client.post("/api/v1/ai/style/suggest", headers=headers, json={"design_id": design_id, "input_data": {}})
    assert ai_style.status_code == 201, ai_style.text
    assert ai_style.json()["job_type"] == "style_suggest"

    ai_tech = client.post(
        "/api/v1/ai/tech-pack",
        headers=headers,
        json={
            "design_id": design_id,
            "input_data": {
                "notes": "A-line dress",
                "fabric": "silk",
                "color": "coral",
                "material_pairs": "coral:silk:#FF6F61",
            },
        },
    )
    assert ai_tech.status_code == 201, ai_tech.text
    assert ai_tech.json()["job_type"] == "tech_pack"
    assert ai_tech.json()["status"] == "queued"

    ai_custom = client.post(
        "/api/v1/ai/jobs",
        headers=headers,
        json={"design_id": design_id, "job_type": "custom_test", "input_data": {"x": 1}},
    )
    assert ai_custom.status_code == 201, ai_custom.text
    custom_job_id = ai_custom.json()["id"]

    ai_get = client.get(f"/api/v1/ai/jobs/{clean_job_id}", headers=headers)
    assert ai_get.status_code == 200
    assert ai_get.json()["id"] == clean_job_id

    ai_get_custom = client.get(f"/api/v1/ai/jobs/{custom_job_id}", headers=headers)
    assert ai_get_custom.status_code == 200
    assert ai_get_custom.json()["job_type"] == "custom_test"

    # Upload route with valid 1x1 PNG.
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
    up = client.post(
        "/api/v1/uploads/image",
        headers=headers,
        files={"file": ("tiny.png", png_1x1, "image/png")},
    )
    assert up.status_code == 200, up.text
    upload_json = up.json()
    assert upload_json["url"]
    assert upload_json["stored_key"].endswith(".png")

    # Exports create/list.
    ex = client.post(
        "/api/v1/exports",
        headers=headers,
        json={"design_id": design_id, "export_type": "png", "file_url": upload_json["url"], "metadata": {"w": 1, "h": 1}},
    )
    assert ex.status_code == 200, ex.text
    assert ex.json()["design_id"] == design_id

    ex_list = client.get(f"/api/v1/exports/design/{design_id}", headers=headers)
    assert ex_list.status_code == 200
    assert len(ex_list.json()) >= 1
