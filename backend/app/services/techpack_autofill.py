"""Zero-cost AI/Magic auto-fill for Create Real Design specs.

Uses Magic look evidence + already-persisted Professional vision analysis.
Never calls OpenAI. Never fabricates precise body/garment measurements,
fabric composition percentages, or production cutting patterns.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_garments import (
    CATEGORIES,
    ROLE_BY_CATEGORY,
    empty_finished_measurements,
)

ANALYSIS_SNAPSHOT_VERSION = "garment_analysis_v1"
_LOCKED_SOURCES = frozenset({"designer", "look"})


def extract_job_evidence(result_data: dict[str, Any] | None) -> dict[str, Any]:
    """Pull summary + design_identity from a completed Magic AIJob.result_data."""
    result = result_data if isinstance(result_data, dict) else {}
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        for key in ("caption", "description", "look_summary"):
            alt = result.get(key)
            if isinstance(alt, str) and alt.strip():
                summary = alt.strip()
                break
        else:
            summary = None
    identity = result.get("design_identity")
    if not isinstance(identity, dict):
        for nest_key in ("structured", "vision", "analysis"):
            nest = result.get(nest_key)
            if isinstance(nest, dict) and isinstance(nest.get("design_identity"), dict):
                identity = nest["design_identity"]
                break
        else:
            identity = None
    return {
        "summary": summary.strip()[:500] if isinstance(summary, str) else None,
        "design_identity": identity if isinstance(identity, dict) else None,
    }


def normalize_category(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    c = raw.strip().lower().replace(" ", "_")
    aliases = {
        "pants": "trousers",
        "pant": "trousers",
        "jeans": "trousers",
        "blouse": "shirt",
        "tee": "top",
        "t-shirt": "top",
        "tshirt": "top",
        "coat": "jacket",
        "gown": "dress",
    }
    c = aliases.get(c, c)
    return c if c in CATEGORIES else None


def apply_visible_analysis_to_piece(
    piece: dict[str, Any],
    analysis: dict[str, Any] | None,
    *,
    only_empty: bool = True,
) -> dict[str, Any]:
    """Map vision analysis onto piece qualitative fields. Never invents cm values."""
    out = deepcopy(piece) if piece else {}
    analysis = analysis if isinstance(analysis, dict) else {}
    if not analysis:
        return out

    detected = normalize_category(analysis.get("category"))
    current = str(out.get("category") or "other")
    det_src = str(out.get("detection_source") or "")
    user_confirmed_cat = bool(out.get("category_user_confirmed"))
    if (
        detected
        and detected != current
        and not user_confirmed_cat
        and det_src.startswith("heuristic")
    ):
        out["category"] = detected
        out["role"] = ROLE_BY_CATEGORY.get(detected, "other")
        out["detection_source"] = "ai_vision"
        # Category swap must not wipe nonempty POM cells (designer or otherwise).
        prior_raw = out.get("finished_measurements")
        prior_finished: dict[str, Any] = prior_raw if isinstance(prior_raw, dict) else {}
        next_finished = empty_finished_measurements(
            detected, str(out.get("units") or "cm")
        )
        for key, cell in prior_finished.items():
            if isinstance(cell, dict) and cell.get("value") not in (None, ""):
                next_finished[key] = dict(cell)
        out["finished_measurements"] = next_finished
        out["category_provenance"] = "ai_inferred"
    elif detected and detected != current and user_confirmed_cat:
        conflicts = list(out.get("ai_conflicts") or []) if isinstance(out.get("ai_conflicts"), list) else []
        conflicts.append(
            {
                "field": "category",
                "user_value": current,
                "ai_value": detected,
                "message": "AI garment category differs from your confirmed category.",
            }
        )
        out["ai_conflicts"] = conflicts

    fit = out.get("fit") if isinstance(out.get("fit"), dict) else {}
    if analysis.get("silhouette") and not (only_empty and fit.get("silhouette")):
        fit["silhouette"] = str(analysis["silhouette"])[:80]
        fit["silhouette_provenance"] = "visually_supported"
        fit["source"] = "ai"
    if analysis.get("fit") and not (only_empty and fit.get("suggestion")):
        fit["suggestion"] = str(analysis["fit"])[:80]
        fit["suggestion_provenance"] = "ai_inferred"
    if analysis.get("length") and not (only_empty and fit.get("length_style")):
        fit["length_style"] = str(analysis["length"])[:80]
        fit["length_style_provenance"] = "visually_supported"
    out["fit"] = fit

    mats = out.get("materials") if isinstance(out.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    if analysis.get("fabric_pattern") and not (only_empty and shell.get("name")):
        shell["name"] = str(analysis["fabric_pattern"])[:120]
        shell["source"] = "ai"
        shell["provenance"] = "visually_supported"
        shell["composition"] = shell.get("composition") or "Unknown"
        shell["composition_note"] = (
            "Fabric composition not verified from image — leave Unknown unless designer confirms."
        )
    mats["shell"] = shell
    out["materials"] = mats

    if analysis.get("colors") and isinstance(analysis["colors"], list):
        colors = [str(c)[:40] for c in analysis["colors"] if c][:6]
        if colors and not (only_empty and out.get("color_hint")):
            out["color_hint"] = ", ".join(colors)[:80]
            out["color_hint_provenance"] = "visually_supported"

    closures = out.get("closures") if isinstance(out.get("closures"), dict) else {}
    if analysis.get("closure_visible") and not (only_empty and closures.get("type")):
        closures["type"] = str(analysis["closure_visible"])[:80]
        closures["source"] = "ai"
        closures["provenance"] = "ai_inferred"
        closures["notes"] = "Visible closure inference — confirm before production."
    out["closures"] = closures

    visible = out.get("visible_details") if isinstance(out.get("visible_details"), dict) else {}
    for key, prov in (
        ("neckline", "visually_supported"),
        ("sleeves", "visually_supported"),
        ("stripe_direction", "visually_supported"),
    ):
        if analysis.get(key) and not (only_empty and visible.get(key)):
            visible[key] = str(analysis[key])[:120]
            visible[f"{key}_provenance"] = prov
    if analysis.get("distinctive_features") and isinstance(analysis["distinctive_features"], list):
        feats = [str(f)[:120] for f in analysis["distinctive_features"] if f][:8]
        if feats and not (only_empty and visible.get("features")):
            visible["features"] = feats
            visible["features_provenance"] = "visually_supported"
    if analysis.get("panels_seams") and not (only_empty and visible.get("panels_seams")):
        visible["panels_seams"] = str(analysis["panels_seams"])[:200]
        visible["panels_seams_provenance"] = "ai_inferred"
    out["visible_details"] = visible

    finished = out.get("finished_measurements") if isinstance(out.get("finished_measurements"), dict) else {}
    cat = str(out.get("category") or "other")
    if not finished:
        out["finished_measurements"] = empty_finished_measurements(cat, "cm")
    else:
        sleeves = str(analysis.get("sleeves") or "").lower()
        sl = finished.get("sleeve_length") if isinstance(finished.get("sleeve_length"), dict) else None
        if isinstance(sl, dict) and sl.get("source") not in _LOCKED_SOURCES:
            if "sleeveless" in sleeves or "spaghetti" in sleeves:
                finished["sleeve_length"] = {
                    **sl,
                    "value": None,
                    "source": "unknown",
                    "note": "Sleeveless / strap — no sleeve length",
                    "provenance": "visually_supported",
                }
            elif "three-quarter" in sleeves or "3/4" in sleeves or "three quarter" in sleeves:
                finished["sleeve_length"] = {
                    **sl,
                    "value": None,
                    "source": "unknown",
                    "note": "Three-quarter sleeve visible — enter length when known",
                    "provenance": "visually_supported",
                    "review_status": "proposed",
                }
        out["finished_measurements"] = finished

    out["ai_fill"] = {
        "schema_version": ANALYSIS_SNAPSHOT_VERSION,
        "confidence": analysis.get("confidence") or "unknown",
        "assumptions": list(analysis.get("assumptions") or [])[:8],
        "source": "persisted_vision_analysis",
        "paid_call": False,
    }
    return out


def snapshot_garment_analysis(
    *,
    pieces: list[dict[str, Any]],
    piece_analyses: dict[str, dict[str, Any]],
    look_summary: str | None,
    design_identity: dict[str, Any] | None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """One versioned structured analysis used consistently across PDF sections."""
    per_piece = []
    for p in pieces:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "")
        analysis = piece_analyses.get(pid) or {}
        illust = p.get("illustrations") if isinstance(p.get("illustrations"), dict) else {}
        if not analysis and isinstance(illust.get("analysis"), dict):
            analysis = illust["analysis"]
        per_piece.append(
            {
                "piece_id": pid,
                "category": p.get("category"),
                "label": p.get("label"),
                "analysis": analysis,
                "visible_details": p.get("visible_details") or {},
            }
        )
    return {
        "schema_version": ANALYSIS_SNAPSHOT_VERSION,
        "run_id": run_id,
        "look_summary": (look_summary or "")[:500],
        "design_identity": design_identity or {},
        "pieces": per_piece,
        "disclaimer": (
            "DRAFT / UNVERIFIED. Visually supported and AI-inferred fields are illustrative. "
            "Unknown measurements stay empty. Not production-ready cutting patterns."
        ),
    }


def outfit_needs_structure_repair(
    outfit: dict[str, Any] | None,
    *,
    look_summary: str | None,
    design_identity: dict[str, Any] | None,
) -> bool:
    """True when heuristic outfit disagrees with Magic look evidence (e.g. one dress vs separates)."""
    if not isinstance(outfit, dict):
        return True
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]
    if not pieces:
        return True
    for p in pieces:
        if p.get("category_user_confirmed") or str(p.get("detection_source") or "") == "designer":
            return False
        mats = p.get("materials") if isinstance(p.get("materials"), dict) else {}
        shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
        if shell.get("source") == "designer" and shell.get("name"):
            return False
    detection = detect_pieces_from_evidence(
        look_summary=look_summary, design_identity=design_identity, units="cm"
    )
    want = [str(p.get("category")) for p in detection.get("pieces") or [] if isinstance(p, dict)]
    have = [str(p.get("category")) for p in pieces]
    if len(want) != len(have):
        return True
    if sorted(want) != sorted(have):
        if have == ["dress"] and "shirt" in want and "trousers" in want:
            return True
        if len(have) == 1 and len(want) > 1:
            return True
    return False


def repair_outfit_from_evidence(
    spec: dict[str, Any],
    *,
    look_summary: str | None,
    design_identity: dict[str, Any] | None,
    units: str = "cm",
) -> dict[str, Any]:
    """Replace unconfirmed heuristic outfit with evidence-based detection (zero paid AI)."""
    out = deepcopy(spec)
    detection = detect_pieces_from_evidence(
        look_summary=look_summary, design_identity=design_identity, units=units
    )
    identity = design_identity if isinstance(design_identity, dict) else {}
    summary_l = (look_summary or "").lower()
    pieces = []
    for p in detection.get("pieces") or []:
        if not isinstance(p, dict):
            continue
        piece = dict(p)
        cat = str(piece.get("category") or "")
        # Prefer color already detected near the garment keyword.
        if not piece.get("color_hint"):
            if cat == "shirt" and "black" in summary_l:
                piece["color_hint"] = "black"
                piece["color_hint_provenance"] = "visually_supported"
            elif cat == "trousers" and "beige" in summary_l:
                piece["color_hint"] = "beige"
                piece["color_hint_provenance"] = "visually_supported"
            elif identity.get("main_colors"):
                piece["color_hint"] = str(identity["main_colors"])[:80]
                piece["color_hint_provenance"] = "visually_supported"
        if identity.get("silhouette") and cat in ("dress", "jumpsuit", "shirt", "top", "jacket"):
            fit = piece.get("fit") if isinstance(piece.get("fit"), dict) else {}
            if not fit.get("silhouette"):
                fit["silhouette"] = str(identity["silhouette"])[:80]
                fit["silhouette_provenance"] = "ai_inferred"
                fit["source"] = "look"
                piece["fit"] = fit
        visible: dict[str, Any] = dict(piece.get("visible_details") or {}) if isinstance(
            piece.get("visible_details"), dict
        ) else {}
        top_like = cat in ("shirt", "top", "jacket", "dress", "jumpsuit")
        if top_like:
            neck = identity.get("neckline")
            if not neck and ("v-slit" in summary_l or "v slit" in summary_l):
                neck = "V-slit neckline"
            if neck and not visible.get("neckline"):
                visible["neckline"] = str(neck)[:120]
                visible["neckline_provenance"] = "visually_supported"
            sleeve = (
                identity.get("sleeve_style")
                or identity.get("sleeves")
                or identity.get("sleeve_type")
            )
            if identity.get("sleeve_length") and not sleeve:
                sleeve = str(identity.get("sleeve_length"))
            if not sleeve and (
                "three-quarter" in summary_l or "3/4" in summary_l or "three quarter" in summary_l
            ):
                sleeve = "three-quarter sleeves"
            if sleeve and not visible.get("sleeves"):
                visible["sleeves"] = str(sleeve)[:120]
                visible["sleeves_provenance"] = "visually_supported"
        if visible:
            piece["visible_details"] = visible
        pieces.append(piece)
    detection["pieces"] = pieces
    detection["piece_count"] = len(pieces)
    detection["autofill"] = {
        "applied": True,
        "paid_call": False,
        "source": "magic_look_evidence",
        "note": "Outfit structure inferred from Magic look evidence — optional corrections in Edit measurements & details.",
    }
    out["outfit"] = detection
    if look_summary:
        prior_notes = str(out.get("look_notes") or "")
        # Replace empty or stale single-dress notes when evidence describes separates.
        if (not prior_notes.strip()) or (
            "dress" in prior_notes.lower()
            and ("shirt" in look_summary.lower() or "trouser" in look_summary.lower())
        ):
            out["look_notes"] = look_summary[:500]
    ai = out.get("ai") if isinstance(out.get("ai"), dict) else {}
    ai["autofill_structure"] = "magic_look_evidence"
    out["ai"] = ai
    return out


def apply_persisted_analyses_to_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Apply each piece's stored illustrations.analysis onto empty qualitative fields."""
    out = deepcopy(spec)
    outfit = out.get("outfit") if isinstance(out.get("outfit"), dict) else {}
    pieces = []
    analyses: dict[str, dict[str, Any]] = {}
    for p in outfit.get("pieces") or []:
        if not isinstance(p, dict):
            continue
        illust = p.get("illustrations") if isinstance(p.get("illustrations"), dict) else {}
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        filled = apply_visible_analysis_to_piece(p, analysis, only_empty=True)
        pieces.append(filled)
        if analysis:
            analyses[str(filled.get("id"))] = analysis
    outfit["pieces"] = pieces
    outfit["piece_count"] = len(pieces)
    out["outfit"] = outfit
    if analyses:
        out["garment_analysis"] = snapshot_garment_analysis(
            pieces=pieces,
            piece_analyses=analyses,
            look_summary=str(out.get("look_notes") or ""),
            design_identity=None,
            run_id=str((out.get("ai") or {}).get("last_run_id") or "") or None,
        )
    return out
