"""Professional generate structure validation, fingerprinting, and image-budget planning.

Fail closed before paid provider calls. Never invent a synthetic ``piece-1`` garment.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from app.core.errors import ValidationAppError
from app.services.techpack_autofill import (
    extract_job_evidence,
    outfit_needs_structure_repair,
    repair_outfit_from_evidence,
)

REQUIRED_IMAGE_KIND = "flat_front"
# Optional illustration kinds, allocated fairly across garments after required fronts.
OPTIONAL_IMAGE_KIND_PHASES: tuple[str, ...] = (
    "flat_back",  # real back when present
    "flat_back_proposed",  # proposed back when allowed
    "detail_callouts",
    "pattern_sheet",
)


def piece_id(piece: dict[str, Any]) -> str:
    return str(piece.get("id") or "").strip()


def list_outfit_pieces(spec: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        return []
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    return [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]


def designer_structure_locked(pieces: list[dict[str, Any]]) -> bool:
    """True when every piece is explicitly designer-confirmed (do not auto-replace)."""
    if not pieces:
        return False
    for p in pieces:
        if p.get("category_user_confirmed"):
            continue
        if str(p.get("detection_source") or "") == "designer":
            continue
        return False
    return True


def outfit_structure_fingerprint(pieces: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for p in sorted(pieces, key=lambda x: piece_id(x)):
        rows.append(
            "|".join(
                [
                    piece_id(p),
                    str(p.get("category") or ""),
                    str(p.get("role") or ""),
                    str(p.get("label") or ""),
                ]
            )
        )
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()[:40]


def validate_professional_pieces(pieces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Require non-empty unique stable IDs; sync caller piece_count separately."""
    if not pieces:
        raise ValidationAppError(
            "Cannot start AI Professional: this draft has no garment pieces. "
            "Open Measurements & details, confirm the outfit pieces from your Magic look, then try again."
        )
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for p in pieces:
        pid = piece_id(p)
        if not pid:
            raise ValidationAppError(
                "Cannot start AI Professional: a garment is missing a stable piece ID. "
                "Re-open the draft so outfit structure can be repaired, then try again."
            )
        if pid in seen:
            raise ValidationAppError(
                f"Cannot start AI Professional: duplicate garment piece ID “{pid}”. "
                "Fix outfit pieces in Measurements & details before generating."
            )
        seen.add(pid)
        if not str(p.get("category") or "").strip():
            raise ValidationAppError(
                f"Cannot start AI Professional: garment “{p.get('label') or pid}” has no category. "
                "Confirm categories in Measurements & details."
            )
        cleaned.append(p)
    return cleaned


def sync_outfit_piece_count(spec: dict[str, Any], pieces: list[dict[str, Any]]) -> dict[str, Any]:
    out = deepcopy(spec) if isinstance(spec, dict) else {}
    outfit = dict(out.get("outfit") if isinstance(out.get("outfit"), dict) else {})
    outfit["pieces"] = pieces
    outfit["piece_count"] = len(pieces)
    out["outfit"] = outfit
    return out


