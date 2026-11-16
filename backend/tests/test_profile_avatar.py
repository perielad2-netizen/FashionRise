"""Private profile avatar upload + serve (not /static/uploads)."""

from __future__ import annotations

import io

from PIL import Image

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
        user_id=__import__("uuid").UUID(user_id)
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
