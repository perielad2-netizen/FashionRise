import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DesignCreate(BaseModel):
    title: str = Field(max_length=300)
    description: str | None = None
    garment_category: str = Field(max_length=64)
    template_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    color_palette_id: uuid.UUID | None = None
    design_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    visibility: str = "private"
    status: str = "draft"


class DesignUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    garment_category: str | None = Field(default=None, max_length=64)
    template_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    color_palette_id: uuid.UUID | None = None
    design_data: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    visibility: str | None = None
    status: str | None = None


class DesignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    garment_category: str
    template_id: uuid.UUID | None
    material_id: uuid.UUID | None
    color_palette_id: uuid.UUID | None
    design_data: dict[str, Any]
    metadata_: dict[str, Any] = Field(serialization_alias="metadata")
    visibility: str
    status: str
    moderation_status: str
    moderation_labels: list[Any] | None
    created_at: datetime
    updated_at: datetime
