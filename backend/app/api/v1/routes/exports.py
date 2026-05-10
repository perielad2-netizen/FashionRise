import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.dependencies import CurrentUser
from app.schemas.export import ExportCreate, ExportRead
from app.services import export_service

router = APIRouter()


@router.post("", response_model=ExportRead)
def create_export(
    data: ExportCreate, user: CurrentUser, db: Session = Depends(get_db)
) -> ExportRead:
    ex = export_service.create_export(db, user, data)
    return ExportRead.model_validate(ex)


@router.get("/design/{design_id}", response_model=list[ExportRead])
def list_exports_for_design(
    design_id: uuid.UUID, user: CurrentUser, db: Session = Depends(get_db)
) -> list[ExportRead]:
    rows = export_service.list_exports_for_design(db, user, design_id)
    return [ExportRead.model_validate(r) for r in rows]
