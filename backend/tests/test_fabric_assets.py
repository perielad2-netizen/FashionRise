"""Private fabric library: ownership, validation, soft-delete recovery."""

from __future__ import annotations

import io

from PIL import Image

from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 64, h: int = 64, color=(180, 40, 80)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, tokens, *, name="Silk test", raw: bytes | None = None, content_type="image/png"):
    data = raw if raw is not None else _png_bytes()
    return client.post(
        "/api/v1/fabrics",
        headers=_auth(tokens),
        files={"file": ("fabric.png", data, content_type)},
        data={"name": name},
    )


def test_upload_list_and_owner_image(client, db_session):
    tokens = register_with_invite(client, db_session, "fab_a@example.com", "fab_a")
    created = _upload(client, tokens, name="Rose silk")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Rose silk"
    assert body["width"] == 64
    assert body["height"] == 64
    assert body["content_type"] == "image/png"
    assert body["deleted"] is False
    asset_id = body["id"]

    listed = client.get("/api/v1/fabrics", headers=_auth(tokens))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == asset_id

    image = client.get(f"/api/v1/fabrics/{asset_id}/image", headers=_auth(tokens))
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/png")
    assert image.headers.get("cache-control") == "private, no-store"
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_cross_account_denied(client, db_session):
    a = register_with_invite(client, db_session, "fab_own@example.com", "fab_own")
    b = register_with_invite(client, db_session, "fab_other@example.com", "fab_other")
    created = _upload(client, a)
    asset_id = created.json()["id"]

    denied = client.get(f"/api/v1/fabrics/{asset_id}/image", headers=_auth(b))
    assert denied.status_code == 404

    meta = client.get(f"/api/v1/fabrics/{asset_id}", headers=_auth(b))
    assert meta.status_code == 404

    anon = client.get(f"/api/v1/fabrics/{asset_id}/image")
    assert anon.status_code == 401


def test_rejects_invalid_and_oversized(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "fab_bad@example.com", "fab_bad")

    bad = client.post(
        "/api/v1/fabrics",
        headers=_auth(tokens),
        files={"file": ("x.bin", b"not-an-image", "image/png")},
        data={"name": "Nope"},
    )
    assert bad.status_code == 400

    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_FABRIC_DIMENSION_PX", "32")
    get_settings.cache_clear()
    huge = _upload(client, tokens, raw=_png_bytes(64, 64))
    assert huge.status_code == 400
    get_settings.cache_clear()
    monkeypatch.delenv("MAX_FABRIC_DIMENSION_PX", raising=False)
    get_settings.cache_clear()


def test_soft_delete_hides_from_library_but_image_still_loads(client, db_session):
    tokens = register_with_invite(client, db_session, "fab_del@example.com", "fab_del")
    created = _upload(client, tokens, name="Keep for history")
    asset_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/fabrics/{asset_id}", headers=_auth(tokens))
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    listed = client.get("/api/v1/fabrics", headers=_auth(tokens))
    assert listed.status_code == 200
    assert listed.json() == []

    # Historical designs can still fetch the bytes for the owner.
    image = client.get(f"/api/v1/fabrics/{asset_id}/image", headers=_auth(tokens))
    assert image.status_code == 200
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"

    meta = client.get(f"/api/v1/fabrics/{asset_id}", headers=_auth(tokens))
    assert meta.status_code == 200
    assert meta.json()["deleted"] is True
