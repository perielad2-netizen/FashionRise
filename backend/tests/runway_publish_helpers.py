"""Shared Runway publish consent payload for API tests."""

from __future__ import annotations

import hashlib

from app.core.config import get_settings


def runway_publish_body() -> dict[str, object]:
    settings = get_settings()
    notice = (settings.runway_share_notice_text or "").strip()
    return {
        "runway_share_attested": True,
        "notice_version": settings.runway_share_consent_version,
        "notice_text_hash": hashlib.sha256(notice.encode("utf-8")).hexdigest(),
    }
