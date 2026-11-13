"""Google OAuth (Gmail) login / register for FashionRise.

Flow:
  1. GET /auth/google/start → redirect to Google
  2. GET /auth/google/callback → exchange code, upsert user, issue tokens
  3a. Web: redirect SPA ``/auth/google/complete#access_token=…&refresh_token=…``
  3b. Android native: redirect custom scheme with a one-time handoff code (no tokens);
      app redeems via POST /auth/google/native-handoff
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError, ValidationAppError
from app.core.security import hash_password
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services import ai_stars, auth_service, invitation_service

_log = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_STATE_MAX_AGE_SEC = 600
_HANDOFF_TTL_SEC = 90
_NATIVE_ANDROID_SCHEME = "app.fashionrise.studio"

# One-time native handoff codes (in-process). Single uvicorn worker in prod.
_handoff_lock = threading.Lock()
_handoffs: dict[str, dict[str, Any]] = {}


def google_oauth_configured() -> bool:
    settings = get_settings()
    return bool(
        (settings.google_oauth_client_id or "").strip()
        and (settings.google_oauth_client_secret or "").strip()
        and (settings.google_oauth_redirect_uri or "").strip()
    )


def _b64url_encode(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return urlsafe_b64decode((raw + pad).encode("ascii"))


def _normalize_client(client: str | None) -> Literal["web", "android"]:
    raw = (client or "web").strip().lower()
    if raw == "android":
        return "android"
    return "web"


def mint_oauth_state(*, next_path: str = "/studio", client: str = "web") -> str:
    safe_next = next_path if next_path.startswith("/") and not next_path.startswith("//") else "/studio"
    payload = {
        "n": secrets.token_urlsafe(16),
        "next": safe_next,
        "client": _normalize_client(client),
        "exp": int(time.time()) + _STATE_MAX_AGE_SEC,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        get_settings().secret_key.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{sig}"


def parse_oauth_state(state: str) -> dict[str, Any]:
    try:
        body, sig = state.split(".", 1)
    except ValueError as exc:
        raise UnauthorizedError("Invalid Google sign-in state") from exc
    expected = hmac.new(
        get_settings().secret_key.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise UnauthorizedError("Invalid Google sign-in state")
    try:
        data = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise UnauthorizedError("Invalid Google sign-in state") from exc
    if not isinstance(data, dict):
        raise UnauthorizedError("Invalid Google sign-in state")
    exp = int(data.get("exp") or 0)
    if exp < int(time.time()):
        raise UnauthorizedError("Google sign-in expired — try again")
    data["client"] = _normalize_client(str(data.get("client") or "web"))
    return data


def _purge_expired_handoffs(now: float | None = None) -> None:
    ts = time.time() if now is None else now
    expired = [k for k, v in _handoffs.items() if float(v.get("exp") or 0) < ts]
    for key in expired:
        _handoffs.pop(key, None)


def mint_native_handoff(*, access: str, refresh: str, next_path: str) -> str:
    """Create a short-lived one-time code that redeems to FashionRise session tokens.

    Tokens never appear in the Android deep link — only this opaque code does.
    """
    safe_next = next_path if next_path.startswith("/") and not next_path.startswith("//") else "/studio"
    code = secrets.token_urlsafe(32)
    with _handoff_lock:
        _purge_expired_handoffs()
        _handoffs[code] = {
            "access": access,
            "refresh": refresh,
            "next": safe_next,
            "exp": time.time() + _HANDOFF_TTL_SEC,
        }
    return code


def redeem_native_handoff(code: str) -> dict[str, str]:
    """Consume a handoff code exactly once. Returns access/refresh/next."""
    key = (code or "").strip()
    if not key or len(key) > 200:
        raise UnauthorizedError("Invalid Google sign-in handoff")
    with _handoff_lock:
        _purge_expired_handoffs()
        row = _handoffs.pop(key, None)
    if row is None:
        raise UnauthorizedError("Google sign-in handoff expired or already used")
    return {
        "access_token": str(row["access"]),
        "refresh_token": str(row["refresh"]),
        "next": str(row.get("next") or "/studio"),
    }


def clear_native_handoffs_for_tests() -> None:
    with _handoff_lock:
        _handoffs.clear()


def authorization_url(*, state: str) -> str:
    if not google_oauth_configured():
        raise ValidationAppError("Google sign-in is not configured")
    settings = get_settings()
    params = {
        "client_id": settings.google_oauth_client_id.strip(),
        "redirect_uri": settings.google_oauth_redirect_uri.strip(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_userinfo(code: str) -> dict[str, Any]:
    if not google_oauth_configured():
        raise ValidationAppError("Google sign-in is not configured")
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id.strip(),
                "client_secret": settings.google_oauth_client_secret.strip(),
                "redirect_uri": settings.google_oauth_redirect_uri.strip(),
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code >= 400:
            _log.warning("google_token_exchange_failed status=%s", token_resp.status_code)
            raise UnauthorizedError("Google sign-in failed — could not verify authorization")
        token_payload = token_resp.json()
        access = token_payload.get("access_token")
        if not access:
            raise UnauthorizedError("Google sign-in failed — missing access token")
        info_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        if info_resp.status_code >= 400:
            raise UnauthorizedError("Google sign-in failed — could not load profile")
        info = info_resp.json()
    if not isinstance(info, dict):
        raise UnauthorizedError("Google sign-in failed — invalid profile")
    return info


def _username_from_email(email: str) -> str:
    local = (email.split("@", 1)[0] or "user").lower()
    cleaned = re.sub(r"[^a-z0-9_]+", "_", local).strip("_")[:40] or "user"
    if cleaned[0].isdigit():
        cleaned = f"u_{cleaned}"
    return cleaned[:48]


def _unique_username(db: Session, base: str) -> str:
    candidate = base
    for _ in range(24):
        exists = db.scalar(select(User.id).where(User.username == candidate))
        if exists is None:
            return candidate
        suffix = secrets.token_hex(2)
        candidate = f"{base[:40]}_{suffix}"
    return f"user_{secrets.token_hex(6)}"


def upsert_google_user(db: Session, *, userinfo: dict[str, Any]) -> User:
    """Find or create a FashionRise user from a verified Google profile."""
    email_raw = str(userinfo.get("email") or "").strip()
    email_norm = invitation_service.normalize_email(email_raw)
    if not email_norm or "@" not in email_norm:
        raise UnauthorizedError("Google account did not provide an email address")
    if userinfo.get("email_verified") is False:
        raise ForbiddenError("Google email is not verified — use a verified Gmail account")

    existing = db.scalar(select(User).where(func.lower(User.email) == email_norm))
    if existing is not None:
        if not existing.is_active:
            raise UnauthorizedError("Account disabled")
        # Google verified the mailbox — mark ownership verified without privilege change.
        if not existing.email_verified:
            existing.email_verified = True
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing

    settings = get_settings()
    if not settings.google_oauth_auto_register:
        raise ForbiddenError(
            "No FashionRise account matches this Google email. "
            "Ask the operator to create an account, or enable Google auto-register."
        )

    display = str(userinfo.get("name") or "").strip() or email_norm.split("@", 1)[0]
    base_username = _username_from_email(email_norm)
    username = _unique_username(db, base_username)
    # Unusable random password — Google users sign in via OAuth (password login still works if they set one later).
    user = User(
        email=email_norm,
        username=username,
        hashed_password=hash_password(secrets.token_urlsafe(48)),
        is_admin=False,
        is_active=True,
        email_verified=True,
    )
    ai_stars.apply_new_user_stars(user)
    db.add(user)
    try:
        db.flush()
        db.add(UserProfile(user_id=user.id, display_name=display[:120]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)
    _log.info("google_oauth_registered email=%s user_id=%s", email_norm, user.id)
    return user


def complete_login_redirect(
    *,
    access: str,
    refresh: str,
    next_path: str = "/studio",
    client: str = "web",
) -> str:
    settings = get_settings()
    app = (settings.public_app_url or "https://fashionrise.app").rstrip("/")
    safe_next = next_path if next_path.startswith("/") and not next_path.startswith("//") else "/studio"
    if _normalize_client(client) == "android":
        # Custom scheme opens the Capacitor Android app. Code is one-time; no JWTs in the URL.
        code = mint_native_handoff(access=access, refresh=refresh, next_path=safe_next)
        q = urlencode({"code": code, "next": safe_next})
        return f"{_NATIVE_ANDROID_SCHEME}://auth/google/native?{q}"
    # Hash fragment keeps tokens out of Referer / most access logs (web only).
    frag = urlencode({"access_token": access, "refresh_token": refresh, "next": safe_next})
    return f"{app}/auth/google/complete#{frag}"


def status_payload() -> dict[str, Any]:
    return {
        "google_oauth_enabled": google_oauth_configured(),
        "auto_register": bool(get_settings().google_oauth_auto_register),
        "note": (
            "When enabled, GET /auth/google/start begins Google Sign-In. "
            "Verified Gmail accounts can log in; new accounts are created when auto_register is true. "
            "Android native uses a one-time handoff code (POST /auth/google/native-handoff)."
        ),
    }


def issue_tokens_for_google_user(db: Session, user: User) -> tuple[str, str]:
    return auth_service.issue_tokens(db, user)
