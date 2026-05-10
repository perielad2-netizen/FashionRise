import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RatingCreate(BaseModel):
    gallery_item_id: uuid.UUID
    score: int = Field(ge=1, le=10)


class RatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gallery_item_id: uuid.UUID
    user_id: uuid.UUID
    score: int
    created_at: datetime
    updated_at: datetime
