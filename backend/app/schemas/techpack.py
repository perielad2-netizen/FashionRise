import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FieldSource = Literal["empty", "designer", "estimate", "ai", "look"]


class MeasuredValue(BaseModel):
    value: float | str | None = None
    unit: str | None = None
    source: FieldSource = "empty"
    note: str | None = None


class TechpackCreate(BaseModel):
    look_id: uuid.UUID
    title: str | None = Field(default=None, max_length=160)


class TechpackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    style_code: str | None = Field(default=None, min_length=1, max_length=64)
    spec: dict[str, Any] | None = None
    bump_revision: bool = False


class TechpackExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    draft_id: uuid.UUID
    filename: str
    byte_size: int
    page_count: int
    revision: int
    status: str
    verification: str
    metadata_: dict[str, Any] = Field(serialization_alias="metadata")
    created_at: datetime


class TechpackDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    look_id: uuid.UUID
    design_id: uuid.UUID | None = None
    title: str
    style_code: str
    revision: int
    status: str
    verification: str
    spec: dict[str, Any]
    front_job_id: uuid.UUID | None = None
    back_job_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    latest_export: TechpackExportRead | None = None


class TechpackListResponse(BaseModel):
    items: list[TechpackDraftRead]
    total: int
    limit: int
    offset: int
