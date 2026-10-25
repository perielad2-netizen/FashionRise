import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# sketch_polish ``input_data`` keys (stored as JSONB on ``ai_jobs``; not a separate column).
STUDIO_SIDES = frozenset({"front", "back"})


class SketchPolishInputData(BaseModel):
    """Documented sketch_polish ``input_data`` shape (extra keys remain allowed)."""

    notes: str | None = None
    mood_notes: str | None = None
    image_base64: str | None = None
    image_url: str | None = None
    local_path_placeholder: str | None = None
    reference_model_id: str | None = Field(
        default=None,
        description="Built-in or legacy croquis id; validated at enqueue (P1 #59).",
    )
    studio_side: Literal["front", "back"] | None = Field(
        default=None,
        description="Which Studio face this sketch raster represents (dual Magic).",
    )
    magic_operation_id: str | None = Field(
        default=None,
        description="Links front/back polish jobs from one coordinated Magic run.",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Same user + key returns existing queued/completed sketch_polish job.",
    )
    shared_garment_spec: dict[str, Any] | str | None = Field(
        default=None,
        description="Cross-side garment brief copied onto paired polish jobs for prompt consistency.",
    )

    model_config = ConfigDict(extra="allow")


class SketchPolishSidePayload(BaseModel):
    """Per-side raster + optional idempotency for dual polish."""

    image_base64: str | None = None
    image_url: str | None = None
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="allow")


class SketchPolishDualBody(BaseModel):
    """POST /ai/sketch/polish-dual — enqueue front and back sketch_polish together."""

    design_id: uuid.UUID | None = None
    magic_operation_id: uuid.UUID | None = Field(
        default=None,
        description="Optional; server generates when omitted.",
    )
    reference_model_id: str | None = None
    mood_notes: str | None = None
    notes: str | None = None
    shared_garment_spec: dict[str, Any] | str | None = None
    front: SketchPolishSidePayload
    back: SketchPolishSidePayload

    @field_validator("front", "back")
    @classmethod
    def _side_has_image(cls, value: SketchPolishSidePayload) -> SketchPolishSidePayload:
        has_b64 = isinstance(value.image_base64, str) and value.image_base64.strip()
        has_url = isinstance(value.image_url, str) and value.image_url.strip()
        if not has_b64 and not has_url:
            raise ValueError("each side must include image_base64 or image_url")
        return value


class SketchPipelineBody(BaseModel):
    """Payload for V2 sketch/style pipeline endpoints (placeholder worker)."""

    design_id: uuid.UUID | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)


class AIJobCreate(BaseModel):
    design_id: uuid.UUID | None = None
    job_type: str = Field(max_length=64)
    input_data: dict[str, Any] = Field(default_factory=dict)


class AIJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    design_id: uuid.UUID | None
    job_type: str
    status: str
    input_data: dict[str, Any]
    result_data: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: Any) -> "AIJobRead":
        """Build a response DTO with sketch base64 stripped and failure meta allowlisted."""
        from app.services.ai_service import (
            sanitize_job_input_for_response,
            sanitize_job_result_for_response,
        )

        err = job.error_message if isinstance(job.error_message, str) else None
        if err is not None:
            err = err.strip()[:240] or None

        return cls(
            id=job.id,
            user_id=job.user_id,
            design_id=job.design_id,
            job_type=job.job_type,
            status=job.status,
            input_data=sanitize_job_input_for_response(
                job.input_data if isinstance(job.input_data, dict) else {}
            ),
            result_data=sanitize_job_result_for_response(
                job.result_data if isinstance(job.result_data, dict) else None
            ),
            error_message=err,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class SketchPolishDualRead(BaseModel):
    magic_operation_id: uuid.UUID
    front_job: AIJobRead
    back_job: AIJobRead
