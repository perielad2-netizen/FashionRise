"""Web Push + native (FCM/APNs) delivery for Runway social events.

Web Push (VAPID) stays independent. Native delivery is fail-closed per platform
until NATIVE_PUSH_* flags and operator credentials are present.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.native_push_device import NativePushDevice
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push import NativePushDeviceCreate, PushSubscriptionCreate
from app.services.push_destinations import (
    build_friend_accepted_url,
    build_friend_request_url,
    build_social_comment_url,
    build_social_item_url,
    sanitize_push_url,
)

logger = logging.getLogger(__name__)


def push_enabled() -> bool:
    s = get_settings()
    return bool((s.vapid_public_key or "").strip() and (s.vapid_private_key or "").strip())


def vapid_public_key() -> str | None:
    key = (get_settings().vapid_public_key or "").strip()
    return key or None


def native_android_enabled() -> bool:
    s = get_settings()
    if not s.native_push_android_enabled:
        return False
    return bool(
        (s.native_push_fcm_service_account_json or "").strip()
        and (s.native_push_fcm_project_id or "").strip()
    )


def native_ios_enabled() -> bool:
    s = get_settings()
    if not s.native_push_ios_enabled:
        return False
    return bool(
        (s.native_push_apns_key_path or "").strip()
        and (s.native_push_apns_key_id or "").strip()
        and (s.native_push_apns_team_id or "").strip()
        and (s.native_push_apns_topic or "").strip()
    )


def upsert_subscription(
    db: Session, user: User, data: PushSubscriptionCreate, *, user_agent: str | None = None
) -> PushSubscription:
    endpoint = str(data.endpoint)
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    ua = (user_agent or data.user_agent or "").strip()[:512] or None
    if existing:
        existing.user_id = user.id
        existing.p256dh = data.p256dh.strip()
        existing.auth = data.auth.strip()
        if ua:
            existing.user_agent = ua
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    row = PushSubscription(
        user_id=user.id,
        endpoint=endpoint,
        p256dh=data.p256dh.strip(),
        auth=data.auth.strip(),
        user_agent=ua,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_subscription(db: Session, user: User, endpoint: str) -> bool:
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.user_id == user.id,
            PushSubscription.endpoint == endpoint,
        )
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def list_user_subscriptions(db: Session, user_id: uuid.UUID) -> list[PushSubscription]:
    return list(
        db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
    )


def upsert_native_device(db: Session, user: User, data: NativePushDeviceCreate) -> NativePushDevice:
    """Idempotent register. Concurrent POSTs of the same token must not 500.

    Unique token constraint races (listener + Settings sync) are recovered by
    rolling back and re-binding the winning row to the current account.
    """
    token = data.device_token.strip()
    version = (data.app_version or "").strip()[:64] or None

    dest_ver = int(getattr(data, "destination_contract_version", 1) or 1)
    dest_ver = max(1, min(10, dest_ver))

    def _bind(existing: NativePushDevice) -> NativePushDevice:
        # Reassign token to current account (account switch on same device).
        existing.user_id = user.id
        existing.platform = data.platform
        if version:
            existing.app_version = version
        existing.destination_contract_version = dest_ver
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    existing = db.scalar(select(NativePushDevice).where(NativePushDevice.device_token == token))
    if existing:
        return _bind(existing)

    row = NativePushDevice(
        user_id=user.id,
        platform=data.platform,
        device_token=token,
        app_version=version,
        destination_contract_version=dest_ver,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(select(NativePushDevice).where(NativePushDevice.device_token == token))
        if raced is None:
            raise
        return _bind(raced)
    db.refresh(row)
    return row


def delete_native_device(db: Session, user: User, device_token: str) -> bool:
    row = db.scalar(
        select(NativePushDevice).where(
            NativePushDevice.user_id == user.id,
            NativePushDevice.device_token == device_token.strip(),
        )
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def delete_all_native_devices_for_user(db: Session, user_id: uuid.UUID) -> int:
    rows = list(db.scalars(select(NativePushDevice).where(NativePushDevice.user_id == user_id)).all())
    for row in rows:
        db.delete(row)
    if rows:
        db.commit()
    return len(rows)


def list_user_native_devices(db: Session, user_id: uuid.UUID) -> list[NativePushDevice]:
    return list(db.scalars(select(NativePushDevice).where(NativePushDevice.user_id == user_id)).all())


def native_url_for_contract(safe_url: str, *, contract_version: int) -> str:
    """Map a sanitized destination to what a native client of ``contract_version`` can open.

    v2+: full typed FashionRise query destinations.
    v1: preserve ``/studio/fashionrise?friends=1…`` (already supported); item/comment
    social deep-links fall back to Social feed root; other studio/privacy paths keep
    their sanitized form (operator / rankings).
    """
    ver = max(1, int(contract_version or 1))
    if ver >= 2:
        return safe_url
    path = (safe_url or "").split("?", 1)[0] or "/studio/fashionrise"
    query = (safe_url.split("?", 1)[1] if "?" in (safe_url or "") else "") or ""
    if path == "/studio/fashionrise":
        if not query:
            return path
        # Existing v1 clients already open Manage friends with friends=1.
        from urllib.parse import parse_qs

        params = parse_qs(query, keep_blank_values=True)
        if params.get("friends") == ["1"]:
            return safe_url
        # item / comment / unknown FashionRise queries → safe Social feed.
        return "/studio/fashionrise"
    # Legacy operator / rankings / privacy paths (no free-form item query).
    return path if path.startswith(("/studio", "/privacy")) else "/studio/fashionrise"


def notify_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    title: str,
    body: str,
    url: str = "/studio/fashionrise",
    tag: str | None = None,
) -> int:
    """Fan-out to Web Push and (when enabled) native devices. Returns successful send count.

    Never raises to callers — engagement APIs must stay reliable if push fails.
    Duplicate prevention: same ``tag`` collapses OS notifications per device channel;
    use entity-scoped tags so unrelated designs/comments do not replace each other.

    Cross-channel note: Web Push and native FCM/APNs both deliver when registered.
    UA/platform matching is **not** reliable physical-device association — do not
    suppress Web Push merely because a native token exists. Browser-specific opt-out
    remains the per-subscription Settings toggle.
    """
    safe_url = sanitize_push_url(url)
    payload = {
        "title": title[:120],
        "body": body[:240],
        "url": safe_url,
        "tag": tag or "fashionrise-social",
    }
    sent = 0

    if push_enabled():
        rows = list_user_subscriptions(db, user_id)
        stale: list[PushSubscription] = []
        for row in rows:
            ok, gone = _send_one(row, payload)
            if ok:
                sent += 1
            elif gone:
                stale.append(row)
        for row in stale:
            try:
                db.delete(row)
                db.commit()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                db.rollback()
                logger.exception("push_subscription_cleanup_failed id=%s", row.id)

    devices = list_user_native_devices(db, user_id)
    stale_native: list[NativePushDevice] = []
    for device in devices:
        if device.platform == "android" and not native_android_enabled():
            continue
        if device.platform == "ios" and not native_ios_enabled():
            continue
        dest_ver = int(getattr(device, "destination_contract_version", 1) or 1)
        device_payload = dict(payload)
        device_payload["url"] = native_url_for_contract(safe_url, contract_version=dest_ver)
        ok, gone = _send_native(device, device_payload)
        if ok:
            sent += 1
        elif gone:
            stale_native.append(device)
    for row in stale_native:
        try:
            db.delete(row)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("native_push_device_cleanup_failed id=%s", row.id)

    return sent


def notify_runway_like(
    db: Session,
    *,
    owner_id: uuid.UUID,
    actor: User,
    look_title: str | None,
    gallery_item_id: uuid.UUID,
) -> None:
    if owner_id == actor.id:
        return
    label = (look_title or "your look").strip() or "your look"
    notify_user(
        db,
        owner_id,
        title="New like on FashionRise",
        body=f"@{actor.username} liked {label}",
        url=build_social_item_url(gallery_item_id),
        tag=f"fr-like-{gallery_item_id}",
    )


def notify_runway_score(
    db: Session,
    *,
    owner_id: uuid.UUID,
    actor: User,
    score: int,
    look_title: str | None,
    gallery_item_id: uuid.UUID,
) -> None:
    if owner_id == actor.id:
        return
    label = (look_title or "your look").strip() or "your look"
    notify_user(
        db,
        owner_id,
        title="New score on FashionRise",
        body=f"@{actor.username} scored {label}: {score}/10",
        url=build_social_item_url(gallery_item_id),
        tag=f"fr-score-{gallery_item_id}",
    )


def notify_runway_comment(
    db: Session,
    *,
    owner_id: uuid.UUID,
    actor: User,
    look_title: str | None,
    snippet: str,
    gallery_item_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> None:
    if owner_id == actor.id:
        return
    label = (look_title or "your look").strip() or "your look"
    preview = (snippet or "").strip()
    if len(preview) > 80:
        preview = preview[:77] + "…"
    notify_user(
        db,
        owner_id,
        title="New comment on FashionRise",
        body=(
            f"@{actor.username} on {label}: {preview}"
            if preview
            else f"@{actor.username} commented on {label}"
        ),
        url=build_social_comment_url(gallery_item_id, comment_id),
        tag=f"fr-comment-{comment_id}",
    )


def notify_comment_like(
    db: Session,
    *,
    author_id: uuid.UUID,
    actor: User,
    snippet: str,
    gallery_item_id: uuid.UUID,
    comment_id: uuid.UUID,
) -> None:
    if author_id == actor.id:
        return
    preview = (snippet or "").strip()
    if len(preview) > 60:
        preview = preview[:57] + "…"
    notify_user(
        db,
        author_id,
        title="Someone liked your comment",
        body=(
            f"@{actor.username} liked “{preview}”"
            if preview
            else f"@{actor.username} liked your comment"
        ),
        url=build_social_comment_url(gallery_item_id, comment_id),
        tag=f"fr-comment-like-{comment_id}",
    )


def notify_friend_request(
    db: Session, *, addressee_id: uuid.UUID, actor: User, friendship_id: uuid.UUID
) -> None:
    """Notify the invitee of a pending friend request (Settings: friend alerts)."""
    if addressee_id == actor.id:
        return
    notify_user(
        db,
        addressee_id,
        title="New friend request",
        body=f"@{actor.username} wants to be friends",
        url=build_friend_request_url(friendship_id),
        tag=f"fr-friend-request-{friendship_id}",
    )


def notify_friend_accepted(
    db: Session, *, requester_id: uuid.UUID, actor: User, friendship_id: uuid.UUID
) -> None:
    """Notify the original requester that their friend request was accepted."""
    if requester_id == actor.id:
        return
    notify_user(
        db,
        requester_id,
        title="Friend request accepted",
        body=f"@{actor.username} accepted your friend request",
        url=build_friend_accepted_url(friendship_id),
        tag=f"fr-friend-accepted-{friendship_id}",
    )


def _send_one(row: PushSubscription, payload: dict[str, Any]) -> tuple[bool, bool]:
    """Returns (ok, gone). gone=True means subscription should be deleted."""
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("pywebpush_not_installed")
        return False, False

    settings = get_settings()
    subscription_info = {
        "endpoint": row.endpoint,
        "keys": {"p256dh": row.p256dh, "auth": row.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key.strip(),
            vapid_claims={"sub": (settings.vapid_subject or "mailto:ops@fashionrise.app").strip()},
        )
        return True, False
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            logger.info("push_subscription_gone endpoint_suffix=%s", row.endpoint[-32:])
            return False, True
        logger.warning("push_send_failed status=%s err=%s", status, exc)
        return False, False
    except Exception:  # noqa: BLE001
        logger.exception("push_send_unexpected")
        return False, False


def _send_native(device: NativePushDevice, payload: dict[str, Any]) -> tuple[bool, bool]:
    """Send to one FCM/APNs token. Returns (ok, gone). Fail-closed if deps missing."""
    if device.platform == "android":
        return _send_fcm(device, payload)
    if device.platform == "ios":
        return _send_apns(device, payload)
    return False, False


def build_fcm_message_body(device_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """FCM HTTP v1 message body for Android (and shared data keys for taps).

    Never set a custom ``click_action`` — FashionRise MainActivity only declares
    MAIN/LAUNCHER + VIEW deep links. A custom action (historically OPEN_URI)
    made notification taps fail to open the app while FCM still accepted the send.
    """
    tag = str(payload.get("tag") or "fashionrise-runway")
    url = str(payload.get("url") or "/studio/runway")
    android_notification: dict[str, Any] = {
        "channel_id": "fashionrise_social",
    }
    return {
        "message": {
            "token": device_token,
            "notification": {"title": payload["title"], "body": payload["body"]},
            "data": {
                "url": url,
                "tag": tag,
            },
            "android": {
                "collapse_key": tag[:64],
                "priority": "HIGH",
                "notification": android_notification,
            },
        }
    }


def _send_fcm(device: NativePushDevice, payload: dict[str, Any]) -> tuple[bool, bool]:
    settings = get_settings()
    sa_path = (settings.native_push_fcm_service_account_json or "").strip()
    project_id = (settings.native_push_fcm_project_id or "").strip()
    if not sa_path or not project_id:
        return False, False
    try:
        import google.auth.transport.requests
        from google.oauth2 import service_account
        import urllib.request
    except ImportError:
        logger.warning("fcm_deps_not_installed")
        return False, False

    try:
        creds = service_account.Credentials.from_service_account_file(
            sa_path,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        creds.refresh(google.auth.transport.requests.Request())
        body = build_fcm_message_body(device.device_token, payload)
        req = urllib.request.Request(
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:  # noqa: S310 — fixed FCM host
            if 200 <= resp.status < 300:
                return True, False
            return False, False
    except Exception as exc:  # noqa: BLE001
        # Treat NOT_FOUND / UNREGISTERED as gone when message contains them.
        msg = str(exc)
        if "NOT_FOUND" in msg or "UNREGISTERED" in msg or "404" in msg:
            logger.info("fcm_token_gone suffix=%s", device.device_token[-12:])
            return False, True
        logger.warning("fcm_send_failed err=%s", type(exc).__name__)
        return False, False


def _send_apns(device: NativePushDevice, payload: dict[str, Any]) -> tuple[bool, bool]:
    """APNs alert via HTTP/2 (httpx). Fail-closed without http2 + operator key file."""
    settings = get_settings()
    key_path = (settings.native_push_apns_key_path or "").strip()
    key_id = (settings.native_push_apns_key_id or "").strip()
    team_id = (settings.native_push_apns_team_id or "").strip()
    topic = (settings.native_push_apns_topic or "").strip()
    if not key_path or not key_id or not team_id or not topic:
        return False, False
    try:
        import time

        import httpx
        from jose import jwt
    except ImportError:
        logger.warning("apns_httpx_jose_not_installed")
        return False, False

    try:
        with open(key_path, encoding="utf-8") as fh:
            key_data = fh.read()
        token = jwt.encode(
            {"iss": team_id, "iat": int(time.time())},
            key_data,
            algorithm="ES256",
            headers={"alg": "ES256", "kid": key_id},
        )
        host = (
            "api.sandbox.push.apple.com"
            if settings.native_push_apns_use_sandbox
            else "api.push.apple.com"
        )
        apns_body = {
            "aps": {
                "alert": {"title": payload["title"], "body": payload["body"]},
                "sound": "default",
                "thread-id": str(payload.get("tag") or "fashionrise-runway")[:64],
            },
            "url": str(payload.get("url") or "/studio/runway"),
            "tag": str(payload.get("tag") or "fashionrise-runway"),
        }
        try:
            client = httpx.Client(http2=True, timeout=12.0)
        except ImportError:
            # httpx without the http2 extra (`h2` missing) — never reached Apple.
            logger.warning("apns_http2_unavailable")
            return False, False
        with client:
            resp = client.post(
                f"https://{host}/3/device/{device.device_token}",
                content=json.dumps(apns_body).encode("utf-8"),
                headers={
                    "authorization": f"bearer {token}",
                    "apns-topic": topic,
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                    "apns-collapse-id": str(payload.get("tag") or "fashionrise-runway")[:64],
                    "content-type": "application/json",
                },
            )
        if resp.status_code in (200, 201):
            return True, False
        if resp.status_code == 410:
            logger.info("apns_token_gone suffix=%s", device.device_token[-12:])
            return False, True
        reason = ""
        try:
            body = resp.json()
            if isinstance(body, dict):
                reason = str(body.get("reason") or "")[:80]
        except Exception:  # noqa: BLE001
            reason = ""
        if reason:
            logger.warning("apns_send_failed status=%s reason=%s", resp.status_code, reason)
        else:
            logger.warning("apns_send_failed status=%s", resp.status_code)
        return False, False
    except TypeError:
        # Older httpx raised TypeError when http2 kwargs were unsupported.
        logger.warning("apns_http2_unavailable")
        return False, False
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "410" in msg or "Unregistered" in msg:
            logger.info("apns_token_gone suffix=%s", device.device_token[-12:])
            return False, True
        logger.warning("apns_send_failed err=%s", type(exc).__name__)
        return False, False
