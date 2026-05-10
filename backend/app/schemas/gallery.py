import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GallerySort = Literal["newest", "top_rated", "trending"]


class GalleryCreate(BaseModel):
    design_id: uuid.UUID
    title: str = Field(max_length=300)
    image_url: str | None = Field(default=None, max_length=1024)
    visibility: str = "public"


class GalleryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    design_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    image_url: str | None
    visibility: str
    rating_average: float | None
    rating_count: int
    likes_count: int
    moderation_status: str
    created_at: datetime
    updated_at: datetime
    liked_by_me: bool | None = None


class GalleryCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class GalleryCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gallery_item_id: uuid.UUID
    user_id: uuid.UUID
    body: str
    moderation_status: str
    created_at: datetime
