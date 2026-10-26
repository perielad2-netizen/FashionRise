"""Default Create Real Design spec + merge helpers.

Every measurement carries an explicit ``source`` so PDFs never imply false precision.
AI-inferred fields are only accepted when the caller marks them — tests/smoke never call paid AI.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

ALLOWED_SOURCES = frozenset({"empty", "designer", "estimate", "ai", "look"})

_BODY_KEYS = ("height", "bust", "waist", "hip")
_GARMENT_KEYS = (
    "garment_length",
    "shoulder_width",
    "sleeve_length",
    "inseam",
    "hem_circumference",
)


def _mv(value: Any = None, *, unit: str | None = None, source: str = "empty", note: str | None = None) -> dict[str, Any]:
    src = source if source in ALLOWED_SOURCES else "empty"
    return {"value": value, "unit": unit, "source": src, "note": note}


def default_spec(*, look_summary: str | None = None, units: str = "cm") -> dict[str, Any]:
    body = {key: _mv(unit=units) for key in _BODY_KEYS}
    garment = {key: _mv(unit=units, source="estimate", note="Estimate — not graded") for key in _GARMENT_KEYS}
    return {
        "schema_version": "1.0",
        "units": units,
        "size_system": "EU",
        "sample_size": "",
        "quantity": None,
        "fit": {"ease": _mv(source="estimate", note="Estimate until patterned"), "silhouette": ""},
        "body": body,
        "garment": garment,
        "materials": {
            "shell": {"name": "", "composition": "", "stretch": "", "width": _mv(unit=units), "source": "empty"},
            "lining": {"name": "", "composition": "", "source": "empty"},
            "interfacing": {"name": "", "source": "empty"},
        },
        "closures": {"type": "", "notes": "", "source": "empty"},
        "seam_allowance": _mv(value=1.0, unit=units, source="estimate", note="Default estimate"),
        "trims": [],
        "bom": [],
        "construction": [
            {
                "step": 1,
                "instruction": "Patternmaker review required before production.",
                "source": "estimate",
            }
        ],
        "pattern_pieces": [],
        "qc_checklist": [
            {"item": "Style code / revision match cover", "checked": False},
            {"item": "Front/back looks match authenticated Magic jobs", "checked": False},
            {"item": "Measurements marked Designer vs Estimate vs Empty", "checked": False},
            {"item": "No fabricated opposite side or cutting figure", "checked": False},
            {"item": "Patternmaker sign-off before production", "checked": False},
        ],
        "look_notes": (look_summary or "").strip()[:500],
        "designer_notes": "",
        "disclaimer": (
            "DRAFT / UNVERIFIED. Values may be designer-entered or estimates. "
            "Not a graded production pattern. Patternmaker review required."
        ),
    }


def normalize_measured(raw: Any, *, default_unit: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _mv(unit=default_unit)
    source = raw.get("source") if isinstance(raw.get("source"), str) else "empty"
    if source not in ALLOWED_SOURCES:
        source = "empty"
    value = raw.get("value")
    if value is not None and not isinstance(value, (int, float, str)):
        value = None
    unit = raw.get("unit") if isinstance(raw.get("unit"), str) else default_unit
    note = raw.get("note") if isinstance(raw.get("note"), str) else None
    return _mv(value, unit=unit, source=source, note=note)


def merge_spec(base: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    """Shallow-merge top-level sections; normalize measurement dicts."""
    out = deepcopy(base) if base else default_spec()
    if not patch:
        return out
    units = patch.get("units") if isinstance(patch.get("units"), str) else out.get("units", "cm")
    out["units"] = units
    for key in ("size_system", "sample_size", "look_notes", "designer_notes", "disclaimer"):
        if key in patch and isinstance(patch[key], str):
            out[key] = patch[key][:2000] if key.endswith("notes") or key == "disclaimer" else patch[key][:120]
    if "quantity" in patch:
        q = patch["quantity"]
        out["quantity"] = q if isinstance(q, (int, float)) or q is None else out.get("quantity")

    if isinstance(patch.get("fit"), dict):
        fit = out.setdefault("fit", {})
        if "silhouette" in patch["fit"] and isinstance(patch["fit"]["silhouette"], str):
            fit["silhouette"] = patch["fit"]["silhouette"][:120]
        if "ease" in patch["fit"]:
            fit["ease"] = normalize_measured(patch["fit"]["ease"], default_unit=units)

    if isinstance(patch.get("body"), dict):
        body = out.setdefault("body", {})
        for key in _BODY_KEYS:
            if key in patch["body"]:
                body[key] = normalize_measured(patch["body"][key], default_unit=units)

    if isinstance(patch.get("garment"), dict):
        garment = out.setdefault("garment", {})
        for key in _GARMENT_KEYS:
            if key in patch["garment"]:
                garment[key] = normalize_measured(patch["garment"][key], default_unit=units)

    if isinstance(patch.get("materials"), dict):
        mats = out.setdefault("materials", {})
        for section in ("shell", "lining", "interfacing"):
            if isinstance(patch["materials"].get(section), dict):
                mats[section] = {**mats.get(section, {}), **patch["materials"][section]}

    if isinstance(patch.get("closures"), dict):
        out["closures"] = {**out.get("closures", {}), **patch["closures"]}

    if "seam_allowance" in patch:
        out["seam_allowance"] = normalize_measured(patch["seam_allowance"], default_unit=units)

    for list_key in ("trims", "bom", "construction", "pattern_pieces", "qc_checklist"):
        if isinstance(patch.get(list_key), list):
            out[list_key] = patch[list_key][:100]

    out["schema_version"] = "1.0"
    return out


def style_code_from_look(look_id: Any) -> str:
    text = str(look_id).replace("-", "").upper()
    return f"FR-{text[:4]}"
