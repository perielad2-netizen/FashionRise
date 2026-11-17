"""Signed email links for FashionRise Social content-report decisions.

Reporting only hides the look from the reporter's client feed. The gallery row
and image stay until a moderator chooses Discard (soft-hide via moderation_status).
Keep dismisses the report and leaves the look public.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from html import escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, UnauthorizedError, ValidationAppError
from app.models.content_report import ContentReport
from app.models.gallery_item import GalleryItem
from app.models.user import User
from app.services import ai_service

_log = logging.getLogger(__name__)

ModerationAction = Literal["view", "image", "keep", "discard"]

# Moderators often open mail days later — keep links usable for two weeks.
_TOKEN_TTL_SECONDS = 14 * 24 * 60 * 60

MODERATION_REJECTED = "rejected"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def mint_moderation_token(
    *,
    report_id: uuid.UUID,
    gallery_item_id: uuid.UUID,
    action: ModerationAction,
    ttl_seconds: int = _TOKEN_TTL_SECONDS,
) -> str:
    payload = {
        "rid": str(report_id),
        "gid": str(gallery_item_id),
        "act": action,
        "exp": int(time.time()) + max(60, int(ttl_seconds)),
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        get_settings().secret_key.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{sig}"


def parse_moderation_token(token: str, *, expected_action: ModerationAction) -> dict[str, Any]:
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise UnauthorizedError("Invalid moderation link") from exc
    expected = hmac.new(
        get_settings().secret_key.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise UnauthorizedError("Invalid moderation link")
    try:
        data = json.loads(_b64url_decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise UnauthorizedError("Invalid moderation link") from exc
    if not isinstance(data, dict):
        raise UnauthorizedError("Invalid moderation link")
    if str(data.get("act") or "") != expected_action:
        raise UnauthorizedError("Invalid moderation link")
    exp = int(data.get("exp") or 0)
    if exp < int(time.time()):
        raise UnauthorizedError("This moderation link has expired")
    try:
        data["report_id"] = uuid.UUID(str(data.get("rid")))
        data["gallery_item_id"] = uuid.UUID(str(data.get("gid")))
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid moderation link") from exc
    return data


def build_moderation_url(*, report_id: uuid.UUID, gallery_item_id: uuid.UUID, action: ModerationAction) -> str:
    settings = get_settings()
    app_url = (settings.public_app_url or "https://fashionrise.app").rstrip("/")
    token = mint_moderation_token(
        report_id=report_id, gallery_item_id=gallery_item_id, action=action
    )
    return (
        f"{app_url}/api/v1/moderation/reports/{report_id}/{action}"
        f"?t={quote(token, safe='')}"
    )


def get_report_for_moderation(db: Session, report_id: uuid.UUID) -> ContentReport:
    row = db.get(ContentReport, report_id)
    if row is None:
        raise NotFoundError("Report not found")
    return row


def get_gallery_item_for_moderation(db: Session, gallery_item_id: uuid.UUID) -> GalleryItem:
    """Load the look even after soft-hide — never requires moderation_status=ok."""
    item = db.get(GalleryItem, gallery_item_id)
    if item is None:
        raise NotFoundError("Look not found")
    return item


def resolve_moderation_image_path(db: Session, item: GalleryItem) -> Path:
    from app.services.looks_service import pick_look_image_job_for_owner

    if item.look_id is None:
        raise NotFoundError("Look image not available")
    owner = db.get(User, item.user_id)
    if owner is None:
        raise NotFoundError("Look image not available")
    job = pick_look_image_job_for_owner(db, owner, item.look_id)
    if job is None:
        raise NotFoundError("Look image not available")
    return ai_service.resolve_completed_job_image_path(job)


def keep_reported_look(db: Session, report: ContentReport) -> ContentReport:
    """Mark report dismissed — look stays public (ok). Does not delete anything."""
    item = get_gallery_item_for_moderation(db, report.gallery_item_id)
    if item.moderation_status == MODERATION_REJECTED:
        # Already discarded earlier — keep restores visibility.
        item.moderation_status = "ok"
    report.status = "dismissed"
    db.commit()
    db.refresh(report)
    _log.info(
        "content_report_kept report_id=%s gallery_item_id=%s",
        report.id,
        report.gallery_item_id,
    )
    return report


def discard_reported_look(db: Session, report: ContentReport) -> ContentReport:
    """Soft-hide the look from all feeds. Does not delete the row or image files."""
    item = get_gallery_item_for_moderation(db, report.gallery_item_id)
    item.moderation_status = MODERATION_REJECTED
    labels = list(item.moderation_labels or []) if isinstance(item.moderation_labels, list) else []
    labels.append(
        {
            "source": "content_report",
            "report_id": str(report.id),
            "reason": report.reason,
            "action": "discard",
        }
    )
    item.moderation_labels = labels
    report.status = "actioned"
    db.commit()
    db.refresh(report)
    _log.info(
        "content_report_discarded report_id=%s gallery_item_id=%s",
        report.id,
        report.gallery_item_id,
    )
    return report


def _html_page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0;
      background: #0c0e14; color: #f5f5f5; }}
    main {{ max-width: 520px; margin: 0 auto; padding: 24px 16px 48px; }}
    h1 {{ font-size: 1.35rem; margin: 0 0 8px; }}
    p {{ line-height: 1.45; color: #c4c4c4; }}
    .meta {{ font-size: 0.9rem; }}
    img {{ max-width: 100%; border-radius: 16px; border: 1px solid rgba(255,255,255,0.12); }}
    .actions {{ display: grid; gap: 10px; margin-top: 20px; }}
    a.btn {{ display: block; text-align: center; text-decoration: none; padding: 14px 16px;
      border-radius: 999px; font-weight: 700; }}
    a.keep {{ background: #166534; color: #fff; }}
    a.discard {{ background: #991b1b; color: #fff; }}
    a.view {{ background: #be185d; color: #fff; }}
    .ok {{ color: #86efac; }}
    .bad {{ color: #fca5a5; }}
  </style>
</head>
<body><main>{body}</main></body>
</html>"""
    return HTMLResponse(content=doc, status_code=status_code)


