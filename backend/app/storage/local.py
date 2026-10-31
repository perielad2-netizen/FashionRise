import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings

_CROQUIS_KEY_RE = re.compile(
    r"^croquis/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"\.png$",
    re.IGNORECASE,
)


class LocalStorageBackend:
    def __init__(self) -> None:
        settings = get_settings()
        # Prefer upload_subdir; tolerate older upload_subdir naming if present.
        subdir = str(
            getattr(settings, "upload_subdir", None) or getattr(settings, "upload_subdir", "uploads")
        )
        self._root = Path(settings.local_storage_root)
        self._subdir = subdir
        self._private_fabric_subdir = str(
            getattr(settings, "private_fabric_subdir", "private_fabrics")
        )
        self._private_techpack_subdir = str(
            getattr(settings, "private_techpack_subdir", "private_techpacks")
        )
        self._private_croquis_subdir = str(
            getattr(settings, "private_croquis_subdir", "private_croquis")
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

    def private_croquis_root(self) -> Path:
        """Owner-private Create My Croquis bytes; never mounted as static files."""
        root = (self._root / self._private_croquis_subdir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(root, 0o700)
        except OSError:
            pass
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

    @staticmethod
    def validate_croquis_storage_key(key: str) -> tuple[uuid.UUID, uuid.UUID]:
        """Reject absolute paths, traversal, and non-UUID identities.

        Returns ``(owner_id, asset_id)`` parsed from the canonical key form
        ``croquis/{owner_uuid}/{asset_uuid}.png``.
        """
        if not key or not isinstance(key, str):
            raise ValueError("private croquis storage key required")
        if "\x00" in key:
            raise ValueError("private croquis storage key is invalid")
        if key.startswith(("/", "\\")) or "://" in key:
            raise ValueError("absolute or URL croquis storage keys are not allowed")
        if ".." in key or "\\" in key:
            raise ValueError("croquis storage key must not contain path traversal")
        normalized = key.strip().lstrip("/")
        match = _CROQUIS_KEY_RE.fullmatch(normalized)
        if match is None:
            raise ValueError("croquis storage key must be croquis/{owner}/{asset}.png")
        return uuid.UUID(match.group(1)), uuid.UUID(match.group(2))

    def _private_croquis_path(self, key: str) -> Path:
        owner_id, asset_id = self.validate_croquis_storage_key(key)
        # Rebuild from validated UUIDs only — never concatenate untrusted segments.
        return self.private_croquis_root() / "croquis" / str(owner_id) / f"{asset_id}.png"

    def _assert_under_croquis_root(self, path: Path) -> Path:
        resolved = path.resolve()
        private_root = self.private_croquis_root()
        public_root = self.public_upload_root()
        try:
            resolved.relative_to(private_root)
        except ValueError as exc:
            raise ValueError("private croquis path escapes private_croquis root") from exc
        try:
            resolved.relative_to(public_root)
        except ValueError:
            pass
        else:
            raise ValueError("refusing to store croquis under public upload root")
        # Reject symlink parents that escape after resolve (defense in depth).
        for parent in [resolved, *resolved.parents]:
            if parent == private_root or private_root in parent.parents or parent == private_root.parent:
                break
            if parent.is_symlink():
                link_target = parent.resolve()
                try:
                    link_target.relative_to(private_root)
                except ValueError as exc:
                    raise ValueError("croquis path symlink escapes private_croquis root") from exc
        return resolved

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

    def delete_private_techpack_file(self, *, key: str) -> None:
        """Best-effort remove of an uncommitted / orphaned private tech-pack PDF."""
        path = self.resolve_private_techpack_file(key=key)
        if path is not None and path.is_file():
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

    def save_private_croquis_file(
        self, *, key: str, data: BinaryIO, content_type: str | None = None
    ) -> Path:
        """Atomically write croquis bytes under ``private_croquis/`` (never public).

        Uses a same-directory temp file + fsync + rename. Refuses overwrite of an
        existing different path identity. Does **not** use ``save_private_file``
        (fabric-hardwired).
        """
        _ = content_type
        self.validate_croquis_storage_key(key)
        path = self._assert_under_croquis_root(self._private_croquis_path(key))
        if path.exists():
            raise ValueError("refusing to overwrite existing croquis asset")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass

        fd, tmp_name = tempfile.mkstemp(
            prefix=".tmp-croquis-",
            suffix=".png",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as out:
                while chunk := data.read(1024 * 1024):
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            os.replace(tmp_path, path)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            # Best-effort directory fsync for durability of the rename.
            try:
                dir_fd = os.open(str(path.parent), os.O_RDONLY)
            except OSError:
                dir_fd = -1
            if dir_fd >= 0:
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            raise
        return path

    def resolve_private_croquis_file(self, *, key: str) -> Path | None:
        try:
            path = self._assert_under_croquis_root(self._private_croquis_path(key))
        except ValueError:
            return None
        if path.is_file() and not path.is_symlink():
            return path
        return None

    def delete_private_croquis_file(self, *, key: str) -> bool:
        """Secure unlink of a private croquis file. Returns True if a file was removed.

        Does not claim that snapshots/backups are purged — only the live path.
        """
        try:
            path = self._assert_under_croquis_root(self._private_croquis_path(key))
        except ValueError:
            return False
        if path.is_symlink():
            return False
        if path.is_file():
            path.unlink()
            return True
        return False
