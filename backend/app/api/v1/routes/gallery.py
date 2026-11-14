import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_optional_user
from app.core.errors import UnauthorizedError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.gallery import (
    GalleryCommentCreate,
    GalleryCommentRead,
    GalleryCreate,
    GalleryRead,
    GallerySort,
)
from app.services import gallery_service

router = APIRouter()


@router.post("", response_model=GalleryRead)
def create_gallery_item(
    data: GalleryCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> GalleryRead:
    item = gallery_service.create_gallery_item(db, user, data)
    return gallery_service.to_gallery_read(item)


@router.get("", response_model=list[GalleryRead])
def list_gallery(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: GallerySort = Query("newest"),
    user: User | None = Depends(get_optional_user),
) -> list[GalleryRead]:
    if sort == "following":
        if user is None:
            raise UnauthorizedError("Sign in to view your following feed")
        rows = gallery_service.list_following_feed(db, viewer=user, limit=limit, offset=offset)
    elif sort == "circle":
        if user is None:
            raise UnauthorizedError("Sign in to view your friends circle feed")
        rows = gallery_service.list_circle_feed(db, viewer=user, limit=limit, offset=offset)
    elif sort == "top10":
        # Worldwide board supports Top 10 / 20 / 50 selectors in the Runway UI.
        rows = gallery_service.list_top_worldwide(db, limit=min(limit, 50))
    else:
        # Full public newest/trending/top_rated stays available for Top 10 tooling,
        # but the web Runway home uses circle + top10 only.
        rows = gallery_service.list_public_gallery(db, limit=limit, offset=offset, sort=sort)
    return gallery_service.to_gallery_reads_for_viewer(db, rows, user)


@router.get("/user/{user_id}", response_model=list[GalleryRead])
def list_user_gallery(user_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GalleryRead]:
    rows = gallery_service.list_user_gallery(db, user_id)
    return [gallery_service.to_gallery_read(r) for r in rows]


@router.post("/comments/{comment_id}/like", status_code=204)
def add_comment_like(
    comment_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> None:
    gallery_service.add_comment_like(db, user, comment_id)


@router.delete("/comments/{comment_id}/like", status_code=204)
def remove_comment_like(
    comment_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> None:
    gallery_service.remove_comment_like(db, user, comment_id)


@router.get("/{gallery_item_id}/comments", response_model=list[GalleryCommentRead])
def list_comments(
    gallery_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> list[GalleryCommentRead]:
    rows = gallery_service.list_gallery_comments(db, gallery_item_id)
    return gallery_service.to_comment_reads_for_viewer(db, rows, user)


@router.post(
    "/{gallery_item_id}/comments",
    response_model=GalleryCommentRead,
    status_code=201,
)
def post_comment(
    gallery_item_id: uuid.UUID,
    data: GalleryCommentCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> GalleryCommentRead:
    row = gallery_service.add_gallery_comment(db, user, gallery_item_id, data)
    return gallery_service.to_comment_read(row, liked_by_me=False)


@router.post("/{gallery_item_id}/like", status_code=204)
def add_like(gallery_item_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    gallery_service.add_gallery_like(db, user, gallery_item_id)


@router.delete("/{gallery_item_id}/like", status_code=204)
def remove_like(gallery_item_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    gallery_service.remove_gallery_like(db, user, gallery_item_id)


@router.get("/{gallery_item_id}/image")
@limiter.limit("120/minute")
def get_gallery_image(
    request: Request,
    gallery_item_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve a published Runway look image to any signed-in FashionRise user."""
    _ = (request.url, user.id)
    path = gallery_service.resolve_gallery_image_file(db, gallery_item_id)
    suffix = path.suffix.lower()
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        path,
        media_type=media,
        filename=f"fashionrise-runway-{gallery_item_id.hex[:12]}{suffix or '.png'}",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/{gallery_item_id}", response_model=GalleryRead)
def get_gallery_item(
    gallery_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GalleryRead:
    item = gallery_service.get_gallery_item(db, gallery_item_id)
    return gallery_service.to_gallery_reads_for_viewer(db, [item], user)[0]
