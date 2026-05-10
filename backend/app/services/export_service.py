import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models.design_export import DesignExport
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.export import ExportCreate


def create_export(db: Session, user: User, data: ExportCreate) -> DesignExport:
    design = db.get(GarmentDesign, data.design_id)
    if not design or design.user_id != user.id:
        raise ForbiddenError("Not allowed to export this design")
    ex = DesignExport(
        design_id=data.design_id,
        user_id=user.id,
        export_type=data.export_type,
        file_url=data.file_url,
        metadata_=data.metadata,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


def list_exports_for_design(db: Session, user: User, design_id: uuid.UUID) -> list[DesignExport]:
    design = db.get(GarmentDesign, design_id)
    if not design:
        raise NotFoundError("Design not found")
    if design.user_id != user.id:
        raise ForbiddenError("Not allowed to view exports for this design")
    return list(
        db.scalars(
            select(DesignExport)
            .where(DesignExport.design_id == design_id)
            .order_by(DesignExport.created_at.desc())
        ).all()
    )
