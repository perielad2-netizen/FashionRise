"""FashionRise Fair Discovery API — sort=discover + impressions (Social PR2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.gallery_item import GalleryItem
from app.models.user import User
from tests.auth_test_helpers import register_with_invite
from tests.runway_publish_helpers import runway_publish_body
from tests.test_looks_api import _add_job, _auth, _store_image


def _publish(client, db_session, tokens, label: str) -> str:
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary=label,
    )
    res = client.post(
        f"/api/v1/looks/{job.id}/publish",
        headers=_auth(tokens),
        json=runway_publish_body(),
    )
    assert res.status_code == 200, res.text
    return res.json()["runway_item_id"]


def test_discover_excludes_older_than_seven_days_and_records_impressions(client, db_session):
    viewer = register_with_invite(client, db_session, "disc_viewer@example.com", "discViewer")
    author = register_with_invite(client, db_session, "disc_author@example.com", "discAuthor")
    hog = register_with_invite(client, db_session, "disc_hog@example.com", "discHog")

    fresh_a = _publish(client, db_session, author, "fresh a")
    fresh_b = _publish(client, db_session, author, "fresh b")
    fresh_c = _publish(client, db_session, author, "fresh c")
    other = _publish(client, db_session, hog, "other creator")

    # Age one look out of the 7-day window.
    stale_item = db_session.get(GalleryItem, uuid.UUID(fresh_c))
    assert stale_item is not None
    stale_item.created_at = datetime.now(timezone.utc) - timedelta(days=8)
    db_session.commit()

    # Give hog a high like count but huge impressions (weak rate).
    hog_item = db_session.get(GalleryItem, uuid.UUID(other))
    assert hog_item is not None
    hog_item.likes_count = 50
    hog_item.unique_impressions_count = 2000
    hog_item.impressions_count = 2000
    # Fresh author looks stay near cold-start.
    for item_id in (fresh_a, fresh_b):
        row = db_session.get(GalleryItem, uuid.UUID(item_id))
        assert row is not None
        row.unique_impressions_count = 1
        row.impressions_count = 1
    db_session.commit()

    res = client.get("/api/v1/gallery?sort=discover&limit=10", headers=_auth(viewer))
    assert res.status_code == 200, res.text
    ids = [row["id"] for row in res.json()]
    assert fresh_c not in ids
    assert fresh_a in ids or fresh_b in ids
    assert other in ids
    # Creator diversification: at most 2 from author in the page.
    assert sum(1 for i in ids if i in {fresh_a, fresh_b, fresh_c}) <= 2

    # Impressions: first post records, second is idempotent; self-view skipped.
    author_user = db_session.query(User).filter(User.email == "disc_author@example.com").one()
    imp = client.post(
        "/api/v1/gallery/impressions",
        headers=_auth(viewer),
        json={"gallery_item_ids": [fresh_a, other, fresh_a]},
    )
    assert imp.status_code == 200, imp.text
    assert imp.json()["recorded"] == 2

    again = client.post(
        "/api/v1/gallery/impressions",
        headers=_auth(viewer),
        json={"gallery_item_ids": [fresh_a, other]},
    )
    assert again.status_code == 200
    assert again.json()["recorded"] == 0

    self_imp = client.post(
        "/api/v1/gallery/impressions",
        headers=_auth(author),
        json={"gallery_item_ids": [fresh_a]},
    )
    assert self_imp.status_code == 200
    assert self_imp.json()["recorded"] == 0

    refreshed = db_session.get(GalleryItem, uuid.UUID(fresh_a))
    assert refreshed is not None
    assert refreshed.unique_impressions_count >= 2
    assert author_user.id == refreshed.user_id


def test_following_circle_top_still_work_alongside_discover(client, db_session):
    peri = register_with_invite(client, db_session, "disc2_peri@example.com", "disc2Peri")
    item = _publish(client, db_session, peri, "peri look")

    for sort in ("discover", "circle", "following", "top10"):
        res = client.get(f"/api/v1/gallery?sort={sort}", headers=_auth(peri))
        assert res.status_code == 200, f"{sort}: {res.text}"

    # Own look can appear on discover (eligibility) and circle; impressions skip self.
    disc = client.get("/api/v1/gallery?sort=discover", headers=_auth(peri))
    assert disc.status_code == 200
    assert any(row["id"] == item for row in disc.json())
