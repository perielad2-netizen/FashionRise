import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.design import DesignCreate, DesignRead, DesignUpdate
from app.services import design_service

router = APIRouter()


@router.post("", response_model=DesignRead, status_code=status.HTTP_201_CREATED)
def create_design(
    data: DesignCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> DesignRead:
    d = design_service.create_design(db, user, data)
    return DesignRead.model_validate(d)


@router.get("/my", response_model=list[DesignRead])
def list_my_designs(user: CurrentUser, db: Session = Depends(get_db)) -> list[DesignRead]:
    rows = design_service.list_my_designs(db, user)
    return [DesignRead.model_validate(r) for r in rows]


@router.get("/{design_id}", response_model=DesignRead)
def get_design(
    design_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> DesignRead:
    d = design_service.get_design(db, design_id, user)
    return DesignRead.model_validate(d)


@router.put("/{design_id}", response_model=DesignRead)
def update_design(
    design_id: uuid.UUID,
    data: DesignUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DesignRead:
    d = design_service.update_design(db, design_id, user, data)
    return DesignRead.model_validate(d)


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_design(
    design_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> Response:
    design_service.delete_design(db, design_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
