"""Reporter feed hide: reported looks stay out of the reporter's Social feeds."""

from __future__ import annotations

import uuid

from app.models.gallery_item import GalleryItem
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


def test_reported_look_hidden_from_reporter_feeds_until_discard(client, db_session):
    reporter = register_with_invite(client, db_session, "hide_rep@example.com", "hideRep")
    author = register_with_invite(client, db_session, "hide_auth@example.com", "hideAuth")
    other = register_with_invite(client, db_session, "hide_other@example.com", "hideOther")

    reported_id = _publish(client, db_session, author, "reported look")
    keep_id = _publish(client, db_session, author, "keep look")

    before = client.get("/api/v1/gallery?sort=discover&limit=50", headers=_auth(reporter))
    assert before.status_code == 200
    assert reported_id in [row["id"] for row in before.json()]

    report = client.post(
        f"/api/v1/gallery/{reported_id}/report",
        headers=_auth(reporter),
        json={"reason": "sexual_content", "details": "test hide"},
    )
    assert report.status_code == 201, report.text

    # Still public/ok for everyone else (Discard not clicked yet).
    item = db_session.get(GalleryItem, uuid.UUID(reported_id))
    assert item is not None
    assert item.moderation_status == "ok"

    after_reporter = client.get(
        "/api/v1/gallery?sort=discover&limit=50", headers=_auth(reporter)
    )
    assert after_reporter.status_code == 200
    reporter_ids = [row["id"] for row in after_reporter.json()]
    assert reported_id not in reporter_ids
    assert keep_id in reporter_ids

    after_other = client.get("/api/v1/gallery?sort=discover&limit=50", headers=_auth(other))
    assert after_other.status_code == 200
    other_ids = [row["id"] for row in after_other.json()]
    assert reported_id in other_ids

    # Profile grid for the author also hides the reported look from the reporter.
    profile = client.get(
        f"/api/v1/gallery/user/{item.user_id}", headers=_auth(reporter)
    )
    assert profile.status_code == 200
    assert reported_id not in [row["id"] for row in profile.json()]

    # Duplicate report still 409 (FE treats as already-hidden).
    again = client.post(
        f"/api/v1/gallery/{reported_id}/report",
        headers=_auth(reporter),
        json={"reason": "sexual_content"},
    )
    assert again.status_code == 409
