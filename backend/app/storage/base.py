from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Pluggable storage: local disk now, S3-compatible later."""

    def save_file(self, *, key: str, data: BinaryIO, content_type: str | None) -> str:
        """Persist binary data; return public URL or path for clients."""

    def delete_file(self, *, key: str) -> None:
        """Best-effort delete (optional for v1)."""
