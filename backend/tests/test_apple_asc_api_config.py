"""ASC App Store Server API credential configuration helpers (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.services import apple_iap


def test_apple_asc_api_configured_requires_all_three(tmp_path: Path, monkeypatch):
    key = tmp_path / "AuthKey_TEST.p8"
    key.write_text("-----BEGIN PRIVATE KEY-----\nMII\n-----END PRIVATE KEY-----\n")

    monkeypatch.setenv("IAP_APPLE_ASC_ISSUER_ID", "")
    monkeypatch.setenv("IAP_APPLE_ASC_KEY_ID", "4N9N354RG3")
    monkeypatch.setenv("IAP_APPLE_ASC_PRIVATE_KEY_PATH", str(key))
    get_settings.cache_clear()
    assert apple_iap.apple_asc_api_configured() is False

    monkeypatch.setenv("IAP_APPLE_ASC_ISSUER_ID", "00000000-0000-0000-0000-000000000001")
    get_settings.cache_clear()
    assert apple_iap.apple_asc_api_configured() is True

    monkeypatch.setenv("IAP_APPLE_ASC_PRIVATE_KEY_PATH", str(tmp_path / "missing.p8"))
    get_settings.cache_clear()
    assert apple_iap.apple_asc_api_configured() is False


def test_load_apple_asc_signing_key_rejects_non_pem(tmp_path: Path, monkeypatch):
    key = tmp_path / "bad.p8"
    key.write_text("not-a-pem\n")
    monkeypatch.setenv("IAP_APPLE_ASC_ISSUER_ID", "00000000-0000-0000-0000-000000000001")
    monkeypatch.setenv("IAP_APPLE_ASC_KEY_ID", "4N9N354RG3")
    monkeypatch.setenv("IAP_APPLE_ASC_PRIVATE_KEY_PATH", str(key))
    get_settings.cache_clear()
    with pytest.raises(ServiceUnavailableError, match="PEM"):
        apple_iap.load_apple_asc_signing_key()
