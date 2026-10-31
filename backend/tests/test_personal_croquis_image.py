"""EXIF orientation + GPS strip + MIME validation for croquis sources."""

from __future__ import annotations

import io
import struct

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.personal_croquis_image import normalize_croquis_source_bytes


def _png(w=32, h=48, color=(10, 20, 30)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif_orientation(orientation: int = 6) -> bytes:
    """Build a JPEG with EXIF Orientation tag (no GPS).

    Orientation 6 = rotate 90 CW, so a 40×20 image becomes 20×40 after transpose.
    """
    img = Image.new("RGB", (40, 20), (200, 50, 50))
    # piexif optional — craft minimal EXIF manually if needed via Pillow
    exif = img.getexif()
    exif[274] = orientation  # Orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif, quality=90)
    return buf.getvalue()


def test_exif_orientation_applied_before_strip():
    raw = _jpeg_with_exif_orientation(6)
    before = Image.open(io.BytesIO(raw))
    assert before.size == (40, 20)
    assert before.getexif().get(274) == 6
    data, ct, w, h = normalize_croquis_source_bytes(raw, declared_content_type="image/jpeg")
    assert ct == "image/png"
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # Orientation 6 → transposed to 20×40
    assert (w, h) == (20, 40)
    out = Image.open(io.BytesIO(data))
    assert out.getexif().get(274) in (None, 1)
    # Re-encoded PNG must not retain JPEG EXIF/GPS payloads
    assert 34853 not in out.getexif()
    assert b"Exif" not in data


def test_normalized_png_has_no_exif_blob():
    raw = _jpeg_with_exif_orientation(1)
    assert b"Exif" in raw or Image.open(io.BytesIO(raw)).getexif()
    data, _, _, _ = normalize_croquis_source_bytes(raw, declared_content_type="image/jpeg")
    out = Image.open(io.BytesIO(data))
    assert dict(out.getexif()) == {} or all(
        k not in out.getexif() for k in (274, 34853, 37500)
    )
    assert b"Exif" not in data


def test_mime_mismatch_and_malformed():
    png = _png()
    with pytest.raises(HTTPException) as mismatch:
        normalize_croquis_source_bytes(png, declared_content_type="image/jpeg")
    assert mismatch.value.status_code == 400

    with pytest.raises(HTTPException) as bad:
        normalize_croquis_source_bytes(b"not-an-image", declared_content_type="image/png")
    assert bad.value.status_code == 400


def test_oversized_dimensions_rejected(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_CROQUIS_DIMENSION_PX", "40")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            normalize_croquis_source_bytes(_png(80, 80), declared_content_type="image/png")
        assert exc.value.status_code == 400
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("MAX_CROQUIS_DIMENSION_PX", raising=False)
        get_settings.cache_clear()


def test_webp_accepted():
    img = Image.new("RGB", (24, 24), (9, 9, 9))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    data, ct, w, h = normalize_croquis_source_bytes(buf.getvalue(), declared_content_type="image/webp")
    assert ct == "image/png"
    assert (w, h) == (24, 24)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_ihdr_bomb_header_rejected(monkeypatch):
    """Craft PNG IHDR claiming huge dimensions without paying decode cost."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_CROQUIS_DIMENSION_PX", "100")
    get_settings.cache_clear()
    try:
        # Minimal PNG signature + IHDR with 10000×10000
        ihdr_data = struct.pack(">IIBBBBB", 10000, 10000, 8, 2, 0, 0, 0)
        import zlib

        ihdr = b"IHDR" + ihdr_data
        chunk = struct.pack(">I", 13) + ihdr + struct.pack(">I", zlib.crc32(ihdr) & 0xFFFFFFFF)
        fake = b"\x89PNG\r\n\x1a\n" + chunk + b"\x00\x00\x00\x00IEND\xaeB`\x82"
        with pytest.raises(HTTPException) as exc:
            normalize_croquis_source_bytes(fake, declared_content_type="image/png")
        assert exc.value.status_code == 400
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv("MAX_CROQUIS_DIMENSION_PX", raising=False)
        get_settings.cache_clear()
