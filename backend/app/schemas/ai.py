import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
        """Build a response DTO with sketch base64 stripped from input_data."""
        from app.services.ai_service import sanitize_job_input_for_response

        return cls(
            id=job.id,
            user_id=job.user_id,
            design_id=job.design_id,
            job_type=job.job_type,
            status=job.status,
            input_data=sanitize_job_input_for_response(
                job.input_data if isinstance(job.input_data, dict) else {}
            ),
            result_data=job.result_data,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
