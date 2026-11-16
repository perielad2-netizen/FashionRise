import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GallerySort = Literal[
    "newest",
    "top_rated",
    "trending",
    "following",
    "circle",
    "top10",
    "discover",
]


class GalleryImpressionsCreate(BaseModel):
    """Batch unique Discover impressions for the signed-in viewer."""

    gallery_item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class GalleryImpressionsResult(BaseModel):
    recorded: int


class GalleryCreate(BaseModel):
    design_id: uuid.UUID | None = None
    look_id: uuid.UUID | None = None
    title: str = Field(max_length=300)
    image_url: str | None = Field(default=None, max_length=1024)
    visibility: str = "public"
    # Required when visibility is public — same notice as Runway / public-publish.
    public_publish_attested: bool = False
    notice_version: str = ""
    notice_text_hash: str = ""

    @model_validator(mode="after")
    def require_design_or_look(self) -> "GalleryCreate":
        if self.design_id is None and self.look_id is None:
            raise ValueError("design_id or look_id is required")
        return self


class GalleryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    design_id: uuid.UUID | None = None
    look_id: uuid.UUID | None = None
    user_id: uuid.UUID
    title: str
    image_url: str | None
    visibility: str
    rating_average: float | None
    rating_count: int
    likes_count: int
    comments_count: int = 0
    moderation_status: str
    created_at: datetime
    updated_at: datetime
    liked_by_me: bool | None = None
    my_score: int | None = None
    """Relative API path for authenticated Runway image bytes (look publishes)."""
    image_path: str | None = None
    """Author username for FashionRise overlays (optional; omitted when unavailable)."""
    username: str | None = None
    """Author profile photo path/url when set — FashionRise look chips use the avatar route."""
    avatar_url: str | None = None


class GalleryCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class GalleryCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gallery_item_id: uuid.UUID
    user_id: uuid.UUID
    body: str
    moderation_status: str
    likes_count: int = 0
    created_at: datetime
    username: str | None = None
    liked_by_me: bool | None = None
