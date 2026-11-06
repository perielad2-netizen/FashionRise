"""CRUD + apply helpers for named body measurement profiles."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.models.body_measurement_profile import BodyMeasurementProfile
from app.models.user import User
from app.schemas.body_measurement_profile import (
    BodyMeasurementProfileCreate,
    BodyMeasurementProfileUpdate,
    normalize_measurements,
)
from app.services.techpack_garments import BODY_KEYS
from app.services.techpack_spec import ensure_v2


def _now() -> datetime:
    return datetime.now(UTC)


def list_profiles(db: Session, user: User) -> list[BodyMeasurementProfile]:
    return list(
        db.scalars(
            select(BodyMeasurementProfile)
            .where(BodyMeasurementProfile.owner_id == user.id)
            .order_by(
                BodyMeasurementProfile.is_default.desc(),
                BodyMeasurementProfile.updated_at.desc(),
            )
        ).all()
    )


def get_owned(
    db: Session, user: User, profile_id: uuid.UUID
) -> BodyMeasurementProfile:
    row = db.get(BodyMeasurementProfile, profile_id)
    if row is None or row.owner_id != user.id:
        raise NotFoundError("Measurement profile not found")
    return row


def get_default(db: Session, user: User) -> BodyMeasurementProfile | None:
    return db.scalars(
        select(BodyMeasurementProfile)
        .where(
            BodyMeasurementProfile.owner_id == user.id,
            BodyMeasurementProfile.is_default.is_(True),
        )
        .limit(1)
    ).first()


def _clear_other_defaults(db: Session, user: User, *, keep_id: uuid.UUID | None) -> None:
    stmt = (
        update(BodyMeasurementProfile)
        .where(
            BodyMeasurementProfile.owner_id == user.id,
            BodyMeasurementProfile.is_default.is_(True),
        )
        .values(is_default=False, updated_at=_now())
    )
    if keep_id is not None:
        stmt = stmt.where(BodyMeasurementProfile.id != keep_id)
    db.execute(stmt)


def create_profile(
    db: Session, user: User, data: BodyMeasurementProfileCreate
) -> BodyMeasurementProfile:
    units = data.units
    measurements = normalize_measurements(data.measurements, units=units)
    # Require at least one filled body point so empty junk profiles are not saved.
    filled = sum(1 for k in BODY_KEYS if measurements[k].get("value") not in (None, ""))
    if filled < 1:
        raise ValidationAppError(
            "Enter at least one body measurement (height, bust, waist, hip, or inseam)."
        )
    existing = list_profiles(db, user)
    if len(existing) >= 40:
        raise ValidationAppError("You can save at most 40 measurement profiles.")
    make_default = bool(data.is_default) or not existing
    if make_default:
        _clear_other_defaults(db, user, keep_id=None)
    row = BodyMeasurementProfile(
        id=uuid.uuid4(),
        owner_id=user.id,
        name=data.name,
        units=units,
        sample_size=data.sample_size,
        measurements=measurements,
        is_default=make_default,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_profile(
    db: Session,
    user: User,
    profile_id: uuid.UUID,
    data: BodyMeasurementProfileUpdate,
) -> BodyMeasurementProfile:
    row = get_owned(db, user, profile_id)
    if data.name is not None:
        row.name = data.name
    if data.units is not None:
        row.units = data.units
    if data.sample_size is not None:
        row.sample_size = data.sample_size
    if data.measurements is not None:
        units = data.units or row.units or "cm"
        measurements = normalize_measurements(data.measurements, units=units)
        filled = sum(1 for k in BODY_KEYS if measurements[k].get("value") not in (None, ""))
        if filled < 1:
            raise ValidationAppError(
                "Enter at least one body measurement (height, bust, waist, hip, or inseam)."
            )
        row.measurements = measurements
    if data.is_default is True:
        _clear_other_defaults(db, user, keep_id=row.id)
        row.is_default = True
    elif data.is_default is False:
        row.is_default = False
    row.updated_at = _now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_profile(db: Session, user: User, profile_id: uuid.UUID) -> None:
    row = get_owned(db, user, profile_id)
    was_default = bool(row.is_default)
    db.delete(row)
    db.flush()
    if was_default:
        nxt = db.scalars(
            select(BodyMeasurementProfile)
            .where(BodyMeasurementProfile.owner_id == user.id)
            .order_by(BodyMeasurementProfile.updated_at.desc())
            .limit(1)
        ).first()
        if nxt is not None:
            nxt.is_default = True
            nxt.updated_at = _now()
            db.add(nxt)
    db.commit()


def apply_profile_to_spec(
    spec: dict[str, Any] | None,
    profile: BodyMeasurementProfile,
) -> dict[str, Any]:
    """Copy profile body measurements onto a V2 techpack spec (designer source)."""
    v2 = ensure_v2(deepcopy(spec) if isinstance(spec, dict) else {})
    units = str(profile.units or v2.get("units") or "cm")
    body = normalize_measurements(profile.measurements, units=units)
    v2["body"] = body
    v2["units"] = units
    if profile.sample_size:
        v2["sample_size"] = profile.sample_size
    ai = v2.get("ai") if isinstance(v2.get("ai"), dict) else {}
    ai = dict(ai)
    ai["body_profile_id"] = str(profile.id)
    ai["body_profile_name"] = profile.name
    ai["dirty_since_generation"] = True
    v2["ai"] = ai
    return v2
