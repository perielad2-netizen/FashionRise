"""Auditable Create Model upload agreement (purpose create_model_upload)."""

from __future__ import annotations

from app.core.config import get_settings
from app.models.user_consent_event import PURPOSE_CREATE_MODEL_UPLOAD
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    clear_synthetic_croquis_notices,
    enable_synthetic_croquis_notices,
    record_upload_rights,
    storage_body,
    upload_rights_body,
)

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (40, 80, 160)).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_consent_rejects_stale_version_and_hash(client, db_session, monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    tokens = register_with_invite(client, db_session, "up_bad@example.com", "up_bad")
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code == 200
    assert client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body()).status_code == 200

    bad_ver = upload_rights_body()
    bad_ver["notice_version"] = "create-model-upload-stale"
    assert client.post(f"{BASE}/consent/upload", headers=_auth(tokens), json=bad_ver).status_code == 400

    bad_hash = upload_rights_body()
    bad_hash["notice_text_hash"] = "c" * 64
    assert client.post(f"{BASE}/consent/upload", headers=_auth(tokens), json=bad_hash).status_code == 400


def test_photo_upload_requires_create_model_upload_consent(client, db_session, monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()
    tokens = register_with_invite(client, db_session, "up_req@example.com", "up_req")
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code == 200
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200
    # Storage alone is not enough — missing create_model_upload agreement.
    denied = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("p.png", _png_bytes(), "image/png")},
        data={"sex": "female", "storage_consent_id": c.json()["id"], "display_name": "X"},
    )
    assert denied.status_code == 400, denied.text
    assert "upload agreement" in denied.json()["detail"].lower()

    record_upload_rights(client, tokens)
    ok = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("p.png", _png_bytes(), "image/png")},
        data={"sex": "female", "storage_consent_id": c.json()["id"], "display_name": "X"},
    )
    assert ok.status_code == 201, ok.text
    # Confirm the purpose was recorded for the user.
    from app.models.user_consent_event import UserConsentEvent

    rows = (
        db_session.query(UserConsentEvent)
        .filter(UserConsentEvent.purpose == PURPOSE_CREATE_MODEL_UPLOAD)
        .all()
    )
    assert len(rows) >= 1
    clear_synthetic_croquis_notices(monkeypatch)
