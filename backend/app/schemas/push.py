from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class PushVapidPublicKey(BaseModel):
    public_key: str
    enabled: bool


class PushSubscriptionCreate(BaseModel):
    endpoint: HttpUrl
    p256dh: str = Field(min_length=8, max_length=255)
    auth: str = Field(min_length=8, max_length=255)
    user_agent: str | None = Field(default=None, max_length=512)


class PushSubscriptionRead(BaseModel):
    id: UUID
    endpoint: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PushSubscriptionDelete(BaseModel):
    endpoint: HttpUrl
