import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.fabric_asset import FabricAssetRead, fabric_asset_to_read
from app.services import fabric_asset_service

router = APIRouter()


@router.get("", response_model=list[FabricAssetRead])
@limiter.limit("120/minute")
def list_my_fabrics(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> list[FabricAssetRead]:
    _ = request.url
    rows = fabric_asset_service.list_fabric_assets(db, user)
    return [fabric_asset_to_read(r) for r in rows]


@router.post("", response_model=FabricAssetRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def upload_fabric(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> FabricAssetRead:
    _ = request.url
    settings = get_settings()
    raw = fabric_asset_service.read_upload_bytes(file.file, settings.max_fabric_upload_bytes)
    row = fabric_asset_service.create_fabric_asset(
        db,
        user,
        raw=raw,
        declared_content_type=file.content_type,
        name=name,
    )
    return fabric_asset_to_read(row)


@router.get("/{asset_id}", response_model=FabricAssetRead)
@limiter.limit("120/minute")
def get_fabric_meta(
    request: Request,
    asset_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FabricAssetRead:
    _ = request.url
    row = fabric_asset_service.get_owned_fabric_asset(db, user, asset_id, include_deleted=True)
    return fabric_asset_to_read(row)


@router.get("/{asset_id}/image")
@limiter.limit("240/minute")
def get_fabric_image(
    request: Request,
    asset_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve fabric bytes only to the owning authenticated user.

    Soft-deleted fabrics remain retrievable so historical designs can paint.
    Never exposed under public ``/static/uploads``.
    """
    _ = request.url
    path = fabric_asset_service.resolve_fabric_image_file(db, user, asset_id)
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"fashionrise-fabric-{asset_id.hex[:12]}.png",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{asset_id}", response_model=FabricAssetRead)
@limiter.limit("60/minute")
def delete_fabric(
    request: Request,
    asset_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FabricAssetRead:
    _ = request.url
    row = fabric_asset_service.soft_delete_fabric_asset(db, user, asset_id)
    return fabric_asset_to_read(row)
