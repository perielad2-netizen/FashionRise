import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.design import DesignRead


class DesignShareRequest(BaseModel):
    friend_user_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class DesignShareTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    source_design_id: uuid.UUID | None
    received_design_id: uuid.UUID | None
    note: str | None
    created_at: datetime
    from_username: str | None = None
    to_username: str | None = None
    received_design: DesignRead | None = None
    fabrics_granted: int = 0
    croquis_granted: int = 0


class DesignShareResult(BaseModel):
    transfer: DesignShareTransferRead
    received_design: DesignRead
    collaboration_id: uuid.UUID
    message: str
