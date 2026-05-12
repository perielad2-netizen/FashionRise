import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_optional_user
from app.core.errors import UnauthorizedError
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
    return GalleryRead.model_validate(item)


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
    else:
        rows = gallery_service.list_public_gallery(db, limit=limit, offset=offset, sort=sort)
    return [GalleryRead.model_validate(r) for r in rows]


@router.get("/user/{user_id}", response_model=list[GalleryRead])
def list_user_gallery(user_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GalleryRead]:
    rows = gallery_service.list_user_gallery(db, user_id)
    return [GalleryRead.model_validate(r) for r in rows]


@router.get("/{gallery_item_id}/comments", response_model=list[GalleryCommentRead])
def list_comments(gallery_item_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GalleryCommentRead]:
    rows = gallery_service.list_gallery_comments(db, gallery_item_id)
    return [GalleryCommentRead.model_validate(r) for r in rows]


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
    return GalleryCommentRead.model_validate(row)


@router.post("/{gallery_item_id}/like", status_code=204)
def add_like(gallery_item_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    gallery_service.add_gallery_like(db, user, gallery_item_id)


@router.delete("/{gallery_item_id}/like", status_code=204)
def remove_like(gallery_item_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    gallery_service.remove_gallery_like(db, user, gallery_item_id)


@router.get("/{gallery_item_id}", response_model=GalleryRead)
def get_gallery_item(
    gallery_item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> GalleryRead:
    item = gallery_service.get_gallery_item(db, gallery_item_id)
    liked: bool | None = None
    if user is not None:
        liked = gallery_service.user_has_liked(db, user.id, gallery_item_id)
    base = GalleryRead.model_validate(item)
    return base.model_copy(update={"liked_by_me": liked})
