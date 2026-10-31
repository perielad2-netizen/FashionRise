"""Create My Croquis Stage A — authorization, consent, gates, ownership."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.personal_croquis import (
    VERSION_STATUS_ACCEPTED,
    VERSION_STATUS_GENERATING,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.models.user_consent_event import PURPOSE_CROQUIS_STORAGE, UserConsentEvent
from app.services import personal_croquis_service as pcs
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    clear_synthetic_croquis_notices,
    enable_synthetic_croquis_notices,
    storage_body,
)

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
    a = client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
    assert a.status_code == 200, a.text
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
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


@pytest.fixture(autouse=True)
def _synthetic_notices(monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    yield
    clear_synthetic_croquis_notices(monkeypatch)


def test_anonymous_rejected(client):
    assert client.get(BASE).status_code == 401
    assert client.post(f"{BASE}/attestations/adults", json=adults_body()).status_code == 401
    assert client.post(f"{BASE}/consent/storage", json=storage_body()).status_code == 401
    assert client.get(f"{BASE}/assets/{uuid.uuid4()}/image").status_code == 401


def test_consent_empty_body_rejected(client, db_session):
    tokens = register_with_invite(client, db_session, "cq_empty@example.com", "cq_empty")
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens)).status_code == 422
    assert client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json={}).status_code == 422
    assert (
        client.post(
            f"{BASE}/attestations/adults",
            headers=_auth(tokens),
            json={"adults_attested": False, "notice_version": "x", "notice_text_hash": "a" * 64},
        ).status_code
        == 422
    )


def test_consent_fail_closed_without_approved_notice(client, db_session, monkeypatch):
    clear_synthetic_croquis_notices(monkeypatch)
    tokens = register_with_invite(client, db_session, "cq_no_notice@example.com", "cq_no_notice")
    denied = client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
    assert denied.status_code == 503
    enable_synthetic_croquis_notices(monkeypatch)


def test_consent_wrong_hash_and_version_rejected(client, db_session):
    tokens = register_with_invite(client, db_session, "cq_badhash@example.com", "cq_badhash")
    bad_hash = adults_body()
    bad_hash["notice_text_hash"] = "b" * 64
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=bad_hash).status_code == 400
    bad_ver = adults_body()
    bad_ver["notice_version"] = "not-the-current-version"
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=bad_ver).status_code == 400


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
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
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
    denied = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert denied.status_code == 400


def test_wrong_user_consent_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        a = register_with_invite(client, db_session, "cq_a@example.com", "cq_a")
        b = register_with_invite(client, db_session, "cq_b@example.com", "cq_b")
        consent_a = _attest_and_consent(client, a)
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
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
        ai = client.post(f"{BASE}/consent/ai", headers=_auth(tokens), json=ai_body())
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

        assert client.get(f"{BASE}/{croquis_id}", headers=_auth(other)).status_code == 404
        assert client.get(f"{BASE}/assets/{asset_id}/image", headers=_auth(other)).status_code == 404
        assert client.post(f"{BASE}/{croquis_id}/archive", headers=_auth(other)).status_code == 404
        assert client.delete(f"{BASE}/{croquis_id}", headers=_auth(other)).status_code == 404
        assert client.get(BASE, headers=_auth(other)).json() == []

        assert client.get(f"{BASE}/{uuid.uuid4()}", headers=_auth(owner)).status_code == 404
        assert client.get(f"{BASE}/assets/{uuid.uuid4()}/image", headers=_auth(owner)).status_code == 404

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

        consent2 = _attest_and_consent(client, tokens)
        created2 = _upload(client, tokens, consent2, name="Second")
        cid2 = created2.json()["id"]
        aid2 = created2.json()["source_asset_id"]
        erased = client.delete(f"{BASE}/{cid2}", headers=_auth(tokens))
        assert erased.status_code == 200
        assert erased.json()["erased"] is True
        erased2 = client.delete(f"{BASE}/{cid2}", headers=_auth(tokens))
        assert erased2.status_code == 200

        row = db_session.query(PrivateMediaAsset).filter(PrivateMediaAsset.id == aid2).one()
        assert row.erase_requested_at is not None
        from app.services.personal_croquis_retention import run_retention_sweep

        run_retention_sweep(db_session, dry_run=False, batch_size=50)
        img = client.get(f"{BASE}/assets/{aid2}/image", headers=_auth(tokens))
        assert img.status_code == 404

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
        from app.models.user import User

        user = db_session.query(User).filter(User.email == "cq_ver@example.com").one()
        v1 = pcs.insert_accepted_version_for_tests(
            db_session, user, croquis, generated_png=_png_bytes(32, 48)
        )
        v2 = pcs.insert_accepted_version_for_tests(
            db_session, user, croquis, generated_png=_png_bytes(40, 60)
        )
        assert v1.version == 1
        assert v2.version == 2
        assert v1.generated_asset_id != v2.generated_asset_id
        original_v1_asset = v1.generated_asset_id
        original_v2_asset = v2.generated_asset_id
        v1_id = v1.id
        v2_id = v2.id

        r1 = client.get(f"{BASE}/{croquis_id}/versions/1", headers=_auth(tokens))
        assert r1.status_code == 200
        assert r1.json()["generated_asset_id"] == str(original_v1_asset)
        r2 = client.get(f"{BASE}/{croquis_id}/versions/2", headers=_auth(tokens))
        assert r2.json()["generated_asset_id"] == str(original_v2_asset)

        # P0-1: accepted generated_asset_id mutation must FAIL (savepoint keeps session alive).
        with pytest.raises(IntegrityError), db_session.begin_nested():
            v1.generated_asset_id = original_v2_asset
            db_session.add(v1)
            db_session.flush()
        db_session.expire_all()
        v1b = db_session.get(PersonalCroquisVersion, v1_id)
        v2b = db_session.get(PersonalCroquisVersion, v2_id)
        assert v1b is not None and v1b.generated_asset_id == original_v1_asset
        assert v2b is not None and v2b.generated_asset_id == original_v2_asset

        other = register_with_invite(client, db_session, "cq_ver2@example.com", "cq_ver2")
        assert client.get(f"{BASE}/{croquis_id}/versions/1", headers=_auth(other)).status_code == 404
    finally:
        _disable_upload(monkeypatch)


def test_pre_accept_status_transition_allowed(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        tokens = register_with_invite(client, db_session, "cq_pre@example.com", "cq_pre")
        consent_id = _attest_and_consent(client, tokens)
        created = _upload(client, tokens, consent_id)
        from app.models.user import User

        user = db_session.query(User).filter(User.email == "cq_pre@example.com").one()
        croquis = db_session.query(PersonalCroquis).filter(PersonalCroquis.id == created.json()["id"]).one()
        asset_id = uuid.uuid4()
        key = f"croquis/{user.id}/{asset_id}.png"
        LocalStorageBackend().save_private_croquis_file(key=key, data=io.BytesIO(_png_bytes(8, 8)))
        asset = PrivateMediaAsset(
            id=asset_id,
            owner_id=user.id,
            kind=KIND_CROQUIS_GENERATED,
            content_type="image/png",
            width=8,
            height=8,
            byte_size=16,
            sha256="c" * 64,
            storage_key=key,
        )
        db_session.add(asset)
        db_session.flush()
        ver = PersonalCroquisVersion(
            id=uuid.uuid4(),
            croquis_id=croquis.id,
            owner_id=user.id,
            version=1,
            generated_asset_id=None,
            status=VERSION_STATUS_GENERATING,
        )
        db_session.add(ver)
        db_session.commit()
        # Legitimate pre-accept transition
        ver.status = VERSION_STATUS_ACCEPTED
        ver.generated_asset_id = asset_id
        ver.accepted_at = datetime.now(UTC)
        db_session.add(ver)
        db_session.commit()
        db_session.refresh(ver)
        assert ver.status == VERSION_STATUS_ACCEPTED
        assert ver.generated_asset_id == asset_id
    finally:
        _disable_upload(monkeypatch)


def test_cross_owner_generated_asset_rejected(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        a = register_with_invite(client, db_session, "cq_own_a@example.com", "cq_own_a")
        b = register_with_invite(client, db_session, "cq_own_b@example.com", "cq_own_b")
        consent_a = _attest_and_consent(client, a)
        consent_b = _attest_and_consent(client, b)
        ca = _upload(client, a, consent_a).json()
        _upload(client, b, consent_b).json()
        from app.models.user import User

        user_a = db_session.query(User).filter(User.email == "cq_own_a@example.com").one()
        user_b = db_session.query(User).filter(User.email == "cq_own_b@example.com").one()
        croquis_a = db_session.get(PersonalCroquis, uuid.UUID(ca["id"]))
        assert croquis_a is not None
        # Create a generated asset owned by B
        asset_id = uuid.uuid4()
        key = f"croquis/{user_b.id}/{asset_id}.png"
        LocalStorageBackend().save_private_croquis_file(key=key, data=io.BytesIO(_png_bytes(8, 8)))
        db_session.add(
            PrivateMediaAsset(
                id=asset_id,
                owner_id=user_b.id,
                kind=KIND_CROQUIS_GENERATED,
                content_type="image/png",
                width=8,
                height=8,
                byte_size=16,
                sha256="d" * 64,
                storage_key=key,
            )
        )
        db_session.flush()
        with pytest.raises(IntegrityError), db_session.begin_nested():
            ver = PersonalCroquisVersion(
                id=uuid.uuid4(),
                croquis_id=croquis_a.id,
                owner_id=user_a.id,
                version=1,
                generated_asset_id=asset_id,
                status=VERSION_STATUS_ACCEPTED,
                accepted_at=datetime.now(UTC),
            )
            db_session.add(ver)
            db_session.flush()
    finally:
        _disable_upload(monkeypatch)


def test_ai_gate_independent_no_provider_calls(client, db_session, monkeypatch):
    _enable_upload(monkeypatch)
    try:
        assert get_settings().my_croquis_ai_enabled is False
        tokens = register_with_invite(client, db_session, "cq_ai@example.com", "cq_ai")
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
        ai = client.post(f"{BASE}/consent/ai", headers=_auth(tokens), json=ai_body())
        assert ai.status_code == 200
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
