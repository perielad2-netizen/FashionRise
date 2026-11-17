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

    dup = client.post(
        f"/api/v1/gallery/{look_id}/report",
        headers=_auth(viewer),
        json={"reason": "spam"},
    )
    assert dup.status_code == 409


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
