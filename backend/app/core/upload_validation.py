"""Image upload validation: size, declared content-type, magic bytes."""

from __future__ import annotations

from typing import BinaryIO

# Magic signatures (first bytes)
_JPEG = (b"\xff\xd8\xff",)
_PNG = (b"\x89PNG\r\n\x1a\n",)
_WEBP = (b"RIFF", b"WEBP")  # RIFF....WEBP at offset 8


def sniff_image_kind(data: bytes) -> str | None:
    """Return a canonical kind: jpeg, png, webp — or None if unrecognized."""
    if len(data) >= 3 and data.startswith(_JPEG[0]):
        return "jpeg"
    if len(data) >= 8 and data.startswith(_PNG[0]):
        return "png"
    if len(data) >= 12 and data[0:4] == _WEBP[0] and data[8:12] == _WEBP[1]:
        return "webp"
    return None


def read_stream_with_limit(stream: BinaryIO, max_bytes: int) -> bytes:
    """Read full stream; raise ValueError if total size exceeds max_bytes."""
    out = bytearray()
    chunk_size = min(1024 * 1024, max_bytes)
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        out.extend(chunk)
        if len(out) > max_bytes:
            raise ValueError("upload_too_large")
    return bytes(out)


def extension_for_kind(kind: str) -> str:
    return {"jpeg": "jpg", "png": "png", "webp": "webp"}.get(kind, "bin")
