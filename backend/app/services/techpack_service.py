"""Create Real Design — owner-scoped techpack drafts + authenticated PDF export."""

from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
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
from app.services.techpack_spec import (
    default_spec,
    ensure_v2,
    merge_spec,
    style_code_from_look,
)
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


def reconcile_professional_export_validity(db: Session, draft: TechpackDraft) -> bool:
    """Idempotently mark Professional Download outdated when export/run ≠ live draft.

    Preserves historical ``export_id`` / ``last_run_id``. Does not bump revision.
    Returns True when a write was performed.
    """
    from app.models.techpack_ai_run import TechpackAIRun
    from app.services.techpack_structure import (
        list_outfit_pieces,
        professional_pack_is_current_for_draft,
    )

    spec = draft.spec if isinstance(draft.spec, dict) else {}
    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
    had_professional = (
        str(ai.get("last_mode") or "") == "professional"
        and bool(ai.get("last_run_id") or ai.get("export_id"))
    )
    if not had_professional:
        return False

    pieces = list_outfit_pieces(spec)
    export_meta: dict | None = None
    run_req: dict | None = None
    bound_export = str(ai.get("export_id") or "").strip()
    if bound_export:
        try:
            export_row = db.get(TechpackExport, uuid.UUID(bound_export))
        except (TypeError, ValueError):
            export_row = None
        if export_row is not None and isinstance(export_row.metadata_, dict):
            export_meta = export_row.metadata_
    run_id = str(ai.get("last_run_id") or "").strip()
    if run_id:
        try:
            run_row = db.get(TechpackAIRun, uuid.UUID(run_id))
        except (TypeError, ValueError):
            run_row = None
        if run_row is not None and isinstance(run_row.request, dict):
            run_req = run_row.request

    if professional_pack_is_current_for_draft(
        pieces=pieces,
        run_request=run_req,
        export_metadata=export_meta,
        spec=spec,
        draft=draft,
        require_input_match=False,
    ):
        return False

    # Desired reconciled state (idempotent — skip write when already applied).
    desired_outdated = bound_export or None
    already = bool(ai.get("dirty_since_generation")) and (
        not desired_outdated or str(ai.get("outdated_export_id") or "") == desired_outdated
    )
    if already:
        return False

    if desired_outdated and not ai.get("outdated_export_id"):
        ai["outdated_export_id"] = desired_outdated
    ai["dirty_since_generation"] = True
    # Preserve historical provenance fields.
    if run_id and not ai.get("last_run_id"):
        ai["last_run_id"] = run_id
    if bound_export and not ai.get("export_id"):
        ai["export_id"] = bound_export
    if not ai.get("last_mode"):
        ai["last_mode"] = "professional"
    spec = dict(spec)
    spec["ai"] = ai
    draft.spec = spec
    draft.updated_at = datetime.now(UTC)
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(draft, "spec")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return True


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


def _look_evidence(db: Session, look) -> tuple[str | None, dict | None]:
    """Pull summary + design_identity from Magic jobs (zero paid AI)."""
    from app.models.ai_job import AIJob
    from app.services.techpack_autofill import extract_job_evidence

    summary = None
    if look.front and look.front.summary:
        summary = look.front.summary
    elif look.back and look.back.summary:
        summary = look.back.summary
    identity = None
    for side in (look.front, look.back):
        if side is None or not side.job_id:
            continue
        job = db.get(AIJob, side.job_id)
        if job is None or not isinstance(job.result_data, dict):
            continue
        evidence = extract_job_evidence(job.result_data)
        if not summary and evidence.get("summary"):
            summary = evidence["summary"]
        if identity is None and evidence.get("design_identity"):
            identity = evidence["design_identity"]
        if summary and identity is not None:
            break
    return summary, identity


def create_draft(db: Session, user: User, data: TechpackCreate) -> TechpackDraftRead:
    look = looks_service.get_look(db, user, data.look_id)
    if not ((look.front and look.front.has_image) or (look.back and look.back.has_image)):
        raise ValidationAppError("Look must have at least one finished Magic image")

    summary, design_identity = _look_evidence(db, look)

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
        spec=default_spec(look_summary=summary, design_identity=design_identity),
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
    """Return draft; repair stale one-piece dress metadata from Magic evidence (no paid AI)."""
    from app.models.ai_job import AIJob
    from app.services.techpack_autofill import (
        apply_persisted_analyses_to_spec,
        extract_job_evidence,
        outfit_needs_structure_repair,
        repair_outfit_from_evidence,
    )

    draft = _owned_draft(db, user, draft_id)
    spec = draft.spec if isinstance(draft.spec, dict) else {}
    look_summary = str(spec.get("look_notes") or "") or None
    design_identity = (
        spec.get("look_design_identity")
        if isinstance(spec.get("look_design_identity"), dict)
        else None
    )
    for jid in (draft.front_job_id, draft.back_job_id):
        if jid is None:
            continue
        job = db.get(AIJob, jid)
        if job is None or not isinstance(job.result_data, dict):
            continue
        evidence = extract_job_evidence(job.result_data)
        if not look_summary and evidence.get("summary"):
            look_summary = evidence["summary"]
        if design_identity is None and evidence.get("design_identity"):
            design_identity = evidence["design_identity"]
    dirty = False
    structure_repaired = False
    prior_ai = spec.get("ai") if isinstance(spec.get("ai"), dict) else {}
    prior_outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    prior_piece_ids = sorted(
        str(p.get("id") or "")
        for p in (prior_outfit.get("pieces") or [])
        if isinstance(p, dict)
    )
    prior_piece_cats = sorted(
        str(p.get("category") or "")
        for p in (prior_outfit.get("pieces") or [])
        if isinstance(p, dict)
    )
    if outfit_needs_structure_repair(
        prior_outfit if prior_outfit else None,
        look_summary=look_summary,
        design_identity=design_identity,
    ):
        spec = repair_outfit_from_evidence(
            spec,
            look_summary=look_summary,
            design_identity=design_identity,
            units=str(spec.get("units") or "cm"),
        )
        dirty = True
        structure_repaired = True
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    has_persisted_analysis = any(
        isinstance((p.get("illustrations") or {}).get("analysis"), dict)
        and (p.get("illustrations") or {}).get("analysis")
        for p in (outfit.get("pieces") or [])
        if isinstance(p, dict)
    )
    if has_persisted_analysis:
        filled = apply_persisted_analyses_to_spec(spec)
        if filled != spec:
            spec = filled
            dirty = True
    if dirty:
        if look_summary and not spec.get("look_notes"):
            spec["look_notes"] = look_summary[:500]
        if design_identity and not isinstance(spec.get("look_design_identity"), dict):
            spec["look_design_identity"] = design_identity
        ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
        new_outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
        new_piece_ids = sorted(
            str(p.get("id") or "")
            for p in (new_outfit.get("pieces") or [])
            if isinstance(p, dict)
        )
        new_piece_cats = sorted(
            str(p.get("category") or "")
            for p in (new_outfit.get("pieces") or [])
            if isinstance(p, dict)
        )
        structure_changed = structure_repaired and (
            prior_piece_ids != new_piece_ids or prior_piece_cats != new_piece_cats
        )
        had_professional = (
            str(prior_ai.get("last_mode") or "") == "professional"
            and bool(prior_ai.get("last_run_id") or prior_ai.get("export_id"))
        )
        # Preserve historical export/run ids; invalidate current Download until regenerate.
        if structure_changed and had_professional:
            if prior_ai.get("export_id"):
                ai["outdated_export_id"] = prior_ai.get("export_id")
            ai["dirty_since_generation"] = True
            # Keep last_run_id / export_id for history; FE hides Download when dirty.
            if prior_ai.get("last_run_id") and not ai.get("last_run_id"):
                ai["last_run_id"] = prior_ai.get("last_run_id")
            if prior_ai.get("export_id") and not ai.get("export_id"):
                ai["export_id"] = prior_ai.get("export_id")
            if prior_ai.get("last_mode") and not ai.get("last_mode"):
                ai["last_mode"] = prior_ai.get("last_mode")
        spec["ai"] = ai
        # Do not bump revision / status on read-time repair.
        draft.spec = spec
        draft.updated_at = datetime.now(UTC)
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(draft, "spec")
        db.add(draft)
        db.commit()
        db.refresh(draft)
    # Even when structure was repaired earlier (dirty already false on disk),
    # invalidate current Download if the bound Professional export contradicts
    # the live outfit (FR-D47D: 1-piece PDF vs 2-piece draft).
    reconcile_professional_export_validity(db, draft)
    return _draft_read(db, draft)


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
            prior_export = str(prior_ai.get("export_id") or ai.get("export_id") or "").strip()
            if prior_export and not ai.get("outdated_export_id"):
                ai["outdated_export_id"] = prior_export
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
                if (
                    isinstance(prior_ill, dict)
                    and prior_ill.get("mode") == "professional"
                    and (not isinstance(cur_ill, dict) or not cur_ill.get("artifacts"))
                ):
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


