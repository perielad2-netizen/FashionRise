"""Publish Magic looks to FashionRise Runway (gallery_items.look_id)."""

from __future__ import annotations

import uuid

from app.models.gallery_item import GalleryItem
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _add_job, _auth, _store_image


def test_publish_look_appears_on_runway_feed(client, db_session):
    tokens = register_with_invite(client, db_session, "runway_pub@example.com", "runway_pub")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    job = _add_job(db_session, user_id=uid, image_url=_store_image(), summary="runway look")
    look_id = str(job.id)

    published = client.post(f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens))
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["runway_item_id"]
    runway_id = body["runway_item_id"]

    again = client.post(f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens))
    assert again.status_code == 200
    assert again.json()["runway_item_id"] == runway_id

    feed = client.get("/api/v1/gallery?sort=newest", headers=_auth(tokens))
    assert feed.status_code == 200, feed.text
    item = next(row for row in feed.json() if row["id"] == runway_id)
    assert item["look_id"] == look_id
    assert item["image_path"] == f"/gallery/{runway_id}/image"

    image = client.get(f"/api/v1/gallery/{runway_id}/image", headers=_auth(tokens))
    assert image.status_code == 200, image.text
    assert image.headers["content-type"].startswith("image/")

    listed = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    look = next(row for row in listed["items"] if row["id"] == look_id)
    assert look["runway_item_id"] == runway_id

    removed = client.delete(f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens))
    assert removed.status_code == 200, removed.text
    assert removed.json()["runway_item_id"] is None
    assert db_session.get(GalleryItem, uuid.UUID(runway_id)) is None
