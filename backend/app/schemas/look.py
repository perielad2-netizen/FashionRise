import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LookSideRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    studio_side: Literal["front", "back"] | None = None
    has_image: bool = False
    summary: str | None = None
    created_at: datetime


class LookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_favorite: bool = False
    is_archived: bool = False
    kind: Literal["single", "dual"]
    created_at: datetime
    updated_at: datetime
    front: LookSideRef | None = None
    back: LookSideRef | None = None
    # Stable refs for future technical-pack (#83) without implementing PDF here.
    design_id: uuid.UUID | None = None
    magic_operation_id: uuid.UUID | None = None


class LookListResponse(BaseModel):
    items: list[LookRead]
    total: int
    limit: int
    offset: int


class LookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    is_favorite: bool | None = None
    is_archived: bool | None = None
