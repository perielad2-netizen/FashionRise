import base64
import binascii
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.ai_job import AIJob
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.ai import STUDIO_SIDES, AIJobCreate, SketchPolishDualBody
from app.services.reference_croquis import reference_from_job_input
from app.storage.local import LocalStorageBackend

_IDEMPOTENT_STATUSES = frozenset({"queued", "completed"})

_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _normalize_idempotency_key(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    key = raw.strip()
    if not key or len(key) > 128:
        if key and len(key) > 128:
            raise ValidationAppError("idempotency_key is too long")
        return None
    return key


def _validate_studio_side(input_data: dict) -> None:
    raw = input_data.get("studio_side")
    if raw is None or raw == "":
        return
    if not isinstance(raw, str):
        raise ValidationAppError("studio_side must be a string")
    side = raw.strip().lower()
    if side not in STUDIO_SIDES:
        raise ValidationAppError("studio_side must be 'front' or 'back'")


def find_sketch_polish_by_idempotency(
    db: Session, user_id: uuid.UUID, idempotency_key: str
) -> AIJob | None:
    key = idempotency_key.strip()
    if not key:
        return None
    return (
        db.query(AIJob)
        .filter(
            AIJob.user_id == user_id,
            AIJob.job_type == "sketch_polish",
            AIJob.status.in_(tuple(_IDEMPOTENT_STATUSES)),
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .order_by(AIJob.created_at.desc())
        .first()
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


def _prepare_sketch_polish_input(input_data: dict | None) -> dict:
    raw = dict(input_data or {})
    _validate_studio_side(raw)
    idem = _normalize_idempotency_key(raw.get("idempotency_key"))
    if idem is not None:
        raw["idempotency_key"] = idem
    elif "idempotency_key" in raw and not str(raw.get("idempotency_key") or "").strip():
        raw.pop("idempotency_key", None)
    op = raw.get("magic_operation_id")
    if isinstance(op, str) and op.strip():
        raw["magic_operation_id"] = op.strip()
    return raw


def enqueue_job(db: Session, user: User, data: AIJobCreate) -> AIJob:
    if data.design_id:
        design = db.get(GarmentDesign, data.design_id)
        if not design:
            raise NotFoundError("Design not found")
        if design.user_id != user.id:
            raise ForbiddenError("Not allowed for this design")
    input_data = data.input_data if isinstance(data.input_data, dict) else {}
    if data.job_type in {"sketch_clean", "sketch_polish", "style_suggest"}:
        _validate_sketch_image_payload(input_data)
    if data.job_type == "sketch_polish":
        input_data = _prepare_sketch_polish_input(input_data)
        idem = input_data.get("idempotency_key")
        if isinstance(idem, str) and idem:
            existing = find_sketch_polish_by_idempotency(db, user.id, idem)
            if existing is not None:
                return existing
        reference_from_job_input(input_data)
        data = AIJobCreate(
            design_id=data.design_id,
            job_type=data.job_type,
            input_data=input_data,
        )
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


def _dual_shared_fields(body: SketchPolishDualBody) -> dict[str, Any]:
    shared: dict[str, Any] = {}
    if body.notes:
        shared["notes"] = body.notes
    if body.mood_notes:
        shared["mood_notes"] = body.mood_notes
    if body.reference_model_id:
        shared["reference_model_id"] = body.reference_model_id
    if body.shared_garment_spec is not None:
        shared["shared_garment_spec"] = body.shared_garment_spec
    return shared


def _merge_dual_side_input(
    side: str,
    side_payload: dict[str, Any],
    shared: dict[str, Any],
    operation_id: str,
) -> dict[str, Any]:
    merged = dict(shared)
    merged.update(side_payload)
    merged["studio_side"] = side
    merged["magic_operation_id"] = operation_id
    return _prepare_sketch_polish_input(merged)


def enqueue_dual_sketch_polish(
    db: Session, user: User, body: SketchPolishDualBody
) -> tuple[AIJob, AIJob, uuid.UUID]:
    """Enqueue coordinated front/back sketch_polish jobs (one transaction)."""
    if body.design_id:
        design = db.get(GarmentDesign, body.design_id)
        if not design:
            raise NotFoundError("Design not found")
        if design.user_id != user.id:
            raise ForbiddenError("Not allowed for this design")

    operation_id = body.magic_operation_id or uuid.uuid4()
    op_str = str(operation_id)
    shared = _dual_shared_fields(body)
    front_payload = body.front.model_dump(exclude_none=True)
    back_payload = body.back.model_dump(exclude_none=True)
    front_input = _merge_dual_side_input("front", front_payload, shared, op_str)
    back_input = _merge_dual_side_input("back", back_payload, shared, op_str)

    _validate_sketch_image_payload(front_input)
    _validate_sketch_image_payload(back_input)
    reference_from_job_input(front_input)
    reference_from_job_input(back_input)

    front_idem = front_input.get("idempotency_key")
    back_idem = back_input.get("idempotency_key")
    front_existing = (
        find_sketch_polish_by_idempotency(db, user.id, front_idem)
        if isinstance(front_idem, str) and front_idem
        else None
    )
    back_existing = (
        find_sketch_polish_by_idempotency(db, user.id, back_idem)
        if isinstance(back_idem, str) and back_idem
        else None
    )

    if front_existing is not None and back_existing is not None:
        return front_existing, back_existing, operation_id

    front_job = front_existing or AIJob(
        user_id=user.id,
        design_id=body.design_id,
        job_type="sketch_polish",
        status="queued",
        input_data=front_input,
        result_data=None,
        error_message=None,
    )
    back_job = back_existing or AIJob(
        user_id=user.id,
        design_id=body.design_id,
        job_type="sketch_polish",
        status="queued",
        input_data=back_input,
        result_data=None,
        error_message=None,
    )
    if front_existing is None:
        db.add(front_job)
    if back_existing is None:
        db.add(back_job)
    db.commit()
    if front_existing is None:
        db.refresh(front_job)
    if back_existing is None:
        db.refresh(back_job)
    return front_job, back_job, operation_id


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
