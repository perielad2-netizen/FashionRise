"""Pydantic schemas for named body measurement profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.techpack_garments import BODY_KEYS

_ALLOWED_UNITS = frozenset({"cm", "in"})
_NAME_MAX = 80


def _normalize_measurement_cell(raw: Any, *, units: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"value": None, "unit": units, "source": "empty"}
    value = raw.get("value")
    if value is None or value == "":
        return {"value": None, "unit": units, "source": "empty", "note": raw.get("note")}
    if isinstance(value, str):
        try:
            value = float(value.strip()) if "." in value.strip() else int(value.strip())
        except ValueError:
            value = value.strip() or None
    source = str(raw.get("source") or "designer").lower()
    if source not in {"empty", "designer", "estimate", "ai", "look", "calculated", "unknown"}:
        source = "designer"
    if value is not None and source == "empty":
        source = "designer"
    return {
        "value": value,
        "unit": str(raw.get("unit") or units),
        "source": source,
        "note": raw.get("note"),
    }


def normalize_measurements(raw: Any, *, units: str = "cm") -> dict[str, dict[str, Any]]:
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, dict[str, Any]] = {}
    for key in BODY_KEYS:
        out[key] = _normalize_measurement_cell(src.get(key), units=units)
    return out


class BodyMeasurementProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=_NAME_MAX)
    units: str = "cm"
    sample_size: str | None = Field(default=None, max_length=32)
    measurements: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def _name_strip(cls, v: str) -> str:
        cleaned = " ".join(v.split()).strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned[:_NAME_MAX]

    @field_validator("units")
    @classmethod
    def _units(cls, v: str) -> str:
        u = (v or "cm").strip().lower()
        if u not in _ALLOWED_UNITS:
            raise ValueError("units must be cm or in")
        return u

    @field_validator("sample_size")
    @classmethod
    def _sample(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(str(v).split()).strip()
        return cleaned[:32] or None


class BodyMeasurementProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=_NAME_MAX)
    units: str | None = None
    sample_size: str | None = Field(default=None, max_length=32)
    measurements: dict[str, Any] | None = None
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = " ".join(v.split()).strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned[:_NAME_MAX]

    @field_validator("units")
    @classmethod
    def _units(cls, v: str | None) -> str | None:
        if v is None:
            return None
        u = v.strip().lower()
        if u not in _ALLOWED_UNITS:
            raise ValueError("units must be cm or in")
        return u


class BodyMeasurementProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    units: str
    sample_size: str | None = None
    measurements: dict[str, Any]
    is_default: bool
    created_at: datetime
    updated_at: datetime


class BodyMeasurementProfileApplyRequest(BaseModel):
    """Apply a saved profile onto a techpack draft's body section."""

    profile_id: uuid.UUID | None = None
    """When omitted, applies the owner's default profile if one exists."""
