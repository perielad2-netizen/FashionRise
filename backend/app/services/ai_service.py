import base64
import binascii
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.models.ai_job import AIJob
from app.models.garment_design import GarmentDesign
from app.models.user import User
from app.schemas.ai import STUDIO_SIDES, AIJobCreate, SketchPolishDualBody
from app.services.reference_croquis import reference_from_job_input
from app.storage.local import LocalStorageBackend

# Durable across all terminal/active states — a failed paid attempt must not
# silently mint another job under the same idempotency key.
_IDEMPOTENT_STATUSES = frozenset({"queued", "running", "completed", "failed"})
_ACTIVE_ATTEMPT_STATUSES = frozenset({"queued", "running", "completed"})

_DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _dual_magic_lock_key(user_id: uuid.UUID) -> int:
    """Owner-scoped advisory lock distinct from Studio/saved design locks."""
    raw = bytearray(user_id.bytes[:8])
    raw[0] ^= 0xC7
    return int.from_bytes(raw, "big", signed=True)


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


def _decode_sketch_image_bytes(input_data: dict) -> bytes | None:
    raw = input_data.get("image_base64")
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise ValidationAppError("image_base64 must be a string")
    match = _DATA_URL_RE.match(raw.strip())
    b64 = match.group(2) if match else raw.strip()
    try:
        decoded = base64.b64decode(b64, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValidationAppError("Sketch image payload is not valid base64") from exc
    return decoded


def _compute_image_fingerprint(input_data: dict) -> str | None:
    decoded = _decode_sketch_image_bytes(input_data)
    if decoded:
        if not decoded:
            raise ValidationAppError("Sketch image payload is empty")
        return hashlib.sha256(decoded).hexdigest()
    url = input_data.get("image_url")
    if isinstance(url, str) and url.strip():
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
    return None


def _prompt_identity_fingerprint(input_data: dict) -> str | None:
    """Canonical prompt/context identity so key reuse cannot return the wrong look."""
    payload = {
        "shared_garment_spec": input_data.get("shared_garment_spec"),
        "reference_model_id": input_data.get("reference_model_id"),
        "notes": input_data.get("notes"),
        "mood_notes": input_data.get("mood_notes"),
    }
    if all(v is None or v == "" for v in payload.values()):
        return None
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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


def _latest_operation_side_job(
    db: Session, user_id: uuid.UUID, operation_id: str, side: str
) -> AIJob | None:
    rows = (
        db.query(AIJob)
        .filter(
            AIJob.user_id == user_id,
            AIJob.job_type == "sketch_polish",
            AIJob.input_data["magic_operation_id"].astext == operation_id,
            AIJob.input_data["studio_side"].astext == side,
        )
        .order_by(AIJob.created_at.desc())
        .all()
    )
    return rows[0] if rows else None


def _design_id_str(design_id: uuid.UUID | None) -> str | None:
    return str(design_id) if design_id is not None else None


def _input_design_id_str(input_data: dict) -> str | None:
    raw = input_data.get("design_id")
    if raw is None or raw == "":
        return None
    return str(raw).strip() or None


def _identity_tuple(
    *,
    studio_side: str | None,
    magic_operation_id: str | None,
    design_id: uuid.UUID | None,
    input_data: dict,
    image_fingerprint: str | None,
) -> tuple[Any, ...]:
    rev = input_data.get("source_revision")
    fp = input_data.get("content_fingerprint")
    content_fp = fp.strip() if isinstance(fp, str) else None
    design = _design_id_str(design_id) or _input_design_id_str(input_data)
    prompt_fp = input_data.get("prompt_fingerprint")
    if not isinstance(prompt_fp, str) or not prompt_fp.strip():
        prompt_fp = _prompt_identity_fingerprint(input_data)
    return (
        (studio_side or "").strip().lower() or None,
        (magic_operation_id or "").strip() or None,
        design,
        rev,
        content_fp or None,
        image_fingerprint,
        prompt_fp if isinstance(prompt_fp, str) and prompt_fp.strip() else None,
    )


def _is_linked_dual_attempt(input_data: dict) -> bool:
    """True when /polish carries both operation id and studio side (Front/Back link)."""
    op = input_data.get("magic_operation_id")
    side = input_data.get("studio_side")
    if not isinstance(op, str) or not op.strip():
        return False
    if not isinstance(side, str):
        return False
    return side.strip().lower() in STUDIO_SIDES


def _require_linked_attempt_fields(input_data: dict) -> None:
    if _normalize_idempotency_key(input_data.get("idempotency_key")) is None:
        raise ValidationAppError(
            "Linked Front/Back Magic requires a stable idempotency_key per attempt."
        )
    rev = input_data.get("source_revision")
    fp = input_data.get("content_fingerprint")
    has_rev = isinstance(rev, int)
    has_fp = isinstance(fp, str) and bool(fp.strip())
    if not has_rev and not has_fp:
        raise ValidationAppError(
            "Linked Front/Back Magic requires source_revision or content_fingerprint."
        )


def _garment_identity_fingerprint(input_data: dict) -> str | None:
    """Garment/model brief only — excludes per-side notes that may differ on retry."""
    payload = {
        "shared_garment_spec": input_data.get("shared_garment_spec"),
        "reference_model_id": input_data.get("reference_model_id"),
    }
    if all(v is None or v == "" for v in payload.values()):
        return None
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _operation_identity_tuple(
    *,
    magic_operation_id: str,
    design_id: uuid.UUID | None,
    input_data: dict,
) -> tuple[Any, ...]:
    """Immutable operation identity for retries — excludes per-attempt raster hash.

    A deliberate re-capture of the same Studio document may change image bytes;
    design id + revision/fingerprint + garment/model brief must stay identical.
    Per-side ``notes`` are not part of this tuple.
    """
    rev = input_data.get("source_revision")
    fp = input_data.get("content_fingerprint")
    content_fp = fp.strip() if isinstance(fp, str) else None
    design = _design_id_str(design_id) or _input_design_id_str(input_data)
    garment_fp = _garment_identity_fingerprint(input_data)
    return (
        (magic_operation_id or "").strip() or None,
        design,
        rev if isinstance(rev, int) else None,
        content_fp or None,
        garment_fp,
    )


def _assert_operation_identity_unchanged(
    existing: AIJob,
    *,
    magic_operation_id: str,
    design_id: uuid.UUID | None,
    prepared_input: dict,
) -> None:
    stored = existing.input_data if isinstance(existing.input_data, dict) else {}
    expected = _operation_identity_tuple(
        magic_operation_id=magic_operation_id,
        design_id=design_id,
        input_data=prepared_input,
    )
    actual = _operation_identity_tuple(
        magic_operation_id=stored.get("magic_operation_id")
        if isinstance(stored.get("magic_operation_id"), str)
        else magic_operation_id,
        design_id=existing.design_id,
        input_data=stored,
    )
    if expected != actual:
        raise ConflictError(
            "Cannot retry Magic — the underlying design identity changed.",
            payload={
                "reason": "operation_identity_mismatch",
                "job_id": str(existing.id),
                "status": existing.status,
            },
        )


def _assert_idempotency_identity(
    existing: AIJob,
    *,
    expected_side: str | None,
    magic_operation_id: str,
    design_id: uuid.UUID | None,
    prepared_input: dict,
    image_fingerprint: str | None,
) -> None:
    stored = existing.input_data if isinstance(existing.input_data, dict) else {}
    stored_fp = stored.get("image_fingerprint")
    if not isinstance(stored_fp, str) or not stored_fp.strip():
        stored_fp = _compute_image_fingerprint(stored)
    expected = _identity_tuple(
        studio_side=expected_side,
        magic_operation_id=magic_operation_id,
        design_id=design_id,
        input_data=prepared_input,
        image_fingerprint=image_fingerprint,
    )
    actual = _identity_tuple(
        studio_side=stored.get("studio_side") if isinstance(stored.get("studio_side"), str) else None,
        magic_operation_id=stored.get("magic_operation_id")
        if isinstance(stored.get("magic_operation_id"), str)
        else None,
        design_id=existing.design_id,
        input_data=stored,
        image_fingerprint=stored_fp if isinstance(stored_fp, str) else None,
    )
    if expected != actual:
        raise ConflictError(
            "Idempotency key already used with different sketch identity.",
            payload={
                "reason": "idempotency_identity_mismatch",
                "job_id": str(existing.id),
                "status": existing.status,
            },
        )
    if expected_side:
        stored_side = stored.get("studio_side")
        if isinstance(stored_side, str) and stored_side.strip().lower() != expected_side:
            raise ConflictError(
                "Idempotency key already used for the opposite studio side.",
                payload={"reason": "idempotency_cross_side", "job_id": str(existing.id)},
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
    if len(b64) > int(max_bytes * 1.4) + 64:
        raise ValidationAppError("Sketch image is too large")
    decoded = _decode_sketch_image_bytes(input_data)
    if not decoded:
        raise ValidationAppError("Sketch image payload is empty")
    if len(decoded) > max_bytes:
        raise ValidationAppError("Sketch image is too large")


def _stamp_revision_fields(raw: dict, source_revision: int | None, content_fingerprint: str | None) -> None:
    if source_revision is not None:
        raw["source_revision"] = source_revision
    if isinstance(content_fingerprint, str) and content_fingerprint.strip():
        raw["content_fingerprint"] = content_fingerprint.strip()


def _prepare_sketch_polish_input(
    input_data: dict | None,
    *,
    design_id: uuid.UUID | None = None,
    source_revision: int | None = None,
    content_fingerprint: str | None = None,
) -> dict:
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
    if design_id is not None:
        raw["design_id"] = str(design_id)
    _stamp_revision_fields(raw, source_revision, content_fingerprint)
    img_fp = _compute_image_fingerprint(raw)
    if img_fp:
        raw["image_fingerprint"] = img_fp
    prompt_fp = _prompt_identity_fingerprint(raw)
    if prompt_fp:
        raw["prompt_fingerprint"] = prompt_fp
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
        rev = input_data.get("source_revision")
        source_revision = rev if isinstance(rev, int) else None
        content_fp = input_data.get("content_fingerprint")
        content_fingerprint = content_fp.strip() if isinstance(content_fp, str) else None
        input_data = _prepare_sketch_polish_input(
            input_data,
            design_id=data.design_id,
            source_revision=source_revision,
            content_fingerprint=content_fingerprint,
        )
        linked = _is_linked_dual_attempt(input_data)
        if linked:
            # Linked Front/Back attempts always use the dual reconcile path:
            # require key + identity, owner lock, one active attempt per side,
            # same-key replay (incl. failed), new key only after explicit failure.
            _require_linked_attempt_fields(input_data)
            side_raw = input_data.get("studio_side")
            side = side_raw.strip().lower() if isinstance(side_raw, str) else ""
            op_raw = input_data.get("magic_operation_id")
            op_str = op_raw.strip() if isinstance(op_raw, str) else ""
            idem = input_data.get("idempotency_key")
            assert isinstance(idem, str) and idem  # enforced above
            reference_from_job_input(input_data)
            db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _dual_magic_lock_key(user.id)})
            existing = find_sketch_polish_by_idempotency(db, user.id, idem)
            job, is_new = _reconcile_or_prepare_job(
                db,
                user,
                existing,
                side=side,
                prepared_input=input_data,
                design_id=data.design_id,
                operation_id=op_str,
            )
            if is_new:
                db.add(job)
                db.commit()
                db.refresh(job)
            return job

        idem = input_data.get("idempotency_key")
        # Ordinary single-side Magic: optional key with identity-bound replay.
        if isinstance(idem, str) and idem:
            db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _dual_magic_lock_key(user.id)})
            existing = find_sketch_polish_by_idempotency(db, user.id, idem)
            if existing is not None:
                side = input_data.get("studio_side")
                expected_side = side.strip().lower() if isinstance(side, str) else None
                op = input_data.get("magic_operation_id")
                op_str = op.strip() if isinstance(op, str) else ""
                _assert_idempotency_identity(
                    existing,
                    expected_side=expected_side,
                    magic_operation_id=op_str,
                    design_id=data.design_id,
                    prepared_input=input_data,
                    image_fingerprint=input_data.get("image_fingerprint"),
                )
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
    shared: dict[str, Any] = {"shared_garment_spec": body.shared_garment_spec}
    if body.notes:
        shared["notes"] = body.notes
    if body.mood_notes:
        shared["mood_notes"] = body.mood_notes
    if body.reference_model_id:
        shared["reference_model_id"] = body.reference_model_id
    return shared


