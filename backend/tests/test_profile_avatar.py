"""Private profile avatar upload + serve (not /static/uploads)."""

from __future__ import annotations

import io
import uuid

from PIL import Image
from sqlalchemy import select

from app.models.user import User
from app.models.user_profile import UserProfile
from app.services import profile_avatar_service
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def _jpeg_bytes(size: int = 120) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size + 40), color=(200, 40, 120)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_upload_and_get_profile_avatar(client, db_session):
    tokens = register_with_invite(client, db_session, "avatar_a@example.com", "avatarA")
    me = client.get("/api/v1/profiles/me", headers=_auth(tokens))
    assert me.status_code == 200
    user_id = me.json()["user_id"]

    upload = client.post(
        "/api/v1/profiles/me/avatar",
        headers=_auth(tokens),
        files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["avatar_url"] == f"/api/v1/profiles/{user_id}/avatar"

    path = LocalStorageBackend().resolve_private_avatar_file(
        user_id=uuid.UUID(user_id)
    )
    assert path is not None and path.is_file()

    served = client.get(f"/api/v1/profiles/{user_id}/avatar")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/jpeg")
    assert len(served.content) > 100


def test_avatar_missing_returns_404(client, db_session):
    tokens = register_with_invite(client, db_session, "avatar_b@example.com", "avatarB")
    me = client.get("/api/v1/profiles/me", headers=_auth(tokens)).json()
    res = client.get(f"/api/v1/profiles/{me['user_id']}/avatar")
    assert res.status_code == 404


def test_legacy_static_avatar_url_does_not_404_profile_when_no_private_file(
    client, db_session
):
    """Legacy /static/uploads avatar_url must not be rewritten; private route 404s
    until a private file exists — profile still returns the legacy URL."""
    tokens = register_with_invite(client, db_session, "avatar_legacy@example.com", "avatarLegacy")
    me = client.get("/api/v1/profiles/me", headers=_auth(tokens)).json()
    user_id = uuid.UUID(me["user_id"])
    profile = db_session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).scalar_one()
    legacy = "/static/uploads/avatars/legacy-noa.jpg"
    profile.avatar_url = legacy
    db_session.add(profile)
    db_session.commit()

    assert LocalStorageBackend().resolve_private_avatar_file(user_id=user_id) is None
    assert profile_avatar_service.resolve_avatar_file(db_session, user_id) is None

    got = client.get("/api/v1/profiles/me", headers=_auth(tokens))
    assert got.status_code == 200
    assert got.json()["avatar_url"] == legacy

    missing = client.get(f"/api/v1/profiles/{user_id}/avatar")
    assert missing.status_code == 404


def test_delete_account_removes_private_avatar_not_other_users(client, db_session):
    owner = register_with_invite(client, db_session, "avatar_del@example.com", "avatarDel")
    other = register_with_invite(client, db_session, "avatar_keep@example.com", "avatarKeep")

    owner_id = client.get("/api/v1/profiles/me", headers=_auth(owner)).json()["user_id"]
    other_id = client.get("/api/v1/profiles/me", headers=_auth(other)).json()["user_id"]

    assert (
        client.post(
            "/api/v1/profiles/me/avatar",
            headers=_auth(owner),
            files={"file": ("me.jpg", _jpeg_bytes(), "image/jpeg")},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/profiles/me/avatar",
            headers=_auth(other),
            files={"file": ("them.jpg", _jpeg_bytes(), "image/jpeg")},
        ).status_code
        == 200
    )

    owner_uuid = uuid.UUID(owner_id)
    other_uuid = uuid.UUID(other_id)
    owner_path = LocalStorageBackend().resolve_private_avatar_file(user_id=owner_uuid)
    other_path = LocalStorageBackend().resolve_private_avatar_file(user_id=other_uuid)
    assert owner_path is not None and owner_path.is_file()
    assert other_path is not None and other_path.is_file()
    other_bytes = other_path.read_bytes()

    deleted = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=_auth(owner),
        json={"confirm": "DELETE"},
    )
    assert deleted.status_code == 204, deleted.text

    assert db_session.execute(select(User).where(User.id == owner_uuid)).scalar_one_or_none() is None
    assert LocalStorageBackend().resolve_private_avatar_file(user_id=owner_uuid) is None
    kept = LocalStorageBackend().resolve_private_avatar_file(user_id=other_uuid)
    assert kept is not None and kept.is_file()
    assert kept.read_bytes() == other_bytes
