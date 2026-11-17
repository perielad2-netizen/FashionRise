"""FashionRise Social content reports — look/designer moderation intake."""

from __future__ import annotations

import uuid

from app.models.content_report import ContentReport
from app.services import email_delivery
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


def test_report_look_persists_and_emails_moderation_inbox(
    client, db_session, monkeypatch
):
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CONTENT_REPORT_NOTIFY_EMAIL", "mod@fashionrise.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    email_delivery.clear_captured_emails()

    viewer = register_with_invite(client, db_session, "rpt_viewer@example.com", "rptViewer")
    author = register_with_invite(client, db_session, "rpt_author@example.com", "rptAuthor")
    look_id = _publish(client, db_session, author, "reported look")

    res = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(viewer),
        json={"reason": "sexual_content", "details": "Inappropriate image"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["gallery_item_id"] == look_id
    assert body["reason"] == "sexual_content"
    assert body["status"] == "open"
    assert body["reported_user_id"]

    row = db_session.get(ContentReport, uuid.UUID(body["id"]))
    assert row is not None
    assert row.details == "Inappropriate image"

    captured = email_delivery.captured_emails()
    assert len(captured) == 1
    assert captured[0].to_email == "mod@fashionrise.test"
    assert "sexual" in captured[0].subject.lower() or "Nudity" in captured[0].subject
    assert look_id in captured[0].body_text
    assert "/api/v1/moderation/reports/" in captured[0].body_text
    assert "/view?t=" in captured[0].body_text
    assert "/keep?t=" in captured[0].body_text
    assert "/discard?t=" in captured[0].body_text
    assert "Nothing is deleted until you choose Discard" in captured[0].body_text

    dup = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(viewer),
        json={"reason": "spam"},
    )
    assert dup.status_code == 409


def _report_and_links(client, db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("CONTENT_REPORT_NOTIFY_EMAIL", "mod@fashionrise.test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    email_delivery.clear_captured_emails()

    viewer = register_with_invite(client, db_session, "rpt_mod_v@example.com", "rptModV")
    author = register_with_invite(client, db_session, "rpt_mod_a@example.com", "rptModA")
    look_id = _publish(client, db_session, author, "moderation look")
    res = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(viewer),
        json={"reason": "harassment"},
    )
    assert res.status_code == 201, res.text
    report_id = res.json()["id"]
    body = email_delivery.captured_emails()[0].body_text
    links = {}
    for action in ("view", "keep", "discard"):
        marker = f"/api/v1/moderation/reports/{report_id}/{action}?t="
        assert marker in body
        start = body.index(marker)
        end = body.find("\n", start)
        links[action] = body[start:end].strip() if end != -1 else body[start:].strip()
        # Email body stores absolute URLs; TestClient needs path+query.
        if links[action].startswith("http"):
            from urllib.parse import urlparse

            parsed = urlparse(links[action])
            links[action] = parsed.path + ("?" + parsed.query if parsed.query else "")
    return look_id, report_id, links


def test_moderation_keep_leaves_look_public(client, db_session, monkeypatch):
    from app.models.gallery_item import GalleryItem

    look_id, report_id, links = _report_and_links(client, db_session, monkeypatch)
    view = client.get(links["view"])
    assert view.status_code == 200
    assert b"Keep design" in view.content
    assert b"Discard design" in view.content

    keep = client.get(links["keep"])
    assert keep.status_code == 200
    assert b"Kept" in keep.content

    report = db_session.get(ContentReport, uuid.UUID(report_id))
    item = db_session.get(GalleryItem, uuid.UUID(look_id))
    assert report is not None and report.status == "dismissed"
    assert item is not None and item.moderation_status == "ok"
    # Look still listed on public gallery.
    feed = client.get("/api/v1/gallery?sort=newest&limit=50")
    assert feed.status_code == 200
    assert look_id in [row["id"] for row in feed.json()]


def test_moderation_discard_hides_without_deleting(client, db_session, monkeypatch):
    from app.models.gallery_item import GalleryItem

    look_id, report_id, links = _report_and_links(client, db_session, monkeypatch)
    discard = client.get(links["discard"])
    assert discard.status_code == 200
    assert b"Discarded" in discard.content
    assert b"not" in discard.content.lower()

    report = db_session.get(ContentReport, uuid.UUID(report_id))
    item = db_session.get(GalleryItem, uuid.UUID(look_id))
    assert report is not None and report.status == "actioned"
    assert item is not None
    assert item.moderation_status == "rejected"
    # Row still exists — soft hide only.
    assert db_session.get(GalleryItem, uuid.UUID(look_id)) is not None

    feed = client.get("/api/v1/gallery?sort=newest&limit=50")
    assert feed.status_code == 200
    assert look_id not in [row["id"] for row in feed.json()]


def test_cannot_report_own_look(client, db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_DELIVERY_BACKEND", "capture")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()
    email_delivery.clear_captured_emails()

    author = register_with_invite(client, db_session, "rpt_self@example.com", "rptSelf")
    look_id = _publish(client, db_session, author, "own look")

    res = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(author),
        json={"reason": "spam"},
    )
    assert res.status_code == 403


def test_report_requires_valid_reason(client, db_session):
    viewer = register_with_invite(client, db_session, "rpt_bad@example.com", "rptBad")
    author = register_with_invite(client, db_session, "rpt_auth2@example.com", "rptAuth2")
    look_id = _publish(client, db_session, author, "look")

    res = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(viewer),
        json={"reason": "not_a_real_reason"},
    )
    assert res.status_code == 422
