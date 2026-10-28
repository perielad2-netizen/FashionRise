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


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text_blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _fit_tokens(piece: dict[str, Any], preferences: dict[str, Any] | None) -> str:
    fit = _as_dict(piece.get("fit"))
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
    mats = _as_dict(piece.get("materials"))
    shell = _as_dict(mats.get("shell"))
    closures = _as_dict(piece.get("closures"))
    fit = _as_dict(piece.get("fit"))
    blob = _text_blob(
        shell.get("name"),
        shell.get("composition"),
        shell.get("suggestion"),
        shell.get("stretch"),
        shell.get("fabric_structure"),
        closures.get("type"),
        closures.get("notes"),
        fit.get("ease_note"),
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
    finished = _as_dict(out.get("finished_measurements"))
    for key, cell in list(finished.items()):
        if not isinstance(cell, dict):
            continue
        meta = POM_DEFINITIONS.get(key)
        if not meta:
            continue
        updated = dict(cell)
        if not updated.get("definition"):
            updated["definition"] = f"{meta['label']} — {meta['method']}"
        updated.setdefault("measure_type", meta["measure_type"])
        finished[key] = updated
    out["finished_measurements"] = finished
    return out


def _looks_like_outfit_color_list_name(name: str) -> bool:
    """True when a BOM/shell name is an outfit color list, not a fabric quality."""
    text = str(name or "").strip()
    if not text:
        return False
    lower = text.lower()
    # e.g. "['Lavender-purple top', 'Golden-yellow shorts'] shell"
    if re.search(r"\[.*\].*(?:fabric|shell|material)", text, flags=re.IGNORECASE):
        return True
    if re.search(r"^\s*\[.*top.*short", text, flags=re.IGNORECASE):
        return True
    return bool(
        "," in text
        and ("fabric" in lower or "shell" in lower)
        and ("top" in lower or "short" in lower or "hoodie" in lower)
    )


def _looks_like_outfit_color_hint(value: Any) -> bool:
    """True when color_hint is an outfit-level multi-garment list, not one garment color."""
    if isinstance(value, (list, tuple)):
        return len(value) >= 2
    text = str(value or "").strip()
    if not text:
        return False
    if re.search(r"^\s*\[.*(?:top|hoodie|short|trouser).*(?:top|hoodie|short|trouser)", text, flags=re.I):
        return True
    # e.g. "lavender hoodie and yellow shorts" shared across pieces
    lower = text.lower()
    garment_hits = sum(
        1
        for tok in ("top", "hoodie", "short", "trouser", "skirt", "dress", "jacket")
        if tok in lower
    )
    return garment_hits >= 2 and (" and " in lower or "," in text or "[" in text)


def _parse_outfit_color_tokens(value: Any) -> list[str]:
    """Extract garment-tagged color tokens from a list-like outfit color dump."""
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    # Prefer bracketed list contents: ['Lavender-purple top', 'Golden-yellow shorts']
    bracket = re.search(r"\[(.*)\]", text)
    if bracket:
        inner = bracket.group(1)
        parts = re.findall(r"['\"]([^'\"]+)['\"]", inner)
        if parts:
            return [p.strip() for p in parts if p.strip()]
        parts = [p.strip() for p in inner.split(",") if p.strip()]
        if parts:
            return parts
    # Fallback: split on " and " / commas when multiple garment words present.
    if " and " in text.lower():
        return [p.strip() for p in re.split(r"\band\b", text, flags=re.I) if p.strip()]
    return [text]


def _primary_color_from_analysis(colors: list[Any] | None) -> str:
    """Pick a short garment color label from visual/structured analysis colors."""
    if not colors:
        return ""
    first = str(colors[0] or "").strip()
    if not first:
        return ""
    # Prefer the body/main color clause before accessory clauses.
    for sep in (" body", " and hood", ",", ";"):
        if sep in first.lower():
            idx = first.lower().index(sep)
            head = first[:idx].strip(" -/")
            if head:
                return head[:80]
    return first[:80]


def _color_from_outfit_tokens(piece: dict[str, Any], tokens: list[str]) -> str:
    """Match a token like 'Golden-yellow shorts' to this piece's category/role."""
    cat = _effective_category(piece)
    role = str(piece.get("role") or "").lower()
    label = str(piece.get("label") or "").lower()
    aliases = {
        "top": ("top", "hoodie", "sweatshirt", "shirt", "jacket", "blouse"),
        "hoodie": ("hoodie", "sweatshirt", "top", "zip"),
        "shorts": ("short", "bottom", "bermuda"),
        "trousers": ("trouser", "pant", "bottom"),
        "skirt": ("skirt",),
        "dress": ("dress",),
        "jacket": ("jacket", "coat", "blazer"),
        "shirt": ("shirt", "blouse", "top"),
    }
    keys = aliases.get(cat, (cat,))
    for tok in tokens:
        low = tok.lower()
        if any(k in low for k in keys) or (role and role in low) or (label and label in low):
            # Strip trailing garment word(s) to leave the color phrase.
            cleaned = tok
            for g in (
                "hoodie",
                "sweatshirt",
                "shorts",
                "short",
                "trousers",
                "pants",
                "jacket",
                "shirt",
                "blouse",
                "top",
                "bottom",
                "dress",
                "skirt",
            ):
                cleaned = re.sub(rf"\b{g}s?\b", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s+", " ", cleaned).strip(" -/,")
            if cleaned:
                return cleaned[:80]
    return ""


def _color_from_look_notes(piece: dict[str, Any], look_notes: str) -> str:
    """Best-effort garment color from look notes when structured evidence is thin."""
    notes = str(look_notes or "").strip()
    if not notes:
        return ""
    cat = _effective_category(piece)
    patterns: dict[str, tuple[str, ...]] = {
        "top": (r"([A-Za-z][\w\-/]*(?:\s+[\w\-/]+){0,2})\s+(?:zip[-\s]?front\s+)?(?:hoodie|sweatshirt|top|shirt)",),
        "hoodie": (r"([A-Za-z][\w\-/]*(?:\s+[\w\-/]+){0,2})\s+(?:zip[-\s]?front\s+)?(?:hoodie|sweatshirt)",),
        "shorts": (r"([A-Za-z][\w\-/]*(?:\s+[\w\-/]+){0,2})\s+(?:mid-thigh\s+)?shorts",),
        "trousers": (r"([A-Za-z][\w\-/]*(?:\s+[\w\-/]+){0,2})\s+(?:trousers|pants)",),
    }
    for pat in patterns.get(cat, ()):
        m = re.search(pat, notes, flags=re.I)
        if m:
            return m.group(1).strip(" -/,")[:80]
    return ""


def derive_piece_garment_color(
    piece: dict[str, Any],
    *,
    look_notes: str = "",
    garment_analysis_piece: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve raw outfit color input; derive a garment-specific color when evidence supports it.

    Never invents fiber composition. Color is not treated as material.
    """
    out = deepcopy(piece)
    raw_hint = out.get("color_hint")
    raw_as_text = (
        ", ".join(str(x) for x in raw_hint)
        if isinstance(raw_hint, (list, tuple))
        else str(raw_hint or "").strip()
    )
    ill = _as_dict(out.get("illustrations"))
    analysis = _as_dict(ill.get("analysis"))
    ga = _as_dict(garment_analysis_piece)
    ga_analysis = _as_dict(ga.get("analysis")) if ga else {}

    analysis_colors = analysis.get("colors") if isinstance(analysis.get("colors"), list) else None
    if not analysis_colors:
        analysis_colors = ga_analysis.get("colors") if isinstance(ga_analysis.get("colors"), list) else None

    outfit_like = _looks_like_outfit_color_hint(raw_hint) or _looks_like_outfit_color_list_name(raw_as_text)
    derived = ""
    provenance = ""

    if analysis_colors:
        derived = _primary_color_from_analysis(analysis_colors)
        if derived:
            provenance = "visually_supported_analysis"

    if not derived and outfit_like:
        tokens = _parse_outfit_color_tokens(raw_hint if raw_hint is not None else raw_as_text)
        derived = _color_from_outfit_tokens(out, tokens)
        if derived:
            provenance = "derived_from_outfit_color_list"

    if not derived:
        derived = _color_from_look_notes(out, look_notes)
        if derived:
            provenance = "derived_from_look_notes"

    if outfit_like or (raw_as_text and derived and derived.lower() != raw_as_text.lower()):
        # Preserve historical input; do not silently drop the outfit-level dump.
        if raw_as_text and "color_hint_raw" not in out:
            out["color_hint_raw"] = raw_hint if raw_hint is not None else raw_as_text
        if derived:
            out["color_hint"] = derived
            out["color_hint_provenance"] = provenance
            out["color_hint_review_status"] = "derived_needs_review"
        elif outfit_like:
            # No safe garment-specific evidence — clear misleading shared list from display.
            out["color_hint"] = ""
            out["color_hint_provenance"] = "outfit_list_cleared_pending_evidence"
            out["color_hint_review_status"] = "needs_review"
    elif not raw_as_text and derived:
        out["color_hint"] = derived
        out["color_hint_provenance"] = provenance
        out["color_hint_review_status"] = "derived_needs_review"

    return out


def apply_artifact_review_decision(
    spec: dict[str, Any],
    *,
    artifact_id: str,
    review_state: str,
    review_message: str,
    reviewer: dict[str, Any] | None = None,
    decided_at: str | None = None,
) -> dict[str, Any]:
    """Mark one illustration artifact with an auditable review (in-memory, non-destructive).

    Does not delete image bytes. Only mutates matching ``artifact_id`` entries.
    Intended for offline preview / tests — persisted reviews go through the
    authenticated draft-bound service path.
    """
    from datetime import datetime, timezone

    out = deepcopy(spec if isinstance(spec, dict) else {})
    target = str(artifact_id or "").strip().lower()
    if not target:
        return out
    state = str(review_state or "").strip().lower()
    message = str(review_message or "").strip()
    when = decided_at or datetime.now(timezone.utc).isoformat()
    rejected = state in _REJECTED_ART
    confirmed = state in _VISUAL_CONFIRMED
    decision = {
        "reviewer": dict(reviewer) if isinstance(reviewer, dict) else {"role": "offline_preview"},
        "review_state": state,
        "review_message": message,
        "decided_at": when,
        "bytes_preserved": True,
        "substituted": False,
    }
    outfit = _as_dict(out.get("outfit"))
    pieces_out: list[Any] = []
    for piece in _as_list(outfit.get("pieces")):
        if not isinstance(piece, dict):
            pieces_out.append(piece)
            continue
        piece_out = dict(piece)
        ill = _as_dict(piece_out.get("illustrations"))
        arts = _as_dict(ill.get("artifacts"))
        changed = False
        for kind, meta in list(arts.items()):
            if not isinstance(meta, dict):
                continue
            aid = str(meta.get("artifact_id") or meta.get("id") or "").strip().lower()
            if aid != target:
                continue
            meta_out = dict(meta)
            meta_out["review_state"] = state
            meta_out["review_message"] = message
            if rejected:
                meta_out["preview_include"] = False
                meta_out["manufacturing_evidence"] = False
            elif confirmed:
                meta_out["preview_include"] = True
                meta_out["manufacturing_evidence"] = True
            else:
                meta_out["preview_include"] = True
                meta_out["manufacturing_evidence"] = False
            meta_out["operator_decision"] = decision
            if meta.get("review_state") and "prior_review_state" not in meta_out:
                meta_out["prior_review_state"] = meta.get("review_state")
            arts[str(kind)] = meta_out
            changed = True
        if changed:
            ill["artifacts"] = arts
            piece_out["illustrations"] = ill
        pieces_out.append(piece_out)
    outfit["pieces"] = pieces_out
    out["outfit"] = outfit
    ai = _as_dict(out.get("ai"))
    log = list(ai.get("artifact_review_decisions") or [])
    log.append({**decision, "artifact_id": str(artifact_id)})
    ai["artifact_review_decisions"] = log
    out["ai"] = ai
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
    mats = _as_dict(out.get("materials"))
    shell = _as_dict(mats.get("shell"))
    name = str(shell.get("name") or "")
    raw_hint = out.get("color_hint")
    color_hint = (
        ", ".join(str(x) for x in raw_hint)
        if isinstance(raw_hint, (list, tuple))
        else str(raw_hint or "")
    )
    # Detect list-like outfit color dump used as fabric name — never as composition.
    if _looks_like_outfit_color_list_name(name):
        shell["colorway_note"] = name
        shell["name"] = ""
        shell["review_status"] = "needs_review"
        shell["review_message"] = (
            "Shell name looked like an outfit color list, not a fabric. "
            "Enter fiber content / fabric quality separately from garment color."
        )
        # Do not invent composition from color lists.
        if "composition" in shell and _looks_like_outfit_color_list_name(str(shell.get("composition") or "")):
            shell["composition"] = ""
    # Preserve outfit-level color dumps for later derivation; do not print them as this garment's color.
    if _looks_like_outfit_color_hint(raw_hint) or _looks_like_outfit_color_list_name(color_hint):
        if "color_hint_raw" not in out:
            out["color_hint_raw"] = raw_hint if raw_hint is not None else color_hint
        # Placeholder until derive_piece_garment_color runs (enrich / PDF).
        out["color_hint"] = ""
        out["color_hint_review_status"] = "needs_review"
    shell.setdefault("composition", shell.get("composition") or "")
    shell.setdefault("fabric_structure", shell.get("fabric_structure") or "")  # knit/woven
    shell.setdefault("stretch", shell.get("stretch") or "")
    shell.setdefault("weight_gsm", shell.get("weight_gsm") or shell.get("gsm") or "")
    mats["shell"] = shell
    # Ensure lining / rib / trim buckets exist for PDF separation.
    for key in ("lining", "interfacing", "rib", "trims"):
        if not isinstance(mats.get(key), dict):
            mats[key] = {"name": "", "source": "empty"}
    out["materials"] = mats
    out["closures"] = normalize_closure_display(_as_dict(out.get("closures")))
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


def _measurement_issue(
    *,
    code: str,
    message: str,
    piece_id: str | None = None,
    pom: str | None = None,
    value_cm: float | None = None,
    exception_allowed_if: str | None = None,
    blocks_sample_ready: bool = True,
) -> dict[str, Any]:
    issue = _issue(
        code=code,
        message=message,
        piece_id=piece_id,
        pom=pom,
        blocks_sample_ready=blocks_sample_ready,
        exception_allowed_if=exception_allowed_if,
    )
    if value_cm is not None:
        issue["value_cm"] = float(value_cm)
    return issue


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
    finished = _as_dict(piece.get("finished_measurements"))
    body_m = body if isinstance(body, dict) else {}
    fit_blob = _fit_tokens(piece, preferences)
    stretch_ok = _stretch_evidence(piece)
    bands = CATEGORY_POM_PLAUSIBLE_CM.get(cat) or CATEGORY_POM_PLAUSIBLE_CM.get(
        str(piece.get("category") or ""), {}
    )
    fit = _as_dict(piece.get("fit"))

    for pom, (lo, hi) in bands.items():
        cell = finished.get(pom)
        cm = _num(cell)
        if cm is None:
            continue
        if cm < lo or cm > hi:
            label = POM_DEFINITIONS.get(pom, {}).get("label", pom)
            issues.append(
                _measurement_issue(
                    code="pom_outside_category_band",
                    piece_id=pid,
                    pom=pom,
                    value_cm=cm,
                    message=(
                        f"{label} = {cm:g} cm is outside the usual {lo:g}–{hi:g} cm band for "
                        f"a {cat}. Designer value preserved — confirm measuring method "
                        f"({POM_DEFINITIONS.get(pom, {}).get('method', 'see POM definition')}) "
                        "or correct the value before sample development."
                    ),
                    exception_allowed_if=(
                        "Evidence-backed measurement exception naming this code/pom/value"
                    ),
                )
            )
            if isinstance(cell, dict) and not _is_explicitly_confirmed(cell):
                # Do not strip an existing explicit confirmation — band findings are
                # carried as readiness issues / exceptions instead.
                cell["review_status"] = "needs_review"

    length_style = str(fit.get("length_style") or "").lower()
    gl = _num(finished.get("garment_length"))
    if gl is not None and ("hip" in length_style or "upper hip" in length_style) and gl >= 100:
        issues.append(
            _measurement_issue(
                code="length_vs_visual_silhouette",
                piece_id=pid,
                pom="garment_length",
                value_cm=gl,
                message=(
                    f"HPS-to-hem length = {gl:g} cm but the design notes describe a hip-length "
                    f"{cat}. Confirm whether this is a full-body / dress length or a data entry error."
                ),
                exception_allowed_if=(
                    "Evidence-backed measurement exception naming this code/pom/value"
                ),
            )
        )
    inseam = _num(finished.get("inseam"))
    if (
        inseam is not None
        and cat == "shorts"
        and inseam >= 50
        and any(
            tok in _text_blob(fit.get("length_style"), fit.get("silhouette"))
            for tok in ("mid-thigh", "thigh", "above-knee", "near-knee")
        )
    ):
        issues.append(
            _measurement_issue(
                code="shorts_inseam_vs_silhouette",
                piece_id=pid,
                pom="inseam",
                value_cm=inseam,
                message=(
                    f"Shorts finished inseam = {inseam:g} cm while the silhouette describes "
                    "mid-thigh / above-knee shorts. Confirm measuring method or correct the POM."
                ),
                exception_allowed_if=(
                    "Evidence-backed measurement exception naming this code/pom/value"
                ),
            )
        )

    body_waist = _num(body_m.get("waist"))
    fin_waist = _num(finished.get("waist"))
    if (
        body_waist is not None
        and fin_waist is not None
        and fin_waist + 0.5 < body_waist
        and not stretch_ok
    ):
        issues.append(
            _measurement_issue(
                code="finished_waist_smaller_than_body",
                piece_id=pid,
                pom="waist",
                value_cm=fin_waist,
                message=(
                    f"Body waist = {body_waist:g} cm but finished waist = {fin_waist:g} cm "
                    "without confirmed stretch/elastic construction. "
                    "Confirm elastic/drawcord/knit stretch or correct measurements."
                ),
                exception_allowed_if=(
                    "Evidence-backed measurement exception naming this code/pom/value"
                ),
            )
        )

    body_hip = _num(body_m.get("hip"))
    fin_hip = _num(finished.get("hip"))
    if (
        body_hip is not None
        and fin_hip is not None
        and abs(fin_hip - body_hip) < 0.6
        and any(tok in fit_blob for tok in _RELAXED_FIT_TOKENS + _REGULAR_FIT_TOKENS)
    ):
        issues.append(
            _measurement_issue(
                code="zero_ease_hip_with_relaxed_fit",
                piece_id=pid,
                pom="hip",
                value_cm=fin_hip,
                message=(
                    f"Body hip = {body_hip:g} cm and finished hip = {fin_hip:g} cm with "
                    "regular/relaxed fit claimed. Finished garment usually needs ease — "
                    "confirm skin-tight intent, stretch fabric, or correct POMs."
                ),
                exception_allowed_if=(
                    "Evidence-backed measurement exception naming this code/pom/value"
                ),
            )
        )

    body_bust = _num(body_m.get("bust"))
    fin_chest = _num(finished.get("chest_bust"))
    if (
        body_bust is not None
        and fin_chest is not None
        and abs(fin_chest - body_bust) < 0.6
        and any(tok in fit_blob for tok in _RELAXED_FIT_TOKENS)
    ):
        issues.append(
            _measurement_issue(
                code="zero_ease_chest_with_relaxed_fit",
                piece_id=pid,
                pom="chest_bust",
                value_cm=fin_chest,
                message=(
                    f"Body bust = {body_bust:g} cm and finished chest = {fin_chest:g} cm with "
                    "relaxed fit. Confirm intentional zero ease / stretch, or correct values."
                ),
                exception_allowed_if=(
                    "Evidence-backed measurement exception naming this code/pom/value"
                ),
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


_DESIGNER_SOURCES = frozenset(
    {
        "designer",
        "designer_confirmed",
        "user",
        "confirmed",
    }
)
_UNRESOLVED_REVIEW = frozenset(
    {
        "open",
        "needs_review",
        "proposed",
        "proposed_unverified",
        "review",
        "unverified",
    }
)
_CONFIRMED_REVIEW = frozenset(
    {
        "confirmed",
        "designer_confirmed",
        "accepted",
        "approved",
        "visual_qa_confirmed",
        "owner_accepted",
    }
)
_VISUAL_CONFIRMED = frozenset(
    {
        "designer_confirmed",
        "visual_qa_confirmed",
        "owner_accepted",
        "confirmed",
    }
)
_REJECTED_ART = frozenset(
    {
        "rejected_category_mismatch",
        "excluded_mismatch",
        "rejected",
    }
)
_KNOWN_GARMENT_CATEGORIES = frozenset(
    {
        "trousers",
        "shorts",
        "top",
        "hoodie",
        "shirt",
        "jacket",
        "dress",
        "skirt",
        "jumpsuit",
    }
)

# Category-required finished POMs that must be present, numeric, and explicitly confirmed.
REQUIRED_POMS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "trousers": ("waist", "hip", "inseam", "front_rise", "leg_opening"),
    "shorts": ("waist", "hip", "inseam", "front_rise", "leg_opening"),
    "top": ("chest_bust", "garment_length", "shoulder_width", "sleeve_length"),
    "hoodie": ("chest_bust", "garment_length", "shoulder_width", "sleeve_length"),
    "shirt": ("chest_bust", "garment_length", "shoulder_width", "sleeve_length"),
    "jacket": ("chest_bust", "garment_length", "shoulder_width", "sleeve_length"),
    "dress": ("chest_bust", "waist", "hip", "garment_length"),
    "skirt": ("waist", "hip", "skirt_length"),
    "jumpsuit": ("chest_bust", "waist", "hip", "garment_length", "inseam"),
}


def _review_status(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("review_status") or "").strip().lower()


def _is_designer_provenance(value: Any) -> bool:
    """True when a value was entered by a designer — provenance only, not approval."""
    if not isinstance(value, dict):
        return False
    return str(value.get("source") or "").strip().lower() in _DESIGNER_SOURCES


def _is_designer_source(value: Any) -> bool:
    """Backward-compatible alias: provenance OR explicit confirmation."""
    return _is_designer_provenance(value) or _is_explicitly_confirmed(value)


def _is_explicitly_confirmed(value: Any) -> bool:
    """Manufacturing approval — source=designer alone is never enough.

    Requires designer_confirmed=True or a confirmed review_status, and rejects
    unresolved statuses such as open / needs_review.
    """
    if not isinstance(value, dict):
        return False
    status = _review_status(value)
    if status in _UNRESOLVED_REVIEW:
        return False
    if value.get("designer_confirmed") is True:
        return True
    return status in _CONFIRMED_REVIEW


def _pom_designer_confirmed(cell: Any) -> bool:
    if not isinstance(cell, dict):
        return False
    if _num(cell) is None:
        return False
    return _is_explicitly_confirmed(cell)


def required_fields_for_category(category: str) -> list[str]:
    cat = _effective_category({"category": category, "label": category})
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


def required_poms_for_piece(piece: dict[str, Any]) -> tuple[str, ...]:
    cat = _effective_category(piece)
    if cat in REQUIRED_POMS_BY_CATEGORY:
        return REQUIRED_POMS_BY_CATEGORY[cat]
    raw = str(piece.get("category") or "other")
    return REQUIRED_POMS_BY_CATEGORY.get(raw, ("garment_length",))


def evaluate_artifact_for_piece(
    piece: dict[str, Any],
    *,
    kind: str,
    artifact_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return inclusion / manufacturing-evidence decision for an illustration.

    Does **not** inspect image pixels. Piece IDs and analysis text alone are not
    proof of correct visual content. Unverified detail art stays reviewable but
    never counts as designer-approved manufacturing evidence.

    Deterministic caption/annotation contradictions vs structured designer
    closures (e.g. buttons vs FLY (ZIPPER) text) force ``proposed_unverified``
    and strip manufacturing evidence — still not a pixel proof.
    """
    from app.services.techpack_spec_fidelity import (
        apply_fidelity_gates_to_artifact_meta,
        detect_closure_caption_mismatch,
    )

    meta = dict(artifact_meta) if isinstance(artifact_meta, dict) else {}
    ill = _as_dict(piece.get("illustrations"))
    analysis = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else None
    if analysis is None:
        analysis = ill.get("analysis") if isinstance(ill.get("analysis"), dict) else None
    # Apply text-level fidelity gates before inclusion decisions.
    meta = apply_fidelity_gates_to_artifact_meta(
        piece, kind=str(kind), artifact_meta=meta, analysis=analysis
    )
    review = str(meta.get("review_state") or "").strip().lower()

    if review in _REJECTED_ART:
        return {
            "include": False,
            "manufacturing_evidence": False,
            "reason": str(
                meta.get("review_message")
                or meta.get("notes")
                or "Marked mismatched — excluded from corrected preview."
            ),
            "review_state": review,
        }

    closure_mismatch = detect_closure_caption_mismatch(
        piece, artifact_meta=meta, analysis=analysis
    )
    if closure_mismatch or meta.get("fidelity_mismatches"):
        reason = str(
            (closure_mismatch or {}).get("message")
            or meta.get("review_message")
            or "Structured designer specification contradicts generated captions/annotations."
        )
        return {
            "include": True,
            "manufacturing_evidence": False,
            "reason": reason,
            "review_state": "proposed_unverified",
            "fidelity_mismatches": meta.get("fidelity_mismatches")
            or ([closure_mismatch] if closure_mismatch else []),
        }

    if review in _VISUAL_CONFIRMED or meta.get("designer_confirmed") is True:
        return {
            "include": True,
            "manufacturing_evidence": True,
            "reason": "Independently confirmed visual content.",
            "review_state": review or "designer_confirmed",
        }

    # Conservatively unverified — may show for review, never manufacturing-approved.
    # Analysis/metadata heuristics may soft-flag only; they do not prove pixels.
    soft = ""
    if kind == "detail_callouts":
        soft = (
            "Detail artwork has not been independently visually confirmed for this garment. "
            "Artifact↔piece IDs and analysis text are not proof of correct image content."
        )
    return {
        "include": True,
        "manufacturing_evidence": False,
        "reason": soft
        or "Illustration remains unverified for manufacturing evidence.",
        "review_state": review or "unverified_visual_content",
    }


def apply_artifact_reviews(spec: dict[str, Any]) -> dict[str, Any]:
    """Annotate illustration artifacts with include/evidence decisions (non-destructive)."""
    from app.services.techpack_spec_fidelity import apply_piece_fidelity_summary

    out = deepcopy(spec)
    outfit = _as_dict(out.get("outfit"))
    pieces_raw = _as_list(outfit.get("pieces"))
    pieces: list[Any] = []
    for piece in pieces_raw:
        if not isinstance(piece, dict):
            pieces.append(piece)
            continue
        piece_out = apply_piece_fidelity_summary(dict(piece))
        ill = _as_dict(piece_out.get("illustrations"))
        arts = _as_dict(ill.get("artifacts"))
        analysis = ill.get("analysis") if isinstance(ill.get("analysis"), dict) else None
        for kind, meta in list(arts.items()):
            if not isinstance(meta, dict):
                continue
            # Prefer piece analysis when artifact meta lacks nested analysis.
            meta_in = dict(meta)
            if analysis and not isinstance(meta_in.get("analysis"), dict):
                meta_in["analysis"] = analysis
            decision = evaluate_artifact_for_piece(
                piece_out, kind=str(kind), artifact_meta=meta_in
            )
            meta_out = dict(meta_in)
            meta_out["preview_include"] = decision["include"]
            meta_out["manufacturing_evidence"] = bool(decision.get("manufacturing_evidence"))
            meta_out["review_state"] = decision["review_state"]
            if decision.get("reason"):
                meta_out["review_message"] = decision["reason"]
            if decision.get("fidelity_mismatches"):
                meta_out["fidelity_mismatches"] = decision["fidelity_mismatches"]
            arts[str(kind)] = meta_out
        ill["artifacts"] = arts
        piece_out["illustrations"] = ill
        pieces.append(piece_out)
    outfit["pieces"] = pieces
    out["outfit"] = outfit
    return out


def normalize_bom_rows(bom: list[Any] | None, *, piece: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Flag/normalize BOM rows that dump outfit color lists as fabric names. Never invent composition."""
    _ = piece
    rows: list[dict[str, Any]] = []
    for row in _as_list(bom):
        if not isinstance(row, dict):
            continue
        item = dict(row)
        name = str(item.get("item") or item.get("name") or "")
        if _looks_like_outfit_color_list_name(name):
            item["original_item"] = name
            item["item"] = "Shell fabric — NOT CONFIRMED"
            item["name"] = item["item"]
            item["review_status"] = "needs_review"
            item["notes"] = (
                str(item.get("notes") or "")
                + " Removed outfit-level color list used as fabric name; enter real shell quality."
            ).strip()
            # Do not invent composition.
            item["composition"] = ""
        rows.append(item)
    return rows


def _fit_ease_confirmed(piece: dict[str, Any], preferences: dict[str, Any] | None) -> bool:
    fit = _as_dict(piece.get("fit"))
    has_value = bool(str(fit.get("suggestion") or fit.get("silhouette") or "").strip())
    if has_value and _is_explicitly_confirmed(fit):
        return True
    prefs = preferences if isinstance(preferences, dict) else {}
    # Preference-level confirmation still requires a named fit on the piece.
    return bool(has_value and prefs.get("fit_preference_confirmed") is True and _is_explicitly_confirmed(prefs))


def _construction_confirmed(piece: dict[str, Any]) -> bool:
    steps = _as_list(piece.get("construction_steps"))
    meaningful = [
        row
        for row in steps
        if isinstance(row, dict) and str(row.get("instruction") or "").strip()
    ]
    if not meaningful:
        return False
    if any(_is_explicitly_confirmed(row) for row in meaningful):
        return True
    # Piece-level construction_confirmed still requires at least one meaningful step
    # and must not be left in an unresolved review state.
    return bool(
        piece.get("construction_confirmed") is True
        and _review_status(piece) not in _UNRESOLVED_REVIEW
    )


def _material_confirmed(piece: dict[str, Any]) -> bool:
    mats = _as_dict(piece.get("materials"))
    shell = _as_dict(mats.get("shell"))
    if _review_status(shell) in _UNRESOLVED_REVIEW:
        return False
    name = str(shell.get("name") or "").strip()
    composition = str(shell.get("composition") or "").strip()
    if not name or not composition:
        return False
    if re.search(r"\[.*\]", name):
        return False
    return _is_explicitly_confirmed(shell)


def _closure_confirmed(piece: dict[str, Any]) -> bool:
    closures = normalize_closure_display(_as_dict(piece.get("closures")))
    if _review_status(closures) in _UNRESOLVED_REVIEW:
        return False
    display = str(closures.get("display_type") or closures.get("type") or "").strip()
    if not display or display == "—":
        return False
    return _is_explicitly_confirmed(closures)


def _tolerances_confirmed(piece: dict[str, Any]) -> bool:
    tol = _as_dict(piece.get("pom_tolerances"))
    if not tol or tol.get("default_cm") is None:
        return False
    if _review_status(tol) in _UNRESOLVED_REVIEW:
        return False
    return _is_explicitly_confirmed(tol)


def _piece_identity_ok(piece: dict[str, Any]) -> bool:
    pid = str(piece.get("id") or "").strip()
    if not pid:
        return False
    raw_cat = str(piece.get("category") or "").strip().lower()
    effective = _effective_category(piece)
    known = effective in _KNOWN_GARMENT_CATEGORIES or raw_cat in _KNOWN_GARMENT_CATEGORIES
    category_confirmed = piece.get("category_confirmed") is True or _is_explicitly_confirmed(
        piece.get("category_review")
    )
    if not raw_cat or raw_cat in {"other", "unknown", "unspecified", "n/a", "na"}:
        return category_confirmed
    return known or category_confirmed


def validate_outfit_structure(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Reject empty / malformed / duplicate / unconfirmed garment identities."""
    issues: list[dict[str, Any]] = []
    outfit = _as_dict(spec.get("outfit"))
    pieces_raw = outfit.get("pieces")
    if not isinstance(pieces_raw, list) or not pieces_raw:
        issues.append(
            _issue(
                code="outfit_empty",
                message=(
                    "Outfit has no garment components. SAMPLE-DEVELOPMENT READY requires at least "
                    "one uniquely identified, category-confirmed piece."
                ),
            )
        )
        return issues

    seen_ids: set[str] = set()
    unique_valid = 0
    for idx, piece in enumerate(pieces_raw):
        if not isinstance(piece, dict):
            issues.append(
                _issue(
                    code="piece_malformed",
                    message=f"Outfit piece at index {idx} is malformed (expected object).",
                )
            )
            continue

        pid = str(piece.get("id") or "").strip()
        duplicate = False
        if not pid:
            issues.append(
                _issue(
                    code="piece_id_missing",
                    message=f"Outfit piece at index {idx} has no unique id.",
                )
            )
        elif pid in seen_ids:
            duplicate = True
            issues.append(
                _issue(
                    code="piece_id_duplicate",
                    piece_id=pid,
                    message=f"Duplicate garment component id “{pid}”.",
                )
            )
        else:
            seen_ids.add(pid)

        raw_cat = str(piece.get("category") or "").strip().lower()
        effective = _effective_category(piece)
        known = effective in _KNOWN_GARMENT_CATEGORIES or raw_cat in _KNOWN_GARMENT_CATEGORIES
        category_confirmed = piece.get("category_confirmed") is True or _is_explicitly_confirmed(
            piece.get("category_review")
        )
        if not raw_cat or raw_cat in {"other", "unknown", "unspecified", "n/a", "na"}:
            if not category_confirmed:
                issues.append(
                    _issue(
                        code="piece_category_unconfirmed",
                        piece_id=pid or None,
                        message=(
                            f"Garment category for piece “{pid or idx}” is missing/unspecified. "
                            "Confirm a manufacturing category before SAMPLE-DEVELOPMENT READY."
                        ),
                    )
                )
                continue
        elif not known and not category_confirmed:
            issues.append(
                _issue(
                    code="piece_category_unconfirmed",
                    piece_id=pid or None,
                    message=(
                        f"Garment category “{raw_cat}” for piece “{pid or idx}” is not a known "
                        "manufacturing category and has not been explicitly confirmed."
                    ),
                )
            )
            continue

        if pid and not duplicate and _piece_identity_ok(piece):
            unique_valid += 1

    if unique_valid < 1:
        issues.append(
            _issue(
                code="outfit_no_valid_pieces",
                message=(
                    "No uniquely identified garment component with a confirmed category is present."
                ),
            )
        )
    return issues


def _collect_measurement_exceptions(spec: dict[str, Any], piece: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for src in (_as_list(spec.get("measurement_exceptions")), _as_list(piece.get("measurement_exceptions"))):
        for row in src:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _exception_covers_issue(
    issue: dict[str, Any],
    *,
    exceptions: list[dict[str, Any]],
    pack_revision: Any = None,
) -> bool:
    """Narrow, evidence-backed exception — never a blanket approval.

    Requires matching code + piece_id + pom + current value_cm, explicit
    confirmation, and (when provided) matching revision.
    """
    code = str(issue.get("code") or "")
    piece_id = str(issue.get("piece_id") or "")
    pom = str(issue.get("pom") or "")
    value = issue.get("value_cm")
    if not code or not piece_id or not pom or not isinstance(value, (int, float)):
        return False

    for row in exceptions:
        if not _is_explicitly_confirmed(row):
            continue
        # Reject blanket / global approvals.
        if row.get("approve_all") is True or row.get("blanket") is True:
            continue
        if str(row.get("code") or "") != code:
            continue
        if str(row.get("piece_id") or "") != piece_id:
            continue
        if str(row.get("pom") or "") != pom:
            continue
        exc_val = row.get("value_cm")
        if not isinstance(exc_val, (int, float)):
            continue
        if abs(float(exc_val) - float(value)) > 0.051:
            continue
        if (
            row.get("revision") is not None
            and pack_revision is not None
            and str(row.get("revision")) != str(pack_revision)
        ):
            continue
        if not str(row.get("rationale") or row.get("notes") or "").strip():
            # Require a short rationale so this is evidence-backed, not a silent tick.
            continue
        return True
    return False


def apply_measurement_exceptions(
    issues: list[dict[str, Any]],
    *,
    spec: dict[str, Any],
    piece: dict[str, Any],
) -> list[dict[str, Any]]:
    """Clear blocks_sample_ready only for narrowly matched confirmed exceptions."""
    exceptions = _collect_measurement_exceptions(spec, piece)
    pack_revision = spec.get("revision")
    out: list[dict[str, Any]] = []
    for issue in issues:
        item = dict(issue)
        if item.get("blocks_sample_ready") and _exception_covers_issue(
            item, exceptions=exceptions, pack_revision=pack_revision
        ):
            item["blocks_sample_ready"] = False
            item["severity"] = "info"
            item["exception_applied"] = True
            item["review_status"] = "exception_confirmed"
            item["message"] = (
                str(item.get("message") or "")
                + " Exception accepted for this specific finding/value/revision."
            ).strip()
        out.append(item)
    return out


def assess_manufacturing_readiness(spec: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed SAMPLE-DEVELOPMENT readiness. Never auto PRODUCTION_APPROVED.

    A checked generic QC checklist alone is insufficient. Category-specific
    finished POMs, fit/ease, materials, closures, construction, tolerances and
    conflict resolution must show explicit review confirmation — not AI
    estimates, generic defaults, or provenance-only ``source=designer``.
    """
    v2: dict[str, Any] = deepcopy(spec) if isinstance(spec, dict) else {}
    issues: list[dict[str, Any]] = []
    issues.extend(validate_sample_size(v2))
    issues.extend(validate_outfit_structure(v2))

    body = _as_dict(v2.get("body"))
    prefs = _as_dict(v2.get("preferences"))
    outfit = _as_dict(v2.get("outfit"))
    pieces = [p for p in _as_list(outfit.get("pieces")) if isinstance(p, dict)]

    missing_required: list[str] = []
    category_requirements: dict[str, list[str]] = {}

    if not str(v2.get("sample_size") or "").strip():
        missing_required.append("named_sample_size")
    if not pieces:
        missing_required.append("outfit_pieces")

    for piece in pieces:
        pid = str(piece.get("id") or "").strip() or "piece"
        if not _piece_identity_ok(piece):
            missing_required.append(f"{pid}:garment_identity")
            continue

        cat = _effective_category(piece)
        reqs = required_fields_for_category(cat)
        category_requirements[pid] = reqs
        piece_n = normalize_shell_material(annotate_pom_definitions(piece))
        meas_issues = apply_measurement_exceptions(
            validate_piece_measurements(piece_n, body=body, preferences=prefs),
            spec=v2,
            piece=piece_n,
        )
        issues.extend(meas_issues)

        finished = _as_dict(piece_n.get("finished_measurements"))
        required_poms = required_poms_for_piece(piece_n)
        missing_poms: list[str] = []
        unconfirmed_poms: list[str] = []
        for pom in required_poms:
            cell = finished.get(pom)
            if _num(cell) is None:
                missing_poms.append(pom)
            elif not _pom_designer_confirmed(cell):
                unconfirmed_poms.append(pom)
        if missing_poms or unconfirmed_poms:
            missing_required.append(f"{pid}:finished_poms_confirmed")
            if "chest_and_length_poms" in reqs and any(
                p in missing_poms + unconfirmed_poms
                for p in ("chest_bust", "garment_length", "shoulder_width", "sleeve_length")
            ):
                missing_required.append(f"{pid}:chest_and_length_poms")
            if "waist_hip_inseam_poms" in reqs and any(
                p in missing_poms + unconfirmed_poms for p in ("waist", "hip", "inseam")
            ):
                missing_required.append(f"{pid}:waist_hip_inseam_poms")
            issues.append(
                _issue(
                    code="finished_poms_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"Category “{cat}” requires explicitly confirmed finished POMs "
                        f"{list(required_poms)} (source=designer alone is insufficient). "
                        + (f"Missing values: {missing_poms}. " if missing_poms else "")
                        + (
                            f"Present but not review-confirmed (open/needs_review/AI/estimate): "
                            f"{unconfirmed_poms}."
                            if unconfirmed_poms
                            else ""
                        )
                    ),
                )
            )

        if not _fit_ease_confirmed(piece_n, prefs):
            missing_required.append(f"{pid}:fit_ease_reviewed")
            issues.append(
                _issue(
                    code="fit_ease_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"Fit/ease for “{piece.get('label') or cat}” lacks explicit review "
                        "confirmation. Provenance-only designer source does not count."
                    ),
                )
            )

        if not _material_confirmed(piece_n):
            missing_required.append(f"{pid}:material_specified")
            issues.append(
                _issue(
                    code="shell_material_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"Shell material/composition for “{piece.get('label') or cat}” must be "
                        "explicitly confirmed (color lists, estimates, and open review are insufficient)."
                    ),
                )
            )

        if not _closure_confirmed(piece_n):
            missing_required.append(f"{pid}:closures_specified")
            issues.append(
                _issue(
                    code="closure_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"Closure/fastener for “{piece.get('label') or cat}” is unconfirmed. "
                        "Boolean placeholders, AI guesses, and open review are not manufacturing specs."
                    ),
                )
            )

        if not _construction_confirmed(piece_n):
            missing_required.append(f"{pid}:construction_decisions")
            issues.append(
                _issue(
                    code="construction_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"Construction decisions for “{piece.get('label') or cat}” are missing or "
                        "only generic defaults. Explicitly confirmed steps are required."
                    ),
                )
            )

        if not _tolerances_confirmed(piece_n):
            missing_required.append(f"{pid}:pom_tolerances")
            issues.append(
                _issue(
                    code="pom_tolerances_unconfirmed",
                    piece_id=pid,
                    message=(
                        f"POM tolerances for “{piece.get('label') or cat}” are not "
                        "explicitly confirmed for the intended sample."
                    ),
                )
            )

        ill = _as_dict(piece.get("illustrations"))
        arts = _as_dict(ill.get("artifacts"))
        for kind, meta in arts.items():
            decision = evaluate_artifact_for_piece(
                piece, kind=str(kind), artifact_meta=meta if isinstance(meta, dict) else {}
            )
            if not decision["include"]:
                issues.append(
                    _issue(
                        code="artifact_category_mismatch",
                        piece_id=pid,
                        message=str(decision["reason"]),
                    )
                )
            elif str(kind) == "detail_callouts" and not decision.get("manufacturing_evidence"):
                issues.append(
                    _issue(
                        code="detail_art_unverified",
                        piece_id=pid,
                        message=str(
                            decision.get("reason")
                            or "Detail artwork is unverified and cannot count as manufacturing evidence."
                        ),
                        severity="warning",
                        blocks_sample_ready=True,
                    )
                )

        if any(i.get("blocks_sample_ready") for i in meas_issues):
            missing_required.append(f"{pid}:major_conflicts_resolved")

    blocking = [i for i in issues if i.get("blocks_sample_ready")]
    qc = _as_list(v2.get("qc_checklist"))
    checklist_complete = bool(qc) and all(isinstance(row, dict) and row.get("checked") for row in qc)
    if not checklist_complete:
        missing_required.append("designer_confirmation_checklist")

    # Fail closed: checklist alone never unlocks SAMPLE READY.
    category_complete = not missing_required and not blocking
    designer_confirmed = bool(checklist_complete and category_complete)

    if blocking or missing_required or not checklist_complete or not category_complete:
        level = READINESS_DESIGN_CONCEPT
    else:
        level = READINESS_SAMPLE_DEVELOPMENT

    return {
        "readiness_level": level,
        "readiness_label": READINESS_LABELS[level],
        "issues": issues,
        "blocking_issue_count": len(blocking),
        "missing_required": sorted(set(missing_required)),
        "category_requirements": category_requirements,
        "designer_confirmed": designer_confirmed,
        "checklist_complete": checklist_complete,
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
    outfit = _as_dict(out.get("outfit"))
    look_notes = str(out.get("look_notes") or "")
    ga = _as_dict(out.get("garment_analysis"))
    ga_by_piece: dict[str, dict[str, Any]] = {}
    for row in _as_list(ga.get("pieces")):
        if isinstance(row, dict) and row.get("piece_id"):
            ga_by_piece[str(row.get("piece_id"))] = row
    pieces: list[dict[str, Any]] = []
    for piece in _as_list(outfit.get("pieces")):
        if not isinstance(piece, dict):
            continue
        pid = str(piece.get("id") or "")
        normalized = normalize_shell_material(annotate_pom_definitions(piece))
        pieces.append(
            derive_piece_garment_color(
                normalized,
                look_notes=look_notes,
                garment_analysis_piece=ga_by_piece.get(pid),
            )
        )
    outfit["pieces"] = pieces
    out["outfit"] = outfit

    assessment = assess_manufacturing_readiness(out)
    prior_raw = _as_list(out.get("warnings"))
    prior = [w for w in prior_raw if isinstance(w, dict)]
    merged: list[Any] = list(prior)
    seen = {
        f"{w.get('code')}|{w.get('piece_id')}|{w.get('pom')}|{w.get('message')}"
        for w in prior
    }
    for issue in assessment["issues"]:
        key = f"{issue.get('code')}|{issue.get('piece_id')}|{issue.get('pom')}|{issue.get('message')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(issue)
    out["warnings"] = merged
    ai = _as_dict(out.get("ai"))
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
