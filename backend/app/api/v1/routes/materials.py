import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import MaterialRead
from app.services import catalog_service

router = APIRouter()


@router.get("", response_model=list[MaterialRead])
def list_materials(db: Session = Depends(get_db)) -> list[MaterialRead]:
    rows = catalog_service.list_materials(db)
    return [MaterialRead.model_validate(r) for r in rows]


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: uuid.UUID, db: Session = Depends(get_db)) -> MaterialRead:
    m = catalog_service.get_material(db, material_id)
    return MaterialRead.model_validate(m)
