import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExportCreate(BaseModel):
    design_id: uuid.UUID
    export_type: str = Field(max_length=64)
    file_url: str | None = Field(default=None, max_length=1024)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    design_id: uuid.UUID
    user_id: uuid.UUID
    export_type: str
    file_url: str | None
    metadata_: dict[str, Any] = Field(serialization_alias="metadata")
    created_at: datetime
