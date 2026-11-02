import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# sketch_polish ``input_data`` keys (stored as JSONB on ``ai_jobs``; not a separate column).
STUDIO_SIDES = frozenset({"front", "back"})


class SketchPolishInputData(BaseModel):
    """Documented sketch_polish ``input_data`` shape (extra keys remain allowed)."""

    notes: str | None = None
    mood_notes: str | None = None
    image_base64: str | None = None
    image_url: str | None = None
    fabric_swatch_base64: str | None = Field(
        default=None,
        description=(
            "Optional PNG/JPEG/WebP data URL of the exact Studio fabric tile "
            "(patterned fills only). Used as images.edit image #2; redacted from API responses."
        ),
    )
    local_path_placeholder: str | None = None
    reference_model_id: str | None = Field(
        default=None,
        description=(
            "Built-in, legacy, utility (custom/blank), or personal croquis id; "
            "validated at enqueue (P1 #59 / #159)."
        ),
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
    source_revision: int | None = Field(
        default=None,
        ge=0,
        description="Studio document revision stamped on sketch_polish jobs when provided.",
    )
    content_fingerprint: str | None = Field(
        default=None,
        max_length=128,
        description="Optional document/content fingerprint for idempotent recovery binding.",
    )
    image_fingerprint: str | None = Field(
        default=None,
        max_length=128,
        description="Server-computed hash of sketch raster (set on enqueue).",
    )

    model_config = ConfigDict(extra="allow")


class SketchPolishSidePayload(BaseModel):
    """Per-side raster + idempotency for dual polish."""

    image_base64: str | None = None
    image_url: str | None = None
    fabric_swatch_base64: str | None = Field(
        default=None,
        description="Optional exact Studio fabric tile for this side (images.edit #2).",
    )
    notes: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="allow")


_SHARED_GARMENT_SPEC_KEYS = frozenset(
    {
        "silhouette",
        "colors",
        "main_colors",
        "materials",
        "notes",
        "garment_category",
        "hem",
        "neckline",
        "details",
    }
)
_MAX_SHARED_GARMENT_SPEC_JSON_CHARS = 4096


