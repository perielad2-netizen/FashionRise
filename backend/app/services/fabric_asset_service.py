"""Private per-user fabric library: validate, normalize, store, and serve."""

from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.upload_validation import (
    probe_image_dimensions,
    read_stream_with_limit,
    sniff_image_kind,
)
from app.models.fabric_asset import FabricAsset
from app.models.user import User
from app.storage.local import LocalStorageBackend

_CONTROL = re.compile(r"[\u0000-\u001F\u007F-\u009F\u2028\u2029]")
_KIND_TO_CT = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def normalize_fabric_name(raw: str | None, fallback: str = "My fabric") -> str:
    settings = get_settings()
    text = (raw or "").replace("\t", " ").replace("\n", " ").replace("\r", " ")
    if _CONTROL.search(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fabric name contains characters that are not allowed.",
        )
    name = " ".join(text.split()).strip()
    if not name:
        name = fallback
    if len(name) > settings.fabric_name_max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Keep the fabric name to {settings.fabric_name_max_length} characters or fewer.",
        )
    return name


def _reject_if_dimensions_invalid(width: int, height: int) -> None:
    settings = get_settings()
    if width < 8 or height < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fabric image is too small (minimum 8×8 pixels).",
        )
    max_dim = settings.max_fabric_dimension_px
    if width > max_dim or height > max_dim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fabric image is too large (max {max_dim}×{max_dim} pixels).",
        )
    max_pixels = max_dim * max_dim
    if width * height > max_pixels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fabric image has too many pixels (max {max_pixels}).",
        )


def _normalize_image_bytes(raw: bytes, kind: str) -> tuple[bytes, str, int, int]:
    """Bound dimensions from container headers before full decode; re-encode as PNG."""
    settings = get_settings()

    # Reject oversized uploads from headers alone — before Image.open/load.
    probed = probe_image_dimensions(raw, kind)
    if probed is not None:
        _reject_if_dimensions_invalid(probed[0], probed[1])

    try:
        img = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    # Defense in depth when header probe was unavailable.
    width, height = img.size
    _reject_if_dimensions_invalid(width, height)

    try:
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    # Normalize to a safe RGB/RGBA raster PNG.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        converted = img.convert("RGBA")
    else:
        converted = img.convert("RGB")

    out = io.BytesIO()
    converted.save(out, format="PNG", optimize=True)
    data = out.getvalue()
    if len(data) > settings.max_fabric_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Normalized fabric image exceeds {settings.max_fabric_upload_size_mb} MB.",
        )
    return data, "image/png", converted.size[0], converted.size[1]


def create_fabric_asset(
    db: Session,
    user: User,
    *,
    raw: bytes,
    declared_content_type: str | None,
    name: str | None,
) -> FabricAsset:
    settings = get_settings()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

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

    png_bytes, content_type, width, height = _normalize_image_bytes(raw, kind)
    asset_id = uuid.uuid4()
    storage_key = f"fabrics/{user.id}/{asset_id}.png"
    storage = LocalStorageBackend()
    # Private subtree — sibling of upload_subdir, never mounted at /static/uploads.
    storage.save_private_file(key=storage_key, data=io.BytesIO(png_bytes), content_type=content_type)

    row = FabricAsset(
        id=asset_id,
        owner_id=user.id,
        name=normalize_fabric_name(name),
        content_type=content_type,
        width=width,
        height=height,
        byte_size=len(png_bytes),
        storage_key=storage_key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_fabric_assets(db: Session, user: User) -> list[FabricAsset]:
    return (
        db.query(FabricAsset)
        .filter(FabricAsset.owner_id == user.id, FabricAsset.deleted_at.is_(None))
        .order_by(FabricAsset.created_at.desc())
        .all()
    )


def get_owned_fabric_asset(
    db: Session,
    user: User,
    asset_id: uuid.UUID,
    *,
    include_deleted: bool = True,
) -> FabricAsset:
    q = db.query(FabricAsset).filter(FabricAsset.id == asset_id, FabricAsset.owner_id == user.id)
    if not include_deleted:
        q = q.filter(FabricAsset.deleted_at.is_(None))
    row = q.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric not found")
    return row


def resolve_fabric_image_file(db: Session, user: User, asset_id: uuid.UUID) -> Path:
    row = get_owned_fabric_asset(db, user, asset_id, include_deleted=True)
    storage = LocalStorageBackend()
    path = storage.resolve_private_file(key=row.storage_key)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fabric image file is missing. Re-upload the fabric or undo that fill.",
        )
    # Defense in depth: never serve a path that lives under the public upload mount.
    try:
        path.resolve().relative_to(storage.public_upload_root())
    except ValueError:
        return path
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Fabric image file is missing. Re-upload the fabric or undo that fill.",
    )


def soft_delete_fabric_asset(db: Session, user: User, asset_id: uuid.UUID) -> FabricAsset:
    row = get_owned_fabric_asset(db, user, asset_id, include_deleted=False)
    row.deleted_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def read_upload_bytes(stream, max_bytes: int) -> bytes:
    try:
        return read_stream_with_limit(stream, max_bytes)
    except ValueError as exc:
        settings = get_settings()
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_fabric_upload_size_mb} MB)",
        ) from exc
