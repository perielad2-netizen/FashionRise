"""Private profile avatar upload + serve (never under /static/uploads)."""

from __future__ import annotations

import io
import uuid

from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.upload_validation import read_stream_with_limit, sniff_image_kind
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services import profile_service
from app.storage.local import LocalStorageBackend

_KIND_TO_CT = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def avatar_api_path(user_id: uuid.UUID) -> str:
    """Same-origin img src that nginx allowlists (not public static uploads)."""
    return f"/api/v1/profiles/{user_id}/avatar"


def _normalize_square_jpeg(raw: bytes, kind: str) -> bytes:
    settings = get_settings()
    edge = max(64, int(settings.avatar_output_px))
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a readable image.",
        ) from exc

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (12, 12, 16))
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    width, height = img.size
    if width < 8 or height < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too small for a profile photo.",
        )

    # Center-crop to square then downscale (client may already crop; keep safe).
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    if side != edge:
        img = img.resize((edge, edge), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def upload_own_avatar(
    db: Session,
    user: User,
    *,
    raw: bytes,
    declared_content_type: str | None,
) -> UserProfile:
    settings = get_settings()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(raw) > settings.max_avatar_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Profile photo is too large.",
        )

    kind = sniff_image_kind(raw)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a recognized image (JPEG, PNG, or WebP)",
        )

    declared = (declared_content_type or "").strip().lower()
    if declared and declared not in settings.allowed_upload_content_types():
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type; allowed: {', '.join(sorted(settings.allowed_upload_content_types()))}",
        )
    if declared:
        expected = _KIND_TO_CT[kind]
        if declared != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content-Type does not match image payload",
            )

    jpeg = _normalize_square_jpeg(raw, kind)
    storage = LocalStorageBackend()
    storage.save_private_avatar_file(user_id=user.id, data=io.BytesIO(jpeg))

    profile = profile_service.get_profile_for_user(db, user.id)
    profile.avatar_url = avatar_api_path(user.id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def is_private_avatar_url(avatar_url: str | None) -> bool:
    """True when avatar_url points at the new private avatar API route."""
    if not avatar_url:
        return False
    value = avatar_url.strip()
    return "/profiles/" in value and value.rstrip("/").endswith("/avatar")


def resolve_avatar_file(db: Session, user_id: uuid.UUID) -> tuple[str, Path] | None:
    """Return (media_type, path) when a private avatar exists for the user.

    Legacy ``/static/uploads/...`` avatar_url values are not rewritten here —
    callers must keep serving those URLs as-is. This route only returns bytes
    that actually live under ``private_avatars/``.
    """
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is None or not profile.avatar_url:
        return None
    path = LocalStorageBackend().resolve_private_avatar_file(user_id=user_id)
    if path is None:
        return None
    return ("image/jpeg", path)


def unlink_private_avatar_after_account_delete(user_id: uuid.UUID) -> bool:
    """Best-effort remove the owner's private avatar after the account row is gone.

    Scoped strictly to ``private_avatars/{user_id}/avatar.jpg`` — never another
    user's file. Call only after a successful account-deletion commit.
    """
    return LocalStorageBackend().delete_private_avatar_file(user_id=user_id)


def read_avatar_upload_bytes(stream, max_bytes: int) -> bytes:
    try:
        return read_stream_with_limit(stream, max_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Profile photo is too large.",
        ) from exc