def render_view_page(
    db: Session,
    *,
    report: ContentReport,
    item: GalleryItem,
) -> HTMLResponse:
    author = db.get(User, item.user_id)
    image_url = build_moderation_url(
        report_id=report.id, gallery_item_id=item.id, action="image"
    )
    keep_url = build_moderation_url(
        report_id=report.id, gallery_item_id=item.id, action="keep"
    )
    discard_url = build_moderation_url(
        report_id=report.id, gallery_item_id=item.id, action="discard"
    )
    status_note = (
        f'<p class="meta">Look status: <strong>{escape(item.moderation_status)}</strong> · '
        f'Report: <strong>{escape(report.status)}</strong></p>'
    )
    body = f"""
    <h1>Review reported look</h1>
    <p class="meta">{escape(item.title or "Untitled look")}</p>
    <p class="meta">Author: @{escape((author.username if author else "?") or "?")}</p>
    <p class="meta">Reason: {escape(report.reason)}</p>
    {status_note}
    <p><img src="{escape(image_url)}" alt="Reported look" /></p>
    <div class="actions">
      <a class="btn keep" href="{escape(keep_url)}">Keep design (it's OK)</a>
      <a class="btn discard" href="{escape(discard_url)}">Discard design (real abuse)</a>
    </div>
    <p class="meta">Discard hides the look from FashionRise Social. It does not permanently delete the files until you choose a later cleanup.</p>
    """
    return _html_page("FashionRise report review", body)


def render_keep_result(report: ContentReport, item: GalleryItem) -> HTMLResponse:
    body = f"""
    <h1 class="ok">Kept</h1>
    <p>Report <code>{escape(str(report.id))}</code> marked dismissed.</p>
    <p>Look “{escape(item.title or "Untitled")}” stays on FashionRise Social
    (moderation_status=<code>{escape(item.moderation_status)}</code>).</p>
    """
    return _html_page("Report dismissed — keep", body)


def render_discard_result(report: ContentReport, item: GalleryItem) -> HTMLResponse:
    body = f"""
    <h1 class="bad">Discarded</h1>
    <p>Report <code>{escape(str(report.id))}</code> marked actioned.</p>
    <p>Look “{escape(item.title or "Untitled")}” is hidden from all feeds
    (moderation_status=<code>rejected</code>). The design row and image files were
    <strong>not</strong> deleted.</p>
    """
    return _html_page("Report actioned — discard", body)


def render_error(message: str, *, status_code: int = 400) -> HTMLResponse:
    body = f"<h1>Moderation link</h1><p>{escape(message)}</p>"
    return _html_page("FashionRise moderation", body, status_code=status_code)


def assert_token_matches_report(
    data: dict[str, Any], report: ContentReport
) -> None:
    if data["report_id"] != report.id:
        raise ValidationAppError("Moderation link does not match this report")
    if data["gallery_item_id"] != report.gallery_item_id:
        raise ValidationAppError("Moderation link does not match this look")
