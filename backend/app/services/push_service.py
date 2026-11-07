"""Web Push delivery for Runway social events.

Designed so a later native store app can share the same notify_* helpers and
fan-out table shape (swap Web Push endpoints for APNs/FCM device tokens).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push import PushSubscriptionCreate

logger = logging.getLogger(__name__)


def push_enabled() -> bool:
    s = get_settings()
    return bool((s.vapid_public_key or "").strip() and (s.vapid_private_key or "").strip())


def vapid_public_key() -> str | None:
    key = (get_settings().vapid_public_key or "").strip()
    return key or None


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


def notify_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    title: str,
    body: str,
    url: str = "/studio/runway",
    tag: str | None = None,
) -> int:
    """Send a Web Push to all of a user's browsers. Returns successful send count.

    Never raises to callers — engagement APIs must stay reliable if push fails.
    """
    if not push_enabled():
        return 0
    rows = list_user_subscriptions(db, user_id)
    if not rows:
        return 0

    payload = {
        "title": title[:120],
        "body": body[:240],
        "url": url,
        "tag": tag or "fashionrise-runway",
    }
    sent = 0
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
    return sent


def notify_runway_like(
    db: Session, *, owner_id: uuid.UUID, actor: User, look_title: str | None
) -> None:
    if owner_id == actor.id:
        return
    label = (look_title or "your look").strip() or "your look"
    notify_user(
        db,
        owner_id,
        title="New like on Runway",
        body=f"@{actor.username} liked {label}",
        tag=f"runway-like-{owner_id}",
    )


def notify_runway_score(
    db: Session, *, owner_id: uuid.UUID, actor: User, score: int, look_title: str | None
) -> None:
    if owner_id == actor.id:
        return
    label = (look_title or "your look").strip() or "your look"
    notify_user(
        db,
        owner_id,
        title="New score on Runway",
        body=f"@{actor.username} scored {label}: {score}/10",
        tag=f"runway-score-{owner_id}",
    )


def notify_runway_comment(
    db: Session, *, owner_id: uuid.UUID, actor: User, look_title: str | None, snippet: str
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
        title="New comment on Runway",
        body=f"@{actor.username} on {label}: {preview}" if preview else f"@{actor.username} commented on {label}",
        tag=f"runway-comment-{owner_id}",
    )


def notify_comment_like(db: Session, *, author_id: uuid.UUID, actor: User, snippet: str) -> None:
    if author_id == actor.id:
        return
    preview = (snippet or "").strip()
    if len(preview) > 60:
        preview = preview[:57] + "…"
    notify_user(
        db,
        author_id,
        title="Someone liked your comment",
        body=f"@{actor.username} liked “{preview}”" if preview else f"@{actor.username} liked your comment",
        tag=f"runway-comment-like-{author_id}",
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
