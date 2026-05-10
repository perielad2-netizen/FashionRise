import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.color_palette import ColorPalette
from app.models.garment_template import GarmentTemplate
from app.models.material_definition import MaterialDefinition


def list_materials(db: Session, *, active_only: bool = True) -> list[MaterialDefinition]:
    q = select(MaterialDefinition)
    if active_only:
        q = q.where(MaterialDefinition.is_active.is_(True))
    return list(db.scalars(q.order_by(MaterialDefinition.name)).all())


def get_material(db: Session, material_id: uuid.UUID) -> MaterialDefinition:
    m = db.get(MaterialDefinition, material_id)
    if not m or not m.is_active:
        raise NotFoundError("Material not found")
    return m


def list_templates(db: Session, *, active_only: bool = True) -> list[GarmentTemplate]:
    q = select(GarmentTemplate)
    if active_only:
        q = q.where(GarmentTemplate.is_active.is_(True))
    return list(db.scalars(q.order_by(GarmentTemplate.category, GarmentTemplate.name)).all())


def get_template(db: Session, template_id: uuid.UUID) -> GarmentTemplate:
    t = db.get(GarmentTemplate, template_id)
    if not t or not t.is_active:
        raise NotFoundError("Template not found")
    return t


def list_palettes(db: Session, *, active_only: bool = True) -> list[ColorPalette]:
    q = select(ColorPalette)
    if active_only:
        q = q.where(ColorPalette.is_active.is_(True))
    return list(db.scalars(q.order_by(ColorPalette.name)).all())
