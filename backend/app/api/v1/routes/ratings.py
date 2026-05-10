import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.rating import RatingCreate, RatingRead
from app.services import rating_service

router = APIRouter()


@router.post("", response_model=RatingRead)
def submit_rating(
    data: RatingCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> RatingRead:
    r = rating_service.upsert_rating(db, user, data)
    return RatingRead.model_validate(r)


@router.get("/gallery/{gallery_item_id}", response_model=list[RatingRead])
def list_ratings(gallery_item_id: uuid.UUID, db: Session = Depends(get_db)) -> list[RatingRead]:
    rows = rating_service.list_ratings_for_gallery(db, gallery_item_id)
    return [RatingRead.model_validate(r) for r in rows]
