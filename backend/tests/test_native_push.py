"""Native push device API + URL sanitization (delivery fail-closed without credentials)."""

from __future__ import annotations

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