def load_magic_evidence(db: Any, draft: Any, spec: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Return (look_summary, design_identity) from draft + persisted Magic jobs (no paid AI)."""
    from app.models.ai_job import AIJob

    look_summary = str(spec.get("look_notes") or "")
    design_identity = (
        spec.get("look_design_identity")
        if isinstance(spec.get("look_design_identity"), dict)
        else None
    )
    for jid in (getattr(draft, "front_job_id", None), getattr(draft, "back_job_id", None)):
        if jid is None:
            continue
        job = db.get(AIJob, jid)
        if job is None or not isinstance(job.result_data, dict):
            continue
        evidence = extract_job_evidence(job.result_data)
        if not look_summary and evidence.get("summary"):
            look_summary = str(evidence["summary"])
        if design_identity is None and evidence.get("design_identity"):
            design_identity = evidence["design_identity"]
        if look_summary and design_identity is not None:
            break
    return look_summary, design_identity if isinstance(design_identity, dict) else None


def evidence_piece_categories(
    *,
    look_summary: str | None,
    design_identity: dict[str, Any] | None,
) -> list[str]:
    from app.services.techpack_detect import detect_pieces_from_evidence

    detection = detect_pieces_from_evidence(
        look_summary=look_summary, design_identity=design_identity, units="cm"
    )
    return [
        str(p.get("category") or "")
        for p in (detection.get("pieces") or [])
        if isinstance(p, dict) and p.get("category")
    ]


def prepare_professional_outfit(
    db: Any,
    draft: Any,
    spec: dict[str, Any],
    *,
    persist_repair: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Resolve + validate outfit for Professional generate.

    Returns ``(spec, pieces, meta)`` where meta includes fingerprint and piece_ids.
    Raises ``ValidationAppError`` before any provider work when structure is unsafe.
    """
    working = ensure_spec_dict(spec)
    look_summary, design_identity = load_magic_evidence(db, draft, working)
    if look_summary and not working.get("look_notes"):
        working["look_notes"] = look_summary[:500]
    if design_identity and not isinstance(working.get("look_design_identity"), dict):
        working["look_design_identity"] = {
            k: design_identity.get(k)
            for k in design_identity
            if design_identity.get(k) is not None
        }

    pieces = list_outfit_pieces(working)
    locked = designer_structure_locked(pieces)
    want = evidence_piece_categories(
        look_summary=look_summary or None, design_identity=design_identity
    )
    have = [str(p.get("category") or "") for p in pieces]
    # Designer-confirmed structure that disagrees with credible Magic evidence → block.
    if locked and want and sorted(want) != sorted(have):
        raise ValidationAppError(
            "Cannot start AI Professional: your confirmed garment structure conflicts with "
            f"Magic look evidence (draft: {', '.join(have) or 'none'}; "
            f"look evidence: {', '.join(want)}). "
            "Update Measurements & details to match the look, or keep your confirmed pieces "
            "and clear conflicting look evidence — then generate again."
        )
    needs = outfit_needs_structure_repair(
        working.get("outfit") if isinstance(working.get("outfit"), dict) else None,
        look_summary=look_summary or None,
        design_identity=design_identity,
    )
    repaired = False
    if needs and not locked:
        if want or not pieces:
            working = repair_outfit_from_evidence(
                working,
                look_summary=look_summary or None,
                design_identity=design_identity,
                units=str(working.get("units") or "cm"),
            )
            pieces = list_outfit_pieces(working)
            repaired = True
        elif not pieces:
            raise ValidationAppError(
                "Cannot start AI Professional: outfit structure is empty and Magic evidence "
                "does not describe clear garments. Confirm pieces in Measurements & details first."
            )

    pieces = validate_professional_pieces(pieces)
    working = sync_outfit_piece_count(working, pieces)
    fingerprint = outfit_structure_fingerprint(pieces)
    meta = {
        "structure_fingerprint": fingerprint,
        "piece_ids": [piece_id(p) for p in pieces],
        "piece_count": len(pieces),
        "structure_repaired": repaired,
        "draft_revision": int(getattr(draft, "revision", None) or 1),
        "look_id": str(getattr(draft, "look_id", "") or ""),
    }
    if persist_repair and repaired:
        draft.spec = working
        from datetime import UTC, datetime

        from sqlalchemy.orm.attributes import flag_modified

        draft.updated_at = datetime.now(UTC)
        flag_modified(draft, "spec")
        db.add(draft)
        db.commit()
        db.refresh(draft)
    return working, pieces, meta


def ensure_spec_dict(spec: Any) -> dict[str, Any]:
    from app.services.techpack_spec import ensure_v2

    if isinstance(spec, dict):
        return ensure_v2(spec)
    return ensure_v2({})


def plan_professional_image_kinds(
    pieces: list[dict[str, Any]],
    *,
    propose_back: bool,
    has_back_image: bool,
    max_images: int,
) -> dict[str, Any]:
    """Fair image budget: every garment gets flat_front before optional arts."""
    pieces = validate_professional_pieces(pieces)
    n = len(pieces)
    max_images = int(max_images)
    if max_images < 1:
        raise ValidationAppError(
            "Cannot start AI Professional: image budget is misconfigured (max images < 1)."
        )
    if n > max_images:
        raise ValidationAppError(
            f"Cannot start AI Professional: this outfit has {n} garments but the image budget "
            f"allows only {max_images} illustration(s) per run. Split the look or raise the "
            "configured image budget before generating — no paid call was made."
        )

    per_piece: dict[str, dict[str, list[str]]] = {
        piece_id(p): {"required": [REQUIRED_IMAGE_KIND], "optional": [], "all": [REQUIRED_IMAGE_KIND]}
        for p in pieces
    }
    remaining = max_images - n

    def _offer(kind: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for p in pieces:
            pid = piece_id(p)
            if kind == "flat_back" and has_back_image:
                out.append((pid, "flat_back"))
            elif kind == "flat_back_proposed" and propose_back and not has_back_image:
                out.append((pid, "flat_back_proposed"))
            elif kind in ("detail_callouts", "pattern_sheet"):
                out.append((pid, kind))
        return out

    for phase in OPTIONAL_IMAGE_KIND_PHASES:
        for pid, kind in _offer(phase):
            if remaining <= 0:
                break
            bucket = per_piece[pid]
            if kind in bucket["all"]:
                continue
            bucket["optional"].append(kind)
            bucket["all"].append(kind)
            remaining -= 1
        if remaining <= 0:
            break

    skipped: list[str] = []
    for phase in OPTIONAL_IMAGE_KIND_PHASES:
        for pid, kind in _offer(phase):
            if kind not in per_piece[pid]["all"]:
                skipped.append(f"{pid}:{kind}:budget_optional_skipped")

    return {
        "max_images": max_images,
        "required_images": n,
        "planned_images": sum(len(v["all"]) for v in per_piece.values()),
        "per_piece": per_piece,
        "skipped_optional": skipped,
    }


def assert_pipeline_covers_required(
    *,
    pieces: list[dict[str, Any]],
    pipeline: dict[str, Any],
) -> None:
    """Reject READY labeling when a mandatory garment/front flat is missing."""
    expected = {piece_id(p) for p in pieces}
    results = [pr for pr in (pipeline.get("piece_results") or []) if isinstance(pr, dict)]
    got_ids = [str(pr.get("piece_id") or "") for pr in results]
    got_set = set(got_ids)
    if len(got_ids) != len(got_set):
        raise ValidationAppError(
            "Professional generation produced duplicate piece results. "
            "Illustrations were not bound as READY — recover without auto-retry."
        )
    missing = expected - got_set
    unexpected = got_set - expected
    if missing or unexpected:
        raise ValidationAppError(
            "Professional generation piece IDs do not match the authorized outfit "
            f"(missing={sorted(missing)}, unexpected={sorted(unexpected)}). "
            "Results were not marked READY."
        )
    for pr in results:
        pid = str(pr.get("piece_id") or "")
        kinds = {
            str(a.get("kind"))
            for a in (pr.get("artifacts") or [])
            if isinstance(a, dict) and a.get("bytes")
        }
        if REQUIRED_IMAGE_KIND not in kinds:
            raise ValidationAppError(
                f"Professional generation is incomplete: garment “{pid}” is missing a front "
                "technical flat. Results were not marked READY."
            )


def run_matches_draft_structure(run_request: dict[str, Any] | None, pieces: list[dict[str, Any]]) -> bool:
    req = run_request if isinstance(run_request, dict) else {}
    fp = str(req.get("structure_fingerprint") or "")
    current = outfit_structure_fingerprint(pieces)
    if fp:
        return fp == current
    # Legacy runs: compare authorized piece_ids when present.
    authorized = req.get("piece_ids")
    if isinstance(authorized, list) and authorized:
        return sorted(str(x) for x in authorized) == sorted(piece_id(p) for p in pieces)
    return True


def structure_meta_json(meta: dict[str, Any]) -> str:
    return json.dumps(meta, sort_keys=True, default=str)
