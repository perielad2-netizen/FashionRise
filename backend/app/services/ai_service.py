import base64
import binascii
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.ai_job import AIJob
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.ai import AIJobCreate
from app.storage.local import LocalStorageBackend

_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _validate_sketch_image_payload(input_data: dict) -> None:
    """Bound vision payloads before enqueue (no OpenAI call)."""
    if not isinstance(input_data, dict):
        raise ValidationAppError("input_data must be an object")
    raw = input_data.get("image_base64")
    if raw is None or raw == "":
        return
    if not isinstance(raw, str):
        raise ValidationAppError("image_base64 must be a string")
    settings = get_settings()
    max_bytes = settings.max_upload_bytes
    match = _DATA_URL_RE.match(raw.strip())
    b64 = match.group(2) if match else raw.strip()
    # Reject obviously oversized base64 before decoding (~4/3 expansion).
    if len(b64) > int(max_bytes * 1.4) + 64:
        raise ValidationAppError("Sketch image is too large")
    try:
        decoded = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValidationAppError("Sketch image payload is not valid base64") from exc
    if not decoded:
        raise ValidationAppError("Sketch image payload is empty")
    if len(decoded) > max_bytes:
        raise ValidationAppError("Sketch image is too large")


def enqueue_job(db: Session, user: User, data: AIJobCreate) -> AIJob:
    if data.design_id:
        design = db.get(GarmentDesign, data.design_id)
        if not design:
            raise NotFoundError("Design not found")
        if design.user_id != user.id:
            raise ForbiddenError("Not allowed for this design")
    if data.job_type in {"sketch_clean", "sketch_polish", "style_suggest"}:
        _validate_sketch_image_payload(data.input_data or {})
    job = AIJob(
        user_id=user.id,
        design_id=data.design_id,
        job_type=data.job_type,
        status="queued",
        input_data=data.input_data,
        result_data=None,
        error_message=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user: User, job_id: uuid.UUID) -> AIJob:
    job = db.get(AIJob, job_id)
    if not job or job.user_id != user.id:
        raise NotFoundError("Job not found")
    return job


_REDACTED_IMAGE_KEYS = ("image_base64", "imageBase64")


def sanitize_job_input_for_response(input_data: dict | None) -> dict:
    """Omit large sketch payloads from API responses; keep DB/worker input intact.

    Unity-compatible: other input_data keys (notes, local_path_placeholder, etc.)
    remain. When a sketch was present, set has_sketch_image=true.
    """
    raw = dict(input_data or {})
    had_image = False
    for key in _REDACTED_IMAGE_KEYS:
        if key in raw:
            had_image = True
            raw.pop(key, None)
    if had_image:
        raw["has_sketch_image"] = True
    return raw


_RESULT_STRIP_KEYS = frozenset(
    {
        "image_base64",
        "imageBase64",
        "b64_json",
        "prompt",
        "image_prompt",
        "moderation_details",
        "raw_error",
        "provider_body",
        "body",
    }
)


def sanitize_job_result_for_response(result_data: dict | None) -> dict | None:
    """Expose only safe result fields; re-normalize failure diagnostics via allowlists."""
    if result_data is None:
        return None
    if not isinstance(result_data, dict):
        return None
    from app.services import sketch_openai

    out: dict = {}
    for key, value in result_data.items():
        if key in _RESULT_STRIP_KEYS:
            continue
        if key == "error":
            cleaned = sketch_openai.normalize_failure_meta(value if isinstance(value, dict) else {})
            if cleaned:
                out["error"] = cleaned
            continue
        out[key] = value
    return out


def extract_result_image_url(result_data: dict | None) -> str | None:
    if not isinstance(result_data, dict):
        return None
    for key in ("image_url", "imageUrl"):
        value = result_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_job_image_file(db: Session, user: User, job_id: uuid.UUID) -> Path:
    """Return the on-disk look image for an owned completed job (authenticated retrieval)."""
    job = get_job(db, user, job_id)
    if job.status != "completed":
        raise NotFoundError("Job image not available")
    url = extract_result_image_url(job.result_data if isinstance(job.result_data, dict) else None)
    if not url:
        raise NotFoundError("Job image not available")
    storage = LocalStorageBackend()
    key = storage.key_from_public_url(url)
    if not key:
        raise NotFoundError("Job image not available")
    path = storage.resolve_existing_file(key=key)
    if path is None:
        raise NotFoundError("Job image not available")
    return path
