import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    bio: str | None
    avatar_url: str | None
    cover_url: str | None
    style_tags: list[Any]
    designs_count: int
    followers_count: int
    rating_average: float | None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = None
    avatar_url: str | None = Field(default=None, max_length=1024)
    cover_url: str | None = Field(default=None, max_length=1024)
    style_tags: list[str] | None = None
