import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings


class LocalStorageBackend:
    def __init__(self) -> None:
        settings = get_settings()
        # Prefer upload_subdir; tolerate older upload_subdir naming if present.
        subdir = getattr(settings, "upload_subdir", None) or getattr(settings, "upload_subdir", "uploads")
        self._root = Path(settings.local_storage_root)
        self._subdir = subdir
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
        # public_upload_base_url already mounts upload_subdir (/static/uploads → …/uploads)
        return f"{self._public_base}/{key.lstrip('/')}"

    def delete_file(self, *, key: str) -> None:
        path = self._full_path(key)
        if path.is_file():
            path.unlink()

    def key_from_public_url(self, url: str | None) -> str | None:
        """Map a stored public upload URL back to a storage key (no network)."""
        if not url or not isinstance(url, str):
            return None
        raw = url.strip()
        if not raw:
            return None
        base = f"{self._public_base}/"
        if raw.startswith(base):
            return raw[len(base) :].lstrip("/")
        marker = "/static/uploads/"
        if marker in raw:
            return raw.split(marker, 1)[1].lstrip("/")
        return None

    def resolve_existing_file(self, *, key: str) -> Path | None:
        path = self._full_path(key).resolve()
        root = (self._root / self._subdir).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if path.is_file():
            return path
        return None
