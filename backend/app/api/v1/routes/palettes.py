from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import ColorPaletteRead
from app.services import catalog_service

router = APIRouter()


@router.get("", response_model=list[ColorPaletteRead])
def list_palettes(db: Session = Depends(get_db)) -> list[ColorPaletteRead]:
    rows = catalog_service.list_palettes(db)
    return [ColorPaletteRead.model_validate(r) for r in rows]
