import os
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings


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

    def delete_file(self, *, key: str) -> None:
        path = self._full_path(key)
        if path.is_file():
            path.unlink()
