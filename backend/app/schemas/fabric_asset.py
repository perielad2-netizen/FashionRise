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
    source: str = Field(default="upload", description="upload | ai")
    prompt_short: str | None = Field(
        default=None,
        description="Short textile description for Magic / Try On when source=ai.",
    )
    color_hex: str | None = None


class AiFabricCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=400)
    color_hex: str | None = Field(default=None, max_length=7)
    name: str | None = Field(default=None, max_length=80)


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
        source=getattr(row, "source", None) or "upload",
        prompt_short=getattr(row, "prompt_short", None),
        color_hex=getattr(row, "color_hex", None),
    )
