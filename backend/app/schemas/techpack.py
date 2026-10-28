import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FieldSource = Literal["empty", "designer", "estimate", "ai", "look", "calculated", "unknown"]


class MeasuredValue(BaseModel):
    value: float | str | None = None
    unit: str | None = None
    source: FieldSource = "empty"
    note: str | None = None


class TechpackCreate(BaseModel):
    look_id: uuid.UUID
    title: str | None = Field(default=None, max_length=160)


class TechpackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    style_code: str | None = Field(default=None, min_length=1, max_length=64)
    spec: dict[str, Any] | None = None
    bump_revision: bool = False


class TechpackExportRequest(BaseModel):
    """Optional body for POST /techpacks/{id}/export.

    Default (empty/omitted) keeps legacy Basic assembly. ``pdf_only_update`` regenerates
    the Professional PDF from persisted illustrations with $0 provider calls.
    """

    mode: Literal["basic", "pdf_only_update"] = "basic"
    idempotency_key: str | None = Field(default=None, max_length=128)


class TechpackExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    draft_id: uuid.UUID
    filename: str
    byte_size: int
    page_count: int
    revision: int
    status: str
    verification: str
    metadata_: dict[str, Any] = Field(serialization_alias="metadata")
    created_at: datetime


class TechpackDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    look_id: uuid.UUID
    design_id: uuid.UUID | None = None
    title: str
    style_code: str
    revision: int
    status: str
    verification: str
    spec: dict[str, Any]
    front_job_id: uuid.UUID | None = None
    back_job_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    latest_export: TechpackExportRead | None = None


class TechpackListResponse(BaseModel):
    items: list[TechpackDraftRead]
    total: int
    limit: int
    offset: int


class TechpackAiConfirmRequest(BaseModel):
    stage: str = Field(default="generate", max_length=64)
    mode: Literal["heuristic", "ai", "analyze", "professional"] = "heuristic"


class TechpackAiGenerateRequest(BaseModel):
    confirm_token: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)
    mode: Literal["heuristic", "ai", "analyze", "professional"] = "heuristic"
    sections: list[str] | None = None
    propose_back: bool = False


class TechpackAiOneTapRequest(BaseModel):
    """One-click Professional authorization — server mints the spend-gated intent."""

    idempotency_key: str = Field(min_length=8, max_length=128)
    propose_back: bool = True
    sections: list[str] | None = None
