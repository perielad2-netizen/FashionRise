import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_optional_user
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import FollowerListItem, FollowStatusRead, ProfileRead, ProfileUpdate
from app.services import follow_service, profile_avatar_service, profile_service

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
def get_my_profile(user: CurrentUser, db: Session = Depends(get_db)) -> ProfileRead:
    return profile_service.build_profile_read(db, user.id, include_private_inventory=True)


@router.put("/me", response_model=ProfileRead)
def update_my_profile(
    data: ProfileUpdate, user: CurrentUser, db: Session = Depends(get_db)
) -> ProfileRead:
    profile_service.update_own_profile(db, user, data)
    return profile_service.build_profile_read(db, user.id, include_private_inventory=True)


@router.post("/me/avatar", response_model=ProfileRead, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
def upload_my_avatar(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ProfileRead:
    """Upload a profile photo into private storage (not /static/uploads)."""
    _ = request.url
    settings = get_settings()
    raw = profile_avatar_service.read_avatar_upload_bytes(
        file.file, settings.max_avatar_upload_bytes
    )
    profile_avatar_service.upload_own_avatar(
        db,
        user,
        raw=raw,
        declared_content_type=file.content_type,
    )
    return profile_service.build_profile_read(db, user.id, include_private_inventory=True)


@router.get("/{user_id}/avatar")
@limiter.limit("240/minute")
def get_profile_avatar(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve a designer's profile photo for same-origin <img> tags.

    Public enough to render on profiles/looks; bytes stay off /static/uploads.
    """
    _ = request.url
    resolved = profile_avatar_service.resolve_avatar_file(db, user_id)
    if resolved is None:
        raise NotFoundError("Avatar not found")
    media_type, path = resolved
    return FileResponse(
        path,
        media_type=media_type,
        filename=f"fashionrise-avatar-{user_id.hex[:12]}.jpg",
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/me/following-ids", response_model=list[uuid.UUID])
def my_following_ids(user: CurrentUser, db: Session = Depends(get_db)) -> list[uuid.UUID]:
    return follow_service.list_following_ids(db, user.id)


@router.get("/{user_id}/followers", response_model=list[FollowerListItem])
def list_profile_followers(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
    limit: int = 50,
    offset: int = 0,
) -> list[FollowerListItem]:
    """People who follow this designer — open from the Followers profile tile."""
    return follow_service.list_followers(
        db,
        user_id,
        viewer_id=viewer.id if viewer else None,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}/following", response_model=list[FollowerListItem])
def list_profile_following(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
    limit: int = 50,
    offset: int = 0,
) -> list[FollowerListItem]:
    """Designers this user follows."""
    return follow_service.list_following_people(
        db,
        user_id,
        viewer_id=viewer.id if viewer else None,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}/follow-status", response_model=FollowStatusRead)
def get_follow_status(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> FollowStatusRead:
    if user is None:
        return FollowStatusRead(user_id=user_id, following=False)
    return FollowStatusRead(
        user_id=user_id,
        following=follow_service.is_following(db, user.id, user_id),
    )


@router.post("/{user_id}/follow", status_code=204)
def follow_creator(user_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    follow_service.follow_user(db, user, user_id)


@router.delete("/{user_id}/follow", status_code=204)
def unfollow_creator(user_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    follow_service.unfollow_user(db, user, user_id)


@router.get("/{user_id}", response_model=ProfileRead)
def get_profile(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> ProfileRead:
    include_private = viewer is not None and viewer.id == user_id
    return profile_service.build_profile_read(
        db, user_id, include_private_inventory=include_private
    )
