"""FashionRise Social — editable profile privacy + My Models publish consent."""

from __future__ import annotations

import hashlib
import io
import uuid

from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models.gallery_item import GalleryItem
from app.models.personal_croquis import (
    VERSION_STATUS_ACCEPTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.models.user import User
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _user(db, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 96), color=(40, 80, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_accepted_croquis(db, user: User, *, name: str = "Studio model") -> PersonalCroquis:
    storage = LocalStorageBackend()
    asset_id = uuid.uuid4()
    key = f"croquis/{user.id}/{asset_id}.png"
    raw = _png_bytes()
    storage.save_private_croquis_file(key=key, data=io.BytesIO(raw), content_type="image/png")
    asset = PrivateMediaAsset(
        id=asset_id,
        owner_id=user.id,
        kind=KIND_CROQUIS_GENERATED,
        content_type="image/png",
        width=64,
        height=96,
        byte_size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        storage_key=key,
    )
    croquis = PersonalCroquis(
        id=uuid.uuid4(),
        owner_id=user.id,
        display_name=name,
        status="uploaded",
    )
    db.add_all([asset, croquis])
    db.flush()
    version = PersonalCroquisVersion(
        id=uuid.uuid4(),
        croquis_id=croquis.id,
        owner_id=user.id,
        version=1,
        generated_asset_id=asset.id,
        status=VERSION_STATUS_ACCEPTED,
    )
    db.add(version)
    db.commit()
    return croquis


def test_public_profile_hides_private_design_inventory(client, db_session):
    tokens = register_with_invite(client, db_session, "prof_a@example.com", "profA")
    other = register_with_invite(client, db_session, "prof_b@example.com", "profB")
    me = _user(db_session, "prof_a@example.com")

    own = client.get("/api/v1/profiles/me", headers=_auth(tokens))
    assert own.status_code == 200
    # Owner may see private inventory count field (can be 0).
    assert "designs_count" in own.json()

    public = client.get(f"/api/v1/profiles/{me.id}", headers=_auth(other))
    assert public.status_code == 200
    body = public.json()
    assert body["designs_count"] == 0
    assert "email" not in body
    assert body["display_name"]


def test_update_own_profile(client, db_session):
    tokens = register_with_invite(client, db_session, "edit_p@example.com", "editP")
    res = client.put(
        "/api/v1/profiles/me",
        headers=_auth(tokens),
        json={"display_name": "Nova Atelier", "bio": "Evening wear & knits."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == "Nova Atelier"
    assert body["bio"] == "Evening wear & knits."


def test_publish_personal_croquis_requires_consent_and_accepted(client, db_session):
    tokens = register_with_invite(client, db_session, "model_p@example.com", "modelP")
    user = _user(db_session, "model_p@example.com")
    croquis = _seed_accepted_croquis(db_session, user)
    settings = get_settings()
    notice = settings.croquis_public_share_notice_text
    digest = hashlib.sha256(notice.encode("utf-8")).hexdigest()

    denied = client.post(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": "0" * 64,
        },
    )
    assert denied.status_code == 422, denied.text
    assert "does not match" in denied.text.lower()

    ok = client.post(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": digest,
        },
    )
    assert ok.status_code == 200, ok.text
    item = ok.json()
    assert item["title"] == croquis.display_name
    assert item["image_url"]
    assert "/static/uploads/" in item["image_url"] or item["image_url"].startswith("http")

    listed = client.get("/api/v1/personal-croquis", headers=_auth(tokens))
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["id"] == str(croquis.id))
    assert row["fashionrise_item_id"] == item["id"]

    # Public gallery lists it for the designer.
    gallery = client.get(f"/api/v1/gallery/user/{user.id}")
    assert gallery.status_code == 200
    assert any(g["id"] == item["id"] for g in gallery.json())

    unpub = client.delete(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
    )
    assert unpub.status_code == 200, unpub.text
    assert unpub.json()["fashionrise_item_id"] is None
    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is None


def test_permanent_erase_removes_public_fashionrise_copy(client, db_session):
    tokens = register_with_invite(client, db_session, "erase_p@example.com", "eraseP")
    user = _user(db_session, "erase_p@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Erase me")
    private = _seed_accepted_croquis(db_session, user, name="Stay private")
    settings = get_settings()
    digest = hashlib.sha256(settings.croquis_public_share_notice_text.encode("utf-8")).hexdigest()

    published = client.post(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": digest,
        },
    )
    assert published.status_code == 200, published.text
    item = published.json()
    item_id = uuid.UUID(item["id"])
    storage = LocalStorageBackend()
    public_key = storage.key_from_public_url(item["image_url"])
    assert public_key
    assert storage.resolve_existing_file(key=public_key) is not None

    # Unrelated private model stays private and is not touched by erase of another.
    assert (
        db_session.scalar(select(GalleryItem).where(GalleryItem.croquis_id == private.id))
        is None
    )

    erased = client.delete(
        f"/api/v1/personal-croquis/{croquis.id}",
        headers=_auth(tokens),
    )
    assert erased.status_code == 200, erased.text
    assert db_session.get(GalleryItem, item_id) is None
    assert storage.resolve_existing_file(key=public_key) is None

    gallery = client.get(f"/api/v1/gallery/user/{user.id}")
    assert gallery.status_code == 200
    assert all(g["id"] != str(item_id) for g in gallery.json())

    # Repeated erase is safe.
    again = client.delete(
        f"/api/v1/personal-croquis/{croquis.id}",
        headers=_auth(tokens),
    )
    assert again.status_code == 200, again.text

    # Cannot re-publish an erased model.
    blocked = client.post(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": digest,
        },
    )
    assert blocked.status_code in (404, 422), blocked.text

    # Unpublished / private model still exists and is unaffected.
    listed = client.get("/api/v1/personal-croquis", headers=_auth(tokens))
    assert listed.status_code == 200
    ids = {r["id"] for r in listed.json()}
    assert str(private.id) in ids
    assert str(croquis.id) not in ids


def test_account_deletion_unlinks_public_my_model_copies(client, db_session):
    tokens = register_with_invite(client, db_session, "acct_p@example.com", "acctP")
    user = _user(db_session, "acct_p@example.com")
    croquis = _seed_accepted_croquis(db_session, user, name="Account model")
    settings = get_settings()
    digest = hashlib.sha256(settings.croquis_public_share_notice_text.encode("utf-8")).hexdigest()

    published = client.post(
        f"/api/v1/personal-croquis/{croquis.id}/publish",
        headers=_auth(tokens),
        json={
            "public_share_attested": True,
            "notice_version": settings.croquis_public_share_consent_version,
            "notice_text_hash": digest,
        },
    )
    assert published.status_code == 200, published.text
    item = published.json()
    storage = LocalStorageBackend()
    public_key = storage.key_from_public_url(item["image_url"])
    assert public_key
    assert storage.resolve_existing_file(key=public_key) is not None

    deleted = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_auth(tokens),
        json={"confirm": "DELETE"},
    )
    assert deleted.status_code == 204, deleted.text
    assert storage.resolve_existing_file(key=public_key) is None
    assert db_session.get(GalleryItem, uuid.UUID(item["id"])) is None
