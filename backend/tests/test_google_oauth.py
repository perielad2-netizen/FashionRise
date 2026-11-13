"""Google OAuth login/register — status, start redirect, upsert user."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import get_settings
from app.services import google_oauth
from tests.auth_test_helpers import register_with_invite


@pytest.fixture()
def google_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://fashionrise.app/api/v1/auth/google/callback",
    )
    monkeypatch.setenv("PUBLIC_APP_URL", "https://fashionrise.app")
    monkeypatch.setenv("GOOGLE_OAUTH_AUTO_REGISTER", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_google_status_disabled_by_default(client):
    res = client.get("/api/v1/auth/google/status")
    assert res.status_code == 200
    body = res.json()
    assert body["google_oauth_enabled"] is False


def test_google_status_enabled(client, google_env):
    res = client.get("/api/v1/auth/google/status")
    assert res.status_code == 200
    body = res.json()
    assert body["google_oauth_enabled"] is True
    assert body["auto_register"] is True


def test_google_start_redirects(client, google_env):
    res = client.get("/api/v1/auth/google/start?next=/studio", follow_redirects=False)
    assert res.status_code == 302
    loc = res.headers["location"]
    assert loc.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    parsed = urlparse(loc)
    qs = parse_qs(parsed.query)
    assert qs["client_id"] == ["test-client-id.apps.googleusercontent.com"]
    assert qs["redirect_uri"] == ["https://fashionrise.app/api/v1/auth/google/callback"]
    assert "state" in qs
    assert "openid" in qs["scope"][0]


def test_google_start_unconfigured(client):
    res = client.get("/api/v1/auth/google/start", follow_redirects=False)
    assert res.status_code == 422


def test_oauth_state_roundtrip(google_env):
    state = google_oauth.mint_oauth_state(next_path="/studio")
    data = google_oauth.parse_oauth_state(state)
    assert data["next"] == "/studio"
    assert data["client"] == "web"


def test_oauth_state_android_client(google_env):
    state = google_oauth.mint_oauth_state(next_path="/studio/home", client="android")
    data = google_oauth.parse_oauth_state(state)
    assert data["client"] == "android"
    assert data["next"] == "/studio/home"


def test_android_complete_redirect_uses_handoff_not_tokens(google_env):
    google_oauth.clear_native_handoffs_for_tests()
    url = google_oauth.complete_login_redirect(
        access="access-token-value",
        refresh="refresh-token-value",
        next_path="/studio/home",
        client="android",
    )
    assert url.startswith("app.fashionrise.studio://auth/google/native?")
    assert "access_token" not in url
    assert "refresh_token" not in url
    qs = parse_qs(urlparse(url).query)
    assert "code" in qs
    code = qs["code"][0]
    redeemed = google_oauth.redeem_native_handoff(code)
    assert redeemed["access_token"] == "access-token-value"
    assert redeemed["refresh_token"] == "refresh-token-value"
    # One-time
    with pytest.raises(Exception):
        google_oauth.redeem_native_handoff(code)


def test_native_handoff_endpoint(client, google_env):
    google_oauth.clear_native_handoffs_for_tests()
    code = google_oauth.mint_native_handoff(
        access="a-token",
        refresh="r-token",
        next_path="/studio/home",
    )
    res = client.post("/api/v1/auth/google/native-handoff", json={"code": code})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"] == "a-token"
    assert body["refresh_token"] == "r-token"
    again = client.post("/api/v1/auth/google/native-handoff", json={"code": code})
    assert again.status_code == 401


def test_upsert_creates_and_reuses(client, db_session, google_env):
    info: dict[str, Any] = {
        "email": "gmail.user@gmail.com",
        "email_verified": True,
        "name": "Gmail User",
        "sub": "google-sub-1",
    }
    user1 = google_oauth.upsert_google_user(db_session, userinfo=info)
    assert user1.email == "gmail.user@gmail.com"
    access, refresh = google_oauth.issue_tokens_for_google_user(db_session, user1)
    assert access and refresh

    user2 = google_oauth.upsert_google_user(db_session, userinfo=info)
    assert user2.id == user1.id


def test_upsert_links_existing_password_user(client, db_session, google_env):
    register_with_invite(
        client,
        db_session,
        email="linked@gmail.com",
        username="linked_user",
    )
    info = {
        "email": "linked@gmail.com",
        "email_verified": True,
        "name": "Linked",
        "sub": "google-sub-2",
    }
    user = google_oauth.upsert_google_user(db_session, userinfo=info)
    assert user.username == "linked_user"


def test_callback_missing_code_redirects_login(client, google_env):
    res = client.get("/api/v1/auth/google/callback", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"].startswith("https://fashionrise.app/login?error=")