def _merge_dual_side_input(
    side: str,
    side_payload: dict[str, Any],
    shared: dict[str, Any],
    operation_id: str,
    *,
    design_id: uuid.UUID | None,
    source_revision: int | None,
    content_fingerprint: str | None,
) -> dict[str, Any]:
    merged = dict(shared)
    merged.update(side_payload)
    merged["studio_side"] = side
    merged["magic_operation_id"] = operation_id
    return _prepare_sketch_polish_input(
        merged,
        design_id=design_id,
        source_revision=source_revision,
        content_fingerprint=content_fingerprint,
    )


def _reconcile_or_prepare_job(
    db: Session,
    user: User,
    existing_by_key: AIJob | None,
    *,
    side: str,
    prepared_input: dict[str, Any],
    design_id: uuid.UUID | None,
    operation_id: str,
) -> tuple[AIJob, bool]:
    """Return (job, is_new). Retries require a new key only when latest side attempt failed."""
    latest = _latest_operation_side_job(db, user.id, operation_id, side)
    request_key = prepared_input.get("idempotency_key")
    request_key = request_key.strip() if isinstance(request_key, str) else ""

    if existing_by_key is not None:
        _assert_idempotency_identity(
            existing_by_key,
            expected_side=side,
            magic_operation_id=operation_id,
            design_id=design_id,
            prepared_input=prepared_input,
            image_fingerprint=prepared_input.get("image_fingerprint"),
        )
        return existing_by_key, False

    if latest is not None:
        latest_key = ""
        if isinstance(latest.input_data, dict):
            raw_key = latest.input_data.get("idempotency_key")
            latest_key = raw_key.strip() if isinstance(raw_key, str) else ""
        if latest.status in _ACTIVE_ATTEMPT_STATUSES:
            raise ConflictError(
                "Magic operation already has an active attempt for this side. "
                "Reuse the original idempotency key or wait for completion.",
                payload={
                    "reason": "operation_side_active",
                    "studio_side": side,
                    "job_id": str(latest.id),
                    "status": latest.status,
                },
            )
        if latest.status == "failed" and request_key and request_key == latest_key:
            # Durable failed-key replay: return original, create zero new jobs.
            _assert_idempotency_identity(
                latest,
                expected_side=side,
                magic_operation_id=operation_id,
                design_id=design_id,
                prepared_input=prepared_input,
                image_fingerprint=prepared_input.get("image_fingerprint"),
            )
            return latest, False
        if latest.status != "failed":
            raise ConflictError(
                "Magic operation side cannot accept a new attempt in its current state.",
                payload={
                    "reason": "operation_side_blocked",
                    "studio_side": side,
                    "job_id": str(latest.id),
                    "status": latest.status,
                },
            )
        # latest failed + new key → explicit retry; garment/design identity must match.
        _assert_operation_identity_unchanged(
            latest,
            magic_operation_id=operation_id,
            design_id=design_id,
            prepared_input=prepared_input,
        )

    job = AIJob(
        user_id=user.id,
        design_id=design_id,
        job_type="sketch_polish",
        status="queued",
        input_data=prepared_input,
        result_data=None,
        error_message=None,
    )
    return job, True