def _illustration_artifact_ids(pieces: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for piece in pieces:
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        for kind in sorted(arts.keys()):
            entry = arts.get(kind)
            if not isinstance(entry, dict):
                continue
            aid = str(entry.get("artifact_id") or entry.get("id") or "").strip()
            if aid:
                ids.append(f"{piece_id_safe(piece)}:{kind}:{aid}")
    return ids


def piece_id_safe(piece: dict[str, Any]) -> str:
    return str(piece.get("id") or "").strip()


_ARTIFACT_REVIEW_REJECTED = frozenset(
    {"rejected_category_mismatch", "excluded_mismatch", "rejected"}
)
_ARTIFACT_REVIEW_CONFIRMED = frozenset(
    {"designer_confirmed", "visual_qa_confirmed", "owner_accepted", "confirmed"}
)


def _authoritative_artifact_review_tokens(
    db: Session,
    user: User,
    draft: TechpackDraft,
) -> list[str]:
    """Server-owned illustration review states that must affect PDF-only fingerprints."""
    from app.models.techpack_ai_artifact import TechpackAIArtifact

    rows = list(
        db.scalars(
            select(TechpackAIArtifact).where(
                TechpackAIArtifact.draft_id == draft.id,
                TechpackAIArtifact.user_id == user.id,
            )
        ).all()
    )
    tokens: list[str] = []
    for row in rows:
        meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
        state = str(row.review_state or "proposed").strip().lower()
        if "preview_include" in meta:
            include = bool(meta.get("preview_include"))
        else:
            include = state not in _ARTIFACT_REVIEW_REJECTED
        tokens.append(
            f"{row.piece_id or ''}:{row.kind}:{row.id}:{state}:{int(include)}"
        )
    return sorted(tokens)


def _pdf_only_content_fingerprint(
    *,
    draft: TechpackDraft,
    render_spec: dict[str, Any],
    pieces: list[dict[str, Any]],
    artifact_reviews: list[str] | None = None,
) -> str:
    """Stable fingerprint for idempotent PDF-only updates (no provider involvement).

    Includes authoritative illustration review tokens so owner reject/reapprove
    decisions force a new assembly even when measurement specs are unchanged.
    """
    # Exclude volatile AI bookkeeping so rebinding current export does not thrash.
    spec_for_hash = dict(render_spec)
    ai = dict(spec_for_hash.get("ai") if isinstance(spec_for_hash.get("ai"), dict) else {})
    for k in (
        "dirty_since_generation",
        "export_id",
        "outdated_export_id",
        "last_run_id",
        "last_mode",
        "actual_cost_usd_cents",
        "estimated_cost_usd_cents",
        "analysis_summary",
        # Review version is mirrored via artifact_reviews tokens; keep out of ai blob.
        "artifact_review_version",
        "artifact_review_decisions",
        "pdf_only_update",
        "assembly_cost_usd_cents",
        "source_run_cost_usd_cents",
        "source_run_paid_sections",
        "new_paid_ai_run",
    ):
        ai.pop(k, None)
    spec_for_hash["ai"] = ai
    payload = {
        "draft_id": str(draft.id),
        "revision": int(draft.revision or 1),
        "title": draft.title,
        "style_code": draft.style_code,
        "front_job_id": str(draft.front_job_id) if draft.front_job_id else None,
        "back_job_id": str(draft.back_job_id) if draft.back_job_id else None,
        "look_id": str(draft.look_id),
        "spec": spec_for_hash,
        "illustration_artifacts": _illustration_artifact_ids(pieces),
        "artifact_reviews": list(artifact_reviews or []),
    }
    blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _norm_job_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def resolve_authorized_magic_source_ids(
    db: Session,
    user: User,
    draft: TechpackDraft,
    run: Any,
) -> tuple[str | None, str | None, str]:
    """Resolve authorized Magic front/back job ids for PDF-only compatibility.

    Preference order:
    1. Immutable snapshot stamped on ``run.request`` (future / newly enqueued runs).
    2. Original Professional export metadata for that run (trusted paid-assembly stamp).
    3. ``missing`` — caller must fail closed (legacy / incomplete provenance).
    """
    req = run.request if isinstance(getattr(run, "request", None), dict) else {}
    req_front = _norm_job_id(req.get("front_job_id"))
    req_back = _norm_job_id(req.get("back_job_id"))
    # Only trust request stamps when at least one side was explicitly recorded.
    # Absent keys on legacy constructors must NOT silently authorize any draft.
    if "front_job_id" in req or "back_job_id" in req:
        return req_front, req_back, "request"

    want = str(run.id)
    rows = list(
        db.scalars(
            select(TechpackExport)
            .where(TechpackExport.draft_id == draft.id, TechpackExport.user_id == user.id)
            .order_by(TechpackExport.created_at.asc())
        ).all()
    )
    fallback_front: str | None = None
    fallback_back: str | None = None
    saw_matching_export = False
    for row in rows:
        meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
        if not bool(meta.get("is_professional")):
            continue
        run_ref = _norm_job_id(meta.get("ai_run_id")) or _norm_job_id(meta.get("source_ai_run_id"))
        if run_ref != want:
            continue
        saw_matching_export = True
        front = _norm_job_id(meta.get("front_job_id"))
        back = _norm_job_id(meta.get("back_job_id"))
        # Prefer the original paid Professional assembly over later PDF-only rows.
        if not bool(meta.get("pdf_only_update")) and (front is not None or back is not None):
            return front, back, "export_meta"
        if fallback_front is None and fallback_back is None and (front is not None or back is not None):
            fallback_front, fallback_back = front, back
    if fallback_front is not None or fallback_back is not None:
        return fallback_front, fallback_back, "export_meta"
    if saw_matching_export:
        # Matching Professional export exists but carries no Magic source ids — legacy unknown.
        return None, None, "missing"
    return None, None, "missing"


def _resolve_owned_professional_source_run(
    db: Session,
    owner: User,
    draft: TechpackDraft,
    *,
    claimed_run_id: str,
) -> tuple[Any | None, list[str]]:
    """Load the claimed Professional run and require user+draft ownership.

    ``draft.spec.ai.last_run_id`` is only a claim — authorization comes from the
    ``TechpackAIRun`` row matching the authenticated owner and current draft.
    """
    from app.models.techpack_ai_run import TechpackAIRun

    reasons: list[str] = []
    try:
        run = db.get(TechpackAIRun, uuid.UUID(str(claimed_run_id)))
    except (TypeError, ValueError):
        run = None
    if run is None:
        reasons.append(
            "The bound Professional run is missing or malformed. "
            "Generate AI PDF again to refresh illustrations."
        )
        return None, reasons
    if run.user_id != owner.id:
        reasons.append(
            "The Professional AI run is not owned by the authenticated user. "
            "Update PDF (No AI) cannot reuse another account’s illustrations."
        )
        return None, reasons
    if run.draft_id != draft.id:
        reasons.append(
            "The Professional AI run belongs to a different draft. "
            "Update PDF (No AI) cannot reuse illustrations from another design."
        )
        return None, reasons
    if run.stage != "professional" or run.status != "completed":
        reasons.append(
            "The bound Professional run is missing or incomplete. "
            "Generate AI PDF again to refresh illustrations."
        )
        return None, reasons
    return run, []


def _validate_professional_illustration_artifacts(
    db: Session,
    owner: User,
    draft: TechpackDraft,
    run: Any,
    pieces: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    """Verify every reused Professional illustration against ``TechpackAIArtifact``.

    Returns ``(blocking_reasons, verified_by_piece_kind)`` where the map values are
    server-owned artifact rows keyed as ``"{piece_id}:{kind}"``. Client storage
    paths alone never authorize reuse.
    """
    from app.models.techpack_ai_artifact import TechpackAIArtifact

    reasons: list[str] = []
    verified: dict[str, Any] = {}
    owned_rows = list(
        db.scalars(
            select(TechpackAIArtifact).where(
                TechpackAIArtifact.run_id == run.id,
                TechpackAIArtifact.draft_id == draft.id,
                TechpackAIArtifact.user_id == owner.id,
            )
        ).all()
    )
    by_id = {str(row.id): row for row in owned_rows}

    for piece in pieces:
        pid = piece_id_safe(piece) or "(unnamed)"
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        if str(ill.get("mode") or "") != "professional":
            reasons.append(
                f"Professional illustrations are missing for garment “{pid}”. "
                "Generate AI PDF to restore artwork before a no-AI PDF update."
            )
            continue
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        if not arts:
            reasons.append(
                f"Professional illustration artifacts are missing for garment “{pid}”. "
                "Generate AI PDF to restore artwork before a no-AI PDF update."
            )
            continue
        if "flat_front" not in arts or not isinstance(arts.get("flat_front"), dict):
            reasons.append(
                f"Professional front illustration is missing for garment “{pid}”. "
                "Generate AI PDF to restore artwork before a no-AI PDF update."
            )
            continue

        for kind, meta in arts.items():
            kind_s = str(kind or "").strip()
            if not kind_s:
                reasons.append(
                    f"Garment “{pid}” has an illustration with an empty artwork kind. "
                    "Remove the forged entry or Generate AI PDF again."
                )
                continue
            if not isinstance(meta, dict):
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” is not a valid artifact reference."
                )
                continue
            aid_raw = str(meta.get("artifact_id") or meta.get("id") or "").strip()
            client_key = str(meta.get("storage_key") or "").strip()
            if not aid_raw:
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” has no artifact id. "
                    "Storage paths alone cannot authorize PDF-only reuse — "
                    "Generate AI PDF again or restore the original Professional pack."
                )
                continue
            row = by_id.get(aid_raw)
            if row is None:
                try:
                    candidate = db.get(TechpackAIArtifact, uuid.UUID(aid_raw))
                except (TypeError, ValueError):
                    candidate = None
                if candidate is None:
                    reasons.append(
                        f"Garment “{pid}” illustration “{kind_s}” references an unknown artifact. "
                        "Refusing substituted artwork for Update PDF (No AI)."
                    )
                    continue
                # Present in DB but not in the owned source-run set — cross-boundary.
                if (
                    candidate.user_id != owner.id
                    or candidate.draft_id != draft.id
                    or candidate.run_id != run.id
                ):
                    reasons.append(
                        f"Garment “{pid}” illustration “{kind_s}” is not from the authorized "
                        "Professional run for this draft. "
                        "Update PDF (No AI) cannot reuse another design’s or user’s artwork."
                    )
                    continue
                row = candidate

            if row.user_id != owner.id or row.draft_id != draft.id or row.run_id != run.id:
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” failed ownership checks. "
                    "Refusing unauthorized Professional artwork reuse."
                )
                continue
            row_piece = str(row.piece_id or "").strip()
            if not row_piece:
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” has incomplete server provenance "
                    "(missing piece association). Failing closed without rewriting history — "
                    "Generate AI PDF again if you need a fresh authorized pack."
                )
                continue
            if row_piece != pid:
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” belongs to a different garment "
                    f"(“{row_piece}”). Refusing substituted Professional artwork."
                )
                continue
            if str(row.kind or "").strip() != kind_s:
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” does not match the stored artwork kind "
                    f"(“{row.kind}”). Refusing mismatched Professional artwork."
                )
                continue
            if client_key and client_key != str(row.storage_key or ""):
                reasons.append(
                    f"Garment “{pid}” illustration “{kind_s}” storage key does not match the "
                    "authorized artifact record. Refusing path-substituted artwork."
                )
                continue
            verified[f"{pid}:{kind_s}"] = row

    return reasons, verified


