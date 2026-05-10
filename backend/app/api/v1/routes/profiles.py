import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.profile import ProfileRead, ProfileUpdate
from app.services import profile_service

router = APIRouter()


@router.get("/me", response_model=ProfileRead)
def get_my_profile(user: CurrentUser, db: Session = Depends(get_db)) -> ProfileRead:
    p = profile_service.get_profile_for_user(db, user.id)
    return ProfileRead.model_validate(p)


@router.put("/me", response_model=ProfileRead)
def update_my_profile(
    data: ProfileUpdate, user: CurrentUser, db: Session = Depends(get_db)
) -> ProfileRead:
    p = profile_service.update_own_profile(db, user, data)
    return ProfileRead.model_validate(p)


@router.get("/{user_id}", response_model=ProfileRead)
def get_profile(user_id: uuid.UUID, db: Session = Depends(get_db)) -> ProfileRead:
    p = profile_service.get_public_profile(db, user_id)
    return ProfileRead.model_validate(p)
