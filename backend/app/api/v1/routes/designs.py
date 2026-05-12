import uuid

from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.design import (
    DesignCreate,
    DesignRead,
    DesignRevisionCreate,
    DesignRevisionRead,
    DesignUpdate,
)
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


@router.get("/{design_id}/revisions", response_model=list[DesignRevisionRead])
def list_design_revisions(
    design_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[DesignRevisionRead]:
    rows = design_service.list_design_revisions(db, design_id, user, limit=limit, offset=offset)
    return [DesignRevisionRead.model_validate(r) for r in rows]


@router.post(
    "/{design_id}/revisions",
    response_model=DesignRevisionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_design_revision(
    design_id: uuid.UUID,
    data: DesignRevisionCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DesignRevisionRead:
    r = design_service.append_design_revision(
        db, design_id, user, data.design_data, data.notes
    )
    return DesignRevisionRead.model_validate(r)


@router.get("/{design_id}/revisions/{revision_number}", response_model=DesignRevisionRead)
def get_design_revision(
    design_id: uuid.UUID,
    revision_number: int,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> DesignRevisionRead:
    r = design_service.get_design_revision(db, design_id, user, revision_number)
    return DesignRevisionRead.model_validate(r)


@router.get("/{design_id}/handoff")
def get_design_handoff(
    design_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
    export_kind: str = Query("manifest_v1", pattern="^(manifest_v1|spec_sheet_v1|spec_sheet_pdf)$"),
) -> dict[str, Any]:
    """Owner-only maker handoff JSON. `export_kind`: manifest_v1 | spec_sheet_v1 | spec_sheet_pdf."""
    if export_kind == "spec_sheet_pdf":
        return design_service.build_handoff_spec_sheet_pdf_placeholder(db, design_id, user)
    if export_kind == "spec_sheet_v1":
        return design_service.build_handoff_spec_sheet(db, design_id, user)
    return design_service.build_handoff_manifest(db, design_id, user)


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
