"""Manufacturing-ready Sample-Development Tech Pack gates (offline, $0).

Separates body vs finished-garment specs, flags contradictory designer POMs for
review (never silent overwrite), computes readiness levels, normalizes materials
presentation, and rejects cross-garment detail artwork from corrected previews.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Readiness levels (explicit; AI completion alone never grants SAMPLE READY)
# ---------------------------------------------------------------------------

READINESS_DESIGN_CONCEPT = "DESIGN_CONCEPT"
READINESS_SAMPLE_DEVELOPMENT = "SAMPLE_DEVELOPMENT_READY"
READINESS_PRODUCTION_APPROVED = "PRODUCTION_APPROVED"  # reserved; never auto-granted

READINESS_LABELS = {
    READINESS_DESIGN_CONCEPT: "DESIGN CONCEPT / DRAFT",
    READINESS_SAMPLE_DEVELOPMENT: "SAMPLE-DEVELOPMENT READY",
    READINESS_PRODUCTION_APPROVED: "PRODUCTION APPROVED",
}

# Measurement method definitions (shown in PDF / review UI).
POM_DEFINITIONS: dict[str, dict[str, str]] = {
    "chest_bust": {
        "label": "Chest / bust",
        "method": "Full circumference at fullest bust/chest, parallel to floor.",
        "measure_type": "circumference",
    },
    "shoulder_width": {
        "label": "Shoulder width",
        "method": "Point-to-point across back shoulder seams (not circumference).",
        "measure_type": "flat_width",
    },
    "garment_length": {
        "label": "Garment length (HPS to hem)",
        "method": "High point of shoulder (HPS) straight down to hem.",
        "measure_type": "length",
    },
    "sleeve_length": {
        "label": "Sleeve length",
        "method": "Shoulder seam to cuff edge along sleeve (outer).",
        "measure_type": "length",
    },
    "armhole": {
        "label": "Armhole",
        "method": "Circumference of armhole seam.",
        "measure_type": "circumference",
    },
    "hem": {
        "label": "Hem",
        "method": "Full hem circumference (or stated flat width ×2 if noted).",
        "measure_type": "circumference",
    },
    "neckline": {
        "label": "Neckline / collar",
        "method": "Neck opening circumference or specified collar stand.",
        "measure_type": "circumference",
    },
    "waist": {
        "label": "Waist",
        "method": "Full waist circumference at waistband / natural waist as specified.",
        "measure_type": "circumference",
    },
    "hip": {
        "label": "Hip",
        "method": "Full hip circumference at fullest seat.",
        "measure_type": "circumference",
    },
    "inseam": {
        "label": "Inseam",
        "method": "Crotch seam to hem along inner leg (finished garment).",
        "measure_type": "length",
    },
    "outseam": {
        "label": "Outseam",
        "method": "Waistband top to hem along outer side seam.",
        "measure_type": "length",
    },
    "front_rise": {
        "label": "Front rise",
        "method": "Crotch seam to top of waistband at CF.",
        "measure_type": "length",
    },
    "back_rise": {
        "label": "Back rise",
        "method": "Crotch seam to top of waistband at CB.",
        "measure_type": "length",
    },
    "thigh": {
        "label": "Thigh",
        "method": "Full thigh circumference 2.5 cm below crotch.",
        "measure_type": "circumference",
    },
    "leg_opening": {
        "label": "Leg opening",
        "method": "Full circumference at hem opening.",
        "measure_type": "circumference",
    },
    "waistband": {
        "label": "Waistband height",
        "method": "Finished waistband depth (height), not circumference.",
        "measure_type": "height",
    },
    "cuff": {
        "label": "Cuff opening",
        "method": "Full cuff opening circumference.",
        "measure_type": "circumference",
    },
    "skirt_length": {
        "label": "Skirt length",
        "method": "Waist to hem at CF (or stated side seam).",
        "measure_type": "length",
    },
    "opening": {
        "label": "Opening / slit",
        "method": "Length of opening/slit as specified.",
        "measure_type": "length",
    },
    "knee": {
        "label": "Knee",
        "method": "Full knee circumference at kneecap level.",
        "measure_type": "circumference",
    },
}

# Soft plausibility bands by category (cm). Outside band → NEEDS REVIEW, not discard.
# Exceptions allowed when stretch/elastic/construction notes justify them.
CATEGORY_POM_PLAUSIBLE_CM: dict[str, dict[str, tuple[float, float]]] = {
    "top": {
        "garment_length": (45.0, 85.0),  # hip-length tops typically ~50–75
        "chest_bust": (70.0, 160.0),
        "sleeve_length": (15.0, 75.0),
        "shoulder_width": (30.0, 55.0),
    },
    "shirt": {
        "garment_length": (55.0, 95.0),
        "chest_bust": (70.0, 160.0),
        "sleeve_length": (15.0, 75.0),
    },
    "jacket": {
        "garment_length": (50.0, 100.0),
        "chest_bust": (80.0, 170.0),
    },
    "hoodie": {  # alias treated as top when detected in label/notes
        "garment_length": (50.0, 85.0),
        "chest_bust": (80.0, 170.0),
    },
    "shorts": {
        "inseam": (5.0, 35.0),  # mid-thigh shorts; 80 cm is trouser-length
        "waist": (55.0, 140.0),
        "hip": (70.0, 160.0),
        "front_rise": (15.0, 40.0),
        "back_rise": (20.0, 50.0),
        "leg_opening": (30.0, 80.0),
    },
    "trousers": {
        "inseam": (55.0, 95.0),
        "waist": (55.0, 140.0),
        "hip": (70.0, 160.0),
    },
    "skirt": {"skirt_length": (30.0, 110.0), "waist": (55.0, 140.0)},
    "dress": {"garment_length": (70.0, 160.0), "chest_bust": (70.0, 160.0)},
}

_RELAXED_FIT_TOKENS = ("relax", "oversized", "loose", "easy", "roomy")
_REGULAR_FIT_TOKENS = ("regular", "classic", "standard")
_STRETCH_TOKENS = ("stretch", "elastic", "elastane", "spandex", "knit", "jersey", "rib")
_HOODIE_TOKENS = ("hoodie", "hooded", "sweatshirt", "zip-up", "zippered")
_SHORTS_TOKENS = ("short", "bermuda", "hot pant")
_TOP_TOKENS = ("hoodie", "hooded", "jacket", "coat", "blazer", "shirt", "blouse", "top", "sweater")


def _num(cell: Any) -> float | None:
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    if not isinstance(value, (int, float)):
        return None
    unit = str(cell.get("unit") or "cm").lower()
    cm = float(value) * 2.54 if unit in ("in", "inch", "inches") else float(value)
    return cm


def _text_blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _fit_tokens(piece: dict[str, Any], preferences: dict[str, Any] | None) -> str:
    fit = piece.get("fit") if isinstance(piece.get("fit"), dict) else {}
    prefs = preferences if isinstance(preferences, dict) else {}
    return _text_blob(
        fit.get("suggestion"),
        fit.get("silhouette"),
        fit.get("ease_note"),
        fit.get("length_style"),
        prefs.get("fit_preference"),
        prefs.get("notes"),
    )


def _stretch_evidence(piece: dict[str, Any]) -> bool:
    mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    closures = piece.get("closures") if isinstance(piece.get("closures"), dict) else {}
    blob = _text_blob(
        shell.get("name"),
        shell.get("composition"),
        shell.get("suggestion"),
        shell.get("stretch"),
        shell.get("fabric_structure"),
        closures.get("type"),
        closures.get("notes"),
        (piece.get("fit") or {}).get("ease_note") if isinstance(piece.get("fit"), dict) else "",
    )
    return any(tok in blob for tok in _STRETCH_TOKENS)


def _effective_category(piece: dict[str, Any]) -> str:
    cat = str(piece.get("category") or "other").lower()
    label = _text_blob(piece.get("label"), piece.get("role"))
    if cat == "top" and any(tok in label for tok in _HOODIE_TOKENS):
        return "hoodie"
    return cat


def annotate_pom_definitions(piece: dict[str, Any]) -> dict[str, Any]:
    """Ensure finished POM cells carry measurement method definitions (non-destructive)."""
    out = deepcopy(piece)
    finished = out.get("finished_measurements") if isinstance(out.get("finished_measurements"), dict) else {}
    for key, cell in list(finished.items()):
        if not isinstance(cell, dict):
            continue
        meta = POM_DEFINITIONS.get(key)
        if not meta:
            continue
        if not cell.get("definition"):
            cell["definition"] = f"{meta['label']} — {meta['method']}"
        cell.setdefault("measure_type", meta["measure_type"])
        finished[key] = cell
    out["finished_measurements"] = finished
    return out


def normalize_closure_display(closures: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize boolean-ish closure text like ``True`` into reviewable unknowns."""
    raw = dict(closures) if isinstance(closures, dict) else {}
    ctype = str(raw.get("type") or "").strip()
    if ctype.lower() in ("true", "false", "1", "0", "yes", "no"):
        raw = {
            **raw,
            "type": "",
            "display_type": "Unconfirmed — boolean placeholder removed",
            "review_status": "needs_review",
            "notes": (
                str(raw.get("notes") or "")
                + " Closure was recorded as a boolean; designer must specify zipper/button/elastic."
            ).strip(),
        }
    else:
        raw["display_type"] = ctype or str(raw.get("suggestion") or "") or "—"
    return raw


