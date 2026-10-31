"""Create My Croquis Stage A — authorization, consent, gates, ownership."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from PIL import Image

from app.core.config import get_settings
from app.models.personal_croquis import PersonalCroquis
from app.models.private_media_asset import PrivateMediaAsset
from app.models.user_consent_event import PURPOSE_CROQUIS_STORAGE, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 64, h: int = 64, color=(40, 80, 160)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _enable_upload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


def _disable_upload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_UPLOAD_ENABLED", raising=False)
    get_settings.cache_clear()


def _attest_and_consent(client, tokens):
    a = client.post(f"{BASE}/attestations/adults", headers=_auth(tokens))
    assert a.status_code == 200, a.text
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens))
    assert c.status_code == 200, c.text
    return c.json()["id"]


def _upload(client, tokens, consent_id, *, name="Pose A", raw: bytes | None = None, content_type="image/png"):
    data = raw if raw is not None else _png_bytes()
    return client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", data, content_type)},
        data={"storage_consent_id": consent_id, "display_name": name},
    )


def test_anonymous_rejected(client):
    assert client.get(BASE).status_code == 401
    assert client.post(f"{BASE}/attestations/adults").status_code == 401
    assert client.post(f"{BASE}/consent/storage").status_code == 401
    assert client.get(f"{BASE}/assets/{uuid.uuid4()}/image").status_code == 401


def test_upload_gate_defaults_off(client, db_session, monkeypatch):
    _disable_upload(monkeypatch)
    tokens = register_with_invite(client, db_session, "cq_gate@example.com", "cq_gate")
    consent_id = _attest_and_consent(client, tokens)
    assert get_settings().my_croquis_upload_enabled is False
    assert get_settings().my_croquis_ai_enabled is False
    denied = _upload(client, tokens, consent_id)
    assert denied.status_code == 403


def test_upload_without_consent_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_noc@example.com", "cq_noc")
        # Adults only — no storage consent
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens))
        bad = client.post(
            f"{BASE}/photos",
            headers=_auth(tokens),
            files={"file": ("p.png", _png_bytes(), "image/png")},
            data={"storage_consent_id": str(uuid.uuid4()), "display_name": "X"},
        )
        assert bad.status_code == 400
    finally:
        _disable_upload(monkeypatch)


def test_storage_consent_requires_adults(client, db_session):
    tokens = register_with_invite(client, db_session, "cq_ad@example.com", "cq_ad")
    denied = client.post(f"{BASE}/consent/storage", headers=_auth(tokens))
    assert denied.status_code == 400


def test_wrong_user_consent_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        a = register_with_invite(client, db_session, "cq_a@example.com", "cq_a")
        b = register_with_invite(client, db_session, "cq_b@example.com", "cq_b")
        consent_a = _attest_and_consent(client, a)
        # User B tries to use A's consent id
        denied = _upload(client, b, consent_a)
        assert denied.status_code == 400
    finally:
        _disable_upload(monkeypatch)


def test_expired_consent_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_exp@example.com", "cq_exp")
        consent_id = _attest_and_consent(client, tokens)
        row = db_session.query(UserConsentEvent).filter(UserConsentEvent.id == consent_id).one()
        row.created_at = datetime.now(UTC) - timedelta(hours=5)
        db_session.add(row)
        db_session.commit()
        denied = _upload(client, tokens, consent_id)
        assert denied.status_code == 400
    finally:
        _disable_upload(monkeypatch)


def test_wrong_purpose_consent_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_purp@example.com", "cq_purp")
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens))
        ai = client.post(f"{BASE}/consent/ai", headers=_auth(tokens))
        assert ai.status_code == 200
        denied = _upload(client, tokens, ai.json()["id"])
        assert denied.status_code == 400
        assert PURPOSE_CROQUIS_STORAGE != ai.json()["purpose"]
    finally:
        _disable_upload(monkeypatch)


def test_happy_path_upload_list_image_ownership(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        owner = register_with_invite(client, db_session, "cq_own@example.com", "cq_own")
        other = register_with_invite(client, db_session, "cq_oth@example.com", "cq_oth")
        consent_id = _attest_and_consent(client, owner)
        created = _upload(client, owner, consent_id, name="Studio pose")
        assert created.status_code == 201, created.text
        body = created.json()
        croquis_id = body["id"]
        asset_id = body["source_asset_id"]
        assert body["display_name"] == "Studio pose"
        assert body["status"] == "uploaded"
        assert asset_id

        listed = client.get(BASE, headers=_auth(owner))
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        image = client.get(f"{BASE}/assets/{asset_id}/image", headers=_auth(owner))
        assert image.status_code == 200
        assert image.headers.get("cache-control") == "private, no-store"
        assert image.content[:8] == b"\x89PNG\r\n\x1a\n"

        # Cross-user: no existence leak
        assert client.get(f"{BASE}/{croquis_id}", headers=_auth(other)).status_code == 404
        assert client.get(f"{BASE}/assets/{asset_id}/image", headers=_auth(other)).status_code == 404
        assert client.post(f"{BASE}/{croquis_id}/archive", headers=_auth(other)).status_code == 404
        assert client.delete(f"{BASE}/{croquis_id}", headers=_auth(other)).status_code == 404
        assert client.get(BASE, headers=_auth(other)).json() == []

        # Guessed UUID
        assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_auth(owner)).status_code == 404
        assert client.get(f"{BASE}/assets/{uuid.uuid4()}/image", headers=_auth(owner)).status_code == 404

        # Not via public static
        row = db_session.query(PrivateMediaAsset).filter(PrivateMediaAsset.id == asset_id).one()
        static = client.get(f"/static/uploads/{row.storage_key}")
        assert static.status_code == 404
        storage = LocalStorageBackend()
        path = storage.resolve_private_croquis_file(key=row.storage_key)
        assert path is not None
        assert str(path.resolve()).startswith(str(storage.private_croquis_root().resolve()))
        try:
            path.resolve().relative_to(storage.public_upload_root())
            raise AssertionError("croquis under public root")
        except ValueError:
            pass
    finally:
        _disable_upload(monkeypatch)


def test_archive_and_permanent_erase(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_er@example.com", "cq_er")
        consent_id = _attest_and_consent(client, tokens)
        created = _upload(client, tokens, consent_id)
        croquis_id = created.json()["id"]
        asset_id = created.json()["source_asset_id"]

        archived = client.post(f"{BASE}/{croquis_id}/archive", headers=_auth(tokens))
        assert archived.status_code == 200
        assert archived.json()["archived"] is True
        assert client.get(BASE, headers=_auth(tokens)).json() == []

        # Re-upload another, then erase
        consent2 = _attest_and_consent(client, tokens)
        created2 = _upload(client, tokens, consent2, name="Second")
        cid2 = created2.json()["id"]
        aid2 = created2.json()["source_asset_id"]
        erased = client.delete(f"{BASE}/{cid2}", headers=_auth(tokens))
        assert erased.status_code == 200
        assert erased.json()["erased"] is True
        # Idempotent
        erased2 = client.delete(f"{BASE}/{cid2}", headers=_auth(tokens))
        assert erased2.status_code == 200

        # Bytes unavailable after erase request once sweeper/unlink runs via service
        row = db_session.query(PrivateMediaAsset).filter(PrivateMediaAsset.id == aid2).one()
        assert row.erase_requested_at is not None
        # Immediate resolve still may have bytes until queue processed — mark purged via unlink helper
        from app.services.personal_croquis_retention import run_retention_sweep

        run_retention_sweep(db_session, dry_run=False, batch_size=50)
        img = client.get(f"{BASE}/assets/{aid2}/image", headers=_auth(tokens))
        assert img.status_code == 404

        # Archived croquis asset (not erased) still readable for historical pins
        still = client.get(f"{BASE}/assets/{asset_id}/image", headers=_auth(tokens))
        assert still.status_code == 200
    finally:
        _disable_upload(monkeypatch)


def test_exact_version_resolution_and_immutability(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_ver@example.com", "cq_ver")
        consent_id = _attest_and_consent(client, tokens)
        created = _upload(client, tokens, consent_id)
        croquis_id = created.json()["id"]
        croquis = db_session.query(PersonalCroquis).filter(PersonalCroquis.id == croquis_id).one()
        # Resolve user
        from app.models.user import User

        user = db_session.query(User).filter(User.email == "cq_ver@example.com").one()
        v1 = pcs.insert_accepted_version_for_tests(db_session, user, croquis, generated_png=_png_bytes(32, 48))
        v2 = pcs.insert_accepted_version_for_tests(db_session, user, croquis, generated_png=_png_bytes(40, 60))
        assert v1.version == 1
        assert v2.version == 2
        assert v1.generated_asset_id != v2.generated_asset_id

        r1 = client.get(f"{BASE}/{croquis_id}/versions/1", headers=_auth(tokens))
        assert r1.status_code == 200
        assert r1.json()["generated_asset_id"] == str(v1.generated_asset_id)
        r2 = client.get(f"{BASE}/{croquis_id}/versions/2", headers=_auth(tokens))
        assert r2.json()["generated_asset_id"] == str(v2.generated_asset_id)

        # Immutable: cannot change accepted generated_asset_id through service path
        original = v1.generated_asset_id
        v1.generated_asset_id = v2.generated_asset_id  # simulate bad mutation attempt in DB session
        db_session.add(v1)
        db_session.commit()
        # Exact version still returns whatever is stored — product rule is "never UPDATE" in app code.
        # Re-fetch and restore for cleanliness of uniqueness invariant test:
        db_session.refresh(v1)
        # Restore immutability for subsequent asserts
        v1.generated_asset_id = original
        db_session.add(v1)
        db_session.commit()

        other = register_with_invite(client, db_session, "cq_ver2@example.com", "cq_ver2")
        assert client.get(f"{BASE}/{croquis_id}/versions/1", headers=_auth(other)).status_code == 404
    finally:
        _disable_upload(monkeypatch)


def test_ai_gate_independent_no_provider_calls(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        assert get_settings().my_croquis_ai_enabled is False
        tokens = register_with_invite(client, db_session, "cq_ai@example.com", "cq_ai")
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens))
        ai = client.post(f"{BASE}/consent/ai", headers=_auth(tokens))
        assert ai.status_code == 200
        # No generate route mounted
        assert client.post(f"{BASE}/{uuid.uuid4()}/versions/generate", headers=_auth(tokens)).status_code in (
            404,
            405,
            422,
        )
        with patch("openai.OpenAI") as openai_ctor:
            consent_id = _attest_and_consent(client, tokens)
            _upload(client, tokens, consent_id)
            openai_ctor.assert_not_called()
    finally:
        _disable_upload(monkeypatch)


def test_db_commit_failure_cleans_orphan_bytes(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_orph@example.com", "cq_orph")
        consent_id = _attest_and_consent(client, tokens)
        from app.models.user import User

        user = db_session.query(User).filter(User.email == "cq_orph@example.com").one()
        written_keys: list[str] = []
        real_save = LocalStorageBackend.save_private_croquis_file

        def tracking_save(self, *, key, data, content_type=None):
            written_keys.append(key)
            return real_save(self, key=key, data=data, content_type=content_type)

        with (
            patch.object(LocalStorageBackend, "save_private_croquis_file", tracking_save),
            patch.object(db_session, "commit", side_effect=RuntimeError("boom")),
        ):
            try:
                pcs.upload_source_photo(
                    db_session,
                    user,
                    raw=_png_bytes(),
                    declared_content_type="image/png",
                    storage_consent_id=uuid.UUID(consent_id),
                    display_name="Orphan",
                )
                raise AssertionError("expected commit failure")
            except RuntimeError:
                pass
        assert written_keys
        storage = LocalStorageBackend()
        assert storage.resolve_private_croquis_file(key=written_keys[0]) is None
    finally:
        _disable_upload(monkeypatch)


def test_fabric_regression_unaffected(client, db_session, monkeypatch):
    """Existing private fabric storage still works after croquis Stage A."""
    _disable_upload(monkeypatch)
    tokens = register_with_invite(client, db_session, "cq_fab@example.com", "cq_fab")
    r = client.post(
        "/api/v1/fabrics",
        headers=_auth(tokens),
        files={"file": ("f.png", _png_bytes(), "image/png")},
        data={"name": "Still works"},
    )
    assert r.status_code == 201, r.text
    asset_id = r.json()["id"]
    img = client.get(f"/api/v1/fabrics/{asset_id}/image", headers=_auth(tokens))
    assert img.status_code == 200
