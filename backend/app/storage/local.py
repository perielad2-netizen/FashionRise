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
        self._private_fabric_subdir = getattr(settings, "private_fabric_subdir", "private_fabrics")
        self._private_techpack_subdir = getattr(
            settings, "private_techpack_subdir", "private_techpacks"
        )
        self._public_base = settings.public_upload_base_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def public_upload_root(self) -> Path:
        """Directory mounted at `/static/uploads` — never store private fabrics here."""
        return (self._root / self._subdir).resolve()

    def private_fabric_root(self) -> Path:
        """Owner-private fabric bytes; not mounted as static files."""
        root = (self._root / self._private_fabric_subdir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def private_techpack_root(self) -> Path:
        """Owner-private tech-pack PDFs; not mounted as static files."""
        root = (self._root / self._private_techpack_subdir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _full_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "")
        return self._root / self._subdir / safe

    def _private_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "")
        return self.private_fabric_root() / safe

    def _private_techpack_path(self, key: str) -> Path:
        safe = key.lstrip("/").replace("..", "")
        return self.private_techpack_root() / safe

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
        root = self.public_upload_root()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        if path.is_file():
            return path
        return None

    def save_private_file(self, *, key: str, data: BinaryIO, content_type: str | None = None) -> Path:
        """Write bytes under the private fabric root (never under `/static/uploads`)."""
        _ = content_type
        if not key:
            raise ValueError("private storage key required")
        path = self._private_path(key).resolve()
        private_root = self.private_fabric_root()
        public_root = self.public_upload_root()
        try:
            path.relative_to(private_root)
        except ValueError as exc:
            raise ValueError("private storage path escapes private root") from exc
        try:
            path.relative_to(public_root)
        except ValueError:
            pass
        else:
            raise ValueError("refusing to store private fabric under public upload root")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            while chunk := data.read(1024 * 1024):
                out.write(chunk)
        return path

    def resolve_private_file(self, *, key: str) -> Path | None:
        path = self._private_path(key).resolve()
        private_root = self.private_fabric_root()
        public_root = self.public_upload_root()
        try:
            path.relative_to(private_root)
        except ValueError:
            return None
        try:
            path.relative_to(public_root)
        except ValueError:
            pass
        else:
            return None
        if path.is_file():
            return path
        return None

    def save_private_techpack_file(self, *, key: str, data: BinaryIO, content_type: str | None = None) -> Path:
        """Write tech-pack bytes under the private techpack root (never public uploads)."""
        _ = content_type
        if not key:
            raise ValueError("private techpack storage key required")
        path = self._private_techpack_path(key).resolve()
        private_root = self.private_techpack_root()
        public_root = self.public_upload_root()
        try:
            path.relative_to(private_root)
        except ValueError as exc:
            raise ValueError("private techpack path escapes private root") from exc
        try:
            path.relative_to(public_root)
        except ValueError:
            pass
        else:
            raise ValueError("refusing to store techpack under public upload root")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            while chunk := data.read(1024 * 1024):
                out.write(chunk)
        return path

    def resolve_private_techpack_file(self, *, key: str) -> Path | None:
        path = self._private_techpack_path(key).resolve()
        private_root = self.private_techpack_root()
        public_root = self.public_upload_root()
        try:
            path.relative_to(private_root)
        except ValueError:
            return None
        try:
            path.relative_to(public_root)
        except ValueError:
            pass
        else:
            return None
        if path.is_file():
            return path
        return None
