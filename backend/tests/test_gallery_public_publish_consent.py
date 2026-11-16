"""POST /gallery public creates require server-verified public-publish consent."""

from __future__ import annotations

import uuid

from tests.auth_test_helpers import register_with_invite
from tests.runway_publish_helpers import gallery_public_publish_body


def _create_design(client, headers: dict) -> str:
    r = client.post(
        "/api/v1/designs",
        headers=headers,
        json={
            "title": f"Gallery consent {uuid.uuid4().hex[:8]}",
            "description": "consent gate",
            "garment_category": "dress",
            "template_id": None,
            "material_id": None,
            "color_palette_id": None,
            "design_data": {"neckline": "VNeck"},
            "metadata": {"source": "pytest"},
            "visibility": "private",
            "status": "draft",
        },
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_gallery_public_create_rejects_missing_consent(client, db_session):
    tokens = register_with_invite(client, db_session, "gal_miss@example.com", "gal_miss")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    design_id = _create_design(client, headers)
    r = client.post(
        "/api/v1/gallery",
        headers=headers,
        json={
            "design_id": design_id,
            "title": "No consent",
            "image_url": "https://example.com/x.png",
            "visibility": "public",
        },
    )
    assert r.status_code == 422, r.text
    msg = r.json()["detail"]["message"].lower()
    assert "rights" in msg or "publish" in msg


def test_gallery_public_create_rejects_stale_version(client, db_session):
    tokens = register_with_invite(client, db_session, "gal_stale@example.com", "gal_stale")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    design_id = _create_design(client, headers)
    body = gallery_public_publish_body()
    body["notice_version"] = "runway-share-stale-old"
    r = client.post(
        "/api/v1/gallery",
        headers=headers,
        json={
            "design_id": design_id,
            "title": "Stale version",
            "image_url": "https://example.com/x.png",
            "visibility": "public",
            **body,
        },
    )
    assert r.status_code == 422, r.text


def test_gallery_public_create_rejects_wrong_hash(client, db_session):
    tokens = register_with_invite(client, db_session, "gal_hash@example.com", "gal_hash")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    design_id = _create_design(client, headers)
    body = gallery_public_publish_body()
    body["notice_text_hash"] = "a" * 64
    r = client.post(
        "/api/v1/gallery",
        headers=headers,
        json={
            "design_id": design_id,
            "title": "Bad hash",
            "image_url": "https://example.com/x.png",
            "visibility": "public",
            **body,
        },
    )
    assert r.status_code == 422, r.text


def test_gallery_public_create_accepts_valid_consent(client, db_session):
    tokens = register_with_invite(client, db_session, "gal_ok@example.com", "gal_ok")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    design_id = _create_design(client, headers)
    r = client.post(
        "/api/v1/gallery",
        headers=headers,
        json={
            "design_id": design_id,
            "title": "Consented public",
            "image_url": "https://example.com/x.png",
            "visibility": "public",
            **gallery_public_publish_body(),
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["visibility"] == "public"


def test_gallery_private_create_skips_public_publish_consent(client, db_session):
    tokens = register_with_invite(client, db_session, "gal_priv@example.com", "gal_priv")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    design_id = _create_design(client, headers)
    r = client.post(
        "/api/v1/gallery",
        headers=headers,
        json={
            "design_id": design_id,
            "title": "Private legacy",
            "image_url": "https://example.com/x.png",
            "visibility": "private",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["visibility"] == "private"
