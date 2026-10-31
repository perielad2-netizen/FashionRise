"""Synthetic Create My Croquis consent fixtures for isolated tests only.

These notice bodies are NOT legal/production copy. They exist so Stage A tests
can exercise explicit acknowledgment without enabling real photo collection.
"""

from __future__ import annotations

import hashlib

from app.core.config import get_settings

SYNTHETIC_ADULTS_NOTICE = "SYNTHETIC_TEST_ADULTS_NOTICE_V1"
SYNTHETIC_STORAGE_NOTICE = "SYNTHETIC_TEST_STORAGE_NOTICE_V1"
SYNTHETIC_AI_NOTICE = "SYNTHETIC_TEST_AI_NOTICE_V1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def enable_synthetic_croquis_notices(monkeypatch) -> None:
    """Inject synthetic approved notices so consent endpoints can be exercised in tests."""
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", SYNTHETIC_ADULTS_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_STORAGE_NOTICE_TEXT", SYNTHETIC_STORAGE_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_AI_NOTICE_TEXT", SYNTHETIC_AI_NOTICE)
    get_settings.cache_clear()


def clear_synthetic_croquis_notices(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", raising=False)
    monkeypatch.delenv("MY_CROQUIS_STORAGE_NOTICE_TEXT", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_NOTICE_TEXT", raising=False)
    get_settings.cache_clear()


def adults_body() -> dict:
    settings = get_settings()
    return {
        "adults_attested": True,
        "notice_version": settings.my_croquis_adults_attestation_version,
        "notice_text_hash": _sha(SYNTHETIC_ADULTS_NOTICE),
    }


def storage_body() -> dict:
    settings = get_settings()
    return {
        "acknowledged": True,
        "adults_attested": True,
        "notice_version": settings.my_croquis_storage_consent_version,
        "notice_text_hash": _sha(SYNTHETIC_STORAGE_NOTICE),
    }


def ai_body() -> dict:
    settings = get_settings()
    return {
        "acknowledged": True,
        "adults_attested": True,
        "notice_version": settings.my_croquis_ai_consent_version,
        "notice_text_hash": _sha(SYNTHETIC_AI_NOTICE),
    }
