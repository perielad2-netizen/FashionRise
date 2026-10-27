"""Create Real Design — owner-scoped techpack drafts + authenticated PDF export."""

from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.techpack_draft import TechpackDraft, TechpackExport
from app.models.user import User
from app.schemas.techpack import (
    TechpackCreate,
    TechpackDraftRead,
    TechpackExportRead,
    TechpackListResponse,
    TechpackUpdate,
)
from app.services import looks_service
from app.services.ai_service import extract_result_image_url
from app.services.techpack_pdf import build_techpack_pdf, resolve_generation_provenance
from app.services.techpack_spec import default_spec, ensure_v2, merge_spec, style_code_from_look
from app.storage.local import LocalStorageBackend


_TITLE_MAX = 160
_STYLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _normalize_title(raw: str | None, fallback: str) -> str:
    title = " ".join((raw or fallback).split()).strip()
    if not title:
        raise ValidationAppError("Title cannot be empty")
    if len(title) > _TITLE_MAX:
        raise ValidationAppError(f"Title must be at most {_TITLE_MAX} characters")
    return title


def _normalize_style_code(raw: str) -> str:
    code = raw.strip().upper()
    if not _STYLE_RE.match(code):
        raise ValidationAppError("Style code must be 1–64 letters, numbers, . _ or -")
    return code


def _export_read(row: TechpackExport) -> TechpackExportRead:
    return TechpackExportRead.model_validate(row)


def _draft_read(db: Session, draft: TechpackDraft) -> TechpackDraftRead:
    """Attach the most relevant export — prefer Professional bound to last AI run."""
    rows = list(
        db.scalars(
            select(TechpackExport)
            .where(TechpackExport.draft_id == draft.id)
            .order_by(TechpackExport.created_at.desc())
        ).all()
    )
    chosen: TechpackExport | None = None
    spec = draft.spec if isinstance(draft.spec, dict) else {}
    ai = spec.get("ai") if isinstance(spec.get("ai"), dict) else {}
    last_run = str(ai.get("last_run_id") or "")
    if last_run:
        for row in rows:
            meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
            if str(meta.get("ai_run_id") or "") == last_run and bool(meta.get("is_professional")):
                chosen = row
                break
    if chosen is None:
        for row in rows:
            meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
            if bool(meta.get("is_professional")):
                chosen = row
                break
    if chosen is None and rows:
        # Ambiguous Basic/heuristic export only when no Professional exists.
        chosen = rows[0]
    payload = TechpackDraftRead.model_validate(draft)
    if chosen is not None:
        payload = payload.model_copy(update={"latest_export": _export_read(chosen)})
    return payload


def _resolve_job_image(storage: LocalStorageBackend, job_id: uuid.UUID | None, db: Session) -> Path | None:
    if job_id is None:
        return None
    from app.models.ai_job import AIJob

    job = db.get(AIJob, job_id)
    if job is None or job.status != "completed":
        return None
    url = extract_result_image_url(job.result_data if isinstance(job.result_data, dict) else None)
    if not url:
        return None
    key = storage.key_from_public_url(url)
    if not key:
        return None
    return storage.resolve_existing_file(key=key)