def normalize_shell_material(piece: dict[str, Any]) -> dict[str, Any]:
    """Separate garment color from shell material; strip outfit color-list fabric names."""
    out = deepcopy(piece)
    mats = out.get("materials") if isinstance(out.get("materials"), dict) else {}
    shell = dict(mats.get("shell") if isinstance(mats.get("shell"), dict) else {})
    name = str(shell.get("name") or "")
    color_hint = str(out.get("color_hint") or "")
    # Detect list-like outfit color dump used as fabric name.
    if re.search(r"\[.*\].*fabric", name, flags=re.I) or (
        "," in name and "fabric" in name.lower() and ("top" in name.lower() or "short" in name.lower())
    ):
        shell["colorway_note"] = name
        shell["name"] = ""
        shell["review_status"] = "needs_review"
        shell["review_message"] = (
            "Shell name looked like an outfit color list, not a fabric. "
            "Enter fiber content / fabric quality separately from garment color."
        )
        if not color_hint:
            # Prefer a short color token from the piece label/category context.
            out["color_hint"] = out.get("label") or color_hint
    shell.setdefault("composition", shell.get("composition") or "")
    shell.setdefault("fabric_structure", shell.get("fabric_structure") or "")  # knit/woven
    shell.setdefault("stretch", shell.get("stretch") or "")
    shell.setdefault("weight_gsm", shell.get("weight_gsm") or shell.get("gsm") or "")
    mats["shell"] = shell
    # Ensure lining / rib / trim buckets exist for PDF separation.
    for key in ("lining", "interfacing", "rib", "trims"):
        if key not in mats or not isinstance(mats.get(key), dict):
            mats[key] = mats.get(key) if isinstance(mats.get(key), dict) else {"name": "", "source": "empty"}
    out["materials"] = mats
    out["closures"] = normalize_closure_display(
        out.get("closures") if isinstance(out.get("closures"), dict) else {}
    )
    return out


