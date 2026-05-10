from pydantic import BaseModel, Field


class ImageUploadResponse(BaseModel):
    url: str = Field(description="Public URL for the stored object")
    stored_key: str = Field(description="Storage key relative to upload subdir")
