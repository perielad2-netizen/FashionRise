import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.auth.dependencies import CurrentUser
from app.core.rate_limit import limiter
from app.core.config import get_settings
from app.core.upload_validation import extension_for_kind, read_stream_with_limit, sniff_image_kind
from app.schemas.upload import ImageUploadResponse
from app.storage.local import LocalStorageBackend

router = APIRouter()


@router.post("/image", response_model=ImageUploadResponse)
@limiter.limit("40/minute")
def upload_image(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> ImageUploadResponse:
    _ = user
    settings = get_settings()
    allowed_ct = settings.allowed_upload_content_types()
    declared = (file.content_type or "").strip().lower()
    if declared and declared not in allowed_ct:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type; allowed: {', '.join(sorted(allowed_ct))}",
        )

    try:
        raw = read_stream_with_limit(file.file, settings.max_upload_bytes)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_upload_size_mb} MB)",
        ) from None

    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    kind = sniff_image_kind(raw)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a recognized image (JPEG, PNG, or WebP)",
        )

    if declared:
        expected = {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }[kind]
        if declared != expected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content-Type does not match image payload",
            )

    ext = extension_for_kind(kind)
    key = f"{uuid.uuid4().hex}.{ext}"
    storage = LocalStorageBackend()
    url = storage.save_file(key=key, data=io.BytesIO(raw), content_type=file.content_type)
    return ImageUploadResponse(url=url, stored_key=key)