def enqueue_dual_sketch_polish(
    db: Session, user: User, body: SketchPolishDualBody
) -> tuple[AIJob, AIJob, uuid.UUID]:
    """Enqueue coordinated front/back sketch_polish jobs under an owner advisory lock."""
    if body.design_id:
        design = db.get(GarmentDesign, body.design_id)
        if not design:
            raise NotFoundError("Design not found")
        if design.user_id != user.id:
            raise ForbiddenError("Not allowed for this design")

    operation_id = body.magic_operation_id
    op_str = str(operation_id)
    shared = _dual_shared_fields(body)
    front_payload = body.front.model_dump(exclude_none=True)
    back_payload = body.back.model_dump(exclude_none=True)
    front_input = _merge_dual_side_input(
        "front",
        front_payload,
        shared,
        op_str,
        design_id=body.design_id,
        source_revision=body.source_revision,
        content_fingerprint=body.content_fingerprint,
    )
    back_input = _merge_dual_side_input(
        "back",
        back_payload,
        shared,
        op_str,
        design_id=body.design_id,
        source_revision=body.source_revision,
        content_fingerprint=body.content_fingerprint,
    )

    _validate_sketch_image_payload(front_input)
    _validate_sketch_image_payload(back_input)
    reference_from_job_input(front_input)
    reference_from_job_input(back_input)

    front_idem = front_input["idempotency_key"]
    back_idem = back_input["idempotency_key"]

    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _dual_magic_lock_key(user.id)})

    front_existing = find_sketch_polish_by_idempotency(db, user.id, front_idem)
    back_existing = find_sketch_polish_by_idempotency(db, user.id, back_idem)

    front_job, front_is_new = _reconcile_or_prepare_job(
        db,
        user,
        front_existing,
        side="front",
        prepared_input=front_input,
        design_id=body.design_id,
        operation_id=op_str,
    )
    back_job, back_is_new = _reconcile_or_prepare_job(
        db,
        user,
        back_existing,
        side="back",
        prepared_input=back_input,
        design_id=body.design_id,
        operation_id=op_str,
    )

    if front_is_new:
        db.add(front_job)
    if back_is_new:
        db.add(back_job)
    db.commit()
    if front_is_new:
        db.refresh(front_job)
    if back_is_new:
        db.refresh(back_job)
    return front_job, back_job, operation_id


def list_jobs_for_magic_operation(
    db: Session, user: User, operation_id: uuid.UUID
) -> list[AIJob]:
    op = str(operation_id)
    rows = (
        db.query(AIJob)
        .filter(
            AIJob.user_id == user.id,
            AIJob.job_type == "sketch_polish",
            AIJob.input_data["magic_operation_id"].astext == op,
        )
        .order_by(AIJob.created_at.asc())
        .all()
    )
    return rows


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
