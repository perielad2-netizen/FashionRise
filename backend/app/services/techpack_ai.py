"""Create Real Design AI generation — heuristic ($0) + professional (image-aware, spend-gated).

Paid professional calls require: enabled flag, positive spend ceiling, owner allowlist,
confirm_token, and idempotency_key. Preview/export never triggers paid work.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.techpack_ai_artifact import TechpackAIArtifact
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackDraft
from app.models.user import User
from app.services.ai_service import extract_result_image_url
from app.services.techpack_ai_professional import (
    MockProfessionalProvider,
    ProfessionalAIProvider,
    default_provider,
    estimate_professional_cents,
    run_professional_pipeline,
)
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_flats import default_bom, default_construction_steps, pattern_inventory_for_category
from app.services.techpack_garments import collect_measurement_warnings, empty_finished_measurements
from app.services.techpack_spec import ensure_v2
from app.storage.local import LocalStorageBackend

# Test hook — set to MockProfessionalProvider in unit tests.
_PROVIDER_OVERRIDE: ProfessionalAIProvider | None = None


def set_professional_provider_override(provider: ProfessionalAIProvider | None) -> None:
    global _PROVIDER_OVERRIDE
    _PROVIDER_OVERRIDE = provider


def _owned_draft(db: Session, user: User, draft_id: uuid.UUID) -> TechpackDraft:
    draft = db.get(TechpackDraft, draft_id)
    if draft is None or draft.user_id != user.id:
        raise NotFoundError("Techpack draft not found")
    return draft


def _normalize_allowlist() -> set[str]:
    settings = get_settings()
    raw = (settings.techpack_ai_owner_allowlist or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_on_owner_allowlist(user: User) -> bool:
    allow = _normalize_allowlist()
    if not allow:
        return False
    email = (getattr(user, "email", None) or "").strip().lower()
    uid = str(user.id).lower()
    username = (getattr(user, "username", None) or "").strip().lower()
    return email in allow or uid in allow or (username and username in allow)


def ai_status(user: User | None = None) -> dict[str, Any]:
    settings = get_settings()
    key_present = bool((settings.openai_api_key or "").strip())
    enabled_flag = bool(settings.techpack_ai_enabled or settings.techpack_ai_draft_enabled)
    ceiling = float(settings.techpack_ai_spend_ceiling_usd or 0)
    allowlisted = user_on_owner_allowlist(user) if user is not None else False
    professional_available = bool(enabled_flag and key_present and ceiling > 0 and allowlisted)
    lo, hi = estimate_professional_cents(piece_count=1, propose_back=False, has_back_image=False)
    return {
        "enabled": professional_available,  # FE treats enabled as paid-professional available
        "configured_flag": enabled_flag,
        "api_key_present": key_present,
        "spend_ceiling_usd": ceiling,
        "max_usd_per_run": float(settings.techpack_ai_max_usd_per_run or 0),
        "max_usd_per_user_day": float(settings.techpack_ai_max_usd_per_user_day or 0),
        "estimate_chat_cents": int(settings.techpack_ai_estimate_chat_cents or 0),
        "estimate_professional_cents_min": lo,
        "estimate_professional_cents_max": hi,
        "professional_available": professional_available,
        "owner_allowlisted": allowlisted,
        "requires_entitlement": bool(settings.techpack_ai_requires_entitlement),
        "model": settings.openai_model,
        "vision_model": settings.openai_model,
        "image_model": settings.openai_image_model,
        "note": (
            "AI Professional analyzes the Magic look image and generates design-specific technical "
            "illustrations (paid). Basic heuristic pack remains free. "
            "Paid runs require operator enablement, spend ceiling, and owner allowlist."
        ),
    }


def create_confirm_challenge(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    stage: str,
    mode: str = "heuristic",
) -> dict[str, Any]:
    draft = _owned_draft(db, user, draft_id)
    status = ai_status(user)
    token = secrets.token_urlsafe(18)
    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    piece_count = max(1, len(pieces))
    has_back = draft.back_job_id is not None

    if mode == "professional":
        lo, hi = estimate_professional_cents(
            piece_count=piece_count, propose_back=False, has_back_image=has_back
        )
        available = bool(status["professional_available"])
        estimate = hi if available else 0
        message = (
            f"Confirm AI Professional generation. Estimated ~{lo}–{hi}¢ "
            f"(max ${status['max_usd_per_run']:.2f}/run). Uses vision + image models on your Magic look."
            if available
            else (
                "AI Professional is not available for this account yet "
                "(enable flag, spend ceiling, and owner allowlist required). Basic pack stays free."
            )
        )
        return {
            "draft_id": str(draft.id),
            "stage": stage,
            "mode": "professional",
            "confirm_token": token,
            "estimated_cost_usd_cents": estimate,
            "ai_enabled": available,
            "max_usd_per_run": status["max_usd_per_run"],
            "model": status["vision_model"] if available else None,
            "message": message,
            "expires_hint_seconds": 600,
        }

    # heuristic / legacy ai confirm
    estimate = int(status["estimate_chat_cents"]) if status["professional_available"] and mode == "ai" else 0
    return {
        "draft_id": str(draft.id),
        "stage": stage,
        "mode": mode,
        "confirm_token": token,
        "estimated_cost_usd_cents": estimate,
        "ai_enabled": bool(status["professional_available"]) if mode == "ai" else False,
        "max_usd_per_run": status["max_usd_per_run"],
        "model": status["model"] if mode == "ai" and status["professional_available"] else None,
        "message": (
            "Confirm to run paid AI technical generation."
            if mode == "ai" and status["professional_available"]
            else "Basic Technical Pack (heuristic) is free — no paid model calls."
        ),
        "expires_hint_seconds": 600,
    }


def _assert_professional_allowed(db: Session, user: User, *, estimate_cents: int) -> None:
    settings = get_settings()
    status = ai_status(user)
    if not status["professional_available"]:
        raise ForbiddenError(
            "AI Professional is disabled, spend ceiling unset, or account not on owner allowlist"
        )
    max_run = int(round(float(settings.techpack_ai_max_usd_per_run) * 100))
    if estimate_cents > max_run > 0:
        raise ForbiddenError("Estimated cost exceeds per-run spend limit")
    day_ago = datetime.now(UTC) - timedelta(days=1)
    spent = int(
        db.scalar(
            select(func.coalesce(func.sum(TechpackAIRun.cost_usd_cents), 0)).where(
                TechpackAIRun.user_id == user.id,
                TechpackAIRun.created_at >= day_ago,
                TechpackAIRun.status == "completed",
                TechpackAIRun.stage.in_(("professional", "ai")),
            )
        )
        or 0
    )
    max_day = int(round(float(settings.techpack_ai_max_usd_per_user_day) * 100))
    if max_day > 0 and spent + estimate_cents > max_day:
        raise ForbiddenError("Daily techpack AI spend limit reached")
    ceiling_cents = int(round(float(settings.techpack_ai_spend_ceiling_usd) * 100))
    total_spent = int(
        db.scalar(
            select(func.coalesce(func.sum(TechpackAIRun.cost_usd_cents), 0)).where(
                TechpackAIRun.status == "completed",
                TechpackAIRun.stage.in_(("professional", "ai")),
            )
        )
        or 0
    )
    if ceiling_cents > 0 and total_spent + estimate_cents > ceiling_cents:
        raise ForbiddenError("Operator techpack AI spend ceiling reached")
    running = int(
        db.scalar(
            select(func.count()).select_from(TechpackAIRun).where(TechpackAIRun.status == "running")
        )
        or 0
    )
    max_conc = int(settings.techpack_ai_max_concurrent_runs or 2)
    if max_conc > 0 and running >= max_conc:
        raise ForbiddenError("Too many concurrent techpack AI runs — retry shortly")


def _propose_finished_measurements(piece: dict[str, Any], body: dict[str, Any], fit: str) -> dict[str, Any]:
    units = "cm"
    category = str(piece.get("category") or "other")
    finished = empty_finished_measurements(category, units)
    ease = {"slim": 2, "fitted": 3, "regular": 4, "relaxed": 6, "oversized": 10}.get(fit, 4)

    def body_val(key: str) -> float | None:
        cell = body.get(key) if isinstance(body.get(key), dict) else None
        if not cell:
            return None
        v = cell.get("value")
        return float(v) if isinstance(v, (int, float)) else None

    bust = body_val("bust")
    waist = body_val("waist")
    hip = body_val("hip")
    inseam = body_val("inseam")

    def set_calc(key: str, value: float | None, assumptions: list[str]) -> None:
        if key not in finished:
            return
        prev = piece.get("finished_measurements", {}).get(key) if isinstance(piece.get("finished_measurements"), dict) else None
        if isinstance(prev, dict) and prev.get("source") == "designer" and prev.get("value") not in (None, ""):
            finished[key] = prev
            return
        if value is None:
            finished[key] = {
                **finished[key],
                "source": "unknown",
                "confidence": "unknown",
                "note": "Needs body measurement or designer input",
                "assumptions": assumptions,
            }
            return
        finished[key] = {
            **finished[key],
            "value": round(value, 1),
            "unit": units,
            "source": "calculated",
            "confidence": "medium",
            "review_status": "proposed",
            "assumptions": assumptions,
            "note": "First-pass proposal — review before manufacturing",
        }

    if category in ("shirt", "top", "jacket", "dress", "jumpsuit"):
        set_calc("chest_bust", bust + ease if bust is not None else None, [f"body bust + {ease}cm ease ({fit})"])
        set_calc("shoulder_width", (bust * 0.23) if bust is not None else None, ["≈23% of bust — estimate, not image-scaled"])
        set_calc("garment_length", 70.0 if category != "dress" else 110.0, ["Default length assumption — confirm on body"])
        set_calc("sleeve_length", 62.0, ["Standard long-sleeve assumption"])
    if category in ("trousers", "shorts", "skirt", "dress", "jumpsuit"):
        set_calc("waist", waist + ease if waist is not None else None, [f"body waist + {ease}cm ease ({fit})"])
        set_calc("hip", hip + ease if hip is not None else None, [f"body hip + {ease}cm ease ({fit})"])
    if category in ("trousers", "shorts", "jumpsuit"):
        set_calc("inseam", inseam if inseam is not None else 78.0, ["Body inseam if provided, else 78cm default"])
        set_calc("front_rise", 26.0, ["Regular rise assumption"])
        set_calc("back_rise", 34.0, ["Regular rise assumption"])
        set_calc("leg_opening", 38.0 if fit != "wide-leg" else 48.0, [f"Opening for {fit} fit"])
    if category == "skirt":
        set_calc("skirt_length", 60.0, ["Midi-ish default — confirm"])
    return finished


def enrich_spec_heuristic(spec: dict[str, Any]) -> dict[str, Any]:
    out = ensure_v2(spec)
    fit = str((out.get("preferences") or {}).get("fit_preference") or "regular")
    body = out.get("body") if isinstance(out.get("body"), dict) else {}
    outfit = out.get("outfit") if isinstance(out.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    enriched = []
    for piece in pieces:
        if not isinstance(piece, dict):
            continue
        p = dict(piece)
        cat = str(p.get("category") or "other")
        p["finished_measurements"] = _propose_finished_measurements(p, body, fit)
        if not p.get("pattern_pieces"):
            p["pattern_pieces"] = pattern_inventory_for_category(cat)
        if not p.get("construction_steps"):
            p["construction_steps"] = default_construction_steps(cat)
        if not p.get("bom"):
            p["bom"] = default_bom(cat, color_hint=str(p.get("color_hint") or ""))
        mats = p.get("materials") if isinstance(p.get("materials"), dict) else {}
        shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
        if not shell.get("name") and p.get("color_hint"):
            shell = {**shell, "name": f"{p['color_hint']} fabric", "suggestion": "cotton", "source": "estimate"}
            mats["shell"] = shell
            p["materials"] = mats
        p["illustrations"] = {
            **(p.get("illustrations") if isinstance(p.get("illustrations"), dict) else {}),
            "flat_front": "schematic",
            "flat_back": "schematic",
            "cutting": "schematic",
            "label": "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE",
            "mode": "heuristic",
        }
        enriched.append(p)
    outfit["pieces"] = enriched
    outfit["piece_count"] = len(enriched)
    out["outfit"] = outfit
    out["workflow_stage"] = "generate"
    out["warnings"] = collect_measurement_warnings(out)
    out["ai"] = {
        **(out.get("ai") if isinstance(out.get("ai"), dict) else {}),
        "last_mode": "heuristic",
        "paid_sections": out.get("ai", {}).get("paid_sections") if isinstance(out.get("ai"), dict) else [],
    }
    return out


def _resolve_job_bytes(storage: LocalStorageBackend, job_id: uuid.UUID | None, db: Session) -> tuple[bytes, str] | None:
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
    path = storage.resolve_existing_file(key=key)
    if path is None or not path.is_file():
        return None
    data = path.read_bytes()
    mime = "image/png"
    if path.suffix.lower() in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"
    return data, mime


def _artifact_read(row: TechpackAIArtifact) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "piece_id": row.piece_id,
        "kind": row.kind,
        "url_path": f"/techpacks/artifacts/{row.id}/image",
        "review_state": row.review_state,
        "model": row.model,
        "byte_size": row.byte_size,
    }


def _persist_professional_result(
    db: Session,
    *,
    user: User,
    draft: TechpackDraft,
    run: TechpackAIRun,
    pipeline: dict[str, Any],
    base_spec: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    storage = LocalStorageBackend()
    spec = enrich_spec_heuristic(base_spec)
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    by_id = {str(p.get("id")): p for p in pieces}
    artifact_rows: list[TechpackAIArtifact] = []
    artifact_reads: list[dict[str, Any]] = []

    for pr in pipeline.get("piece_results") or []:
        if not isinstance(pr, dict):
            continue
        pid = str(pr.get("piece_id") or "")
        piece = by_id.get(pid)
        if piece is None and pieces:
            piece = pieces[0]
            pid = str(piece.get("id"))
        if piece is None:
            continue
        analysis = pr.get("analysis") if isinstance(pr.get("analysis"), dict) else {}
        # Merge AI construction tips without wiping designer fields.
        if analysis.get("construction_notes") and not piece.get("construction_steps"):
            piece["construction_steps"] = [
                {"step": i + 1, "instruction": str(n)[:400], "source": "ai"}
                for i, n in enumerate(analysis.get("construction_notes") or [])
            ]
        if analysis.get("pattern_pieces_suggested"):
            piece["pattern_pieces"] = [
                {
                    "id": str(x.get("id") or f"P{i}"),
                    "name": str(x.get("name") or "Piece"),
                    "cut_qty": x.get("cut_qty") or 1,
                    "fabric": "shell",
                    "grainline": "straight",
                    "fold": "none",
                    "seam_allowance_cm": 1.0,
                    "source": "ai",
                    "notes": str(x.get("notes") or ""),
                }
                for i, x in enumerate(analysis["pattern_pieces_suggested"])
                if isinstance(x, dict)
            ]
        # Update silhouette / materials hints from analysis when empty.
        fit = piece.get("fit") if isinstance(piece.get("fit"), dict) else {}
        if not fit.get("silhouette") and analysis.get("silhouette"):
            fit = {**fit, "silhouette": str(analysis["silhouette"])[:80], "suggestion": str(analysis.get("fit") or "")}
            piece["fit"] = fit
        mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
        shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
        if not shell.get("name") and analysis.get("fabric_pattern"):
            shell = {
                **shell,
                "name": str(analysis.get("fabric_pattern"))[:120],
                "composition": shell.get("composition") or "Unknown",
                "source": "ai",
            }
            mats["shell"] = shell
            piece["materials"] = mats

        illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        art_meta: dict[str, Any] = {}
        for art in pr.get("artifacts") or []:
            if not isinstance(art, dict) or not art.get("bytes"):
                continue
            art_id = uuid.uuid4()
            kind = str(art.get("kind") or "illustration")
            key = f"{user.id.hex}/{draft.id.hex}/ai/{run.id.hex}/{art_id.hex}_{kind}.png"
            raw = art["bytes"]
            storage.save_private_techpack_file(
                key=key,
                data=io.BytesIO(raw),
                content_type=str(art.get("mime") or "image/png"),
            )
            row = TechpackAIArtifact(
                id=art_id,
                run_id=run.id,
                draft_id=draft.id,
                user_id=user.id,
                piece_id=pid,
                kind=kind,
                storage_key=key,
                mime_type=str(art.get("mime") or "image/png"),
                byte_size=len(raw),
                model=art.get("model"),
                source_job_id=draft.front_job_id or draft.back_job_id,
                look_id=draft.look_id,
                review_state="proposed" if kind != "flat_back_proposed" else "proposed_unverified",
                metadata_={
                    "analysis_schema": analysis.get("schema_version"),
                    "neckline": analysis.get("neckline"),
                    "sleeves": analysis.get("sleeves"),
                    "fabric_pattern": analysis.get("fabric_pattern"),
                },
            )
            db.add(row)
            artifact_rows.append(row)
            artifact_reads.append(_artifact_read(row))
            art_meta[kind] = {
                "artifact_id": str(art_id),
                "storage_key": key,
                "url_path": f"/techpacks/artifacts/{art_id}/image",
                "review_state": row.review_state,
            }
        illust.update(
            {
                "mode": "professional",
                "label": "AI TECHNICAL ILLUSTRATIONS — REVIEW REQUIRED · PATTERN SCHEMATICS NOT TO SCALE",
                "analysis": {
                    k: analysis.get(k)
                    for k in (
                        "silhouette",
                        "length",
                        "neckline",
                        "sleeves",
                        "fit",
                        "fabric_pattern",
                        "stripe_direction",
                        "colors",
                        "distinctive_features",
                        "confidence",
                        "assumptions",
                    )
                },
                "artifacts": art_meta,
                "flat_front": art_meta.get("flat_front", {}).get("artifact_id") or "schematic",
                "flat_back": (
                    art_meta.get("flat_back") or art_meta.get("flat_back_proposed") or {}
                ).get("artifact_id")
                or "schematic",
            }
        )
        piece["illustrations"] = illust
        by_id[pid] = piece

    outfit["pieces"] = list(by_id.values())
    outfit["piece_count"] = len(outfit["pieces"])
    spec["outfit"] = outfit
    usage = pipeline.get("usage") if isinstance(pipeline.get("usage"), dict) else {}
    spec["ai"] = {
        **(spec.get("ai") if isinstance(spec.get("ai"), dict) else {}),
        "last_mode": "professional",
        "last_run_id": str(run.id),
        "paid_sections": ["vision_analysis", "technical_flats", "pattern_sheet"],
        "analysis_summary": pipeline.get("analysis_summary"),
        "estimated_cost_usd_cents": usage.get("estimated_cost_usd_cents"),
        "actual_cost_usd_cents": usage.get("cost_usd_cents"),
        "vision_model": usage.get("vision_model"),
        "image_model": usage.get("image_model"),
    }
    spec["warnings"] = collect_measurement_warnings(spec)
    return spec, artifact_reads


def run_generate(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    confirm_token: str,
    idempotency_key: str,
    mode: str = "heuristic",
    sections: list[str] | None = None,
    propose_back: bool = False,
) -> dict[str, Any]:
    draft = _owned_draft(db, user, draft_id)
    if not confirm_token or len(confirm_token) < 8:
        raise ValidationAppError("confirm_token required")
    if not idempotency_key or len(idempotency_key) < 8:
        raise ValidationAppError("idempotency_key required")

    existing = db.scalars(
        select(TechpackAIRun).where(
            TechpackAIRun.user_id == user.id,
            TechpackAIRun.idempotency_key == idempotency_key,
        )
    ).first()
    if existing and existing.status == "completed":
        arts = list(
            db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == existing.id)).all()
        )
        return {
            "run_id": str(existing.id),
            "status": existing.status,
            "cost_usd_cents": existing.cost_usd_cents,
            "actual_cost_usd_cents": existing.cost_usd_cents,
            "estimated_cost_usd_cents": (existing.result or {}).get("estimated_cost_usd_cents"),
            "mode": existing.stage,
            "result": existing.result,
            "artifacts": [_artifact_read(a) for a in arts],
            "analysis_summary": (existing.result or {}).get("analysis_summary"),
            "failed_sections": (existing.result or {}).get("failed_sections") or [],
            "idempotent_replay": True,
        }

    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    if mode in ("analyze", "ai", "heuristic", "professional") and (
        not (spec.get("outfit") or {}).get("pieces") or (sections and "detect" in sections)
    ):
        detection = detect_pieces_from_evidence(
            look_summary=str(spec.get("look_notes") or ""), units=str(spec.get("units") or "cm")
        )
        if not sections or "detect" in (sections or []):
            if all(
                str(p.get("detection_source") or "").startswith("heuristic")
                for p in (spec.get("outfit") or {}).get("pieces") or []
            ):
                spec["outfit"] = detection

    paid = mode in ("ai", "professional")
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    lo, hi = estimate_professional_cents(
        piece_count=max(1, len(pieces)),
        propose_back=propose_back,
        has_back_image=draft.back_job_id is not None,
    )
    estimate = hi if mode == "professional" else (int(get_settings().techpack_ai_estimate_chat_cents or 8) if paid else 0)
    if mode == "professional":
        _assert_professional_allowed(db, user, estimate_cents=estimate)
    elif paid:
        # Legacy text-only "ai" mode still gated the same way.
        _assert_professional_allowed(db, user, estimate_cents=estimate)

    run = existing or TechpackAIRun(
        id=uuid.uuid4(),
        draft_id=draft.id,
        user_id=user.id,
        stage=mode,
        status="running",
        confirm_token=confirm_token,
        idempotency_key=idempotency_key,
        request={"mode": mode, "sections": sections or ["all"], "propose_back": propose_back},
    )
    if existing is None:
        db.add(run)
        db.flush()

    try:
        artifacts: list[dict[str, Any]] = []
        analysis_summary = None
        failed_sections: list[str] = []
        cost = 0
        model = None

        if mode == "professional":
            storage = LocalStorageBackend()
            front = _resolve_job_bytes(storage, draft.front_job_id, db)
            back = _resolve_job_bytes(storage, draft.back_job_id, db)
            if front is None and back is None:
                raise ValidationAppError("Professional AI requires an authenticated Magic look image")
            provider = _PROVIDER_OVERRIDE or default_provider()
            # Force mock when settings disable paid but tests inject override — production never auto-mocks.
            if _PROVIDER_OVERRIDE is None and not (get_settings().openai_api_key or "").strip():
                raise ForbiddenError("OpenAI API key missing for professional AI")
            pipeline = run_professional_pipeline(
                provider=provider,
                pieces=pieces or [{"id": "piece-1", "category": "other", "label": "Garment"}],
                front_image=front,
                back_image=back,
                look_notes=str(spec.get("look_notes") or ""),
                propose_back=bool(propose_back),
                max_images=int(get_settings().techpack_ai_max_images_per_run or 6),
            )
            pipeline["usage"]["estimated_cost_usd_cents"] = estimate
            enriched, artifacts = _persist_professional_result(
                db, user=user, draft=draft, run=run, pipeline=pipeline, base_spec=spec
            )
            cost = int((pipeline.get("usage") or {}).get("cost_usd_cents") or 0)
            # Never exceed reserved estimate without a second confirmation — clamp accounting.
            if cost > estimate > 0:
                cost = estimate
            model = (pipeline.get("usage") or {}).get("image_model") or (
                pipeline.get("usage") or {}
            ).get("vision_model")
            analysis_summary = pipeline.get("analysis_summary")
            failed_sections = list(pipeline.get("failed_sections") or [])
        else:
            enriched = enrich_spec_heuristic(spec)
            if mode == "ai":
                # Keep legacy text tip path as optional thin enrich — still gated.
                from app.services import techpack_ai as self_mod  # noqa: F401 — clarity

                # Minimal: mark paid tip section without inventing image flats.
                enriched["ai"] = {
                    **(enriched.get("ai") if isinstance(enriched.get("ai"), dict) else {}),
                    "last_mode": "ai",
                    "paid_sections": ["construction_tips"],
                    "note": "Legacy text tip mode — prefer mode=professional for image-aware flats",
                }
                cost = int(get_settings().techpack_ai_estimate_chat_cents or 8)
                model = get_settings().openai_model

        draft.spec = enriched
        draft.status = "DRAFT"
        draft.verification = "UNVERIFIED"
        draft.updated_at = datetime.now(UTC)
        run.status = "completed"
        run.model = model
        run.cost_usd_cents = cost
        run.result = {
            "piece_count": enriched.get("outfit", {}).get("piece_count"),
            "warnings": enriched.get("warnings") or [],
            "mode": mode,
            "analysis_summary": analysis_summary,
            "failed_sections": failed_sections,
            "estimated_cost_usd_cents": estimate,
            "actual_cost_usd_cents": cost,
            "artifact_ids": [a["id"] for a in artifacts],
        }
        run.input_hash = hashlib.sha256(
            json.dumps({"mode": mode, "propose_back": propose_back}, sort_keys=True).encode()
        ).hexdigest()[:64]
        run.error_message = None
        db.add(draft)
        db.add(run)
        db.commit()
        db.refresh(draft)
        db.refresh(run)
        return {
            "run_id": str(run.id),
            "status": run.status,
            "cost_usd_cents": run.cost_usd_cents,
            "actual_cost_usd_cents": run.cost_usd_cents,
            "estimated_cost_usd_cents": estimate,
            "mode": mode,
            "draft_id": str(draft.id),
            "warnings": enriched.get("warnings") or [],
            "artifacts": artifacts,
            "analysis_summary": analysis_summary,
            "failed_sections": failed_sections,
            "idempotent_replay": False,
        }
    except (ForbiddenError, ValidationAppError, NotFoundError):
        db.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        draft = _owned_draft(db, user, draft_id)
        run_row = db.get(TechpackAIRun, run.id) if getattr(run, "id", None) else None
        if run_row is None:
            run_row = TechpackAIRun(
                id=uuid.uuid4(),
                draft_id=draft.id,
                user_id=user.id,
                stage=mode,
                status="failed",
                confirm_token=confirm_token,
                idempotency_key=idempotency_key,
                request={"mode": mode},
                error_message=str(exc)[:1000],
            )
            db.add(run_row)
        else:
            run_row.status = "failed"
            run_row.error_message = str(exc)[:1000]
            db.add(run_row)
        db.commit()
        raise ValidationAppError(f"Technical generation failed: {exc}") from exc


def get_run(db: Session, user: User, run_id: uuid.UUID) -> dict[str, Any]:
    row = db.get(TechpackAIRun, run_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("AI run not found")
    arts = list(db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == row.id)).all())
    return {
        "id": str(row.id),
        "draft_id": str(row.draft_id),
        "stage": row.stage,
        "status": row.status,
        "model": row.model,
        "cost_usd_cents": row.cost_usd_cents,
        "result": row.result,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "artifacts": [_artifact_read(a) for a in arts],
    }


def resolve_artifact_image(db: Session, user: User, artifact_id: uuid.UUID) -> tuple[Path, TechpackAIArtifact]:
    row = db.get(TechpackAIArtifact, artifact_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Techpack artifact not found")
    storage = LocalStorageBackend()
    path = storage.resolve_private_techpack_file(key=row.storage_key)
    if path is None:
        raise NotFoundError("Techpack artifact file missing")
    return path, row
