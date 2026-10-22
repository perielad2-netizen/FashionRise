"""Private fabric library: ownership, validation, soft-delete recovery."""

from __future__ import annotations

import io
from unittest.mock import patch

from PIL import Image

from app.models.fabric_asset import FabricAsset
from app.storage.local import LocalStorageBackend
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


def test_private_storage_outside_static_uploads(client, db_session):
    """Fabric bytes must not live under the directory mounted at /static/uploads."""
    tokens = register_with_invite(client, db_session, "fab_priv@example.com", "fab_priv")
    created = _upload(client, tokens, name="Private silk")
    assert created.status_code == 201, created.text
    asset_id = created.json()["id"]

    row = db_session.query(FabricAsset).filter(FabricAsset.id == asset_id).one()
    storage = LocalStorageBackend()
    path = storage.resolve_private_file(key=row.storage_key)
    assert path is not None and path.is_file()

    public_root = storage.public_upload_root()
    private_root = storage.private_fabric_root()
    resolved = path.resolve()
    assert str(resolved).startswith(str(private_root.resolve()))
    try:
        resolved.relative_to(public_root)
        raise AssertionError(f"fabric file is under public upload root: {resolved}")
    except ValueError:
        pass

    # Public static mount must not expose the private key (404 / missing).
    static_probe = client.get(f"/static/uploads/{row.storage_key}")
    assert static_probe.status_code == 404

    # Owner-auth image route still works.
    image = client.get(f"/api/v1/fabrics/{asset_id}/image", headers=_auth(tokens))
    assert image.status_code == 200
    assert image.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_oversized_dimensions_rejected_before_pixel_load(client, db_session, monkeypatch):
    """Header dimensions are rejected before Image.open / load decompresses pixels."""
    tokens = register_with_invite(client, db_session, "fab_dim@example.com", "fab_dim")

    from app.core.config import get_settings
    from app.core.upload_validation import probe_image_dimensions

    # Confirm PNG IHDR probe sees 96×96 without Pillow.
    assert probe_image_dimensions(_png_bytes(96, 96), "png") == (96, 96)

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_FABRIC_DIMENSION_PX", "48")
    get_settings.cache_clear()

    open_calls: list[str] = []
    original_open = Image.open

    def tracking_open(*args, **kwargs):
        open_calls.append("open")
        return original_open(*args, **kwargs)

    try:
        with patch.object(Image, "open", tracking_open):
            rejected = _upload(client, tokens, raw=_png_bytes(96, 96))
            assert rejected.status_code == 400
            assert open_calls == [], f"expected no Image.open before reject, got {open_calls}"

            accepted = _upload(client, tokens, raw=_png_bytes(32, 32), name="Ok size")
            assert accepted.status_code == 201, accepted.text
            assert open_calls, "accepted upload should decode via Image.open"
    finally:
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
