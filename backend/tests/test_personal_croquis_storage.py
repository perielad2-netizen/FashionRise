"""Dedicated private_croquis storage security tests."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.storage.croquis_unlink import CroquisUnlinkOutcome
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

    assert backend.delete_private_croquis_file(key=key) is CroquisUnlinkOutcome.REMOVED
    assert backend.resolve_private_croquis_file(key=key) is None
    assert backend.delete_private_croquis_file(key=key) is CroquisUnlinkOutcome.ALREADY_ABSENT


def test_refuses_overwrite_and_public_alias(storage_root):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    backend.save_private_croquis_file(key=key, data=io.BytesIO(b"one"))
    with pytest.raises(ValueError, match="overwrite"):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"two"))

    assert backend.private_croquis_root() != backend.private_fabric_root()
    assert backend.private_croquis_root() != backend.public_upload_root()


def test_no_clobber_race_against_existing_destination(storage_root, monkeypatch):
    """Simulate destination appearing between write and publish — must not clobber."""
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    dest = backend._private_croquis_path(key)
    dest.parent.mkdir(parents=True, exist_ok=True)

    real_link = os.link

    def race_link(src, dst):
        # Another writer created the destination first.
        Path(dst).write_bytes(b"preexisting")
        return real_link(src, dst)

    monkeypatch.setattr(os, "link", race_link)
    with pytest.raises(ValueError, match="overwrite"):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"new-bytes"))
    assert dest.read_bytes() == b"preexisting"


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
    link_path = link_parent / str(owner)
    link_path.symlink_to(outside, target_is_directory=True)

    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"
    with pytest.raises(ValueError):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"nope"))
    assert backend.resolve_private_croquis_file(key=key) is None
    assert backend.delete_private_croquis_file(key=key) is CroquisUnlinkOutcome.UNSAFE
    assert secret.read_bytes() == b"secret"


def test_in_root_symlink_alias_rejected(storage_root):
    """Symlink to another directory inside private_croquis must still be rejected."""
    backend = LocalStorageBackend()
    root = backend.private_croquis_root()
    real_owner = uuid.uuid4()
    alias_owner = uuid.uuid4()
    real_dir = root / "croquis" / str(real_owner)
    real_dir.mkdir(parents=True, exist_ok=True)
    (root / "croquis").mkdir(parents=True, exist_ok=True)
    alias = root / "croquis" / str(alias_owner)
    alias.symlink_to(real_dir, target_is_directory=True)

    asset = uuid.uuid4()
    key = f"croquis/{alias_owner}/{asset}.png"
    with pytest.raises(ValueError, match="symlink"):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"alias"))
    assert list(real_dir.glob("*.png")) == []


def test_atomic_write_cleans_temp_on_failure(storage_root, monkeypatch):
    backend = LocalStorageBackend()
    owner = uuid.uuid4()
    asset = uuid.uuid4()
    key = f"croquis/{owner}/{asset}.png"

    def boom_install(tmp_path, path):
        raise OSError("simulated publish failure")

    monkeypatch.setattr(backend, "_install_croquis_no_clobber", boom_install)
    with pytest.raises(OSError):
        backend.save_private_croquis_file(key=key, data=io.BytesIO(b"data"))

    parent = backend.private_croquis_root() / "croquis" / str(owner)
    if parent.exists():
        temps = list(parent.glob(".tmp-croquis-*"))
        assert temps == []
    assert backend.resolve_private_croquis_file(key=key) is None


def test_missing_file_resolve_returns_none(storage_root):
    backend = LocalStorageBackend()
    key = f"croquis/{uuid.uuid4()}/{uuid.uuid4()}.png"
    assert backend.resolve_private_croquis_file(key=key) is None


def test_unsafe_key_delete_outcome(storage_root):
    backend = LocalStorageBackend()
    assert backend.delete_private_croquis_file(key="../evil.png") is CroquisUnlinkOutcome.UNSAFE
