"""Dedicated private_croquis storage security tests."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.storage.local import LocalStorageBackend


@pytest.fixture()
def storage_root(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield tmp_path / "storage"
    get_settings.cache_clear()
    monkeypatch.delenv("LOCAL_STORAGE_ROOT", raising=False)
    get_settings.cache_clear()


def test_croquis_key_validation_rejects_traversal(storage_root):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    good = f"croquis/{owner}/{asset}.png"
    backend.validate_croquis_storage_key(good)

    bad_keys = [
        "",
        "../etc/passwd",
        f"/croquis/{owner}/{asset}.png",
        f"croquis/{owner}/../{asset}.png",
        f"croquis/{owner}/{asset}.jpg",
        "croquis/not-a-uuid/also-bad.png",
        f"fabrics/{owner}/{asset}.png",
        f"croquis\\{owner}\\{asset}.png",
        f"croquis/{owner}/{asset}.png\x00.png",
        "http://evil/croquis/x",
    ]
    for key in bad_keys:
        with pytest.raises(ValueError):
            backend.validate_croquis_storage_key(key)


def test_save_resolve_delete_roundtrip(storage_root):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    path = backend.save_private_croquis_file(key=key, data=io.BytesIO(data))
    assert path.is_file()
    assert path.resolve().relative_to(backend.private_croquis_root())
    with pytest.raises(ValueError):
        path.resolve().relative_to(backend.public_upload_root())

    resolved = backend.resolve_private_croquis_file(key=key)
    assert resolved == path.resolve() or resolved == path
    assert resolved is not None and resolved.read_bytes() == data

    assert backend.delete_private_croquis_file(key=key) is True
    assert backend.resolve_private_croquis_file(key=key) is None
    assert backend.delete_private_croquis_file(key=key) is False  # idempotent


def test_refuses_overwrite_and_public_alias(storage_root):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    backend.save_private_croquis_file(key=key, data=io.BytesIO(b"one"))
    with pytest.raises(ValueError, match="overwrite"):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"two"))

    # Fabric hardwired method must not be used for croquis keys accidentally
    # (different root) — ensure dedicated root differs.
    assert backend.private_croquis_root() != backend.private_fabric_root()
    assert backend.private_croquis_root() != backend.public_upload_root()


def test_symlink_escape_rejected(storage_root):
    backend = LocalStorageBackend()
    outside = Path(storage_root).parent / "outside_escape"
    outside.mkdir(parents=True, exist_ok=True)
    secret = outside / "secret.bin"
    secret.write_bytes(b"secret")

    croquis_root = backend.private_croquis_root()
    link_parent = croquis_root / "croquis"
    link_parent.mkdir(parents=True, exist_ok=True)
    owner = uuid.uuid4()
    # Symlink owner directory to outside
    link_path = link_parent / str(owner)
    link_path.symlink_to(outside, target_is_directory=True)

    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    with pytest.raises(ValueError):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"nope"))
    assert backend.resolve_private_croquis_file(key=key) is None
    assert secret.read_bytes() == b"secret"


def test_atomic_write_cleans_temp_on_failure(storage_root, monkeypatch):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"

    real_replace = os.replace

    def boom_replace(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "replace", boom_replace)
    with pytest.raises(OSError):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"data"))
    monkeypatch.setattr(os, "replace", real_replace)

    parent = backend.private_croquis_root() / "croquis" / str(owner)
    if parent.exists():
        temps = list(parent.glob(".tmp-croquis-*"))
        assert temps == []
    assert backend.resolve_private_croquis_file(key=key) is None


def test_missing_file_resolve_returns_none(storage_root):
    backend = LocalStorageBackend()
    key = f"croquis/{uuid.uuid4()}/{uuid.uuid4()}.png"
    assert backend.resolve_private_croquis_file(key=key) is None
