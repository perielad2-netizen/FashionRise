"""Publish Magic looks to FashionRise Runway (gallery_items.look_id)."""

from __future__ import annotations

import uuid

from app.models.gallery_item import GalleryItem
from app.models.user_consent_event import PURPOSE_RUNWAY_SHARE, UserConsentEvent
from tests.auth_test_helpers import register_with_invite
from tests.runway_publish_helpers import runway_publish_body
from tests.test_looks_api import _add_job, _auth, _store_image


def test_publish_look_requires_share_consent_checkbox(client, db_session):
    tokens = register_with_invite(client, db_session, "runway_ack@example.com", "runway_ack")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    job = _add_job(db_session, user_id=uid, image_url=_store_image(), summary="needs ack")
    look_id = str(job.id)

    missing = client.post(f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens))
    assert missing.status_code == 422, missing.text

    denied = client.post(
        f"/api/v1/looks/{look_id}/publish",
        headers=_auth(tokens),
        json={**runway_publish_body(), "runway_share_attested": False},
    )
    assert denied.status_code == 422, denied.text


def test_publish_look_appears_on_runway_feed(client, db_session):
    tokens = register_with_invite(client, db_session, "runway_pub@example.com", "runway_pub")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    job = _add_job(db_session, user_id=uid, image_url=_store_image(), summary="runway look")
    look_id = str(job.id)
    body_json = runway_publish_body()

    published = client.post(
        f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens), json=body_json
    )
    assert published.status_code == 200, published.text
    body = published.json()
    assert body["runway_item_id"]
    runway_id = body["runway_item_id"]
    assert (
        db_session.query(UserConsentEvent)
        .filter(
            UserConsentEvent.owner_id == uid,
            UserConsentEvent.purpose == PURPOSE_RUNWAY_SHARE,
        )
        .count()
        == 1
    )

    again = client.post(
        f"/api/v1/looks/{look_id}/publish", headers=_auth(tokens), json=body_json
    )
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


def test_unpublish_look_succeeds_when_feed_item_has_ratings(client, db_session):
    """StarOff / Remove from FashionRise must not 500 when the look was scored."""
    from app.models.rating import Rating
    from app.models.user import User
    from app.services.friendship_service import ensure_accepted_friends

    owner = register_with_invite(client, db_session, "runway_rate_o@example.com", "runwayRateO")
    scorer = register_with_invite(client, db_session, "runway_rate_s@example.com", "runwayRateS")
    owner_user = db_session.query(User).filter(User.email == "runway_rate_o@example.com").one()
    scorer_user = db_session.query(User).filter(User.email == "runway_rate_s@example.com").one()
    ensure_accepted_friends(db_session, owner_user, scorer_user)

    me = client.get("/api/v1/auth/me", headers=_auth(owner)).json()
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image(), summary="rated")
    look_id = str(job.id)
    published = client.post(
        f"/api/v1/looks/{look_id}/publish",
        headers=_auth(owner),
        json=runway_publish_body(),
    )
    assert published.status_code == 200, published.text
    runway_id = published.json()["runway_item_id"]

    rate = client.post(
        "/api/v1/ratings",
        headers=_auth(scorer),
        json={"gallery_item_id": runway_id, "score": 9},
    )
    assert rate.status_code == 200, rate.text
    assert (
        db_session.query(Rating).filter(Rating.gallery_item_id == uuid.UUID(runway_id)).count() == 1
    )

    removed = client.delete(f"/api/v1/looks/{look_id}/publish", headers=_auth(owner))
    assert removed.status_code == 200, removed.text
    assert removed.json()["runway_item_id"] is None
    assert db_session.get(GalleryItem, uuid.UUID(runway_id)) is None
    assert (
        db_session.query(Rating).filter(Rating.gallery_item_id == uuid.UUID(runway_id)).count() == 0
    )


def test_delete_look_removes_runway_publish_from_feed(client, db_session):
    """My Looks delete must not leave a black empty reel on FashionRise."""
    tokens = register_with_invite(client, db_session, "runway_del@example.com", "runway_del")
    viewer = register_with_invite(client, db_session, "runway_del_v@example.com", "runway_delv")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    job = _add_job(db_session, user_id=uid, image_url=_store_image(), summary="to delete")
    look_id = str(job.id)

    published = client.post(
        f"/api/v1/looks/{look_id}/publish",
        headers=_auth(tokens),
        json=runway_publish_body(),
    )
    assert published.status_code == 200, published.text
    runway_id = published.json()["runway_item_id"]

    feed_before = client.get("/api/v1/gallery?sort=newest", headers=_auth(viewer))
    assert feed_before.status_code == 200
    assert any(row["id"] == runway_id for row in feed_before.json())

    deleted = client.delete(f"/api/v1/looks/{look_id}", headers=_auth(tokens))
    assert deleted.status_code == 204, deleted.text
    assert db_session.get(GalleryItem, uuid.UUID(runway_id)) is None

    feed_after = client.get("/api/v1/gallery?sort=newest", headers=_auth(viewer))
    assert feed_after.status_code == 200
    assert all(row["id"] != runway_id for row in feed_after.json())
    assert (
        client.get(f"/api/v1/gallery/{runway_id}/image", headers=_auth(viewer)).status_code == 404
    )

    # Idempotent re-delete still succeeds and leaves feed clean.
    assert client.delete(f"/api/v1/looks/{look_id}", headers=_auth(tokens)).status_code == 204


def test_feed_excludes_orphaned_deleted_look_publish(client, db_session):
    """Defense: gallery rows for tombstoned looks must not appear even if unpublish was skipped."""
    from datetime import UTC, datetime

    from app.models.magic_look_meta import MagicLookMeta

    tokens = register_with_invite(client, db_session, "runway_orph@example.com", "runway_orph")
    viewer = register_with_invite(client, db_session, "runway_orph_v@example.com", "runway_orphv")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    job = _add_job(db_session, user_id=uid, image_url=_store_image(), summary="orphan")
    look_id = job.id

    published = client.post(
        f"/api/v1/looks/{look_id}/publish",
        headers=_auth(tokens),
        json=runway_publish_body(),
    )
    assert published.status_code == 200, published.text
    runway_id = uuid.UUID(published.json()["runway_item_id"])

    meta = db_session.get(MagicLookMeta, look_id)
    if meta is None:
        meta = MagicLookMeta(id=look_id, user_id=uid)
        db_session.add(meta)
    meta.is_deleted = True
    meta.deleted_at = datetime.now(UTC)
    db_session.add(meta)
    db_session.commit()
    assert db_session.get(GalleryItem, runway_id) is not None

    feed = client.get("/api/v1/gallery?sort=newest", headers=_auth(viewer))
    assert feed.status_code == 200
    assert all(row["id"] != str(runway_id) for row in feed.json())

    discover = client.get("/api/v1/gallery?sort=discover", headers=_auth(viewer))
    assert discover.status_code == 200
    assert all(row["id"] != str(runway_id) for row in discover.json())

    profile = client.get(f"/api/v1/gallery/user/{uid}", headers=_auth(viewer))
    assert profile.status_code == 200
    assert all(row["id"] != str(runway_id) for row in profile.json())
