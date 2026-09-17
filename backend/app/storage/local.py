import os
import uuid
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlparse

from app.core.config import get_settings


def is_loopback_url(url: str) -> bool:
    """True for localhost / 127.x URLs. HTTP GET of these deadlocks the in-process AI worker."""
    host = (urlparse(str(url).strip()).hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return True
    return host.startswith("127.")


class LocalStorageBackend:
    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.local_storage_root)
        self._subdir = settings.upload_subdir
        self._public_base = settings.public_upload_base_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "")
        return self._root / self._subdir / safe

    def save_file(self, *, key: str | None, data: BinaryIO, content_type: str | None) -> str:
        _ = content_type
        if not key:
            key = f"{uuid.uuid4().hex}.bin"
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            while chunk := data.read(1024 * 1024):
                out.write(chunk)
        # public_upload_base_url mounts upload_subdir (e.g. /static/uploads → …/uploads)
        return f"{self._public_base}/{key.lstrip('/')}"

    def key_from_public_url(self, url: str) -> str | None:
        """Map a /static/uploads/... URL back to the storage key, ignoring host."""
        if not url or not str(url).strip():
            return None
        path = unquote(urlparse(str(url).strip()).path or "").replace("\\", "/")
        sub = (self._subdir or "uploads").strip("/")
        for prefix in (f"/{sub}/", "/static/uploads/", "/uploads/"):
            if prefix in path:
                key = path.split(prefix, 1)[1].lstrip("/")
                if key:
                    return key
        return None

    def read_public_url(self, url: str) -> bytes | None:
        """Read bytes from disk for our own public URL. Avoids HTTP self-fetch (uvicorn deadlock)."""
        key = self.key_from_public_url(url)
        if not key:
            return None
        path = self._full_path(key)
        if path.is_file():
            return path.read_bytes()
        return None

    def delete_file(self, *, key: str) -> None:
        path = self._full_path(key)
        if path.is_file():
            path.unlink()
