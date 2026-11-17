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
SYNTHETIC_UPLOAD_NOTICE = "SYNTHETIC_TEST_CREATE_MODEL_UPLOAD_NOTICE_V1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def enable_synthetic_croquis_notices(monkeypatch) -> None:
    """Inject synthetic approved notices so consent endpoints can be exercised in tests."""
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", SYNTHETIC_ADULTS_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_STORAGE_NOTICE_TEXT", SYNTHETIC_STORAGE_NOTICE)
    monkeypatch.setenv("MY_CROQUIS_AI_NOTICE_TEXT", SYNTHETIC_AI_NOTICE)
    monkeypatch.setenv("CREATE_MODEL_UPLOAD_NOTICE_TEXT", SYNTHETIC_UPLOAD_NOTICE)
    get_settings.cache_clear()


def clear_synthetic_croquis_notices(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_ADULTS_NOTICE_TEXT", raising=False)
    monkeypatch.delenv("MY_CROQUIS_STORAGE_NOTICE_TEXT", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_NOTICE_TEXT", raising=False)
    monkeypatch.delenv("CREATE_MODEL_UPLOAD_NOTICE_TEXT", raising=False)
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


def upload_rights_body() -> dict:
    """Complete Create Model upload agreement (short + seven-point) synthetic body."""
    settings = get_settings()
    return {
        "acknowledged": True,
        "adults_attested": True,
        "notice_version": settings.create_model_upload_consent_version,
        "notice_text_hash": _sha(settings.create_model_upload_notice_text),
    }


def ai_body(*, croquis_id: str | None = None) -> dict:
    """AI consent body. Stage C requires croquis_id to bind consent to the source photo."""
    settings = get_settings()
    body: dict = {
        "acknowledged": True,
        "adults_attested": True,
        "notice_version": settings.my_croquis_ai_consent_version,
        "notice_text_hash": _sha(SYNTHETIC_AI_NOTICE),
    }
    if croquis_id is not None:
        body["croquis_id"] = croquis_id
    return body


def _auth_headers(tokens: dict) -> dict[str, str]:
    token = tokens.get("access_token") or tokens.get("accessToken") or ""
    return {"Authorization": f"Bearer {token}"}


def record_upload_rights(client, tokens: dict) -> None:
    """Record create_model_upload after adults (+ usually storage) are already done."""
    r = client.post(
        "/api/v1/personal-croquis/consent/upload",
        headers=_auth_headers(tokens),
        json=upload_rights_body(),
    )
    assert r.status_code == 200, r.text


def attest_storage_and_upload_rights(client, tokens: dict) -> str:
    """Adults → storage → create_model_upload. Returns storage consent id."""
    a = client.post(
        "/api/v1/personal-croquis/attestations/adults",
        headers=_auth_headers(tokens),
        json=adults_body(),
    )
    assert a.status_code == 200, a.text
    c = client.post(
        "/api/v1/personal-croquis/consent/storage",
        headers=_auth_headers(tokens),
        json=storage_body(),
    )
    assert c.status_code == 200, c.text
    record_upload_rights(client, tokens)
    return c.json()["id"]
