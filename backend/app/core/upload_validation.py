"""Image upload validation: size, declared content-type, magic bytes."""

from __future__ import annotations

import struct
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


def probe_image_dimensions(data: bytes, kind: str) -> tuple[int, int] | None:
    """Read width/height from container headers without decompressing pixels.

    Returns None when headers are incomplete or unrecognized (caller may fall
    back to a library open + size check). Used to reject oversized uploads
    before expensive Image.load() / decode work.
    """
    if kind == "png":
        # Signature (8) + IHDR length/type (8) + width/height (8)
        if len(data) < 24 or not data.startswith(_PNG[0]):
            return None
        if data[12:16] != b"IHDR":
            return None
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if kind == "jpeg":
        # Walk markers until SOF0/1/2/3 (baseline/extended/progressive).
        i = 2
        n = len(data)
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            while i < n and data[i] == 0xFF:
                i += 1
            if i >= n:
                break
            marker = data[i]
            i += 1
            if marker in (0xD8, 0xD9):  # SOI / EOI
                continue
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # TEM / RSTn
                continue
            if i + 1 >= n:
                break
            seg_len = struct.unpack(">H", data[i : i + 2])[0]
            if seg_len < 2 or i + seg_len > n:
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3) and seg_len >= 7:
                height, width = struct.unpack(">HH", data[i + 3 : i + 7])
                return int(width), int(height)
            i += seg_len
        return None

    if kind == "webp":
        if len(data) < 30 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
            return None
        fourcc = data[12:16]
        if fourcc == b"VP8X" and len(data) >= 30:
            # Canvas width/height are 24-bit little-endian (minus one).
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return w, h
        if fourcc == b"VP8 " and len(data) >= 30:
            # Lossy bitstream: sync code 0x9d012a then 14-bit width/height.
            if data[23:26] != b"\x9d\x01\x2a":
                return None
            wh = struct.unpack("<HH", data[26:30])
            return wh[0] & 0x3FFF, wh[1] & 0x3FFF
        if fourcc == b"VP8L" and len(data) >= 25:
            # Lossless: signature 0x2f then 14-bit width-1 / height-1 packed.
            if data[20] != 0x2F:
                return None
            bits = int.from_bytes(data[21:25], "little")
            w = (bits & 0x3FFF) + 1
            h = ((bits >> 14) & 0x3FFF) + 1
            return w, h
        return None

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
