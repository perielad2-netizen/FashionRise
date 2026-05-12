import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_optional_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import FollowStatusRead, ProfileRead, ProfileUpdate
from app.services import follow_service, profile_service

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
def get_my_profile(user: CurrentUser, db: Session = Depends(get_db)) -> ProfileRead:
    return profile_service.build_profile_read(db, user.id)


@router.put("/me", response_model=ProfileRead)
def update_my_profile(
    data: ProfileUpdate, user: CurrentUser, db: Session = Depends(get_db)
) -> ProfileRead:
    profile_service.update_own_profile(db, user, data)
    return profile_service.build_profile_read(db, user.id)


@router.get("/me/following-ids", response_model=list[uuid.UUID])
def my_following_ids(user: CurrentUser, db: Session = Depends(get_db)) -> list[uuid.UUID]:
    return follow_service.list_following_ids(db, user.id)


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
def get_profile(user_id: uuid.UUID, db: Session = Depends(get_db)) -> ProfileRead:
    return profile_service.build_profile_read(db, user_id)
