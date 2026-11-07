import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FriendUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None


class FriendshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    created_at: datetime
    accepted_at: datetime | None = None
    friend: FriendUserRead


class FriendRequestCreate(BaseModel):
    """Add by FashionRise username (preferred) or exact user id."""

    username: str | None = Field(default=None, min_length=1, max_length=64)
    user_id: uuid.UUID | None = None
