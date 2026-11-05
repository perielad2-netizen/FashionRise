import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FabricAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    content_type: str
    width: int
    height: int
    byte_size: int
    created_at: datetime
    deleted: bool = Field(
        description="True when removed from My Fabrics; image may still load for historical designs.",
    )


def fabric_asset_to_read(row) -> FabricAssetRead:
    return FabricAssetRead(
        id=row.id,
        name=row.name,
        content_type=row.content_type,
        width=row.width,
        height=row.height,
        byte_size=row.byte_size,
        created_at=row.created_at,
        deleted=row.deleted_at is not None,
    )
