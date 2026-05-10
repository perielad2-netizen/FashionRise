import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import GarmentTemplateRead
from app.services import catalog_service

router = APIRouter()


@router.get("", response_model=list[GarmentTemplateRead])
def list_templates(db: Session = Depends(get_db)) -> list[GarmentTemplateRead]:
    rows = catalog_service.list_templates(db)
    return [GarmentTemplateRead.model_validate(r) for r in rows]


@router.get("/{template_id}", response_model=GarmentTemplateRead)
def get_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> GarmentTemplateRead:
    t = catalog_service.get_template(db, template_id)
    return GarmentTemplateRead.model_validate(t)
