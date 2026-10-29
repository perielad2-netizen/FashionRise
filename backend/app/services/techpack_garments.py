"""Garment taxonomy + per-category measurement schemas for Create Real Design V2."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CATEGORIES = (
    "dress",
    "shirt",
    "top",
    "jacket",
    "skirt",
    "trousers",
    "shorts",
    "jumpsuit",
    "set",
    "other",
)

ROLE_BY_CATEGORY = {
    "dress": "one_piece",
    "shirt": "top",
    "top": "top",
    "jacket": "outer",
    "skirt": "bottom",
    "trousers": "bottom",
    "shorts": "bottom",
    "jumpsuit": "one_piece",
    "set": "set",
    "other": "other",
}

# Finished-garment POM keys by category (never show shirt POMs on trousers, etc.).
FINISHED_POM: dict[str, tuple[str, ...]] = {
    "shirt": (
        "chest_bust",
        "shoulder_width",
        "garment_length",
        "sleeve_length",
        "armhole",
        "cuff",
        "hem",
        "neckline",
    ),
    "top": (
        "chest_bust",
        "shoulder_width",
        "garment_length",
        "sleeve_length",
        "armhole",
        "hem",
        "neckline",
    ),
    "jacket": (
        "chest_bust",
        "shoulder_width",
        "garment_length",
        "sleeve_length",
        "armhole",
        "hem",
        "neckline",
    ),
    "trousers": (
        "waist",
        "hip",
        "inseam",
        "outseam",
        "front_rise",
        "back_rise",
        "thigh",
        "knee",
        "leg_opening",
        "waistband",
    ),
    "shorts": ("waist", "hip", "inseam", "outseam", "front_rise", "back_rise", "thigh", "leg_opening", "waistband"),
    "skirt": ("waist", "hip", "skirt_length", "waistband", "hem", "opening"),
    "dress": (
        "chest_bust",
        "waist",
        "hip",
        "garment_length",
        "shoulder_width",
        "armhole",
        "sleeve_length",
        "hem",
        "neckline",
    ),
    "jumpsuit": (
        "chest_bust",
        "waist",
        "hip",
        "garment_length",
        "inseam",
        "shoulder_width",
        "sleeve_length",
        "hem",
    ),
    "other": ("garment_length", "waist", "hip", "chest_bust"),
    "set": (),
}

POM_LABELS = {
    "chest_bust": "Chest / bust circumference",
    "shoulder_width": "Shoulder width",
    "garment_length": "Garment length (HPS to hem)",
    "sleeve_length": "Sleeve length",
    "armhole": "Armhole circumference",
    "cuff": "Cuff opening",
    "hem": "Hem circumference",
    "neckline": "Neckline / collar",
    "waist": "Waist circumference",
    "hip": "Hip circumference",
    "inseam": "Inseam",
    "outseam": "Outseam",
    "front_rise": "Front rise",
    "back_rise": "Back rise",
    "thigh": "Thigh circumference",
    "knee": "Knee circumference",
    "leg_opening": "Leg opening",
    "waistband": "Waistband height",
    "skirt_length": "Skirt length",
    "opening": "Opening / slit",
}

BODY_KEYS = ("height", "bust", "waist", "hip", "inseam")

SHELL_SUGGESTIONS = (
    "cotton",
    "denim",
    "linen",
    "silk",
    "polyester blend",
    "jersey knit",
    "wool blend",
    "other",
    "unknown",
)

CLOSURE_SUGGESTIONS = (
    "buttons",
    "zipper",
    "invisible zipper",
    "snaps",
    "hook-and-eye",
    "elastic waistband",
    "pull-on",
    "none",
)

SILHOUETTE_SUGGESTIONS = (
    "slim",
    "regular",
    "relaxed",
    "oversized",
    "fitted",
    "A-line",
    "flared",
    "straight",
    "tapered",
    "wide-leg",
)

# Physically implausible finished POM thresholds (cm) → review warning.
POM_WARN_MAX_CM = {
    "shoulder_width": 60,
    "inseam": 110,
    "garment_length": 180,
    "sleeve_length": 90,
    "waist": 200,
    "hip": 220,
    "chest_bust": 200,
    "thigh": 120,
}


def _mv(
    value: Any = None,
    *,
    unit: str | None = "cm",
    source: str = "empty",
    note: str | None = None,
    definition: str | None = None,
    confidence: str = "unknown",
    review_status: str = "open",
    assumptions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "source": source,
        "note": note,
        "definition": definition,
        "confidence": confidence,
        "review_status": review_status,
        "assumptions": assumptions or [],
    }


def empty_finished_measurements(category: str, units: str = "cm") -> dict[str, Any]:
    keys = FINISHED_POM.get(category, FINISHED_POM["other"])
    out: dict[str, Any] = {}
    for key in keys:
        out[key] = _mv(
            unit=units,
            definition=POM_LABELS.get(key),
            source="empty",
            confidence="unknown",
        )
    return out


def default_piece(
    *,
    piece_id: str,
    category: str,
    label: str,
    role: str | None = None,
    color_hint: str = "",
    detection_source: str = "user",
    units: str = "cm",
) -> dict[str, Any]:
    cat = category if category in CATEGORIES else "other"
    return {
        "id": piece_id,
        "category": cat,
        "label": label,
        "role": role or ROLE_BY_CATEGORY.get(cat, "other"),
        "color_hint": color_hint,
        "detection_source": detection_source,
        "materials": {
            "shell": {"name": "", "suggestion": "", "composition": "", "source": "empty"},
            "lining": {"name": "", "source": "empty"},
            "interfacing": {"name": "", "source": "empty"},
        },
        "closures": {"type": "", "suggestion": "", "notes": "", "source": "empty"},
        "fit": {"silhouette": "", "suggestion": "", "ease_note": ""},
        "finished_measurements": empty_finished_measurements(cat, units),
        "seam_allowance": _mv(value=1.0, unit=units, source="estimate", note="Default draft SA", confidence="low"),
        "bom": [],
        "pattern_pieces": [],
        "construction_steps": [],
        "illustrations": {
            "flat_front": "schematic_pending",
            "flat_back": "schematic_pending",
            "cutting": "schematic_pending",
            "label": "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE",
        },
    }


def migrate_v1_spec_to_v2(spec: dict[str, Any] | None, *, look_summary: str | None = None) -> dict[str, Any]:
    """Upgrade a V1 flat spec into multi-piece V2 without dropping user data."""
    base = deepcopy(spec) if isinstance(spec, dict) else {}
    if str(base.get("schema_version") or "").startswith("2"):
        return base

    units = str(base.get("units") or "cm")
    mats = base.get("materials") if isinstance(base.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    closures = base.get("closures") if isinstance(base.get("closures"), dict) else {}
    fit = base.get("fit") if isinstance(base.get("fit"), dict) else {}
    garment = base.get("garment") if isinstance(base.get("garment"), dict) else {}

    category = "dress"
    summary = (look_summary or base.get("look_notes") or "").lower()
    if "trouser" in summary or "pant" in summary:
        category = "trousers"
    if "shirt" in summary or "blouse" in summary:
        category = "shirt"
    if ("shirt" in summary or "top" in summary) and ("trouser" in summary or "pant" in summary):
        # multi-piece handled by detector; keep single piece fallback as other
        category = "shirt"

    piece = default_piece(
        piece_id="piece-1",
        category=category,
        label=shell.get("name") or category.title(),
        color_hint="",
        detection_source="migrated_v1",
        units=units,
    )
    piece["materials"]["shell"] = {
        "name": shell.get("name") or "",
        "composition": shell.get("composition") or "",
        "suggestion": "",
        "source": shell.get("source") or ("designer" if shell.get("name") else "empty"),
    }
    piece["closures"] = {
        "type": closures.get("type") or "",
        "suggestion": "",
        "notes": closures.get("notes") or "",
        "source": closures.get("source") or "empty",
    }
    piece["fit"]["silhouette"] = fit.get("silhouette") or ""
    # Map legacy garment POMs into finished measurements where names overlap.
    legacy_map = {
        "garment_length": "garment_length",
        "shoulder_width": "shoulder_width",
        "sleeve_length": "sleeve_length",
        "inseam": "inseam",
        "hem_circumference": "hem",
    }
    for legacy, target in legacy_map.items():
        if target in piece["finished_measurements"] and isinstance(garment.get(legacy), dict):
            piece["finished_measurements"][target] = {
                **piece["finished_measurements"][target],
                **garment[legacy],
                "definition": POM_LABELS.get(target),
            }

    body = base.get("body") if isinstance(base.get("body"), dict) else {}
    return {
        "schema_version": "2.0",
        "workflow_stage": "understand",
        "units": units,
        "size_system": base.get("size_system") or "EU",
        "sample_size": base.get("sample_size") or "",
        "quantity": base.get("quantity"),
        "look_notes": base.get("look_notes") or "",
        "designer_notes": base.get("designer_notes") or "",
        "disclaimer": base.get("disclaimer")
        or (
            "DRAFT / UNVERIFIED. AI illustrations are PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. "
            "Patternmaker review required before production."
        ),
        "outfit": {"piece_count": 1, "pieces": [piece], "detection_confidence": "migrated"},
        "body": {k: body.get(k) or _mv(unit=units) for k in BODY_KEYS},
        "preferences": {
            "fit_preference": fit.get("silhouette") or "regular",
            "notes": "",
        },
        "warnings": [],
        "qc_checklist": base.get("qc_checklist")
        or [
            {"item": "Garment categories confirmed by designer", "checked": False},
            {"item": "Finished measurements reviewed (body vs garment separated)", "checked": False},
            {"item": "Pattern schematics labeled NOT TO SCALE", "checked": False},
            {"item": "Patternmaker sign-off before production", "checked": False},
        ],
        "ai": {"last_run_id": None, "paid_sections": []},
        "v1_legacy": {
            "garment": garment,
            "materials": mats,
            "bom": base.get("bom") or [],
            "construction": base.get("construction") or [],
        },
    }


def collect_measurement_warnings(spec: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    for piece in pieces:
        if not isinstance(piece, dict):
            continue
        finished = piece.get("finished_measurements") if isinstance(piece.get("finished_measurements"), dict) else {}
        for key, cell in finished.items():
            if not isinstance(cell, dict):
                continue
            value = cell.get("value")
            unit = str(cell.get("unit") or "cm").lower()
            if not isinstance(value, (int, float)):
                continue
            cm = float(value) * 2.54 if unit in ("in", "inch", "inches") else float(value)
            limit = POM_WARN_MAX_CM.get(key)
            if limit is not None and cm > limit:
                warnings.append(
                    {
                        "code": "implausible_measurement",
                        "piece_id": piece.get("id"),
                        "pom": key,
                        "value": value,
                        "unit": unit,
                        "message": (
                            f"{POM_LABELS.get(key, key)} of {value} {unit} looks physically implausible "
                            f"for a garment. Review before manufacturing."
                        ),
                        "severity": "error",
                    }
                )
                cell["review_status"] = "needs_review"
                cell["confidence"] = "low"
    # Category-aware manufacturing contradictions (body vs finished, silhouette bands).
    # Never silently corrects designer values — only flags NEEDS REVIEW.
    try:
        from app.services.techpack_manufacturing import (
            assess_manufacturing_readiness,
            validate_piece_measurements,
            validate_sample_size,
        )

        body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
        prefs = spec.get("preferences") if isinstance(spec.get("preferences"), dict) else {}
        for issue in validate_sample_size(spec):
            warnings.append(issue)
        for piece in pieces:
            if not isinstance(piece, dict):
                continue
            for issue in validate_piece_measurements(piece, body=body, preferences=prefs):
                warnings.append(issue)
        # Keep assessment available for callers that only collect warnings.
        _ = assess_manufacturing_readiness
    except Exception:  # noqa: BLE001 — never break draft load on review helpers
        pass
    return warnings