def _issue(
    *,
    code: str,
    message: str,
    severity: str = "error",
    piece_id: str | None = None,
    pom: str | None = None,
    blocks_sample_ready: bool = True,
    exception_allowed_if: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        "piece_id": piece_id,
        "pom": pom,
        "blocks_sample_ready": blocks_sample_ready,
        "exception_allowed_if": exception_allowed_if,
        "review_status": "needs_review",
    }


def validate_piece_measurements(
    piece: dict[str, Any],
    *,
    body: dict[str, Any] | None = None,
    preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Flag contradictory / implausible finished POMs without changing values."""
    issues: list[dict[str, Any]] = []
    pid = str(piece.get("id") or "")
    cat = _effective_category(piece)
    finished = piece.get("finished_measurements") if isinstance(piece.get("finished_measurements"), dict) else {}
    body = body if isinstance(body, dict) else {}
    fit_blob = _fit_tokens(piece, preferences)
    stretch_ok = _stretch_evidence(piece)
    bands = CATEGORY_POM_PLAUSIBLE_CM.get(cat) or CATEGORY_POM_PLAUSIBLE_CM.get(
        str(piece.get("category") or ""), {}
    )

    for pom, (lo, hi) in bands.items():
        cell = finished.get(pom)
        cm = _num(cell)
        if cm is None:
            continue
        if cm < lo or cm > hi:
            label = POM_DEFINITIONS.get(pom, {}).get("label", pom)
            issues.append(
                _issue(
                    code="pom_outside_category_band",
                    piece_id=pid,
                    pom=pom,
                    message=(
                        f"{label} = {cm:g} cm is outside the usual {lo:g}–{hi:g} cm band for "
                        f"a {cat}. Designer value preserved — confirm measuring method "
                        f"({POM_DEFINITIONS.get(pom, {}).get('method', 'see POM definition')}) "
                        "or correct the value before sample development."
                    ),
                    exception_allowed_if="Confirmed construction/material/fit exception documented",
                )
            )
            if isinstance(cell, dict):
                cell["review_status"] = "needs_review"

    # Explicit FR-style contradictions from visual length cues.
    length_style = ""
    fit = piece.get("fit") if isinstance(piece.get("fit"), dict) else {}
    length_style = str(fit.get("length_style") or "").lower()
    gl = _num(finished.get("garment_length"))
    if gl is not None and ("hip" in length_style or "upper hip" in length_style) and gl >= 100:
        issues.append(
            _issue(
                code="length_vs_visual_silhouette",
                piece_id=pid,
                pom="garment_length",
                message=(
                    f"HPS-to-hem length = {gl:g} cm but the design notes describe a hip-length "
                    f"{cat}. Confirm whether this is a full-body / dress length or a data entry error."
                ),
            )
        )
    inseam = _num(finished.get("inseam"))
    if (
        inseam is not None
        and cat == "shorts"
        and inseam >= 50
        and any(tok in _text_blob(fit.get("length_style"), fit.get("silhouette")) for tok in ("mid-thigh", "thigh", "above-knee", "near-knee"))
    ):
        issues.append(
            _issue(
                code="shorts_inseam_vs_silhouette",
                piece_id=pid,
                pom="inseam",
                message=(
                    f"Shorts finished inseam = {inseam:g} cm while the silhouette describes "
                    "mid-thigh / above-knee shorts. Confirm measuring method or correct the POM."
                ),
            )
        )

    # Body vs finished ease contradictions (regular/relaxed without stretch).
    body_waist = _num(body.get("waist"))
    fin_waist = _num(finished.get("waist"))
    if body_waist is not None and fin_waist is not None and fin_waist + 0.5 < body_waist:
        if not stretch_ok:
            issues.append(
                _issue(
                    code="finished_waist_smaller_than_body",
                    piece_id=pid,
                    pom="waist",
                    message=(
                        f"Body waist = {body_waist:g} cm but finished waist = {fin_waist:g} cm "
                        "without confirmed stretch/elastic construction. "
                        "Confirm elastic/drawcord/knit stretch or correct measurements."
                    ),
                    exception_allowed_if="Stretch fabric or elastic waist confirmed by designer",
                )
            )

    body_hip = _num(body.get("hip"))
    fin_hip = _num(finished.get("hip"))
    if (
        body_hip is not None
        and fin_hip is not None
        and abs(fin_hip - body_hip) < 0.6
        and any(tok in fit_blob for tok in _RELAXED_FIT_TOKENS + _REGULAR_FIT_TOKENS)
    ):
        issues.append(
            _issue(
                code="zero_ease_hip_with_relaxed_fit",
                piece_id=pid,
                pom="hip",
                message=(
                    f"Body hip = {body_hip:g} cm and finished hip = {fin_hip:g} cm with "
                    "regular/relaxed fit claimed. Finished garment usually needs ease — "
                    "confirm skin-tight intent, stretch fabric, or correct POMs."
                ),
                exception_allowed_if="Zero-ease / stretch fit intentionally confirmed",
            )
        )

    body_bust = _num(body.get("bust"))
    fin_chest = _num(finished.get("chest_bust"))
    if (
        body_bust is not None
        and fin_chest is not None
        and abs(fin_chest - body_bust) < 0.6
        and any(tok in fit_blob for tok in _RELAXED_FIT_TOKENS)
    ):
        issues.append(
            _issue(
                code="zero_ease_chest_with_relaxed_fit",
                piece_id=pid,
                pom="chest_bust",
                message=(
                    f"Body bust = {body_bust:g} cm and finished chest = {fin_chest:g} cm with "
                    "relaxed fit. Confirm intentional zero ease / stretch, or correct values."
                ),
                exception_allowed_if="Zero-ease / stretch fit intentionally confirmed",
            )
        )

    return issues


def validate_sample_size(spec: dict[str, Any]) -> list[dict[str, Any]]:
    sample = str(spec.get("sample_size") or "").strip()
    system = str(spec.get("size_system") or "").strip()
    if not sample:
        return [
            _issue(
                code="sample_size_missing",
                message=(
                    "Named sample size is missing. Sample-development packs require a confirmed "
                    f"sample size (size system currently “{system or 'unspecified'}”)."
                ),
            )
        ]
    return []


def evaluate_artifact_for_piece(
    piece: dict[str, Any],
    *,
    kind: str,
    artifact_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return inclusion decision for an illustration artifact on this piece.

    Preserves provenance; never substitutes another garment's artwork.
    """
    meta = dict(artifact_meta) if isinstance(artifact_meta, dict) else {}
    review = str(meta.get("review_state") or "").lower()
    if review in {"rejected_category_mismatch", "excluded_mismatch", "rejected"}:
        return {
            "include": False,
            "reason": str(meta.get("review_message") or meta.get("notes") or "Marked mismatched — excluded from corrected preview."),
            "review_state": review,
        }

    cat = str(piece.get("category") or "").lower()
    ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis = ill.get("analysis") if isinstance(ill.get("analysis"), dict) else {}
    analysis_cat = str(analysis.get("category") or analysis.get("garment_category") or "").lower()
    blob = _text_blob(
        analysis.get("summary"),
        analysis.get("silhouette"),
        analysis.get("garment_category"),
        analysis.get("category"),
        meta.get("vision_notes"),
        meta.get("notes"),
    )

    # Strong mismatch: shorts/trousers piece but detail/analysis clearly about hoodie/top outerwear.
    if kind == "detail_callouts" and cat in {"shorts", "trousers", "skirt"}:
        if any(tok in blob for tok in _HOODIE_TOKENS) or analysis_cat in {"top", "hoodie", "jacket"}:
            # Only reject when shorts tokens are absent from the analysis blob.
            if not any(tok in blob for tok in _SHORTS_TOKENS) and "trouser" not in blob:
                return {
                    "include": False,
                    "reason": (
                        f"Detail sheet analysis appears to describe a {_TOP_TOKENS[0]}/top garment "
                        f"while this component is “{cat}”. Original file preserved; excluded from "
                        "corrected preview — do not treat as shorts construction detail."
                    ),
                    "review_state": "rejected_category_mismatch",
                }
    if kind == "detail_callouts" and cat in {"top", "shirt", "jacket"}:
        if any(tok in blob for tok in ("inseam", "front rise", "leg opening")) and any(
            tok in blob for tok in _SHORTS_TOKENS
        ):
            return {
                "include": False,
                "reason": "Detail sheet appears to describe bottoms while this component is a top. Excluded from corrected preview.",
                "review_state": "rejected_category_mismatch",
            }

    return {"include": True, "reason": "", "review_state": review or "accepted"}


def apply_artifact_reviews(spec: dict[str, Any]) -> dict[str, Any]:
    """Annotate illustration artifacts with include/exclude decisions (non-destructive copy)."""
    out = deepcopy(spec)
    outfit = out.get("outfit") if isinstance(out.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    for piece in pieces:
        if not isinstance(piece, dict):
            continue
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        for kind, meta in list(arts.items()):
            if not isinstance(meta, dict):
                continue
            decision = evaluate_artifact_for_piece(piece, kind=str(kind), artifact_meta=meta)
            meta = dict(meta)
            meta["preview_include"] = decision["include"]
            if not decision["include"]:
                meta["review_state"] = decision["review_state"]
                meta["review_message"] = decision["reason"]
            arts[str(kind)] = meta
        ill["artifacts"] = arts
        piece["illustrations"] = ill
    outfit["pieces"] = pieces
    out["outfit"] = outfit
    return out


def required_fields_for_category(category: str) -> list[str]:
    cat = category if category in CATEGORY_POM_PLAUSIBLE_CM else category
    base = [
        "sample_size",
        "finished_poms_confirmed",
        "fit_ease_reviewed",
        "material_specified",
        "closures_specified",
        "construction_decisions",
        "pom_tolerances",
        "major_conflicts_resolved",
    ]
    if cat in {"top", "hoodie", "jacket", "shirt"}:
        base.append("chest_and_length_poms")
    if cat in {"shorts", "trousers"}:
        base.append("waist_hip_inseam_poms")
    return base


def assess_manufacturing_readiness(spec: dict[str, Any]) -> dict[str, Any]:
    """Compute readiness level + structured review findings. Never auto PRODUCTION_APPROVED."""
    v2 = deepcopy(spec) if isinstance(spec, dict) else {}
    issues: list[dict[str, Any]] = []
    issues.extend(validate_sample_size(v2))

    body = v2.get("body") if isinstance(v2.get("body"), dict) else {}
    prefs = v2.get("preferences") if isinstance(v2.get("preferences"), dict) else {}
    outfit = v2.get("outfit") if isinstance(v2.get("outfit"), dict) else {}
    pieces = [p for p in (outfit.get("pieces") or []) if isinstance(p, dict)]

    missing_required: list[str] = []
    if not str(v2.get("sample_size") or "").strip():
        missing_required.append("named_sample_size")

    for piece in pieces:
        piece_n = normalize_shell_material(annotate_pom_definitions(piece))
        issues.extend(validate_piece_measurements(piece_n, body=body, preferences=prefs))
        # Material / closure completeness
        mats = piece_n.get("materials") if isinstance(piece_n.get("materials"), dict) else {}
        shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
        if not str(shell.get("name") or "").strip() and not str(shell.get("composition") or "").strip():
            missing_required.append(f"{piece.get('id')}:shell_material")
            issues.append(
                _issue(
                    code="shell_material_missing",
                    piece_id=str(piece.get("id") or ""),
                    message=(
                        f"Shell material for “{piece.get('label') or piece.get('category')}” is not specified "
                        "(color lists are not fabric names)."
                    ),
                )
            )
        if str(shell.get("review_status") or "") == "needs_review":
            issues.append(
                _issue(
                    code="shell_material_needs_review",
                    piece_id=str(piece.get("id") or ""),
                    message=str(shell.get("review_message") or "Shell material needs designer review."),
                )
            )
        closures = piece_n.get("closures") if isinstance(piece_n.get("closures"), dict) else {}
        if str(closures.get("review_status") or "") == "needs_review" or not str(
            closures.get("display_type") or closures.get("type") or ""
        ).strip() or str(closures.get("display_type") or "") == "—":
            missing_required.append(f"{piece.get('id')}:closures")
            issues.append(
                _issue(
                    code="closure_unconfirmed",
                    piece_id=str(piece.get("id") or ""),
                    message=(
                        f"Closure/fastener for “{piece.get('label') or piece.get('category')}” is unconfirmed. "
                        "Do not print boolean placeholders."
                    ),
                )
            )
        # Artifact mismatches
        ill = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        arts = ill.get("artifacts") if isinstance(ill.get("artifacts"), dict) else {}
        for kind, meta in arts.items():
            decision = evaluate_artifact_for_piece(piece, kind=str(kind), artifact_meta=meta if isinstance(meta, dict) else {})
            if not decision["include"]:
                issues.append(
                    _issue(
                        code="artifact_category_mismatch",
                        piece_id=str(piece.get("id") or ""),
                        message=decision["reason"],
                        severity="error",
                    )
                )

        # POM tolerances — required note for sample ready
        tol = piece.get("pom_tolerances") if isinstance(piece.get("pom_tolerances"), dict) else {}
        if not tol:
            missing_required.append(f"{piece.get('id')}:pom_tolerances")

    blocking = [i for i in issues if i.get("blocks_sample_ready")]
    # Designer-confirmed gate: require qc checklist items checked for sample-ready.
    qc = v2.get("qc_checklist") if isinstance(v2.get("qc_checklist"), list) else []
    confirmed = all(isinstance(row, dict) and row.get("checked") for row in qc) if qc else False
    if not confirmed:
        missing_required.append("designer_confirmation_checklist")

    if blocking or missing_required or not confirmed:
        level = READINESS_DESIGN_CONCEPT
    else:
        level = READINESS_SAMPLE_DEVELOPMENT

    # Never auto-elevate to PRODUCTION_APPROVED.
    return {
        "readiness_level": level,
        "readiness_label": READINESS_LABELS[level],
        "issues": issues,
        "blocking_issue_count": len(blocking),
        "missing_required": sorted(set(missing_required)),
        "designer_confirmed": confirmed,
        "production_approved": False,
        "body_vs_finished_separated": True,
        "pattern_status": {
            "sewing_pattern_supplied": False,
            "message": (
                "No production sewing pattern is supplied. NOT-TO-SCALE schematics are planning aids only. "
                "A patternmaker must develop the sample pattern from confirmed POMs and construction."
            ),
        },
    }


def enrich_spec_for_manufacturing_preview(spec: dict[str, Any]) -> dict[str, Any]:
    """Non-destructive enrichment used by corrected PDF preview and offline tests."""
    out = apply_artifact_reviews(deepcopy(spec) if isinstance(spec, dict) else {})
    outfit = out.get("outfit") if isinstance(out.get("outfit"), dict) else {}
    pieces = []
    for piece in outfit.get("pieces") or []:
        if not isinstance(piece, dict):
            continue
        p = normalize_shell_material(annotate_pom_definitions(piece))
        pieces.append(p)
    outfit = dict(outfit)
    outfit["pieces"] = pieces
    out["outfit"] = outfit

    assessment = assess_manufacturing_readiness(out)
    # Merge issues into warnings without dropping prior warnings.
    prior = [w for w in (out.get("warnings") if isinstance(out.get("warnings"), list) else [])]
    merged = list(prior)
    seen = {
        f"{w.get('code')}|{w.get('piece_id')}|{w.get('pom')}|{w.get('message')}"
        for w in prior
        if isinstance(w, dict)
    }
    for issue in assessment["issues"]:
        key = f"{issue.get('code')}|{issue.get('piece_id')}|{issue.get('pom')}|{issue.get('message')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(issue)
    out["warnings"] = merged
    ai = dict(out.get("ai") if isinstance(out.get("ai"), dict) else {})
    ai["manufacturing_readiness"] = {
        "level": assessment["readiness_level"],
        "label": assessment["readiness_label"],
        "blocking_issue_count": assessment["blocking_issue_count"],
        "missing_required": assessment["missing_required"],
        "designer_confirmed": assessment["designer_confirmed"],
        "production_approved": False,
        "pattern_status": assessment["pattern_status"],
    }
    out["ai"] = ai
    return out
