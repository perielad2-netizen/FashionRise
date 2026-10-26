"""My Looks: aggregate completed sketch_polish jobs into owner-scoped gallery looks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationAppError
from app.models.ai_job import AIJob
from app.models.magic_look_meta import MagicLookMeta
from app.models.user import User
from app.schemas.look import LookListResponse, LookRead, LookSideRef, LookUpdate
from app.services.ai_service import extract_result_image_url
from app.storage.local import LocalStorageBackend


def _meta_deleted(meta: MagicLookMeta | None) -> bool:
    return bool(meta is not None and meta.is_deleted)

LookFilter = Literal["all", "favorites", "archived"]

_TITLE_MAX = 120


@dataclass
class _SideCandidate:
    job: AIJob
    studio_side: str | None
    has_image: bool
    summary: str | None


@dataclass
class _LookBucket:
    look_id: uuid.UUID
    magic_operation_id: uuid.UUID | None
    jobs: list[AIJob] = field(default_factory=list)


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


def _look_id_for_job(job: AIJob) -> tuple[uuid.UUID, uuid.UUID | None]:
    data = job.input_data if isinstance(job.input_data, dict) else {}
    op = _parse_uuid(data.get("magic_operation_id"))
    if op is not None:
        return op, op
    return job.id, None


def _studio_side(job: AIJob) -> str | None:
    data = job.input_data if isinstance(job.input_data, dict) else {}
    raw = data.get("studio_side")
    if not isinstance(raw, str):
        return None
    side = raw.strip().lower()
    return side if side in ("front", "back") else None


def _job_summary(job: AIJob) -> str | None:
    result = job.result_data if isinstance(job.result_data, dict) else {}
    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()[:500]
    return None


def _image_available(job: AIJob, storage: LocalStorageBackend) -> bool:
    if job.status != "completed":
        return False
    url = extract_result_image_url(job.result_data if isinstance(job.result_data, dict) else None)
    if not url:
        return False
    key = storage.key_from_public_url(url)
    if not key:
        return False
    return storage.resolve_existing_file(key=key) is not None


def _default_title(created_at: datetime) -> str:
    local = created_at.astimezone(UTC)
    return f"Look · {local.strftime('%b %d, %Y')}"


def _normalize_title(raw: str | None) -> str | None:
    if raw is None:
        return None
    title = " ".join(raw.split()).strip()
    if not title:
        raise ValidationAppError("Title cannot be empty")
    if len(title) > _TITLE_MAX:
        raise ValidationAppError(f"Title must be at most {_TITLE_MAX} characters")
    return title


def _pick_side(jobs: list[AIJob], side: str | None, storage: LocalStorageBackend) -> _SideCandidate | None:
    """Prefer latest completed job with an available image; never prefer failed over success."""
    matched: list[AIJob] = []
    for job in jobs:
        job_side = _studio_side(job)
        if side is None:
            if job_side in (None, "front"):
                matched.append(job)
        elif job_side == side:
            matched.append(job)
    if not matched:
        return None
    matched.sort(key=lambda j: j.created_at, reverse=True)
    # Prefer completed-with-image, then completed, then latest attempt (for status display).
    with_image = [j for j in matched if _image_available(j, storage)]
    if with_image:
        job = with_image[0]
        return _SideCandidate(job=job, studio_side=_studio_side(job) or side, has_image=True, summary=_job_summary(job))
    completed = [j for j in matched if j.status == "completed"]
    job = completed[0] if completed else matched[0]
    return _SideCandidate(
        job=job,
        studio_side=_studio_side(job) or side,
        has_image=False,
        summary=_job_summary(job) if job.status == "completed" else None,
    )


def _side_ref(candidate: _SideCandidate | None) -> LookSideRef | None:
    if candidate is None:
        return None
    side = candidate.studio_side
    return LookSideRef(
        job_id=candidate.job.id,
        studio_side=side if side in ("front", "back") else None,
        has_image=candidate.has_image,
        summary=candidate.summary,
        created_at=candidate.job.created_at,
    )


def _to_look_read(
    bucket: _LookBucket,
    meta: MagicLookMeta | None,
    storage: LocalStorageBackend,
) -> LookRead | None:
    front = _pick_side(bucket.jobs, "front", storage)
    back = _pick_side(bucket.jobs, "back", storage)
    # Historical single jobs often omit studio_side — treat as front.
    if front is None and back is None:
        front = _pick_side(bucket.jobs, None, storage)
    # A look is gallery-eligible only when at least one finished image exists.
    if not ((front and front.has_image) or (back and back.has_image)):
        return None

    created_candidates = [c.job.created_at for c in (front, back) if c and c.has_image]
    created_at = min(created_candidates) if created_candidates else bucket.jobs[0].created_at
    updated_candidates = [c.job.updated_at for c in (front, back) if c]
    updated_at = max(updated_candidates) if updated_candidates else created_at
    if meta is not None:
        updated_at = max(updated_at, meta.updated_at)

    title = (meta.title if meta and meta.title else None) or _default_title(created_at)
    kind: Literal["single", "dual"] = "dual" if (front and front.has_image and back and back.has_image) else "single"
    # Partial dual (op id present, one side ready) still surfaces as dual when op exists.
    if bucket.magic_operation_id is not None and (front or back):
        has_front_side = any(_studio_side(j) == "front" for j in bucket.jobs)
        has_back_side = any(_studio_side(j) == "back" for j in bucket.jobs)
        if has_front_side and has_back_side and (
            (front and back) or (front and front.has_image) or (back and back.has_image)
        ):
            kind = "dual"

    design_id = None
    for job in sorted(bucket.jobs, key=lambda j: j.created_at, reverse=True):
        if job.design_id:
            design_id = job.design_id
            break

    front_ref = None
    if front and (front.has_image or (kind == "dual" and front.studio_side == "front")):
        front_ref = _side_ref(front)

    back_ref = None
    if back and (back.has_image or kind == "dual"):
        back_ref = _side_ref(back)

    return LookRead(
        id=bucket.look_id,
        title=title,
        is_favorite=bool(meta.is_favorite) if meta else False,
        is_archived=bool(meta.is_archived) if meta else False,
        kind=kind,
        created_at=created_at,
        updated_at=updated_at,
        front=front_ref,
        back=back_ref,
        design_id=design_id,
        magic_operation_id=bucket.magic_operation_id,
    )


def _load_polish_jobs(db: Session, user: User) -> list[AIJob]:
    return list(
        db.scalars(
            select(AIJob)
            .where(AIJob.user_id == user.id, AIJob.job_type == "sketch_polish")
            .order_by(AIJob.created_at.desc())
        ).all()
    )


def _build_buckets(jobs: list[AIJob]) -> list[_LookBucket]:
    buckets: dict[uuid.UUID, _LookBucket] = {}
    order: list[uuid.UUID] = []
    for job in jobs:
        look_id, op_id = _look_id_for_job(job)
        bucket = buckets.get(look_id)
        if bucket is None:
            bucket = _LookBucket(look_id=look_id, magic_operation_id=op_id)
            buckets[look_id] = bucket
            order.append(look_id)
        bucket.jobs.append(job)
        if op_id is not None:
            bucket.magic_operation_id = op_id
    return [buckets[i] for i in order]


def list_looks(
    db: Session,
    user: User,
    *,
    filter_name: LookFilter = "all",
    q: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> LookListResponse:
    if limit < 1 or limit > 100:
        raise ValidationAppError("limit must be between 1 and 100")
    if offset < 0:
        raise ValidationAppError("offset must be >= 0")
    if filter_name not in ("all", "favorites", "archived"):
        raise ValidationAppError("filter must be all, favorites, or archived")

    jobs = _load_polish_jobs(db, user)
    buckets = _build_buckets(jobs)
    storage = LocalStorageBackend()
    meta_rows = {
        row.id: row
        for row in db.scalars(select(MagicLookMeta).where(MagicLookMeta.user_id == user.id)).all()
    }

    looks: list[LookRead] = []
    for bucket in buckets:
        meta = meta_rows.get(bucket.look_id)
        if _meta_deleted(meta):
            continue
        read = _to_look_read(bucket, meta, storage)
        if read is None:
            continue
        looks.append(read)

    query = (q or "").strip().lower()
    filtered: list[LookRead] = []
    for look in looks:
        if filter_name == "all" and look.is_archived:
            continue
        if filter_name == "favorites" and (not look.is_favorite or look.is_archived):
            continue
        if filter_name == "archived" and not look.is_archived:
            continue
        if query and query not in look.title.lower():
            continue
        filtered.append(look)

    filtered.sort(key=lambda item: item.created_at, reverse=True)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return LookListResponse(items=page, total=total, limit=limit, offset=offset)


def get_look(db: Session, user: User, look_id: uuid.UUID) -> LookRead:
    jobs = _load_polish_jobs(db, user)
    buckets = {b.look_id: b for b in _build_buckets(jobs)}
    bucket = buckets.get(look_id)
    if bucket is None:
        raise NotFoundError("Look not found")
    meta = db.get(MagicLookMeta, look_id)
    if meta is not None and meta.user_id != user.id:
        raise NotFoundError("Look not found")
    if _meta_deleted(meta):
        raise NotFoundError("Look not found")
    storage = LocalStorageBackend()
    read = _to_look_read(bucket, meta if meta and meta.user_id == user.id else None, storage)
    if read is None:
        raise NotFoundError("Look not found")
    return read


def _ensure_meta(db: Session, user: User, look_id: uuid.UUID) -> MagicLookMeta:
    # Validate the look exists for this owner before writing metadata.
    get_look(db, user, look_id)
    row = db.get(MagicLookMeta, look_id)
    if row is None:
        row = MagicLookMeta(id=look_id, user_id=user.id)
        db.add(row)
        db.flush()
    elif row.user_id != user.id:
        raise NotFoundError("Look not found")
    if row.is_deleted:
        raise NotFoundError("Look not found")
    return row


def update_look(db: Session, user: User, look_id: uuid.UUID, data: LookUpdate) -> LookRead:
    if data.title is None and data.is_favorite is None and data.is_archived is None:
        raise ValidationAppError("No look fields to update")
    row = _ensure_meta(db, user, look_id)
    if data.title is not None:
        row.title = _normalize_title(data.title)
    if data.is_favorite is not None:
        row.is_favorite = bool(data.is_favorite)
    if data.is_archived is not None:
        row.is_archived = bool(data.is_archived)
    db.add(row)
    db.commit()
    return get_look(db, user, look_id)


def delete_look(db: Session, user: User, look_id: uuid.UUID) -> None:
    """Tombstone a look in magic_look_meta. Idempotent for the owner.

    Does not erase ai_jobs rows or generated image files. Deleted looks are
    excluded from list/get/patch; archive/restore cannot revive them.
    """
    meta = db.get(MagicLookMeta, look_id)
    if meta is not None and meta.user_id != user.id:
        raise NotFoundError("Look not found")
    if meta is not None and meta.is_deleted:
        return

    jobs = _load_polish_jobs(db, user)
    buckets = {b.look_id: b for b in _build_buckets(jobs)}
    bucket = buckets.get(look_id)
    if bucket is None:
        raise NotFoundError("Look not found")
    storage = LocalStorageBackend()
    read = _to_look_read(bucket, meta if meta and meta.user_id == user.id else None, storage)
    if read is None:
        raise NotFoundError("Look not found")

    if meta is None:
        meta = MagicLookMeta(id=look_id, user_id=user.id)
        db.add(meta)
        db.flush()
    meta.is_deleted = True
    meta.deleted_at = datetime.now(UTC)
    db.add(meta)
    db.commit()
