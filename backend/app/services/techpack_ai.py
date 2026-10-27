"""Create Real Design AI generation — heuristic ($0) + professional (image-aware, spend-gated).

Paid professional one-tap enqueues a durable TechpackAIRun (status=queued) and returns
promptly; fashionrise-ai-worker claims and executes the paid pipeline off the HTTP path.
Preview/export never triggers paid work.
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
from app.services.sketch_openai import SketchConfigError
from app.services.techpack_ai_professional import (
    ProfessionalAIProvider,
    default_provider,
    estimate_professional_cents,
    run_professional_pipeline,
)
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_flats import (
    default_bom,
    default_construction_steps,
    pattern_inventory_for_category,
)
from app.services.techpack_garments import (
    collect_measurement_warnings,
    empty_finished_measurements,
)
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
    """Legacy helper — allowlist is no longer a feature gate (kept for ops introspection)."""
    settings = get_settings()
    raw = (settings.techpack_ai_owner_allowlist or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def user_on_owner_allowlist(user: User) -> bool:
    """Deprecated: AI Professional no longer requires a separate owner allowlist.

    Cloudflare Access already gates the private app. Authenticated FashionRise users
    may use Professional subject to enablement + spend ceilings.
    """
    _ = user
    return True


def ai_status(user: User | None = None) -> dict[str, Any]:
    settings = get_settings()
    key_present = bool((settings.openai_api_key or "").strip())
    enabled_flag = bool(settings.techpack_ai_enabled or settings.techpack_ai_draft_enabled)
    ceiling = float(settings.techpack_ai_spend_ceiling_usd or 0)
    # Any authenticated FashionRise account (CF Access already gates the private app).
    # Spend / concurrency gates still enforce in _assert_professional_allowed.
    _ = user
    professional_available = bool(enabled_flag and key_present and ceiling > 0)
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
        # Always true for API compat — allowlist is no longer a gate.
        "owner_allowlisted": True,
        "requires_entitlement": bool(settings.techpack_ai_requires_entitlement),
        "model": settings.openai_model,
        "vision_model": settings.openai_model,
        "image_model": settings.openai_image_model,
        "note": (
            "AI Professional analyzes the Magic look image and generates design-specific technical "
            "illustrations (paid). Available to authenticated FashionRise accounts when enabled "
            "with a spend ceiling; per-run / daily / operator ceilings still apply."
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
                "AI Professional is not available yet "
                "(enable flag, API key, and spend ceiling required)."
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
            "AI Professional is disabled, OpenAI key missing, or spend ceiling unset"
        )
    max_run = int(round(float(settings.techpack_ai_max_usd_per_run) * 100))
    if estimate_cents > max_run > 0:
        raise ForbiddenError("Estimated cost exceeds per-run spend limit")
    day_ago = datetime.now(UTC) - timedelta(days=1)
    # Count known paid usage across completed / failed / reconciliation — never ignore partial spend.
    billable_statuses = ("completed", "failed", "reconciliation_required", "running", "queued")
    spent = int(
        db.scalar(
            select(func.coalesce(func.sum(TechpackAIRun.cost_usd_cents), 0)).where(
                TechpackAIRun.user_id == user.id,
                TechpackAIRun.created_at >= day_ago,
                TechpackAIRun.status.in_(billable_statuses),
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
                TechpackAIRun.status.in_(billable_statuses),
                TechpackAIRun.stage.in_(("professional", "ai")),
            )
        )
        or 0
    )
    if ceiling_cents > 0 and total_spent + estimate_cents > ceiling_cents:
        raise ForbiddenError("Operator techpack AI spend ceiling reached")
    running = int(
        db.scalar(
            select(func.count())
            .select_from(TechpackAIRun)
            .where(TechpackAIRun.status.in_(("queued", "running")))
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

    # Never invent garment dimensions from thin air. Only propose when designer body
    # measurements exist; otherwise leave empty / explicitly unknown.
    if category in ("shirt", "top", "jacket", "dress", "jumpsuit"):
        set_calc(
            "chest_bust",
            bust + ease if bust is not None else None,
            [f"body bust + {ease}cm ease ({fit})"] if bust is not None else ["Needs body bust or designer input"],
        )
        set_calc(
            "shoulder_width",
            (bust * 0.23) if bust is not None else None,
            ["≈23% of bust — estimate, not image-scaled"]
            if bust is not None
            else ["Needs body bust — not fabricated from image"],
        )
        set_calc(
            "garment_length",
            None,
            ["Garment length not measured from image — enter when known"],
        )
        set_calc(
            "sleeve_length",
            None,
            ["Sleeve length not fabricated — enter when known or confirm from visible style"],
        )
    if category in ("trousers", "shorts", "skirt", "dress", "jumpsuit"):
        set_calc(
            "waist",
            waist + ease if waist is not None else None,
            [f"body waist + {ease}cm ease ({fit})"] if waist is not None else ["Needs body waist or designer input"],
        )
        set_calc(
            "hip",
            hip + ease if hip is not None else None,
            [f"body hip + {ease}cm ease ({fit})"] if hip is not None else ["Needs body hip or designer input"],
        )
    if category in ("trousers", "shorts", "jumpsuit"):
        set_calc(
            "inseam",
            inseam if inseam is not None else None,
            ["From body inseam"] if inseam is not None else ["Inseam not fabricated — enter when known"],
        )
        set_calc("front_rise", None, ["Front rise unknown — enter when known"])
        set_calc("back_rise", None, ["Back rise unknown — enter when known"])
        set_calc("leg_opening", None, ["Leg opening unknown — enter when known"])
    if category == "skirt":
        set_calc("skirt_length", None, ["Skirt length unknown — enter when known"])
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
    prior = out.get("ai") if isinstance(out.get("ai"), dict) else {}
    # Heuristic regenerate must not keep claiming prior paid Professional sections.
    out["ai"] = {
        **prior,
        "last_mode": "heuristic",
        "paid_sections": [],
        "actual_cost_usd_cents": 0,
        "prior_professional_run_id": prior.get("last_run_id")
        if prior.get("last_mode") == "professional"
        else prior.get("prior_professional_run_id"),
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
                    "notes": str(x.get("notes") or "")
                    + " — illustrative inventory, not a verified cutting pattern",
                    "provenance": "ai_inferred",
                }
                for i, x in enumerate(analysis["pattern_pieces_suggested"])
                if isinstance(x, dict)
            ]

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
                        "schema_version",
                        "category",
                        "silhouette",
                        "length",
                        "neckline",
                        "sleeves",
                        "fit",
                        "closure_visible",
                        "fabric_pattern",
                        "stripe_direction",
                        "colors",
                        "panels_seams",
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
                "status_banner": "DRAFT / UNVERIFIED",
            }
        )
        piece["illustrations"] = illust
        from app.services.techpack_autofill import apply_visible_analysis_to_piece

        piece = apply_visible_analysis_to_piece(piece, analysis, only_empty=True)
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
        "autofill_applied": True,
        "autofill_paid_call": False,
    }
    from app.services.techpack_compatibility import (
        collect_compatibility_warnings,
        filter_construction_steps,
        filter_pattern_inventory,
        is_sleeveless_analysis,
    )
    from app.services.techpack_autofill import snapshot_garment_analysis

    # Post-process construction / inventory against vision analysis.
    piece_analyses: dict[str, dict[str, Any]] = {}
    for piece in outfit.get("pieces") or []:
        if not isinstance(piece, dict):
            continue
        illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        if analysis:
            piece_analyses[str(piece.get("id") or "")] = analysis
        if piece.get("construction_steps"):
            piece["construction_steps"] = filter_construction_steps(
                list(piece.get("construction_steps") or []),
                analysis=analysis,
            )
        if piece.get("pattern_pieces"):
            piece["pattern_pieces"] = filter_pattern_inventory(
                [p for p in (piece.get("pattern_pieces") or []) if isinstance(p, dict)],
                analysis=analysis,
            )
        elif is_sleeveless_analysis(analysis):
            from app.services.techpack_flats import pattern_inventory_for_category

            piece["pattern_pieces"] = filter_pattern_inventory(
                pattern_inventory_for_category(str(piece.get("category") or "other")),
                analysis=analysis,
                ai_suggested=analysis.get("pattern_pieces_suggested")
                if isinstance(analysis.get("pattern_pieces_suggested"), list)
                else None,
            )

    look_identity = (
        spec.get("look_design_identity")
        if isinstance(spec.get("look_design_identity"), dict)
        else None
    )
    spec["garment_analysis"] = snapshot_garment_analysis(
        pieces=list(outfit.get("pieces") or []),
        piece_analyses=piece_analyses,
        look_summary=str(spec.get("look_notes") or ""),
        design_identity=look_identity,
        run_id=str(run.id),
    )
    spec["warnings"] = collect_measurement_warnings(spec) + collect_compatibility_warnings(spec)
    return spec, artifact_reads


def _set_run_progress(
    db: Session,
    run: TechpackAIRun,
    progress: dict[str, Any],
    *,
    cost_usd_cents: int | None = None,
    provider_in_flight: dict[str, Any] | None = None,
    clear_in_flight: bool = False,
) -> None:
    """Persist named pipeline phase + known spend for FE polling (commit so other sessions see it)."""
    req = dict(run.request) if isinstance(run.request, dict) else {}
    req["progress"] = progress
    if cost_usd_cents is not None:
        run.cost_usd_cents = max(int(run.cost_usd_cents or 0), int(cost_usd_cents))
        req["usage"] = {
            **(req.get("usage") if isinstance(req.get("usage"), dict) else {}),
            "cost_usd_cents": run.cost_usd_cents,
        }
    if clear_in_flight:
        req.pop("provider_in_flight", None)
    elif provider_in_flight is not None:
        req["provider_in_flight"] = provider_in_flight
    run.request = req
    db.add(run)
    db.commit()
    db.refresh(run)


def _run_status_payload(db: Session, run: TechpackAIRun) -> dict[str, Any]:
    arts = list(
        db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run.id)).all()
    )
    req = run.request if isinstance(run.request, dict) else {}
    result = run.result if isinstance(run.result, dict) else {}
    export_id = result.get("export_id")
    pdf_ready = bool(result.get("pdf_ready")) and bool(export_id)
    # Budget-recorded cents (internal reservation / fallback accounting) — not verified wallet billing.
    budget_cents = result.get("budget_recorded_usd_cents")
    if budget_cents is None:
        budget_cents = int(run.cost_usd_cents or 0)
    download_path = f"/api/v1/techpacks/exports/{export_id}/pdf" if export_id else None
    # Ready for the user only when Professional PDF is bound to this exact run.
    progress = req.get("progress") or result.get("progress")
    if run.status == "completed" and not pdf_ready:
        # Never claim Ready without a verified Professional PDF for this run.
        if isinstance(progress, dict) and progress.get("phase") == "ready":
            progress = {
                **progress,
                "phase": "assembling",
                "message": "Preparing your PDF…",
            }
    return {
        "run_id": str(run.id),
        "id": str(run.id),
        "draft_id": str(run.draft_id),
        "status": run.status,
        "status_url": f"/api/v1/techpacks/ai/runs/{run.id}",
        "cost_usd_cents": int(run.cost_usd_cents or 0),
        "actual_cost_usd_cents": int(run.cost_usd_cents or 0),
        "budget_recorded_usd_cents": int(budget_cents or 0),
        "estimated_cost_usd_cents": result.get("estimated_cost_usd_cents")
        or (req.get("estimate_cents") if isinstance(req, dict) else None),
        "mode": run.stage,
        "stage": run.stage,
        "progress": progress,
        "result": result,
        "error_message": run.error_message,
        "artifacts": [_artifact_read(a) for a in arts],
        "analysis_summary": result.get("analysis_summary"),
        "failed_sections": result.get("failed_sections") or [],
        "export_id": str(export_id) if export_id else None,
        "download_path": download_path,
        "pdf_ready": pdf_ready,
        "pdf_filename": result.get("pdf_filename"),
        "safe_retry": run.status not in ("running", "queued", "reconciliation_required")
        and not (run.status == "failed" and int(run.cost_usd_cents or 0) > 0),
    }


def ensure_professional_pdf_for_run(
    db: Session, user: User, run: TechpackAIRun
) -> TechpackAIRun:
    """Idempotently assemble/bind Professional PDF for a completed illustration run (zero OpenAI)."""
    from app.services import techpack_service

    if run.stage != "professional":
        return run
    result = dict(run.result) if isinstance(run.result, dict) else {}
    export_id_raw = result.get("export_id")
    if export_id_raw and result.get("pdf_ready"):
        # Verify file still readable; otherwise reassemble.
        try:
            techpack_service.resolve_export_pdf_path(db, user, uuid.UUID(str(export_id_raw)))
            # Keep draft.ai.export_id in sync for reopen/Download without a new paid run.
            draft = _owned_draft(db, user, run.draft_id)
            spec = draft.spec if isinstance(draft.spec, dict) else {}
            ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
            if ai.get("export_id") != str(export_id_raw) or ai.get("dirty_since_generation"):
                ai["export_id"] = str(export_id_raw)
                ai["dirty_since_generation"] = False
                ai["last_run_id"] = str(run.id)
                ai["last_mode"] = "professional"
                spec["ai"] = ai
                draft.spec = spec
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(draft, "spec")
                db.add(draft)
                db.commit()
            return run
        except Exception:  # noqa: BLE001
            pass

    arts = list(
        db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run.id)).all()
    )
    if not arts and run.status != "completed":
        return run

    exported = techpack_service.export_pdf(
        db,
        user,
        run.draft_id,
        ai_run_id=run.id,
        require_professional=True,
    )
    draft = _owned_draft(db, user, run.draft_id)
    spec = draft.spec if isinstance(draft.spec, dict) else {}
    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
    ai["export_id"] = str(exported.id)
    ai["dirty_since_generation"] = False
    ai["last_run_id"] = str(run.id)
    ai["last_mode"] = "professional"
    spec["ai"] = ai
    draft.spec = spec
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(draft, "spec")
    db.add(draft)

    ready_progress = {
        "phase": "ready",
        "message": "Your AI Technical Pack is ready",
    }
    req = dict(run.request) if isinstance(run.request, dict) else {}
    req["progress"] = ready_progress
    run.request = req
    result.update(
        {
            "export_id": str(exported.id),
            "pdf_ready": True,
            "pdf_filename": exported.filename,
            "download_path": f"/api/v1/techpacks/exports/{exported.id}/pdf",
            "draft_revision": int(draft.revision or 1),
            "budget_recorded_usd_cents": int(run.cost_usd_cents or 0),
            "progress": ready_progress,
        }
    )
    run.result = result
    if run.status not in ("failed", "reconciliation_required", "queued", "running"):
        run.status = "completed"
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def enqueue_generate_one_tap_professional(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    idempotency_key: str,
    propose_back: bool = True,
    sections: list[str] | None = None,
) -> dict[str, Any]:
    """Authorize one bounded Professional run and enqueue durable work (HTTP returns promptly)."""
    challenge = create_confirm_challenge(
        db, user, draft_id, stage="generate", mode="professional"
    )
    if not challenge.get("ai_enabled"):
        raise ForbiddenError(
            challenge.get("message")
            or "AI Professional is not available for this account"
        )
    draft = _owned_draft(db, user, draft_id)
    if not idempotency_key or len(idempotency_key) < 8:
        raise ValidationAppError("idempotency_key required")

    existing = db.scalars(
        select(TechpackAIRun).where(
            TechpackAIRun.user_id == user.id,
            TechpackAIRun.idempotency_key == idempotency_key,
        )
    ).first()
    if existing is not None:
        payload = _run_status_payload(db, existing)
        payload["idempotent_replay"] = True
        if existing.status in ("queued", "running"):
            payload["message"] = (
                "Generation already in progress for this request. Wait or reopen the draft."
            )
        elif existing.status == "reconciliation_required":
            payload["safe_retry"] = False
            payload["message"] = (
                "Previous attempt needs reconciliation — usable artifacts are preserved; "
                "do not start a new paid run until recovery is confirmed."
            )
        elif existing.status == "failed" and int(existing.cost_usd_cents or 0) > 0:
            payload["safe_retry"] = False
            payload["message"] = (
                "Previous attempt recorded usage. Start a new confirmed generation to continue."
            )
        return payload

    inflight = db.scalars(
        select(TechpackAIRun)
        .where(
            TechpackAIRun.user_id == user.id,
            TechpackAIRun.draft_id == draft.id,
            TechpackAIRun.stage == "professional",
            TechpackAIRun.status.in_(("queued", "running")),
        )
        .order_by(TechpackAIRun.created_at.desc())
    ).first()
    if inflight is not None:
        payload = _run_status_payload(db, inflight)
        payload["idempotent_replay"] = True
        payload["message"] = "A Professional generation is already in progress for this draft."
        return payload

    # Reuse a completed Professional run + PDF for this draft revision (no second paid job).
    spec_now = draft.spec if isinstance(draft.spec, dict) else {}
    ai_now = spec_now.get("ai") if isinstance(spec_now.get("ai"), dict) else {}
    dirty = bool(ai_now.get("dirty_since_generation"))
    if not dirty:
        completed = db.scalars(
            select(TechpackAIRun)
            .where(
                TechpackAIRun.user_id == user.id,
                TechpackAIRun.draft_id == draft.id,
                TechpackAIRun.stage == "professional",
                TechpackAIRun.status == "completed",
            )
            .order_by(TechpackAIRun.created_at.desc())
        ).first()
        if completed is not None:
            completed = ensure_professional_pdf_for_run(db, user, completed)
            payload = _run_status_payload(db, completed)
            if payload.get("pdf_ready"):
                result = completed.result if isinstance(completed.result, dict) else {}
                same_rev = int(result.get("draft_revision") or 0) == int(draft.revision or 1)
                if same_rev or not result.get("draft_revision"):
                    payload["idempotent_replay"] = True
                    payload["reused_completed"] = True
                    payload["message"] = "Using your existing AI Technical Pack for this design."
                    return payload

    effective_propose = bool(propose_back) if draft.back_job_id is None else False
    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    _lo, hi = estimate_professional_cents(
        piece_count=max(1, len(pieces)),
        propose_back=effective_propose,
        has_back_image=draft.back_job_id is not None,
    )
    _assert_professional_allowed(db, user, estimate_cents=hi)

    run = TechpackAIRun(
        id=uuid.uuid4(),
        draft_id=draft.id,
        user_id=user.id,
        stage="professional",
        status="queued",
        confirm_token=str(challenge["confirm_token"]),
        idempotency_key=idempotency_key,
        request={
            "mode": "professional",
            "sections": sections or ["all"],
            "propose_back": effective_propose,
            "authorization": "user_click_one_tap",
            "estimate_cents": hi,
            "progress": {
                "phase": "preparing",
                "message": "Preparing your design",
                "pieces_done": 0,
                "pieces_total": max(1, len(pieces)),
            },
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    payload = _run_status_payload(db, run)
    payload["idempotent_replay"] = False
    payload["accepted"] = True
    return payload


def run_generate_one_tap_professional(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    idempotency_key: str,
    propose_back: bool = True,
    sections: list[str] | None = None,
) -> dict[str, Any]:
    """Enqueue durable Professional work — does not wait on the paid provider pipeline."""
    return enqueue_generate_one_tap_professional(
        db,
        user,
        draft_id,
        idempotency_key=idempotency_key,
        propose_back=propose_back,
        sections=sections,
    )


def _fail_run_preserve_cost(
    db: Session,
    run_id: uuid.UUID,
    *,
    error: str,
    provider_called: bool,
    force_zero_if_no_usage: bool = False,
) -> None:
    run_row = db.get(TechpackAIRun, run_id)
    if run_row is None:
        return
    req = dict(run_row.request) if isinstance(run_row.request, dict) else {}
    known = int(run_row.cost_usd_cents or 0)
    usage = req.get("usage") if isinstance(req.get("usage"), dict) else {}
    known = max(known, int(usage.get("cost_usd_cents") or 0))
    if force_zero_if_no_usage and known == 0:
        run_row.cost_usd_cents = 0
    else:
        run_row.cost_usd_cents = known
    run_row.status = "failed"
    run_row.error_message = error[:1000]
    req["provider_called"] = provider_called
    req.pop("provider_in_flight", None)
    run_row.request = req
    result = dict(run_row.result) if isinstance(run_row.result, dict) else {}
    result["actual_cost_usd_cents"] = run_row.cost_usd_cents
    run_row.result = result
    db.add(run_row)
    db.commit()


def execute_professional_run(db: Session, run_id: uuid.UUID) -> dict[str, Any]:
    """Worker entry: execute a claimed Professional run to completion / failure / reconciliation."""
    run = db.get(TechpackAIRun, run_id)
    if run is None:
        raise NotFoundError("AI run not found")
    user = db.get(User, run.user_id)
    if run.status == "completed" and user is not None:
        try:
            run = ensure_professional_pdf_for_run(db, user, run)
        except Exception:  # noqa: BLE001
            db.rollback()
            run = db.get(TechpackAIRun, run_id) or run
        return _run_status_payload(db, run)
    if run.status == "reconciliation_required":
        if user is not None:
            result = run.result if isinstance(run.result, dict) else {}
            arts = list(
                db.scalars(
                    select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run.id)
                ).all()
            )
            if arts and not result.get("pdf_ready"):
                try:
                    run = ensure_professional_pdf_for_run(db, user, run)
                except Exception:  # noqa: BLE001
                    db.rollback()
                    run = db.get(TechpackAIRun, run_id) or run
        return _run_status_payload(db, run)
    if run.status not in ("running", "queued"):
        return _run_status_payload(db, run)

    if user is None:
        run.status = "failed"
        run.error_message = "User missing for techpack AI run"
        db.add(run)
        db.commit()
        return _run_status_payload(db, run)

    draft = _owned_draft(db, user, run.draft_id)
    req = dict(run.request) if isinstance(run.request, dict) else {}
    if isinstance(req.get("provider_in_flight"), dict) and req["provider_in_flight"]:
        run.status = "reconciliation_required"
        run.error_message = (
            "Provider call was in flight when the worker stopped. "
            "Manual recovery required — do not auto-retry."
        )[:1000]
        db.add(run)
        db.commit()
        return _run_status_payload(db, run)

    if run.status == "queued":
        run.status = "running"
        db.add(run)
        db.commit()
        db.refresh(run)

    mode = "professional"
    propose_back = bool(req.get("propose_back"))
    sections = req.get("sections") if isinstance(req.get("sections"), list) else ["all"]
    estimate = int(req.get("estimate_cents") or 0)
    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]

    try:
        storage = LocalStorageBackend()
        front = _resolve_job_bytes(storage, draft.front_job_id, db)
        back = _resolve_job_bytes(storage, draft.back_job_id, db)
        if front is None and back is None:
            raise ValidationAppError("Professional AI requires an authenticated Magic look image")
        provider = _PROVIDER_OVERRIDE or default_provider()
        if _PROVIDER_OVERRIDE is None and not (get_settings().openai_api_key or "").strip():
            raise ForbiddenError("OpenAI API key missing for professional AI")

        def _on_progress(progress: dict[str, Any]) -> None:
            try:
                cost = progress.get("cost_usd_cents")
                in_flight = progress.get("provider_in_flight")
                clear = bool(progress.get("clear_in_flight"))
                clean = {
                    k: v
                    for k, v in progress.items()
                    if k not in ("cost_usd_cents", "provider_in_flight", "clear_in_flight")
                }
                _set_run_progress(
                    db,
                    run,
                    clean,
                    cost_usd_cents=int(cost) if cost is not None else None,
                    provider_in_flight=in_flight if isinstance(in_flight, dict) else None,
                    clear_in_flight=clear,
                )
            except Exception:  # noqa: BLE001
                db.rollback()

        pipeline = run_professional_pipeline(
            provider=provider,
            pieces=pieces or [{"id": "piece-1", "category": "other", "label": "Garment"}],
            front_image=front,
            back_image=back,
            look_notes=str(spec.get("look_notes") or ""),
            propose_back=bool(propose_back),
            max_images=int(get_settings().techpack_ai_max_images_per_run or 6),
            on_progress=_on_progress,
        )
        usage_cost = int((pipeline.get("usage") or {}).get("cost_usd_cents") or 0)
        _set_run_progress(
            db,
            run,
            {
                "phase": "assembling",
                "message": "Assembling your PDF",
                "pieces_done": max(1, len(pieces)),
                "pieces_total": max(1, len(pieces)),
            },
            cost_usd_cents=usage_cost,
            clear_in_flight=True,
        )
        pipeline["usage"]["estimated_cost_usd_cents"] = estimate
        enriched, artifacts = _persist_professional_result(
            db, user=user, draft=draft, run=run, pipeline=pipeline, base_spec=spec
        )
        cost = int((pipeline.get("usage") or {}).get("cost_usd_cents") or usage_cost or 0)
        model = (pipeline.get("usage") or {}).get("image_model") or (
            pipeline.get("usage") or {}
        ).get("vision_model")
        analysis_summary = pipeline.get("analysis_summary")
        failed_sections = list(pipeline.get("failed_sections") or [])

        # Persist illustrations first so PDF assembly (and recovery) can use them.
        ai_block = enriched.get("ai") if isinstance(enriched.get("ai"), dict) else {}
        ai_block = {
            **ai_block,
            "dirty_since_generation": False,
            "budget_recorded_usd_cents": max(int(run.cost_usd_cents or 0), cost),
        }
        enriched["ai"] = ai_block
        draft.spec = enriched
        draft.status = "DRAFT"
        draft.verification = "UNVERIFIED"
        draft.updated_at = datetime.now(UTC)
        run.model = model
        run.cost_usd_cents = max(int(run.cost_usd_cents or 0), cost)
        assembling = {
            "phase": "assembling",
            "message": "Preparing your PDF…",
            "pieces_done": max(1, len(pieces)),
            "pieces_total": max(1, len(pieces)),
        }
        req2 = dict(run.request) if isinstance(run.request, dict) else {}
        req2["progress"] = assembling
        req2.pop("provider_in_flight", None)
        run.request = req2
        run.result = {
            "piece_count": enriched.get("outfit", {}).get("piece_count"),
            "warnings": enriched.get("warnings") or [],
            "mode": mode,
            "analysis_summary": analysis_summary,
            "failed_sections": failed_sections,
            "estimated_cost_usd_cents": estimate,
            "actual_cost_usd_cents": run.cost_usd_cents,
            "budget_recorded_usd_cents": run.cost_usd_cents,
            "artifact_ids": [a["id"] for a in artifacts],
            "progress": assembling,
            "sections": sections,
            "pdf_ready": False,
            "draft_revision": int(draft.revision or 1),
        }
        run.input_hash = hashlib.sha256(
            json.dumps({"mode": mode, "propose_back": propose_back}, sort_keys=True).encode()
        ).hexdigest()[:64]
        run.error_message = None
        # Not completed/ready until Professional PDF is assembled and bound to this run.
        run.status = "running"
        db.add(draft)
        db.add(run)
        db.commit()
        db.refresh(run)
        db.refresh(draft)

        from app.services import techpack_service

        try:
            exported = techpack_service.export_pdf(
                db,
                user,
                draft.id,
                ai_run_id=run.id,
                require_professional=True,
            )
        except Exception as pdf_exc:  # noqa: BLE001
            # Illustrations are preserved; do not claim Ready without a PDF.
            run_row = db.get(TechpackAIRun, run_id)
            if run_row is not None:
                req_fail = dict(run_row.request) if isinstance(run_row.request, dict) else {}
                req_fail["progress"] = {
                    "phase": "assembling",
                    "message": "Could not finish PDF — illustrations are saved",
                }
                run_row.request = req_fail
                run_row.status = "reconciliation_required"
                run_row.error_message = f"PDF assembly failed: {type(pdf_exc).__name__}"[:1000]
                result_fail = dict(run_row.result) if isinstance(run_row.result, dict) else {}
                result_fail["pdf_ready"] = False
                result_fail["pdf_error"] = str(pdf_exc)[:400]
                run_row.result = result_fail
                db.add(run_row)
                db.commit()
            raise ValidationAppError(
                "AI illustrations were saved, but the Professional PDF could not be assembled. "
                "Your design is safe — reopen Create Real Design to recover without a new paid run."
            ) from pdf_exc

        run = db.get(TechpackAIRun, run_id)
        draft = _owned_draft(db, user, draft.id)
        assert run is not None
        ready_progress = {
            "phase": "ready",
            "message": "Your AI Technical Pack is ready",
            "pieces_done": max(1, len(pieces)),
            "pieces_total": max(1, len(pieces)),
        }
        req3 = dict(run.request) if isinstance(run.request, dict) else {}
        req3["progress"] = ready_progress
        run.request = req3
        result_ok = dict(run.result) if isinstance(run.result, dict) else {}
        result_ok.update(
            {
                "export_id": str(exported.id),
                "pdf_ready": True,
                "pdf_filename": exported.filename,
                "download_path": f"/api/v1/techpacks/exports/{exported.id}/pdf",
                "draft_revision": int(draft.revision or 1),
                "progress": ready_progress,
            }
        )
        run.result = result_ok
        run.status = "completed"
        spec_final = draft.spec if isinstance(draft.spec, dict) else {}
        ai_final = dict(spec_final.get("ai") if isinstance(spec_final.get("ai"), dict) else {})
        ai_final["export_id"] = str(exported.id)
        ai_final["dirty_since_generation"] = False
        ai_final["last_run_id"] = str(run.id)
        ai_final["last_mode"] = "professional"
        spec_final["ai"] = ai_final
        draft.spec = spec_final
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(draft, "spec")
        db.add(draft)
        db.add(run)
        db.commit()
        db.refresh(run)
        return _run_status_payload(db, run)
    except (ForbiddenError, ValidationAppError, NotFoundError) as exc:
        db.rollback()
        _fail_run_preserve_cost(db, run_id, error=str(exc), provider_called=False)
        raise
    except SketchConfigError as exc:
        db.rollback()
        _fail_run_preserve_cost(
            db, run_id, error=str(exc), provider_called=False, force_zero_if_no_usage=True
        )
        raise ValidationAppError(
            "AI Professional could not start because of a server configuration problem. "
            "Your design is safe. Please try again after the issue is fixed."
        ) from exc
    except Exception as exc:
        db.rollback()
        run_row = db.get(TechpackAIRun, run_id)
        req_now = run_row.request if run_row and isinstance(run_row.request, dict) else {}
        if isinstance(req_now.get("provider_in_flight"), dict) and req_now["provider_in_flight"]:
            if run_row is not None:
                run_row.status = "reconciliation_required"
                run_row.error_message = (
                    f"Uncertain provider outcome: {type(exc).__name__}. Do not auto-retry."
                )[:1000]
                db.add(run_row)
                db.commit()
            raise ValidationAppError(
                "AI Professional may have partially completed. Your design is safe. "
                "Recover existing illustrations before starting a new paid run."
            ) from exc
        _fail_run_preserve_cost(db, run_id, error=str(exc), provider_called=True)
        raise ValidationAppError(
            "AI Professional generation failed. Your design is safe. "
            "If illustrations already appear, preview/download without regenerating."
        ) from exc


def latest_run_for_draft(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Resume helper — return newest run for this draft (running/completed/failed)."""
    draft = _owned_draft(db, user, draft_id)
    row = db.scalars(
        select(TechpackAIRun)
        .where(TechpackAIRun.user_id == user.id, TechpackAIRun.draft_id == draft.id)
        .order_by(TechpackAIRun.created_at.desc())
    ).first()
    if row is None:
        return None
    return get_run(db, user, row.id)


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
    authorization: str | None = None,
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
    if existing and existing.status == "running":
        # Unknown network outcome — do not start a second paid attempt for the same intent.
        return {
            "run_id": str(existing.id),
            "status": "running",
            "cost_usd_cents": existing.cost_usd_cents or 0,
            "actual_cost_usd_cents": existing.cost_usd_cents or 0,
            "mode": existing.stage,
            "idempotent_replay": True,
            "message": "Generation already in progress for this request. Wait or reopen the draft.",
        }
    if existing and existing.status == "failed" and int(existing.cost_usd_cents or 0) > 0:
        # Partial paid failure recorded — do not silently re-bill under the same key.
        arts = list(
            db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == existing.id)).all()
        )
        return {
            "run_id": str(existing.id),
            "status": "failed",
            "cost_usd_cents": existing.cost_usd_cents,
            "actual_cost_usd_cents": existing.cost_usd_cents,
            "mode": existing.stage,
            "error_message": existing.error_message,
            "artifacts": [_artifact_read(a) for a in arts],
            "failed_sections": (existing.result or {}).get("failed_sections") or [],
            "idempotent_replay": True,
            "safe_retry": False,
            "message": "Previous attempt recorded usage. Start a new confirmed generation to continue.",
        }

    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    from app.services.techpack_autofill import (
        extract_job_evidence,
        outfit_needs_structure_repair,
        repair_outfit_from_evidence,
        apply_persisted_analyses_to_spec,
    )

    look_summary = str(spec.get("look_notes") or "")
    design_identity = (
        spec.get("look_design_identity")
        if isinstance(spec.get("look_design_identity"), dict)
        else None
    )
    # Prefer already-persisted Magic job evidence (no paid calls).
    if design_identity is None or not look_summary:
        from app.models.ai_job import AIJob

        for jid in (draft.front_job_id, draft.back_job_id):
            if jid is None:
                continue
            job = db.get(AIJob, jid)
            if job is None or not isinstance(job.result_data, dict):
                continue
            evidence = extract_job_evidence(job.result_data)
            if not look_summary and evidence.get("summary"):
                look_summary = str(evidence["summary"])
                if not spec.get("look_notes"):
                    spec["look_notes"] = look_summary[:500]
            if design_identity is None and evidence.get("design_identity"):
                design_identity = evidence["design_identity"]
                spec["look_design_identity"] = {
                    k: design_identity.get(k)
                    for k in design_identity
                    if design_identity.get(k) is not None
                }
            if look_summary and design_identity is not None:
                break

    if outfit_needs_structure_repair(
        spec.get("outfit") if isinstance(spec.get("outfit"), dict) else None,
        look_summary=look_summary,
        design_identity=design_identity,
    ):
        spec = repair_outfit_from_evidence(
            spec,
            look_summary=look_summary,
            design_identity=design_identity,
            units=str(spec.get("units") or "cm"),
        )
    elif mode in ("analyze", "ai", "heuristic", "professional") and (
        not (spec.get("outfit") or {}).get("pieces") or (sections and "detect" in sections)
    ):
        detection = detect_pieces_from_evidence(
            look_summary=look_summary,
            design_identity=design_identity,
            units=str(spec.get("units") or "cm"),
        )
        if not sections or "detect" in (sections or []):
            if all(
                str(p.get("detection_source") or "").startswith("heuristic")
                for p in (spec.get("outfit") or {}).get("pieces") or []
            ):
                spec["outfit"] = detection

    # Reuse persisted vision analysis onto empty qualitative fields (zero paid).
    spec = apply_persisted_analyses_to_spec(spec)

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
        request={
            "mode": mode,
            "sections": sections or ["all"],
            "propose_back": propose_back,
            "authorization": authorization or "confirm_token",
            "progress": {
                "phase": "preparing",
                "message": "Preparing your design",
                "pieces_done": 0,
                "pieces_total": max(1, len(pieces)),
            },
        },
    )
    if existing is None:
        db.add(run)
        db.commit()
        db.refresh(run)

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

            def _on_progress(progress: dict[str, Any]) -> None:
                try:
                    _set_run_progress(db, run, progress)
                except Exception:  # noqa: BLE001
                    db.rollback()

            pipeline = run_professional_pipeline(
                provider=provider,
                pieces=pieces or [{"id": "piece-1", "category": "other", "label": "Garment"}],
                front_image=front,
                back_image=back,
                look_notes=str(spec.get("look_notes") or ""),
                propose_back=bool(propose_back),
                max_images=int(get_settings().techpack_ai_max_images_per_run or 6),
                on_progress=_on_progress,
            )
            _set_run_progress(
                db,
                run,
                {
                    "phase": "assembling",
                    "message": "Assembling your PDF",
                    "pieces_done": max(1, len(pieces)),
                    "pieces_total": max(1, len(pieces)),
                },
            )
            pipeline["usage"]["estimated_cost_usd_cents"] = estimate
            enriched, artifacts = _persist_professional_result(
                db, user=user, draft=draft, run=run, pipeline=pipeline, base_spec=spec
            )
            # Record provider-reported actual usage; do not clamp incurred cost downward.
            cost = int((pipeline.get("usage") or {}).get("cost_usd_cents") or 0)
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
        ready_progress = {
            "phase": "ready",
            "message": "Your AI Technical Pack is ready",
            "pieces_done": max(1, len(pieces)),
            "pieces_total": max(1, len(pieces)),
        }
        req = dict(run.request) if isinstance(run.request, dict) else {}
        req["progress"] = ready_progress
        run.request = req
        run.result = {
            "piece_count": enriched.get("outfit", {}).get("piece_count"),
            "warnings": enriched.get("warnings") or [],
            "mode": mode,
            "analysis_summary": analysis_summary,
            "failed_sections": failed_sections,
            "estimated_cost_usd_cents": estimate,
            "actual_cost_usd_cents": cost,
            "artifact_ids": [a["id"] for a in artifacts],
            "progress": ready_progress,
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
    except SketchConfigError as exc:
        db.rollback()
        if getattr(run, "id", None):
            _fail_run_preserve_cost(
                db,
                run.id,
                error=str(exc),
                provider_called=False,
                force_zero_if_no_usage=True,
            )
        raise ValidationAppError(
            "AI Professional could not start because of a server configuration problem. "
            "Your design is safe. Please try again after the issue is fixed."
        ) from exc
    except Exception as exc:
        db.rollback()
        if getattr(run, "id", None):
            _fail_run_preserve_cost(
                db, run.id, error=str(exc), provider_called=True
            )
        raise ValidationAppError(
            "AI Professional generation failed. Your design is safe. "
            "If illustrations already appear, preview/download without regenerating."
        ) from exc


def get_run(db: Session, user: User, run_id: uuid.UUID) -> dict[str, Any]:
    row = db.get(TechpackAIRun, run_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("AI run not found")
    # Zero-cost recovery: completed illustration runs missing a bound PDF get one assembled.
    if row.stage == "professional" and row.status in ("completed", "reconciliation_required"):
        result = row.result if isinstance(row.result, dict) else {}
        arts = list(
            db.scalars(select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == row.id)).all()
        )
        if arts and (not result.get("pdf_ready") or not result.get("export_id")):
            try:
                row = ensure_professional_pdf_for_run(db, user, row)
            except Exception:  # noqa: BLE001
                db.rollback()
                row = db.get(TechpackAIRun, run_id) or row
    payload = _run_status_payload(db, row)
    payload["created_at"] = row.created_at.isoformat() if row.created_at else None
    payload["model"] = row.model
    return payload


def resolve_artifact_image(db: Session, user: User, artifact_id: uuid.UUID) -> tuple[Path, TechpackAIArtifact]:
    row = db.get(TechpackAIArtifact, artifact_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("Techpack artifact not found")
    storage = LocalStorageBackend()
    path = storage.resolve_private_techpack_file(key=row.storage_key)
    if path is None:
        raise NotFoundError("Techpack artifact file missing")
    return path, row
