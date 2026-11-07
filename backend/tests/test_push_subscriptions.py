"""Web Push subscribe API + notify helpers (no real browser push in CI)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import push_service
from app.services.friendship_service import ensure_accepted_friends
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _add_job, _auth, _store_image


def _vapid_env(monkeypatch):
    # Deterministic fake keys — send path is mocked; subscribe only checks non-empty.
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BFakePublicKeyForTestsOnlyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "FakePrivateKeyForTestsOnlyXXXXXXXX")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:test@fashionrise.app")
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_vapid_public_key_disabled_without_config(client, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    res = client.get("/api/v1/push/vapid-public-key")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["enabled"] is False
    assert body["public_key"] == ""


def test_subscribe_requires_vapid(client, db_session, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "push.off@example.com", "pushOff")
    res = client.post(
        "/api/v1/push/subscriptions",
        headers=_auth(tokens),
        json={
            "endpoint": "https://push.example/sub/1",
            "p256dh": "p256dh-key-value",
            "auth": "auth-key-value",
        },
    )
    assert res.status_code == 503, res.text


def test_subscribe_list_unsubscribe(client, db_session, monkeypatch):
    _vapid_env(monkeypatch)
    tokens = register_with_invite(client, db_session, "push.on@example.com", "pushOn")
    headers = _auth(tokens)

    created = client.post(
        "/api/v1/push/subscriptions",
        headers=headers,
        json={
            "endpoint": "https://push.example/sub/abc",
            "p256dh": "p256dh-key-value",
            "auth": "auth-key-value",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["endpoint"] == "https://push.example/sub/abc"

    listed = client.get("/api/v1/push/subscriptions", headers=headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1

    # Upsert same endpoint under same user
    again = client.post(
        "/api/v1/push/subscriptions",
        headers=headers,
        json={
            "endpoint": "https://push.example/sub/abc",
            "p256dh": "p256dh-key-value-2",
            "auth": "auth-key-value-2",
        },
    )
    assert again.status_code == 201, again.text
    listed2 = client.get("/api/v1/push/subscriptions", headers=headers).json()
    assert len(listed2) == 1

    deleted = client.request(
        "DELETE",
        "/api/v1/push/subscriptions",
        headers=headers,
        json={"endpoint": "https://push.example/sub/abc"},
    )
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/v1/push/subscriptions", headers=headers).json() == []


def test_like_triggers_push_to_owner(client, db_session, monkeypatch):
    _vapid_env(monkeypatch)
    peri = register_with_invite(client, db_session, "push.peri@example.com", "pushPeri")
    yaniv = register_with_invite(client, db_session, "push.yaniv@example.com", "pushYaniv")
    peri_user = db_session.query(User).filter(User.email == "push.peri@example.com").one()
    yaniv_user = db_session.query(User).filter(User.email == "push.yaniv@example.com").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    # Owner (yaniv) has a subscription
    db_session.add(
        PushSubscription(
            user_id=yaniv_user.id,
            endpoint="https://push.example/yaniv-device",
            p256dh="p256dh-key-value",
            auth="auth-key-value",
        )
    )
    db_session.commit()

    me = client.get("/api/v1/auth/me", headers=_auth(yaniv)).json()
    job = _add_job(
        db_session,
        user_id=uuid.UUID(me["id"]),
        image_url=_store_image(),
        summary="push look",
    )
    published = client.post(f"/api/v1/looks/{job.id}/publish", headers=_auth(yaniv))
    assert published.status_code == 200, published.text
    item_id = published.json()["runway_item_id"]

    with patch.object(push_service, "_send_one", return_value=(True, False)) as send:
        liked = client.post(f"/api/v1/gallery/{item_id}/like", headers=_auth(peri))
        assert liked.status_code == 204, liked.text
        assert send.call_count == 1
