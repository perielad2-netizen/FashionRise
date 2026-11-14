from datetime import datetime
from typing import Literal
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


class NativePushCapability(BaseModel):
    android_enabled: bool
    ios_enabled: bool


class NativePushDeviceCreate(BaseModel):
    platform: Literal["android", "ios"]
    device_token: str = Field(min_length=16, max_length=4096)
    app_version: str | None = Field(default=None, max_length=64)


class NativePushDeviceRead(BaseModel):
    id: UUID
    platform: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NativePushDeviceDelete(BaseModel):
    device_token: str = Field(min_length=16, max_length=4096)
