"""Create Real Design V2 AI generation with spend controls.

Paid calls only after explicit confirm_token + enabled flag + positive spend ceiling.
Heuristic generation always available (0 cost) to produce rich technical content.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackDraft
from app.models.user import User
from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_flats import default_bom, default_construction_steps, pattern_inventory_for_category
from app.services.techpack_garments import collect_measurement_warnings, empty_finished_measurements
from app.services.techpack_spec import ensure_v2


def _owned_draft(db: Session, user: User, draft_id: uuid.UUID) -> TechpackDraft:
    draft = db.get(TechpackDraft, draft_id)
    if draft is None or draft.user_id != user.id:
        raise NotFoundError("Techpack draft not found")
    return draft


def ai_status() -> dict[str, Any]:
    settings = get_settings()
    key_present = bool((settings.openai_api_key or "").strip())
    enabled = bool(settings.techpack_ai_enabled or settings.techpack_ai_draft_enabled)
    ceiling = float(settings.techpack_ai_spend_ceiling_usd or 0)
    return {
        "enabled": enabled and key_present and ceiling > 0,
        "configured_flag": enabled,
        "api_key_present": key_present,
        "spend_ceiling_usd": ceiling,
        "max_usd_per_run": float(settings.techpack_ai_max_usd_per_run or 0),
        "max_usd_per_user_day": float(settings.techpack_ai_max_usd_per_user_day or 0),
        "estimate_chat_cents": int(settings.techpack_ai_estimate_chat_cents or 0),
        "requires_entitlement": bool(settings.techpack_ai_requires_entitlement),
        "model": settings.openai_model,
        "note": (
            "Paid AI runs only after explicit confirmation. "
            "Heuristic technical generation (0 cost) always available."
        ),
    }


def create_confirm_challenge(db: Session, user: User, draft_id: uuid.UUID, *, stage: str) -> dict[str, Any]:
    draft = _owned_draft(db, user, draft_id)
    status = ai_status()
    token = secrets.token_urlsafe(18)
    estimate = int(status["estimate_chat_cents"])
    return {
        "draft_id": str(draft.id),
        "stage": stage,
        "confirm_token": token,
        "estimated_cost_usd_cents": estimate if status["enabled"] else 0,
        "ai_enabled": status["enabled"],
        "model": status["model"] if status["enabled"] else None,
        "message": (
            "Confirm to run paid AI technical generation."
            if status["enabled"]
            else "Paid AI is not enabled. You can still generate a heuristic technical pack at $0."
        ),
        "expires_hint_seconds": 600,
    }


def _assert_spend_allowed(db: Session, user: User, *, estimate_cents: int) -> None:
    settings = get_settings()
    status = ai_status()
    if not status["enabled"]:
        raise ForbiddenError("Paid techpack AI is disabled or spend ceiling is not configured")
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
                TechpackAIRun.status == "completed"
            )
        )
        or 0
    )
    if ceiling_cents > 0 and total_spent + estimate_cents > ceiling_cents:
        raise ForbiddenError("Operator techpack AI spend ceiling reached")


def _propose_finished_measurements(piece: dict[str, Any], body: dict[str, Any], fit: str) -> dict[str, Any]:
    """Rule-based first-pass finished POMs. Never invents pixel-derived cm from images."""
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
        # Never overwrite designer-entered values (including implausible ones needing review).
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
    """Fill BOM, construction, pattern inventory, and measurement proposals at $0."""
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
            "flat_front": "schematic",
            "flat_back": "schematic",
            "cutting": "schematic",
            "label": "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE",
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


def _optional_paid_chat_enrich(spec: dict[str, Any]) -> tuple[dict[str, Any], int, str | None]:
    """Optional OpenAI JSON enrich for construction notes. Returns (spec, cost_cents, model)."""
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        return spec, 0, None
    try:
        from openai import OpenAI

        from app.services.sketch_openai import chat_completion_kwargs
    except Exception:  # noqa: BLE001
        return spec, 0, None

    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    summary = {
        "pieces": [
            {"id": p.get("id"), "category": p.get("category"), "label": p.get("label")}
            for p in pieces
            if isinstance(p, dict)
        ],
        "look_notes": spec.get("look_notes"),
        "fit": (spec.get("preferences") or {}).get("fit_preference"),
    }
    client = OpenAI(api_key=key, base_url=settings.openai_base_url or None, timeout=settings.openai_timeout_seconds)
    kwargs = chat_completion_kwargs(
        model=settings.openai_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a fashion technical designer. Return JSON only with key "
                    "`piece_notes`: array of {id, construction_tip, bom_tip}. "
                    "Do not invent exact centimeter measurements from images. "
                    "Keep tips manufacturing-practical and short."
                ),
            },
            {"role": "user", "content": json.dumps(summary)},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=800,
    )
    result = client.chat.completions.create(**kwargs)
    content = (result.choices[0].message.content or "").strip() if result.choices else ""
    try:
        parsed = json.loads(content) if content else {}
    except json.JSONDecodeError:
        parsed = {}
    tips = parsed.get("piece_notes") if isinstance(parsed, dict) else None
    if isinstance(tips, list):
        by_id = {t.get("id"): t for t in tips if isinstance(t, dict)}
        for p in pieces:
            if not isinstance(p, dict):
                continue
            tip = by_id.get(p.get("id")) or {}
            if tip.get("construction_tip"):
                steps = list(p.get("construction_steps") or [])
                steps.append(
                    {
                        "step": len(steps) + 1,
                        "instruction": str(tip["construction_tip"])[:400],
                        "source": "ai",
                    }
                )
                p["construction_steps"] = steps
            if tip.get("bom_tip"):
                bom = list(p.get("bom") or [])
                bom.append(
                    {
                        "item": "AI note",
                        "qty": "—",
                        "unit": "",
                        "source": "ai",
                        "notes": str(tip["bom_tip"])[:300],
                    }
                )
                p["bom"] = bom
        outfit["pieces"] = pieces
        spec["outfit"] = outfit
    # Conservative fixed estimate; actual provider billing may differ.
    cost = int(settings.techpack_ai_estimate_chat_cents or 8)
    return spec, cost, settings.openai_model


def run_generate(
    db: Session,
    user: User,
    draft_id: uuid.UUID,
    *,
    confirm_token: str,
    idempotency_key: str,
    mode: str = "heuristic",
    sections: list[str] | None = None,
) -> dict[str, Any]:
    """Generate technical content. mode=heuristic|ai. AI requires confirm + spend gates."""
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
        return {
            "run_id": str(existing.id),
            "status": existing.status,
            "cost_usd_cents": existing.cost_usd_cents,
            "mode": existing.stage,
            "result": existing.result,
            "idempotent_replay": True,
        }

    spec = ensure_v2(draft.spec if isinstance(draft.spec, dict) else {})
    # Refresh detection if outfit empty / unconfirmed single fallback and user asked analyze.
    if mode in ("analyze", "ai", "heuristic") and (
        not (spec.get("outfit") or {}).get("pieces")
        or (sections and "detect" in sections)
    ):
        detection = detect_pieces_from_evidence(look_summary=str(spec.get("look_notes") or ""), units=str(spec.get("units") or "cm"))
        # Preserve user-edited pieces if already confirmed.
        if not sections or "detect" in (sections or []):
            if all(str(p.get("detection_source") or "").startswith("heuristic") for p in (spec.get("outfit") or {}).get("pieces") or []):
                spec["outfit"] = detection

    paid = mode == "ai"
    estimate = int(get_settings().techpack_ai_estimate_chat_cents or 8) if paid else 0
    if paid:
        _assert_spend_allowed(db, user, estimate_cents=estimate)

    run = existing or TechpackAIRun(
        id=uuid.uuid4(),
        draft_id=draft.id,
        user_id=user.id,
        stage=mode,
        status="running",
        confirm_token=confirm_token,
        idempotency_key=idempotency_key,
        request={"mode": mode, "sections": sections or ["all"]},
    )
    if existing is None:
        db.add(run)
        db.flush()

    try:
        enriched = enrich_spec_heuristic(spec)
        cost = 0
        model = None
        if paid:
            enriched, cost, model = _optional_paid_chat_enrich(enriched)
            paid_sections = list((enriched.get("ai") or {}).get("paid_sections") or [])
            if "construction_tips" not in paid_sections:
                paid_sections.append("construction_tips")
            enriched["ai"] = {
                **(enriched.get("ai") if isinstance(enriched.get("ai"), dict) else {}),
                "last_run_id": str(run.id),
                "last_mode": "ai",
                "paid_sections": paid_sections,
            }
        # Never overwrite a previously successful draft revision on failure — we commit only on success.
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
            "mode": "ai" if paid else "heuristic",
        }
        run.input_hash = hashlib.sha256(json.dumps({"mode": mode}, sort_keys=True).encode()).hexdigest()[:64]
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
            "mode": "ai" if paid else "heuristic",
            "draft_id": str(draft.id),
            "warnings": enriched.get("warnings") or [],
            "idempotent_replay": False,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        # Re-open session state for error row without wiping draft.
        draft = _owned_draft(db, user, draft_id)
        run = db.get(TechpackAIRun, run.id) if run.id else None
        if run is None:
            run = TechpackAIRun(
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
            db.add(run)
        else:
            run.status = "failed"
            run.error_message = str(exc)[:1000]
            db.add(run)
        db.commit()
        raise ValidationAppError(f"Technical generation failed: {exc}") from exc


def get_run(db: Session, user: User, run_id: uuid.UUID) -> dict[str, Any]:
    row = db.get(TechpackAIRun, run_id)
    if row is None or row.user_id != user.id:
        raise NotFoundError("AI run not found")
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
    }
