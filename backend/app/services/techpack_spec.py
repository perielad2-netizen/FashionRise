"""Create Real Design spec helpers (V1 compatible + V2 multi-piece)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.techpack_detect import detect_pieces_from_evidence
from app.services.techpack_garments import (
    BODY_KEYS,
    collect_measurement_warnings,
    default_piece,
    migrate_v1_spec_to_v2,
)

ALLOWED_SOURCES = frozenset({"empty", "designer", "estimate", "ai", "look", "calculated", "unknown"})


def _mv(value: Any = None, *, unit: str | None = None, source: str = "empty", note: str | None = None) -> dict[str, Any]:
    src = source if source in ALLOWED_SOURCES else "empty"
    return {"value": value, "unit": unit, "source": src, "note": note}


def default_spec(*, look_summary: str | None = None, units: str = "cm") -> dict[str, Any]:
    """V2 default — guided multi-piece outfit with heuristic detection."""
    detection = detect_pieces_from_evidence(look_summary=look_summary, units=units)
    body = {key: _mv(unit=units) for key in BODY_KEYS}
    return {
        "schema_version": "2.0",
        "workflow_stage": "understand",
        "units": units,
        "size_system": "EU",
        "sample_size": "",
        "quantity": None,
        "look_notes": (look_summary or "").strip()[:500],
        "designer_notes": "",
        "disclaimer": (
            "DRAFT / UNVERIFIED. Technical flats and pattern pieces are "
            "PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. Patternmaker review required."
        ),
        "outfit": detection,
        "body": body,
        "preferences": {"fit_preference": "regular", "notes": ""},
        "warnings": [],
        "qc_checklist": [
            {"item": "Outfit piece categories confirmed", "checked": False},
            {"item": "Body vs finished measurements separated", "checked": False},
            {"item": "Implausible measurements reviewed", "checked": False},
            {"item": "Schematics labeled NOT TO SCALE", "checked": False},
            {"item": "Patternmaker sign-off before production", "checked": False},
        ],
        "ai": {"last_run_id": None, "paid_sections": []},
    }


def style_code_from_look(look_id: Any) -> str:
    text = str(look_id).replace("-", "").upper()
    return f"FR-{text[:4]}"


def ensure_v2(spec: dict[str, Any] | None, *, look_summary: str | None = None) -> dict[str, Any]:
    if not isinstance(spec, dict) or not spec:
        return default_spec(look_summary=look_summary)
    if str(spec.get("schema_version") or "").startswith("2"):
        out = deepcopy(spec)
    else:
        out = migrate_v1_spec_to_v2(spec, look_summary=look_summary)
    out["warnings"] = collect_measurement_warnings(out)
    return out


def merge_spec(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    out = ensure_v2(base)
    if not patch:
        return out
    # Allow full V2 replace of known top-level keys (body/preferences deep-merged).
    for key in (
        "workflow_stage",
        "units",
        "size_system",
        "sample_size",
        "look_notes",
        "designer_notes",
        "disclaimer",
        "outfit",
        "qc_checklist",
        "ai",
    ):
        if key in patch:
            out[key] = deepcopy(patch[key])
    if "body" in patch and isinstance(patch["body"], dict):
        body = out.get("body") if isinstance(out.get("body"), dict) else {}
        merged_body = deepcopy(body)
        for bkey, bval in patch["body"].items():
            if isinstance(bval, dict) and isinstance(merged_body.get(bkey), dict):
                merged_body[bkey] = {**merged_body[bkey], **deepcopy(bval)}
            else:
                merged_body[bkey] = deepcopy(bval)
        out["body"] = merged_body
    if "preferences" in patch and isinstance(patch["preferences"], dict):
        prefs = out.get("preferences") if isinstance(out.get("preferences"), dict) else {}
        out["preferences"] = {**prefs, **deepcopy(patch["preferences"])}
    if "quantity" in patch:
        q = patch["quantity"]
        out["quantity"] = q if isinstance(q, (int, float)) or q is None else out.get("quantity")

    # Piece-level safety: ensure each piece has an id/category.
    outfit = out.get("outfit") if isinstance(out.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    cleaned = []
    for idx, piece in enumerate(pieces):
        if not isinstance(piece, dict):
            continue
        if not piece.get("id"):
            piece = {**default_piece(piece_id=f"piece-{idx+1}", category="other", label=f"Piece {idx+1}"), **piece}
            piece["id"] = piece.get("id") or f"piece-{idx+1}"
        cleaned.append(piece)

    # Map legacy V1 top-level materials/closures/fit onto the first piece when present.
    if cleaned and isinstance(patch.get("materials"), dict):
        mats = cleaned[0].get("materials") if isinstance(cleaned[0].get("materials"), dict) else {}
        shell_patch = patch["materials"].get("shell") if isinstance(patch["materials"].get("shell"), dict) else {}
        if shell_patch:
            shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
            mats["shell"] = {**shell, **deepcopy(shell_patch), "source": shell_patch.get("source") or "designer"}
            cleaned[0]["materials"] = mats
    if cleaned and isinstance(patch.get("closures"), dict):
        closures = cleaned[0].get("closures") if isinstance(cleaned[0].get("closures"), dict) else {}
        cleaned[0]["closures"] = {**closures, **deepcopy(patch["closures"])}
    if cleaned and isinstance(patch.get("fit"), dict):
        fit = cleaned[0].get("fit") if isinstance(cleaned[0].get("fit"), dict) else {}
        cleaned[0]["fit"] = {**fit, **deepcopy(patch["fit"])}

    outfit["pieces"] = cleaned
    outfit["piece_count"] = len(cleaned)
    out["outfit"] = outfit
    out["schema_version"] = "2.0"
    out["warnings"] = collect_measurement_warnings(out)
    return out
