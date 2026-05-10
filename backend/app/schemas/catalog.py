import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    family: str
    description: str | None
    sheen_level: float | None
    softness_level: float | None
    weight_class: str | None
    drape_character: str | None
    stretch_level: float | None
    luxury_score: int | None
    season_tags: list[Any]
    recommended_categories: list[Any]
    metadata_: dict[str, Any] = Field(serialization_alias="metadata")
    texture_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GarmentTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    description: str | None
    template_data: dict[str, Any]
    preview_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ColorPaletteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    colors: list[Any]
    tags: list[Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
