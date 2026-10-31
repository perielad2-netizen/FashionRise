"""Source-photo validation and normalization for Create My Croquis Stage A.

Rules (accepted design §8):
- MIME from bytes (JPEG/PNG/WebP only)
- Bounded bytes / dimensions / pixels
- Apply EXIF orientation **before** stripping metadata
- Re-encode as PNG without GPS/EXIF
- No network / provider processing
"""

from __future__ import annotations

import io

from fastapi import HTTPException, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.core.upload_validation import probe_image_dimensions, sniff_image_kind

_KIND_TO_CT = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
_DecompressionBombError = getattr(Image, "DecompressionBombError", OSError)


def _reject_if_dimensions_invalid(width: int, height: int) -> None:
    settings = get_settings()
    if width < 8 or height < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too small (minimum 8×8 pixels).",
        )
    max_dim = settings.max_croquis_dimension_px
    if width > max_dim or height > max_dim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image is too large (max {max_dim}×{max_dim} pixels).",
        )
    max_pixels = settings.max_croquis_total_pixels
    if width * height > max_pixels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image has too many pixels (max {max_pixels}).",
        )


def normalize_croquis_source_bytes(
    raw: bytes,
    *,
    declared_content_type: str | None,
) -> tuple[bytes, str, int, int]:
    """Validate and normalize a source photo to PNG without EXIF/GPS."""
    settings = get_settings()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(raw) > settings.max_croquis_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_croquis_upload_size_mb} MB)",
        )

    allowed = settings.allowed_upload_content_types()
    declared = (declared_content_type or "").strip().lower()
    if declared and declared not in allowed:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type; allowed: {', '.join(sorted(allowed))}",
        )

    kind = sniff_image_kind(raw)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a recognized image (JPEG, PNG, or WebP)",
        )
    if declared and declared != _KIND_TO_CT[kind]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content-Type does not match image payload",
        )

    probed = probe_image_dimensions(raw, kind)
    if probed is not None:
        _reject_if_dimensions_invalid(probed[0], probed[1])

    # Decompression bomb guard before full pixel load.
    Image.MAX_IMAGE_PIXELS = settings.max_croquis_total_pixels

    try:
        opened = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    width, height = opened.size
    _reject_if_dimensions_invalid(width, height)

    try:
        # EXIF orientation must be applied before metadata strip / re-encode.
        oriented: Image.Image = ImageOps.exif_transpose(opened) or opened
    except (OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    try:
        oriented.load()
    except (UnidentifiedImageError, OSError, ValueError, _DecompressionBombError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    # Drop all EXIF/GPS by converting and saving a fresh PNG.
    if oriented.mode in ("RGBA", "LA") or (
        oriented.mode == "P" and "transparency" in oriented.info
    ):
        converted = oriented.convert("RGBA")
    else:
        converted = oriented.convert("RGB")
    # Bound normalized output dimensions (downscale if needed; never upscale).
    max_dim = settings.max_croquis_dimension_px
    cw, ch = converted.size
    if cw > max_dim or ch > max_dim:
        converted.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    # Explicitly omit exif= — Pillow PNG writer will not embed EXIF/GPS.
    converted.save(out, format="PNG", optimize=True)
    data = out.getvalue()
    if len(data) > settings.max_croquis_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Normalized image exceeds {settings.max_croquis_upload_size_mb} MB.",
        )
    return data, "image/png", converted.size[0], converted.size[1]