def _validate_shared_garment_spec_value(spec: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(spec, str):
        text = spec.strip()
        if not text:
            raise ValueError("shared_garment_spec must be a non-empty object")
        if len(text) > _MAX_SHARED_GARMENT_SPEC_JSON_CHARS:
            raise ValueError("shared_garment_spec is too large")
        return {"notes": text}
    if not isinstance(spec, dict) or not spec:
        raise ValueError("shared_garment_spec must be a non-empty object")
    encoded = json.dumps(spec, separators=(",", ":"), sort_keys=True)
    if len(encoded) > _MAX_SHARED_GARMENT_SPEC_JSON_CHARS:
        raise ValueError("shared_garment_spec is too large")
    for key, value in spec.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("shared_garment_spec keys must be non-empty strings")
        if key not in _SHARED_GARMENT_SPEC_KEYS:
            raise ValueError(f"shared_garment_spec key not allowed: {key}")
        if isinstance(value, (dict, list)):
            if len(json.dumps(value)) > 1024:
                raise ValueError("shared_garment_spec nested value is too large")
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError("shared_garment_spec values must be JSON primitives or small lists")
    return spec


class SketchPolishDualBody(BaseModel):
    """POST /ai/sketch/polish-dual — enqueue front and back sketch_polish together."""

    design_id: uuid.UUID | None = None
    magic_operation_id: uuid.UUID = Field(
        description="Client-issued id linking front/back jobs for one Magic run (required).",
    )
    source_revision: int | None = Field(
        default=None,
        ge=0,
        description="Studio document revision at enqueue time (immutable binding).",
    )
    content_fingerprint: str | None = Field(
        default=None,
        max_length=128,
        description="Optional content hash when revision alone is insufficient.",
    )
    reference_model_id: str | None = None
    mood_notes: str | None = None
    notes: str | None = None
    shared_garment_spec: dict[str, Any] | str = Field(
        description="Required cross-side garment brief; FE must supply for coordinated prompts.",
    )
    front: SketchPolishSidePayload
    back: SketchPolishSidePayload

    @field_validator("shared_garment_spec")
    @classmethod
    def _shared_spec(cls, value: dict[str, Any] | str) -> dict[str, Any] | str:
        return _validate_shared_garment_spec_value(value)

    @field_validator("content_fingerprint")
    @classmethod
    def _strip_fingerprint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("front", "back")
    @classmethod
    def _side_has_image(cls, value: SketchPolishSidePayload) -> SketchPolishSidePayload:
        has_b64 = isinstance(value.image_base64, str) and value.image_base64.strip()
        has_url = isinstance(value.image_url, str) and value.image_url.strip()
        if not has_b64 and not has_url:
            raise ValueError("each side must include image_base64 or image_url")
        return value

    @field_validator("back")
    @classmethod
    def _distinct_idempotency_keys(
        cls, back: SketchPolishSidePayload, info
    ) -> SketchPolishSidePayload:
        front = info.data.get("front")
        if (
            isinstance(front, SketchPolishSidePayload)
            and front.idempotency_key.strip() == back.idempotency_key.strip()
        ):
            raise ValueError("front and back idempotency_key must differ")
        return back

    @model_validator(mode="after")
    def _revision_binding(self) -> "SketchPolishDualBody":
        has_fp = isinstance(self.content_fingerprint, str) and self.content_fingerprint.strip()
        if self.source_revision is None and not has_fp:
            raise ValueError("source_revision or content_fingerprint is required")
        return self


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


class MagicOperationJobsRead(BaseModel):
    """GET /ai/magic-operations/{id}/jobs — recovery poll for a coordinated dual run."""

    magic_operation_id: uuid.UUID
    jobs: list[AIJobRead]


class ApprovedGarmentPiece(BaseModel):
    category: Literal["tops", "bottoms", "one-pieces", "auto"]
    image_base64: str = Field(min_length=32)

    model_config = ConfigDict(extra="forbid")


class PersonalTryOnBody(BaseModel):
    """POST /ai/personal-try-on — photorealistic try-on on original croquis photo."""

    croquis_id: uuid.UUID
    croquis_version: int = Field(ge=1)
    garment_image_base64: str = Field(min_length=32)
    idempotency_key: str = Field(min_length=1, max_length=128)
    design_id: uuid.UUID | None = None
    source_revision: int = Field(ge=1)
    content_fingerprint: str = Field(min_length=1, max_length=128)
    consent_acknowledged: bool = False
    consent_version: str = Field(min_length=1, max_length=64)
    # Optional Studio-derived color/material/accessory hints (never invent beyond image 2).
    design_hints: list[str] | None = Field(default=None, max_length=8)
    # Explicit provider choice — never auto-switched after a refusal.
    # fashn_max = owner-only Try-On Max experiment (#173).
    provider: Literal["openai", "fashn", "fashn_max"] = "openai"
    # Owner-accepted realistic product plates (required for FASHN after #161).
    approved_garment_pieces: list[ApprovedGarmentPiece] | None = None
    garment_realism_job_id: uuid.UUID | None = None
    # Max experiment knobs (ignored unless provider=fashn_max).
    fashn_max_generation_mode: Literal["fast", "balanced", "quality"] | None = None
    fashn_max_resolution: Literal["1k", "2k", "4k"] | None = None
    fashn_max_prompt: str | None = Field(default=None, max_length=1000)
    fashn_max_seed: int | None = Field(default=None, ge=0, le=4_294_967_295)

    model_config = ConfigDict(extra="forbid")


class PersonalTryOnFashnPrepareBody(BaseModel):
    """POST /ai/personal-try-on/fashn/prepare — offline garment plate preview (no paid call)."""

    garment_image_base64: str = Field(min_length=32)

    model_config = ConfigDict(extra="forbid")


class PersonalTryOnFashnPrepareRead(BaseModel):
    layout: str
    fashn_calls: int
    estimate_cents: int
    realism_calls: int = 1
    realism_estimate_cents: int = 8
    combined_estimate_cents: int = 16
    garment_fingerprint: str
    quality_ok: bool = True
    quality_notes: str = ""
    composite_preview_base64: str
    pieces: list[dict]
    notes: str
    consent_version: str
    notice_text: str
    notice_hash: str
    provider: str = "fashn"
    configured: bool
    live_http: bool
    openai_live_http: bool = False


class PersonalGarmentRealismBody(BaseModel):
    """POST /ai/personal-try-on/fashn/garment-realism — paid OpenAI product-image stage."""

    croquis_id: uuid.UUID
    croquis_version: int = Field(ge=1)
    garment_image_base64: str = Field(min_length=32)
    plate_pieces: list[ApprovedGarmentPiece] = Field(min_length=1, max_length=4)
    garment_fingerprint: str = Field(min_length=8, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    design_id: uuid.UUID | None = None
    consent_acknowledged: bool = False
    consent_version: str = Field(min_length=1, max_length=64)

    model_config = ConfigDict(extra="forbid")


class PersonalTryOnPreflightRead(BaseModel):
    enabled: bool
    live_http: bool
    consent_version: str
    notice_text: str
    notice_hash: str
    prompt_version: str
    estimate_cents: int
    max_exposure_cents: int
    # Optional FASHN specialist path (explicit user choice).
    fashn_enabled: bool = False
    fashn_configured: bool = False
    fashn_live_http: bool = False
    fashn_consent_version: str | None = None
    fashn_notice_text: str | None = None
    fashn_notice_hash: str | None = None
    fashn_estimate_cents_per_call: int | None = None
    fashn_prompt_version: str | None = None
    fashn_realism_estimate_cents_per_piece: int | None = None
    fashn_combined_estimate_cents_one_piece: int | None = None
    fashn_one_click: bool = False
    # Owner-only Try-On Max experiment (#173) — server-gated; FE must not invent access.
    fashn_max_enabled: bool = False
    fashn_max_configured: bool = False
    fashn_max_live_http: bool = False
    fashn_max_owner_allowed: bool = False
    fashn_max_prompt_version: str | None = None
    fashn_max_default_prompt: str | None = None
    fashn_max_default_generation_mode: str | None = None
    fashn_max_default_resolution: str | None = None
    fashn_max_soft_budget_credits: int | None = None
    fashn_max_credits_balanced_1k: int | None = None
    fashn_max_credits_quality_1k: int | None = None
    fashn_max_estimate_cents_balanced_1k: int | None = None
    fashn_max_estimate_cents_quality_1k: int | None = None