def apply_server_owned_illustration_artifacts(
    render_spec: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Rewrite illustration artifact refs to server-owned ids/keys before PDF assembly."""
    from copy import deepcopy

    out: dict[str, Any] = deepcopy(render_spec)
    raw_outfit = out.get("outfit")
    outfit: dict[str, Any] = raw_outfit if isinstance(raw_outfit, dict) else {}
    raw_pieces = outfit.get("pieces")
    pieces: list[Any] = raw_pieces if isinstance(raw_pieces, list) else []
    for piece in pieces:
        if not isinstance(piece, dict):
            continue
        pid = piece_id_safe(piece)
        raw_ill = piece.get("illustrations")
        ill: dict[str, Any] = raw_ill if isinstance(raw_ill, dict) else {}
        raw_arts = ill.get("artifacts")
        arts: dict[str, Any] = raw_arts if isinstance(raw_arts, dict) else {}
        if not arts:
            continue
        rewritten: dict[str, Any] = {}
        for kind, meta in arts.items():
            kind_s = str(kind or "").strip()
            row = verified.get(f"{pid}:{kind_s}")
            if row is None:
                # Leave excluded; assess already blocked unknown entries.
                if isinstance(meta, dict):
                    rewritten[kind_s] = dict(meta)
                continue
            base: dict[str, Any] = dict(meta) if isinstance(meta, dict) else {}
            base["artifact_id"] = str(row.id)
            base["id"] = str(row.id)
            base["storage_key"] = str(row.storage_key)
            base["url_path"] = f"/techpacks/artifacts/{row.id}/image"
            base["review_state"] = str(row.review_state or base.get("review_state") or "proposed")
            row_meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
            if row_meta.get("review_message") and not base.get("review_message"):
                base["review_message"] = row_meta.get("review_message")
            if "preview_include" in row_meta:
                base["preview_include"] = bool(row_meta.get("preview_include"))
            elif str(base["review_state"]).lower() in {
                "rejected_category_mismatch",
                "excluded_mismatch",
                "rejected",
            }:
                base["preview_include"] = False
            if row_meta.get("last_operator_decision"):
                base["operator_decision"] = row_meta.get("last_operator_decision")
            # Never treat client path as authoritative once rewritten.
            base["server_owned"] = True
            rewritten[kind_s] = base
        ill = dict(ill)
        ill["artifacts"] = rewritten
        ill["mode"] = "professional"
        piece["illustrations"] = ill
    outfit = dict(outfit)
    outfit["pieces"] = pieces
    out["outfit"] = outfit
    return out


def assess_pdf_only_update_compatibility(
    db: Session,
    draft: TechpackDraft,
    *,
    user: User | None = None,
) -> tuple[bool, list[str], Any | None]:
    """Return (ok, blocking_reasons, source_run) for a no-AI PDF refresh.

    Fail closed when garment identity or Professional illustrations cannot be reused safely.
    Never calls a paid provider. Authorizes the source run and each illustration via
    server-owned ``TechpackAIRun`` / ``TechpackAIArtifact`` rows — not client paths.
    """
    from app.services.techpack_structure import (
        list_outfit_pieces,
        run_matches_draft_structure,
    )

    reasons: list[str] = []
    owner = user
    if owner is None:
        owner = db.get(User, draft.user_id)
    if owner is None:
        reasons.append("Draft owner is missing; cannot authorize a PDF-only update.")
        return False, reasons, None

    spec = draft.spec if isinstance(draft.spec, dict) else {}
    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
    pieces = list_outfit_pieces(spec)
    run_id = str(ai.get("last_run_id") or "").strip()
    if str(ai.get("last_mode") or "") != "professional" or not run_id:
        reasons.append(
            "No completed Professional AI pack is bound to this draft. "
            "Generate AI PDF once before using Update PDF (No AI)."
        )
        return False, reasons, None

    run, run_reasons = _resolve_owned_professional_source_run(
        db, owner, draft, claimed_run_id=run_id
    )
    if run is None:
        return False, run_reasons, None

    req = run.request if isinstance(run.request, dict) else {}
    if not run_matches_draft_structure(req, pieces):
        reasons.append(
            "Garment identity changed since the Professional illustrations were created "
            "(piece count, piece IDs, or category no longer match). "
            "Review garments and Generate AI PDF to refresh illustrations — "
            "old artwork will not be reused silently."
        )
        return False, reasons, run

    auth_front, auth_back, provenance = resolve_authorized_magic_source_ids(
        db, owner, draft, run
    )
    if provenance == "missing":
        reasons.append(
            "Original Magic source identity for this Professional pack is unknown "
            "(legacy run without trusted export provenance). "
            "Generate AI PDF again before using Update PDF (No AI)."
        )
        return False, reasons, run

    draft_front = _norm_job_id(draft.front_job_id)
    draft_back = _norm_job_id(draft.back_job_id)
    if auth_front != draft_front:
        if auth_front and not draft_front:
            reasons.append(
                "The Magic look front image is missing. "
                "Restore the original look or Generate AI PDF for the new source."
            )
        elif not auth_front and draft_front:
            reasons.append(
                "A Magic look front image was added after Professional generation. "
                "Generate AI PDF to create illustrations for the new look."
            )
        else:
            reasons.append(
                "The Magic look front image changed since Professional generation. "
                "Generate AI PDF to create illustrations for the new look."
            )
        return False, reasons, run
    if auth_back != draft_back:
        if auth_back and not draft_back:
            reasons.append(
                "The Magic look back image is missing. "
                "Restore the original look or Generate AI PDF for the new source."
            )
        elif not auth_back and draft_back:
            reasons.append(
                "A Magic look back image was added after Professional generation. "
                "Generate AI PDF to create illustrations for the new look."
            )
        else:
            reasons.append(
                "The Magic look back image changed since Professional generation. "
                "Generate AI PDF to create illustrations for the new look."
            )
        return False, reasons, run

    art_reasons, _verified = _validate_professional_illustration_artifacts(
        db, owner, draft, run, pieces
    )
    if art_reasons:
        reasons.extend(art_reasons)
        return False, reasons, run
    return True, [], run


def find_export_by_pdf_only_fingerprint(
    db: Session,
    user: User,
    *,
    draft_id: uuid.UUID,
    fingerprint: str,
    revision: int | None = None,
) -> TechpackExport | None:
    if not fingerprint:
        return None
    rows = list(
        db.scalars(
            select(TechpackExport)
            .where(TechpackExport.draft_id == draft_id, TechpackExport.user_id == user.id)
            .order_by(TechpackExport.created_at.desc())
        ).all()
    )
    for row in rows:
        meta = row.metadata_ if isinstance(row.metadata_, dict) else {}
        if not bool(meta.get("pdf_only_update")):
            continue
        if str(meta.get("pdf_only_fingerprint") or "") != fingerprint:
            continue
        row_rev = int(meta.get("draft_revision") or row.revision or -2)
        if revision is not None and row_rev != int(revision):
            continue
        if revision is None and row_rev != int(row.revision or -2):
            continue
        return row
    return None


def _bind_current_professional_export(
    db: Session,
    draft: TechpackDraft,
    *,
    export: TechpackExport,
    source_run_id: str | None,
    prior_export_id: str | None,
    commit: bool = True,
) -> TechpackDraft:
    """Mark *export* as the current Download without creating a paid AI run."""
    from sqlalchemy.orm.attributes import flag_modified

    spec = dict(draft.spec) if isinstance(draft.spec, dict) else {}
    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
    if prior_export_id and prior_export_id != str(export.id):
        ai["outdated_export_id"] = prior_export_id
    ai["export_id"] = str(export.id)
    ai["dirty_since_generation"] = False
    if source_run_id:
        ai["last_run_id"] = source_run_id
    ai["last_mode"] = "professional"
    # Do not invent a new paid cost — keep prior recorded cents if present.
    spec["ai"] = ai
    draft.spec = spec
    draft.updated_at = datetime.now(UTC)
    flag_modified(draft, "spec")
    db.add(draft)
    if commit:
        db.commit()
        db.refresh(draft)
    return draft


def _lock_owned_draft(db: Session, user: User, draft_id: uuid.UUID) -> TechpackDraft:
    draft = db.scalars(
        select(TechpackDraft)
        .where(TechpackDraft.id == draft_id, TechpackDraft.user_id == user.id)
        .with_for_update()
    ).one_or_none()
    if draft is None:
        raise NotFoundError("Techpack draft not found")
    return draft


_ALLOWED_ARTIFACT_REVIEW_STATES = frozenset(
    {
        "rejected_category_mismatch",
        "excluded_mismatch",
        "rejected",
        "proposed",
        "proposed_unverified",
        "designer_confirmed",
        "visual_qa_confirmed",
        "owner_accepted",
        "confirmed",
    }
)


def _techpack_run_stage(run: Any) -> str:
    """Authoritative run stage/mode for review and PDF-only gates.

    ``TechpackAIRun.stage`` is the column of record (``professional``, ``generate``,
    etc.). Fall back to ``request.mode`` only when stage is blank so legacy rows
    remain inspectable. Never treat a missing SQLAlchemy attribute as Professional.
    """
    stage = str(getattr(run, "stage", "") or "").strip().lower()
    if stage:
        return stage
    request = getattr(run, "request", None)
    if isinstance(request, dict):
        return str(request.get("mode") or "").strip().lower()
    return ""


def _artifact_referenced_in_outfit(
    spec: dict[str, Any],
    *,
    artifact_id: uuid.UUID | str,
    piece_id: str | None,
    kind: str | None,
) -> bool:
    """True when the draft outfit illustrations reference this artifact id."""
    target = str(artifact_id).strip().lower()
    if not target:
        return False
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    for piece in outfit.get("pieces") or []:
        if not isinstance(piece, dict):
            continue
        if piece_id and piece_id_safe(piece) and piece_id_safe(piece) != str(piece_id):
            continue
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        for art_kind, meta in arts.items():
            if kind and str(art_kind) != str(kind):
                continue
            if not isinstance(meta, dict):
                continue
            aid = str(meta.get("artifact_id") or meta.get("id") or "").strip().lower()
            if aid == target:
                return True
    return False


def _assert_artifact_review_source_binding(
    db: Session,
    user: User,
    draft: TechpackDraft,
    row: Any,
    *,
    spec: dict[str, Any],
) -> None:
    """Fail closed unless the artifact belongs to the current Professional source pack.

    Rules:
    - Artifact run must be owned by the authenticated user + current draft.
    - Run stage must be ``professional``. Legacy blank stage is allowed only when
      the draft already records authoritative Professional evidence for this same
      run (``ai.last_mode=professional`` and ``ai.last_run_id`` matches) — never for
      ``basic`` / ``generate`` / other non-Professional stages on the same draft.
    - Artifact ``run_id`` must equal the draft's current ``ai.last_run_id`` (historical
      runs that are not the bound source pack cannot dirty the current export).
    - Artifact must appear in the current outfit illustration refs for its piece/kind
      (unreferenced rows cannot spuriously invalidate the pack).
    """
    from app.models.techpack_ai_run import TechpackAIRun

    run = db.get(TechpackAIRun, row.run_id)
    if run is None or run.user_id != user.id or run.draft_id != draft.id:
        raise ValidationAppError(
            "Artifact is not bound to an owned Professional run for this draft."
        )

    stage = _techpack_run_stage(run)
    ai = spec.get("ai") if isinstance(spec.get("ai"), dict) else {}
    last_run_id = str(ai.get("last_run_id") or "").strip()
    last_mode = str(ai.get("last_mode") or "").strip().lower()
    legacy_blank_ok = (
        stage == ""
        and last_mode == "professional"
        and last_run_id
        and last_run_id == str(run.id)
        and str(getattr(run, "status", "") or "").strip().lower() == "completed"
    )
    if stage != "professional" and not legacy_blank_ok:
        raise ValidationAppError(
            "Artifact is not bound to an owned Professional run for this draft. "
            f"Disallowed run stage “{stage or 'unknown'}” cannot authorize review "
            "invalidation of the current Professional pack."
        )

    if not last_run_id or last_run_id != str(row.run_id):
        raise ValidationAppError(
            "Artifact belongs to a historical or unbound AI run that is not the "
            "current Professional source pack. Review it only after it is part of "
            "the active pack, or Generate AI PDF for a fresh authorized pack."
        )

    if not _artifact_referenced_in_outfit(
        spec,
        artifact_id=row.id,
        piece_id=row.piece_id,
        kind=str(row.kind or "") or None,
    ):
        raise ValidationAppError(
            "Artifact is not referenced by the current draft garment illustrations. "
            "Unreferenced historical artwork cannot invalidate the current PDF."
        )


def _stamp_artifact_review_into_draft_spec(
    spec: dict[str, Any],
    *,
    artifact_id: str,
    piece_id: str | None,
    kind: str,
    review_state: str,
    review_message: str,
    preview_include: bool,
    manufacturing_evidence: bool,
    decision: dict[str, Any],
) -> dict[str, Any]:
    """Mirror the authoritative artifact review onto draft.spec illustration refs."""
    out = dict(spec)
    outfit = dict(out.get("outfit") if isinstance(out.get("outfit"), dict) else {})
    pieces_out: list[Any] = []
    target = str(artifact_id).strip().lower()
    for piece in outfit.get("pieces") or []:
        if not isinstance(piece, dict):
            pieces_out.append(piece)
            continue
        piece_out = dict(piece)
        if piece_id and piece_id_safe(piece_out) and piece_id_safe(piece_out) != str(piece_id):
            pieces_out.append(piece_out)
            continue
        ill = dict(piece_out.get("illustrations") if isinstance(piece_out.get("illustrations"), dict) else {})
        arts = dict(ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {})
        changed = False
        for art_kind, meta in list(arts.items()):
            if not isinstance(meta, dict):
                continue
            if kind and str(art_kind) != str(kind):
                continue
            aid = str(meta.get("artifact_id") or meta.get("id") or "").strip().lower()
            if aid != target:
                continue
            meta_out = dict(meta)
            if meta.get("review_state") and "prior_review_state" not in meta_out:
                meta_out["prior_review_state"] = meta.get("review_state")
            meta_out["review_state"] = review_state
            meta_out["review_message"] = review_message
            meta_out["preview_include"] = preview_include
            meta_out["manufacturing_evidence"] = manufacturing_evidence
            meta_out["operator_decision"] = decision
            arts[str(art_kind)] = meta_out
            changed = True
        if changed:
            ill["artifacts"] = arts
            piece_out["illustrations"] = ill
        pieces_out.append(piece_out)
    outfit["pieces"] = pieces_out
    out["outfit"] = outfit
    return out


def record_owned_artifact_review(
    db: Session,
    user: User,
    artifact_id: uuid.UUID,
    *,
    review_state: str,
    review_message: str,
) -> dict[str, Any]:
    """Persist an owner review and invalidate the current Professional PDF binding.

    Verifies authenticated ownership of artifact, draft, and source run. Never deletes
    illustration or PDF bytes. Never triggers AI. Reviewer identity is derived from
    the authenticated principal (client cannot spoof operator).
    """
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.techpack_ai_artifact import TechpackAIArtifact
    from app.services.techpack_ai import _artifact_read

    row = db.get(TechpackAIArtifact, artifact_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Techpack artifact not found")

    state = str(review_state or "").strip().lower()
    if state not in _ALLOWED_ARTIFACT_REVIEW_STATES:
        raise ValidationAppError(f"Unsupported artifact review_state “{review_state}”.")
    message = str(review_message or "").strip()
    if not message:
        raise ValidationAppError("review_message is required for an auditable owner decision.")

    # Serialize against concurrent PDF-only assembly on the same draft.
    draft = _lock_owned_draft(db, user, row.draft_id)
    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    # Fail closed for disallowed stages (incl. same-user/same-draft non-Professional),
    # historical runs not bound as the current source pack, and unreferenced artifacts.
    # Legacy blank stage is allowed only with verified Professional draft evidence.
    _assert_artifact_review_source_binding(db, user, draft, row, spec=spec)
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    if row.piece_id:
        piece_ids = {piece_id_safe(p) for p in pieces}
        if str(row.piece_id) not in piece_ids:
            raise ValidationAppError(
                "Artifact piece association does not match the current draft outfit."
            )

    meta = dict(row.metadata_) if isinstance(row.metadata_, dict) else {}
    prior_state = str(row.review_state or "")
    last = meta.get("last_operator_decision") if isinstance(meta.get("last_operator_decision"), dict) else {}
    identical = (
        prior_state == state
        and str(last.get("review_message") or "") == message
        and str(last.get("reviewer_user_id") or "") == str(user.id)
    )

    when = datetime.now(UTC).isoformat()
    rejected = state in _ARTIFACT_REVIEW_REJECTED
    confirmed = state in _ARTIFACT_REVIEW_CONFIRMED
    preview_include = False if rejected else True
    manufacturing_evidence = bool(confirmed)
    decision = {
        "reviewer_user_id": str(user.id),
        "reviewer_username": str(user.username or ""),
        "role": "owner",
        "review_state": state,
        "review_message": message,
        "decided_at": when,
        "prior_review_state": prior_state,
        "bytes_preserved": True,
        "substituted": False,
        "piece_id": row.piece_id,
        "kind": row.kind,
        "draft_id": str(draft.id),
        "run_id": str(row.run_id),
    }
    if identical:
        # Repeated identical review is a no-op for revision, but still report current validity.
        ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
        db.commit()
        return {
            **_artifact_read(row),
            "operator_decision": last or decision,
            "bytes_preserved": True,
            "file_deleted": False,
            "idempotent": True,
            "draft_id": str(draft.id),
            "draft_revision": int(draft.revision or 1),
            "dirty_since_generation": bool(ai.get("dirty_since_generation")),
            "outdated_export_id": ai.get("outdated_export_id"),
            "export_id": ai.get("export_id"),
            "pdf_invalidated": bool(ai.get("dirty_since_generation")),
        }

    decisions = list(meta.get("operator_decisions") or [])
    decisions.append(decision)
    meta["operator_decisions"] = decisions
    meta["last_operator_decision"] = decision
    meta["preview_include"] = preview_include
    meta["manufacturing_evidence"] = manufacturing_evidence
    if message:
        meta["review_message"] = message
    row.review_state = state
    row.metadata_ = meta
    flag_modified(row, "metadata_")
    db.add(row)

    # Atomically invalidate the currently bound Professional PDF and bump revision so
    # FE shows Update PDF (No AI) and PDF-only fingerprint cannot reuse the old export.
    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
    prior_export = str(ai.get("export_id") or "").strip()
    if prior_export:
        ai["outdated_export_id"] = prior_export
    ai["dirty_since_generation"] = True
    ai["artifact_review_version"] = int(ai.get("artifact_review_version") or 0) + 1
    log = list(ai.get("artifact_review_decisions") or [])
    # Audit log without private storage paths.
    log.append(
        {
            "artifact_id": str(row.id),
            "piece_id": row.piece_id,
            "kind": row.kind,
            "review_state": state,
            "review_message": message,
            "reviewer_user_id": str(user.id),
            "decided_at": when,
            "bytes_preserved": True,
        }
    )
    ai["artifact_review_decisions"] = log[-20:]
    stamped = _stamp_artifact_review_into_draft_spec(
        spec,
        artifact_id=str(row.id),
        piece_id=row.piece_id,
        kind=str(row.kind),
        review_state=state,
        review_message=message,
        preview_include=preview_include,
        manufacturing_evidence=manufacturing_evidence,
        decision=decision,
    )
    stamped["ai"] = ai
    draft.spec = stamped
    draft.revision = int(draft.revision or 1) + 1
    draft.updated_at = datetime.now(UTC)
    flag_modified(draft, "spec")
    db.add(draft)
    db.commit()
    db.refresh(row)
    db.refresh(draft)

    return {
        **_artifact_read(row),
        "operator_decision": decision,
        "bytes_preserved": True,
        "file_deleted": False,
        "idempotent": False,
        "draft_id": str(draft.id),
        "draft_revision": int(draft.revision or 1),
        "dirty_since_generation": True,
        "outdated_export_id": ai.get("outdated_export_id"),
        "export_id": ai.get("export_id"),
        "pdf_invalidated": True,
        "new_paid_ai_run": False,
    }


def _cleanup_orphan_pdf(storage: LocalStorageBackend, storage_key: str) -> None:
    try:
        storage.delete_private_techpack_file(key=storage_key)
    except OSError:  # pragma: no cover — best-effort cleanup
        pass


def export_pdf_only_update(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    idempotency_key: str | None = None,
) -> TechpackExportRead:
    """Regenerate the Professional PDF from saved specs + persisted illustrations ($0 AI).

    Creates a NEW versioned export when content changed. Preserves historical PDFs and
    the original Professional run/cost metadata. Binds the new export as current only
    after successful assembly. Idempotent for identical revision-bound content.
    Concurrent identical requests serialize on the draft row and converge on one export.
    """
    # Serialize PDF-only decisions for this draft (duplicate posts + bind CAS).
    draft = _lock_owned_draft(db, user, draft_id)
    ok, reasons, source_run = assess_pdf_only_update_compatibility(db, draft, user=user)
    if not ok:
        # Do not session.rollback() here — shared test transactions and later
        # request work on the same Session must keep prior committed rows.
        raise ValidationAppError(" ".join(reasons) or "PDF-only update is not available for this draft.")
    if source_run is None:
        raise ValidationAppError("PDF-only update is not available for this draft.")

    revision_snapshot = int(draft.revision or 1)
    render_spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    outfit = render_spec.get("outfit") if isinstance(render_spec.get("outfit"), dict) else {}
    raw_pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    pieces: list[dict[str, Any]] = [p for p in raw_pieces if isinstance(p, dict)]
    # Fingerprint the saved draft content (pre-rewrite) so CAS compares designer
    # edits — not server-owned artifact metadata normalization. Review tokens from
    # authoritative TechpackAIArtifact rows are included so reject/reapprove forces
    # a new assembly.
    review_tokens = _authoritative_artifact_review_tokens(db, user, draft)
    fingerprint = _pdf_only_content_fingerprint(
        draft=draft,
        render_spec=render_spec,
        pieces=pieces,
        artifact_reviews=review_tokens,
    )
    # Re-resolve verified artifacts and rewrite storage refs from server-owned rows
    # so PDF assembly never opens a client-supplied private path as authorization.
    art_reasons, verified = _validate_professional_illustration_artifacts(
        db, user, draft, source_run, pieces
    )
    if art_reasons:
        raise ValidationAppError(" ".join(art_reasons))
    render_spec = apply_server_owned_illustration_artifacts(render_spec, verified)
    outfit = render_spec.get("outfit") if isinstance(render_spec.get("outfit"), dict) else {}
    raw_pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    pieces = [p for p in raw_pieces if isinstance(p, dict)]

    ai = render_spec.get("ai") if isinstance(render_spec.get("ai"), dict) else {}
    prior_export_id = str(ai.get("export_id") or "").strip() or None
    source_run_id = str(source_run.id) if source_run is not None else None

    # Idempotency: reuse an existing identical PDF-only export and rebind as current.
    existing = find_export_by_pdf_only_fingerprint(
        db, user, draft_id=draft.id, fingerprint=fingerprint, revision=revision_snapshot
    )
    if existing is not None:
        if prior_export_id != str(existing.id) or bool(ai.get("dirty_since_generation")):
            _bind_current_professional_export(
                db,
                draft,
                export=existing,
                source_run_id=source_run_id,
                prior_export_id=prior_export_id,
                commit=True,
            )
        else:
            db.commit()
        return _export_read(existing)

    # Fingerprint is authoritative; client idempotency_key collapses only via that content key.
    _ = idempotency_key

    storage = LocalStorageBackend()
    front_path = _resolve_job_image(storage, draft.front_job_id, db)
    back_path = _resolve_job_image(storage, draft.back_job_id, db)
    if front_path is None and back_path is None:
        raise ValidationAppError("Cannot export PDF without at least one Magic look image")

    # Historical source-run cost stays attributed to the paid run — not this $0 assembly.
    source_run_cents = 0
    if source_run is not None:
        source_run_cents = int(source_run.cost_usd_cents or 0)
    if not source_run_cents:
        source_run_cents = int(ai.get("actual_cost_usd_cents") or 0)
    source_paid_sections = list(
        ai.get("paid_sections") or []
    )
    # Stamp PDF-only provenance onto the render spec so cover/footer metadata
    # distinguish $0 assembly from the historical paid source run.
    ai_stamp = dict(ai)
    ai_stamp["pdf_only_update"] = True
    ai_stamp["assembly_cost_usd_cents"] = 0
    ai_stamp["actual_cost_usd_cents"] = 0
    ai_stamp["source_run_cost_usd_cents"] = source_run_cents
    ai_stamp["source_run_paid_sections"] = source_paid_sections
    ai_stamp["new_paid_ai_run"] = False
    ai_stamp["last_mode"] = "professional"
    if source_run_id:
        ai_stamp["last_run_id"] = source_run_id
    render_spec = dict(render_spec)
    render_spec["ai"] = ai_stamp

    provenance = resolve_generation_provenance(render_spec)
    provenance = {
        **provenance,
        "mode": "pdf_only_update",
        "label": provenance.get("label")
        or "PDF-only update ($0 assembly · reused AI Professional arts)",
        "is_professional": True,
        "pdf_only_update": True,
        "run_id": source_run_id or provenance.get("run_id") or "",
        "assembly_cost_usd_cents": 0,
        "source_run_cost_usd_cents": source_run_cents,
    }

    # Snapshot fields needed after we release the row lock for slow PDF render.
    title = draft.title
    style_code = draft.style_code
    look_id = draft.look_id
    front_job_id = draft.front_job_id
    back_job_id = draft.back_job_id
    db.commit()  # release FOR UPDATE during render; re-lock + CAS before bind

    pdf_bytes, page_count = build_techpack_pdf(
        title=title,
        style_code=style_code,
        revision=revision_snapshot,
        status="DRAFT",
        verification="UNVERIFIED",
        look_id=str(look_id),
        front_image=front_path,
        back_image=back_path,
        spec=render_spec,
    )
    export_id = uuid.uuid4()
    filename = f"{style_code}_r{revision_snapshot}_techpack.pdf".replace("/", "-")
    storage_key = f"{user.id.hex}/{draft_id.hex}/{export_id.hex}.pdf"
    wrote_pdf = False
    try:
        storage.save_private_techpack_file(
            key=storage_key,
            data=io.BytesIO(pdf_bytes),
            content_type="application/pdf",
        )
        wrote_pdf = True

        # Re-lock and CAS: refuse to bind a stale-revision export over newer saved specs.
        draft = _lock_owned_draft(db, user, draft_id)
        live_revision = int(draft.revision or 1)
        if live_revision != revision_snapshot:
            raise ConflictError(
                "Draft was edited during PDF assembly. Save settled — retry Update PDF (No AI).",
                payload={
                    "reason": "draft_revision_changed",
                    "expected_revision": revision_snapshot,
                    "current_revision": live_revision,
                },
            )
        # Re-validate identity under the lock (Magic source / garment may have drifted).
        ok2, reasons2, source_run2 = assess_pdf_only_update_compatibility(
            db, draft, user=user
        )
        if not ok2:
            raise ValidationAppError(
                " ".join(reasons2) or "PDF-only update is not available for this draft."
            )
        source_run_id = str(source_run2.id) if source_run2 is not None else source_run_id

        live_spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
        live_outfit = live_spec.get("outfit") if isinstance(live_spec.get("outfit"), dict) else {}
        live_raw = live_outfit.get("pieces") if isinstance(live_outfit.get("pieces"), list) else []
        live_pieces = [p for p in live_raw if isinstance(p, dict)]
        live_reviews = _authoritative_artifact_review_tokens(db, user, draft)
        live_fp = _pdf_only_content_fingerprint(
            draft=draft,
            render_spec=live_spec,
            pieces=live_pieces,
            artifact_reviews=live_reviews,
        )
        if live_fp != fingerprint:
            raise ConflictError(
                "Draft content changed during PDF assembly. Retry Update PDF (No AI).",
                payload={"reason": "pdf_only_fingerprint_changed"},
            )

        # Another concurrent identical assembly may have won while we rendered.
        raced = find_export_by_pdf_only_fingerprint(
            db, user, draft_id=draft.id, fingerprint=fingerprint, revision=revision_snapshot
        )
        live_ai = live_spec.get("ai") if isinstance(live_spec.get("ai"), dict) else {}
        prior_export_id = str(live_ai.get("export_id") or "").strip() or prior_export_id
        if raced is not None:
            _cleanup_orphan_pdf(storage, storage_key)
            wrote_pdf = False
            if prior_export_id != str(raced.id) or bool(live_ai.get("dirty_since_generation")):
                _bind_current_professional_export(
                    db,
                    draft,
                    export=raced,
                    source_run_id=source_run_id,
                    prior_export_id=prior_export_id,
                    commit=True,
                )
            else:
                db.commit()
            return _export_read(raced)

        row = TechpackExport(
            id=export_id,
            draft_id=draft.id,
            user_id=user.id,
            storage_key=storage_key,
            filename=filename,
            byte_size=len(pdf_bytes),
            page_count=page_count,
            revision=revision_snapshot,
            status="DRAFT",
            verification="UNVERIFIED",
            metadata_={
                "look_id": str(look_id),
                "front_job_id": str(front_job_id) if front_job_id else None,
                "back_job_id": str(back_job_id) if back_job_id else None,
                "front_image_present": front_path is not None,
                "back_image_present": back_path is not None,
                "height_rows": 1,
                "schema_version": str(render_spec.get("schema_version") or "2.0"),
                "piece_count": len(pieces),
                "cutting_uses_schematics": True,
                "cutting_reuses_magic_looks": False,
                "magic_looks_on_cover_overview_only": True,
                "generation_mode": "pdf_only_update",
                "generation_label": provenance.get("label")
                or "PDF-only update ($0 assembly · reused AI Professional arts)",
                "is_professional": True,
                # Provenance of illustrations — NOT a new paid AI run id for billing.
                "ai_run_id": source_run_id,
                "source_ai_run_id": source_run_id,
                "pdf_only_update": True,
                "pdf_only_fingerprint": fingerprint,
                "new_paid_ai_run": False,
                "provider_calls": 0,
                "assembly_cost_usd_cents": 0,
                # This PDF assembly cost nothing; keep source-run cost distinct.
                "actual_cost_usd_cents": 0,
                "budget_recorded_usd_cents": 0,
                "paid_sections": [],
                "source_run_cost_usd_cents": source_run_cents,
                "source_run_paid_sections": source_paid_sections,
                "vision_model": provenance.get("vision_model") or ai.get("vision_model"),
                "image_model": provenance.get("image_model") or ai.get("image_model"),
                "draft_revision": revision_snapshot,
            },
        )
        db.add(row)
        _bind_current_professional_export(
            db,
            draft,
            export=row,
            source_run_id=source_run_id,
            prior_export_id=prior_export_id,
            commit=False,
        )
        db.commit()
        db.refresh(row)
    except (ConflictError, ValidationAppError):
        if wrote_pdf:
            _cleanup_orphan_pdf(storage, storage_key)
        raise
    except Exception:
        # Unexpected bind/commit failure — drop the uncommitted artifact.
        if wrote_pdf:
            _cleanup_orphan_pdf(storage, storage_key)
        raise

    # Intentionally do NOT rewrite source_run.result.export_id — historical run PDF
    # stays on the run; draft.ai.export_id is the current Download pointer.
    return _export_read(row)


def export_pdf(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    ai_run_id: uuid.UUID | None = None,
    require_professional: bool = False,
    pdf_only_update: bool = False,
    idempotency_key: str | None = None,
) -> TechpackExportRead:
    """Assemble a private PDF from the current draft (no OpenAI calls).

    When *ai_run_id* is set, bind metadata to that run and reuse an existing matching
    Professional export instead of creating a duplicate.

    When *pdf_only_update* is True, regenerate from persisted Professional illustrations,
    create a new versioned export, and bind it as current (see ``export_pdf_only_update``).
    """
    if pdf_only_update:
        return export_pdf_only_update(
            db, user, draft_id, idempotency_key=idempotency_key
        )

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
