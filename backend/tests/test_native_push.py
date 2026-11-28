"""Native push device API + URL sanitization (delivery fail-closed without credentials)."""

from __future__ import annotations

import json
from unittest.mock import patch

from app.models.native_push_device import NativePushDevice
from app.models.user import User
from app.services import push_service
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _clear_native_env(monkeypatch):
    monkeypatch.setenv("NATIVE_PUSH_ANDROID_ENABLED", "false")
    monkeypatch.setenv("NATIVE_PUSH_IOS_ENABLED", "false")
    monkeypatch.setenv("NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("NATIVE_PUSH_FCM_PROJECT_ID", "")
    monkeypatch.setenv("NATIVE_PUSH_APNS_KEY_PATH", "")
    monkeypatch.setenv("NATIVE_PUSH_APNS_KEY_ID", "")
    monkeypatch.setenv("NATIVE_PUSH_APNS_TEAM_ID", "")
    from app.core.config import get_settings

    get_settings.cache_clear()


def _enable_android_flags(monkeypatch):
    monkeypatch.setenv("NATIVE_PUSH_ANDROID_ENABLED", "true")
    monkeypatch.setenv("NATIVE_PUSH_FCM_SERVICE_ACCOUNT_JSON", "/tmp/fake-fcm.json")
    monkeypatch.setenv("NATIVE_PUSH_FCM_PROJECT_ID", "fashionrise-test")
    from app.core.config import get_settings

    get_settings.cache_clear()


def test_native_capability_fail_closed(client, monkeypatch):
    _clear_native_env(monkeypatch)
    res = client.get("/api/v1/push/native/capability")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["android_enabled"] is False
    assert body["ios_enabled"] is False


def test_register_native_device_requires_enablement(client, db_session, monkeypatch):
    _clear_native_env(monkeypatch)
    tokens = register_with_invite(client, db_session, "np.off@example.com", "npOff")
    res = client.post(
        "/api/v1/push/native/devices",
        headers=_auth(tokens),
        json={"platform": "android", "device_token": "a" * 32},
    )
    assert res.status_code == 503, res.text


def test_register_list_unregister_native_device(client, db_session, monkeypatch):
    _enable_android_flags(monkeypatch)
    tokens = register_with_invite(client, db_session, "np.on@example.com", "npOn")
    headers = _auth(tokens)
    token = "fcm-token-" + ("x" * 24)

    created = client.post(
        "/api/v1/push/native/devices",
        headers=headers,
        json={"platform": "android", "device_token": token, "app_version": "1.0.0"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["platform"] == "android"

    listed = client.get("/api/v1/push/native/devices", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Account switch: same token reassigned to another user
    tokens_b = register_with_invite(client, db_session, "np.b@example.com", "npB")
    again = client.post(
        "/api/v1/push/native/devices",
        headers=_auth(tokens_b),
        json={"platform": "android", "device_token": token},
    )
    assert again.status_code == 201, again.text
    assert client.get("/api/v1/push/native/devices", headers=headers).json() == []
    assert len(client.get("/api/v1/push/native/devices", headers=_auth(tokens_b)).json()) == 1

    deleted = client.request(
        "DELETE",
        "/api/v1/push/native/devices",
        headers=_auth(tokens_b),
        json={"device_token": token},
    )
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/v1/push/native/devices", headers=_auth(tokens_b)).json() == []


def test_fcm_message_omits_custom_click_action():
    """Regression: custom click_action OPEN_URI prevented Android tap-to-open."""
    body = push_service.build_fcm_message_body(
        "fcm-token-example",
        {
            "title": "FashionRise push test",
            "body": "Controlled delivery test — tap to open Runway.",
            "url": "/studio/runway",
            "tag": "operator-push-test",
        },
    )
    msg = body["message"]
    assert msg["notification"]["title"] == "FashionRise push test"
    assert msg["data"]["url"] == "/studio/runway"
    assert msg["data"]["tag"] == "operator-push-test"
    android_n = msg["android"]["notification"]
    assert android_n["channel_id"] == "fashionrise_social"
    assert "click_action" not in android_n
    # Entire serialized body must not reintroduce the broken action.
    assert "OPEN_URI" not in json.dumps(body)
    assert "click_action" not in json.dumps(body)


def test_sanitize_push_url_allowlist():
    assert push_service.sanitize_push_url("/studio/runway") == "/studio/runway"
    assert push_service.sanitize_push_url("https://fashionrise.app/studio/runway") == "/studio/runway"
    assert push_service.sanitize_push_url("https://evil.example/phish") == "/studio/runway"
    assert push_service.sanitize_push_url("/api/v1/auth/me") == "/studio/runway"
    # Password-reset / verify / OAuth / token-bearing URLs must never be push destinations.
    assert push_service.sanitize_push_url("/reset-password#token=abc") == "/studio/runway"
    assert push_service.sanitize_push_url("/verify-email#token=xyz") == "/studio/runway"
    assert push_service.sanitize_push_url("/forgot-password") == "/studio/runway"
    assert push_service.sanitize_push_url("/auth/google/complete#access_token=x") == "/studio/runway"
    assert push_service.sanitize_push_url("/studio/runway?token=leak") == "/studio/runway"
    assert push_service.sanitize_push_url("/privacy") == "/privacy"
    # Manage friends sheet — only friends=1 on fashionrise is allowed through.
    assert (
        push_service.sanitize_push_url("/studio/fashionrise?friends=1")
        == "/studio/fashionrise?friends=1"
    )
    assert push_service.sanitize_push_url("/studio/runway?friends=1") == "/studio/runway"
    assert push_service.sanitize_push_url("/studio/fashionrise?friends=1&token=x") == "/studio/runway"


def test_register_native_device_idempotent_same_token(client, db_session, monkeypatch):
    """Repeated POST of the same FCM token must stay 201 (no UniqueViolation 500)."""
    _enable_android_flags(monkeypatch)
    tokens = register_with_invite(client, db_session, "np.idem@example.com", "npIdem")
    headers = _auth(tokens)
    token = "fcm-idem-" + ("y" * 24)
    body = {"platform": "android", "device_token": token}
    first = client.post("/api/v1/push/native/devices", headers=headers, json=body)
    second = client.post("/api/v1/push/native/devices", headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    listed = client.get("/api/v1/push/native/devices", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_upsert_native_device_recovers_unique_race(monkeypatch):
    """IntegrityError on insert commit re-binds the winning token row (no 500)."""
    from sqlalchemy.exc import IntegrityError

    from app.schemas.push import NativePushDeviceCreate

    _enable_android_flags(monkeypatch)
    user = User(id=__import__("uuid").uuid4(), email="a@ex.com", username="a", hashed_password="x")
    winner = NativePushDevice(
        id=__import__("uuid").uuid4(),
        user_id=__import__("uuid").uuid4(),
        platform="android",
        device_token="fcm-race-" + ("z" * 24),
    )
    db = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    state = {"n": 0}

    def scalar(_stmt):
        state["n"] += 1
        if state["n"] == 1:
            return None
        return winner

    def commit():
        if state["n"] == 1:
            raise IntegrityError("INSERT", {}, Exception("uq_native_push_devices_token"))
        return None

    db.scalar.side_effect = scalar
    db.commit.side_effect = commit
    out = push_service.upsert_native_device(
        db,
        user,
        NativePushDeviceCreate(platform="android", device_token=winner.device_token),
    )
    assert out is winner
    assert winner.user_id == user.id
    assert db.rollback.called
    assert db.commit.call_count >= 2


def test_notify_skips_native_when_disabled(client, db_session, monkeypatch):
    _clear_native_env(monkeypatch)
    # Keep web push off too
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    tokens = register_with_invite(client, db_session, "np.notify@example.com", "npNotify")
    user = db_session.query(User).filter(User.email == "np.notify@example.com").one()
    db_session.add(
        NativePushDevice(user_id=user.id, platform="android", device_token="t" * 40)
    )
    db_session.commit()

    with patch.object(push_service, "_send_fcm", return_value=(True, False)) as send:
        n = push_service.notify_user(db_session, user.id, title="t", body="b")
        assert n == 0
        assert send.call_count == 0

    _ = tokens


def test_web_push_ua_platform_detection():
    assert (
        push_service.web_push_ua_platform(
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/157.0.0.0 Mobile Safari/537.36"
        )
        == "android"
    )
    assert (
        push_service.web_push_ua_platform(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
        )
        == "ios"
    )
    assert (
        push_service.web_push_ua_platform(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        is None
    )
    assert push_service.web_push_ua_platform(None) is None


def test_notify_prefers_native_over_same_device_web_push(client, db_session, monkeypatch):
    """Android Chrome Web Push is skipped when an active native Android token exists."""
    _enable_android_flags(monkeypatch)
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "BK" + ("x" * 86))
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-test-key")
    from app.core.config import get_settings
    from app.models.push_subscription import PushSubscription

    get_settings.cache_clear()

    tokens = register_with_invite(client, db_session, "np.dedupe@example.com", "npDedupe")
    user = db_session.query(User).filter(User.email == "np.dedupe@example.com").one()
    db_session.add(
        NativePushDevice(user_id=user.id, platform="android", device_token="n" * 40)
    )
    android_web = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/android-chrome",
        p256dh="p256dh-android",
        auth="auth-android",
        user_agent=(
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/157.0.0.0 Mobile Safari/537.36"
        ),
    )
    desktop_web = PushSubscription(
        user_id=user.id,
        endpoint="https://fcm.googleapis.com/fcm/send/desktop-chrome",
        p256dh="p256dh-desktop",
        auth="auth-desktop",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    db_session.add_all([android_web, desktop_web])
    db_session.commit()

    with (
        patch.object(push_service, "_send_fcm", return_value=(True, False)) as send_fcm,
        patch.object(push_service, "_send_one", return_value=(True, False)) as send_web,
    ):
        n = push_service.notify_user(
            db_session, user.id, title="New comment", body="dup check", tag="runway-comment-x"
        )
        assert send_fcm.call_count == 1
        assert send_web.call_count == 1  # desktop only
        assert send_web.call_args.args[0].endpoint.endswith("desktop-chrome")
        assert n == 2

    # Subscriptions retained (skip is send-time only).
    remaining = (
        db_session.query(PushSubscription).filter(PushSubscription.user_id == user.id).count()
    )
    assert remaining == 2
    _ = tokens