def create_draft(db: Session, user: User, data: TechpackCreate) -> TechpackDraftRead:
    look = looks_service.get_look(db, user, data.look_id)
    if not ((look.front and look.front.has_image) or (look.back and look.back.has_image)):
        raise ValidationAppError("Look must have at least one finished Magic image")

    summary = None
    if look.front and look.front.summary:
        summary = look.front.summary
    elif look.back and look.back.summary:
        summary = look.back.summary

    title = _normalize_title(data.title, look.title)
    style_code = style_code_from_look(look.id)
    # Avoid colliding style codes for the same owner by appending a short suffix when needed.
    existing_codes = set(
        db.scalars(select(TechpackDraft.style_code).where(TechpackDraft.user_id == user.id)).all()
    )
    if style_code in existing_codes:
        style_code = f"{style_code}-{uuid.uuid4().hex[:4].upper()}"

    draft = TechpackDraft(
        id=uuid.uuid4(),
        user_id=user.id,
        look_id=look.id,
        design_id=look.design_id,
        title=title,
        style_code=style_code,
        revision=1,
        status="DRAFT",
        verification="UNVERIFIED",
        spec=default_spec(look_summary=summary),
        front_job_id=look.front.job_id if look.front and look.front.has_image else None,
        back_job_id=look.back.job_id if look.back and look.back.has_image else None,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_read(db, draft)


def list_drafts(
    db: Session,
    user: User,
    *,
    look_id: uuid.UUID | None = None,
    limit: int = 24,
    offset: int = 0,
) -> TechpackListResponse:
    if limit < 1 or limit > 100:
        raise ValidationAppError("limit must be between 1 and 100")
    if offset < 0:
        raise ValidationAppError("offset must be >= 0")
    filters = [TechpackDraft.user_id == user.id]
    if look_id is not None:
        filters.append(TechpackDraft.look_id == look_id)
    total = int(db.scalar(select(func.count()).select_from(TechpackDraft).where(*filters)) or 0)
    rows = list(
        db.scalars(
            select(TechpackDraft)
            .where(*filters)
            .order_by(TechpackDraft.updated_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return TechpackListResponse(
        items=[_draft_read(db, r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def _owned_draft(db: Session, user: User, draft_id: uuid.UUID) -> TechpackDraft:
    draft = db.get(TechpackDraft, draft_id)
    if draft is None or draft.user_id != user.id:
        raise NotFoundError("Techpack draft not found")
    return draft


def get_draft(db: Session, user: User, draft_id: uuid.UUID) -> TechpackDraftRead:
    return _draft_read(db, _owned_draft(db, user, draft_id))


def update_draft(db: Session, user: User, draft_id: uuid.UUID, data: TechpackUpdate) -> TechpackDraftRead:
    draft = _owned_draft(db, user, draft_id)
    if data.title is None and data.style_code is None and data.spec is None and not data.bump_revision:
        raise ValidationAppError("No techpack fields to update")
    prior_spec = draft.spec if isinstance(draft.spec, dict) else {}
    prior_ai = prior_spec.get("ai") if isinstance(prior_spec.get("ai"), dict) else {}
    had_professional = (
        str(prior_ai.get("last_mode") or "") == "professional" and bool(prior_ai.get("last_run_id"))
    )
    was_dirty = bool(prior_ai.get("dirty_since_generation"))
    if data.title is not None:
        draft.title = _normalize_title(data.title, draft.title)
    if data.style_code is not None:
        draft.style_code = _normalize_style_code(data.style_code)
    if data.spec is not None:
        if not isinstance(data.spec, dict):
            raise ValidationAppError("spec must be an object")
        draft.spec = merge_spec(prior_spec, data.spec)
        # Mark dirty when designer edits after a completed Professional run so Generate
        # cannot silently reuse the previous paid PDF for changed inputs.
        if had_professional:
            merged = draft.spec if isinstance(draft.spec, dict) else {}
            ai = dict(merged.get("ai") if isinstance(merged.get("ai"), dict) else {})
            # Preserve server-owned AI lineage; client cannot wipe last_run_id / mode.
            if prior_ai.get("last_run_id") and not ai.get("last_run_id"):
                ai["last_run_id"] = prior_ai.get("last_run_id")
            if prior_ai.get("last_mode") and not ai.get("last_mode"):
                ai["last_mode"] = prior_ai.get("last_mode")
            for k in (
                "paid_sections",
                "vision_model",
                "image_model",
                "analysis_summary",
                "actual_cost_usd_cents",
                "estimated_cost_usd_cents",
                "export_id",
            ):
                if prior_ai.get(k) is not None and ai.get(k) is None:
                    ai[k] = prior_ai.get(k)
            ai["dirty_since_generation"] = True
            merged["ai"] = ai
            # Preserve piece illustrations that the client omitted/stale-cleared.
            outfit = merged.get("outfit") if isinstance(merged.get("outfit"), dict) else {}
            pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
            prior_outfit = prior_spec.get("outfit") if isinstance(prior_spec.get("outfit"), dict) else {}
            prior_pieces = {
                str(p.get("id")): p
                for p in (prior_outfit.get("pieces") or [])
                if isinstance(p, dict) and p.get("id")
            }
            for piece in pieces:
                if not isinstance(piece, dict):
                    continue
                pid = str(piece.get("id") or "")
                prior_piece = prior_pieces.get(pid)
                if not prior_piece:
                    continue
                prior_ill = prior_piece.get("illustrations")
                cur_ill = piece.get("illustrations")
                if isinstance(prior_ill, dict) and prior_ill.get("mode") == "professional":
                    if not isinstance(cur_ill, dict) or not cur_ill.get("artifacts"):
                        piece["illustrations"] = prior_ill
            outfit["pieces"] = pieces
            merged["outfit"] = outfit
            draft.spec = merged
            # One revision bump when first becoming dirty after a Professional PDF.
            if not was_dirty:
                draft.revision = int(draft.revision or 1) + 1
    if data.bump_revision and not (had_professional and data.spec is not None and not was_dirty):
        draft.revision = int(draft.revision or 1) + 1
    # Exports always remain DRAFT / UNVERIFIED until a future verification workflow.
    draft.status = "DRAFT"
    draft.verification = "UNVERIFIED"
    draft.updated_at = datetime.now(UTC)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_read(db, draft)


def find_export_for_ai_run(
    db: Session, user: User, *, draft_id: uuid.UUID, ai_run_id: uuid.UUID
) -> TechpackExport | None:
    """Return newest Professional export bound to this AI run (metadata.ai_run_id)."""
    rows = list(
        db.scalars(
            select(TechpackExport)
            .where(TechpackExport.draft_id == draft_id, TechpackExport.user_id == user.id)
            .order_by(TechpackExport.created_at.desc())
        ).all()
    )
    want = str(ai_run_id)
    for row in rows:
        meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
        if str(meta.get("ai_run_id") or "") == want and bool(meta.get("is_professional")):
            return row
    return None


def export_pdf(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    ai_run_id: uuid.UUID | None = None,
    require_professional: bool = False,
) -> TechpackExportRead:
    """Assemble a private PDF from the current draft (no OpenAI calls).

    When *ai_run_id* is set, bind metadata to that run and reuse an existing matching
    Professional export instead of creating a duplicate.
    """
    draft = _owned_draft(db, user, draft_id)
    if ai_run_id is not None:
        existing = find_export_for_ai_run(db, user, draft_id=draft.id, ai_run_id=ai_run_id)
        if existing is not None:
            return _export_read(existing)

    storage = LocalStorageBackend()
    front_path = _resolve_job_image(storage, draft.front_job_id, db)
    back_path = _resolve_job_image(storage, draft.back_job_id, db)
    if front_path is None and back_path is None:
        raise ValidationAppError("Cannot export PDF without at least one Magic look image")

    status = "DRAFT"
    verification = "UNVERIFIED"
    render_spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    outfit = render_spec.get("outfit") if isinstance(render_spec.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    provenance = resolve_generation_provenance(render_spec)
    if ai_run_id is not None:
        # Force bind to the completing Professional run (provenance may lag before flush).
        provenance = {
            **provenance,
            "mode": "professional",
            "label": "AI Professional",
            "is_professional": True,
            "run_id": str(ai_run_id),
        }
    if require_professional and not provenance.get("is_professional"):
        raise ValidationAppError(
            "Professional PDF requires persisted AI illustrations for this draft"
        )
    pdf_bytes, page_count = build_techpack_pdf(
        title=draft.title,
        style_code=draft.style_code,
        revision=int(draft.revision or 1),
        status=status,
        verification=verification,
        look_id=str(draft.look_id),
        front_image=front_path,
        back_image=back_path,
        spec=render_spec,
    )
    export_id = uuid.uuid4()
    filename = f"{draft.style_code}_r{draft.revision}_techpack.pdf".replace("/", "-")
    storage_key = f"{user.id.hex}/{draft.id.hex}/{export_id.hex}.pdf"
    storage.save_private_techpack_file(
        key=storage_key,
        data=io.BytesIO(pdf_bytes),
        content_type="application/pdf",
    )
    row = TechpackExport(
        id=export_id,
        draft_id=draft.id,
        user_id=user.id,
        storage_key=storage_key,
        filename=filename,
        byte_size=len(pdf_bytes),
        page_count=page_count,
        revision=int(draft.revision or 1),
        status=status,
        verification=verification,
        metadata_={
            "look_id": str(draft.look_id),
            "front_job_id": str(draft.front_job_id) if draft.front_job_id else None,
            "back_job_id": str(draft.back_job_id) if draft.back_job_id else None,
            "front_image_present": front_path is not None,
            "back_image_present": back_path is not None,
            "height_rows": 1,
            "schema_version": str(render_spec.get("schema_version") or "2.0"),
            "piece_count": len(pieces),
            "cutting_uses_schematics": True,
            # V2 cutting pages use deterministic schematics, not Magic photo reuse.
            "cutting_reuses_magic_looks": False,
            "magic_looks_on_cover_overview_only": True,
            "generation_mode": provenance["mode"],
            "generation_label": provenance["label"],
            "is_professional": provenance["is_professional"],
            "ai_run_id": provenance["run_id"] or (str(ai_run_id) if ai_run_id else None),
            "vision_model": provenance["vision_model"] or None,
            "image_model": provenance["image_model"] or None,
            # Budget-recorded cents from the AI run — not verified OpenAI wallet billing.
            "budget_recorded_usd_cents": provenance["actual_cost_usd_cents"],
            "actual_cost_usd_cents": provenance["actual_cost_usd_cents"],
            "paid_sections": provenance["paid_sections"],
            "draft_revision": int(draft.revision or 1),
        },
    )
    db.add(row)
    draft.updated_at = datetime.now(UTC)
    db.add(draft)
    db.commit()
    db.refresh(row)
    return _export_read(row)


def list_exports(db: Session, user: User, draft_id: uuid.UUID) -> list[TechpackExportRead]:
    _owned_draft(db, user, draft_id)
    rows = list(
        db.scalars(
            select(TechpackExport)
            .where(TechpackExport.draft_id == draft_id, TechpackExport.user_id == user.id)
            .order_by(TechpackExport.created_at.desc())
        ).all()
    )
    return [_export_read(r) for r in rows]


def resolve_export_pdf_path(db: Session, user: User, export_id: uuid.UUID) -> tuple[Path, TechpackExport]:
    row = db.get(TechpackExport, export_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Techpack export not found")
    storage = LocalStorageBackend()
    path = storage.resolve_private_techpack_file(key=row.storage_key)
    if path is None:
        raise NotFoundError("Techpack PDF file missing")
    return path, row


def ai_draft_assist_disabled() -> None:
    """Fail closed — paid AI draft assist is off unless explicitly enabled later."""
    settings = get_settings()
    if not settings.techpack_ai_draft_enabled:
        raise ForbiddenError("AI draft assist is disabled for this environment")
    raise ForbiddenError("AI draft assist is not available in this release")
