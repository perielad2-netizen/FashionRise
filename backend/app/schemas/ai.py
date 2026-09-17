import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SketchPipelineBody(BaseModel):
    """Payload for V2 sketch/style/tech-pack pipeline endpoints."""

    design_id: uuid.UUID | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)


class AIJobCreate(BaseModel):
    design_id: uuid.UUID | None = None
    job_type: str = Field(max_length=64)
    input_data: dict[str, Any] = Field(default_factory=dict)


class AIJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    design_id: uuid.UUID | None
    job_type: str
    status: str
    input_data: dict[str, Any]
    result_data: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
