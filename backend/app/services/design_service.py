import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, NotFoundError
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.design import DesignCreate, DesignUpdate


def _assert_owner(design: GarmentDesign, user: User) -> None:
    if design.user_id != user.id:
        raise ForbiddenError("Not allowed to modify this design")


def create_design(db: Session, user: User, data: DesignCreate) -> GarmentDesign:
    d = GarmentDesign(
        user_id=user.id,
        title=data.title,
        description=data.description,
        garment_category=data.garment_category,
        template_id=data.template_id,
        material_id=data.material_id,
        color_palette_id=data.color_palette_id,
        design_data=data.design_data,
        metadata_=data.metadata,
        visibility=data.visibility,
        status=data.status,
    )
    db.add(d)
    db.flush()
    _bump_design_count(db, user.id, 1)
    db.commit()
    db.refresh(d)
    return d


def list_my_designs(db: Session, user: User) -> list[GarmentDesign]:
    return list(
        db.scalars(
            select(GarmentDesign).where(GarmentDesign.user_id == user.id).order_by(GarmentDesign.created_at.desc())
        ).all()
    )


def get_design(db: Session, design_id: uuid.UUID, user: User | None) -> GarmentDesign:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    if user and d.user_id == user.id:
        return d
    if d.visibility == "public" and d.moderation_status == "ok":
        return d
    raise NotFoundError("Design not found")


def update_design(db: Session, design_id: uuid.UUID, user: User, data: DesignUpdate) -> GarmentDesign:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    _assert_owner(d, user)
    if data.title is not None:
        d.title = data.title
    if data.description is not None:
        d.description = data.description
    if data.garment_category is not None:
        d.garment_category = data.garment_category
    if data.template_id is not None:
        d.template_id = data.template_id
    if data.material_id is not None:
        d.material_id = data.material_id
    if data.color_palette_id is not None:
        d.color_palette_id = data.color_palette_id
    if data.design_data is not None:
        d.design_data = data.design_data
    if data.metadata is not None:
        d.metadata_ = data.metadata
    if data.visibility is not None:
        d.visibility = data.visibility
    if data.status is not None:
        d.status = data.status
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def delete_design(db: Session, design_id: uuid.UUID, user: User) -> None:
    d = db.get(GarmentDesign, design_id)
    if not d:
        raise NotFoundError("Design not found")
    _assert_owner(d, user)
    db.delete(d)
    _bump_design_count(db, user.id, -1)
    db.commit()


def _bump_design_count(db: Session, user_id: uuid.UUID, delta: int) -> None:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile:
        profile.designs_count = max(0, profile.designs_count + delta)
        db.add(profile)
