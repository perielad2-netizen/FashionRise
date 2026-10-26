"""Garment / material / measurement compatibility helpers for Create Real Design PDFs.

Never invent corrections — emit review warnings and filter unsupported generic steps.
"""

from __future__ import annotations

from typing import Any

from app.services.techpack_garments import POM_LABELS

_SLEEVELESS_TOKENS = (
    "sleeveless",
    "no sleeve",
    "without sleeve",
    "strap",
    "spaghetti",
    "tank",
    "halter",
    "cami",
)

_FABRIC_FAMILIES: dict[str, frozenset[str]] = {
    "silk": frozenset({"silk", "satin", "charmeuse", "chiffon", "habotai"}),
    "cotton": frozenset({"cotton", "jersey", "poplin", "twill", "denim", "canvas", "voile"}),
    "wool": frozenset({"wool", "woolen", "woollen", "cashmere", "tweed", "flannel"}),
    "linen": frozenset({"linen", "ramie"}),
    "polyester": frozenset({"polyester", "poly", "nylon", "acrylic", "viscose", "rayon"}),
    "leather": frozenset({"leather", "suede", "nappa"}),
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def is_sleeveless_analysis(analysis: dict[str, Any] | None) -> bool:
    if not isinstance(analysis, dict):
        return False
    sleeves = _text(analysis.get("sleeves"))
    if not sleeves:
        return False
    return any(tok in sleeves for tok in _SLEEVELESS_TOKENS)


def fabric_family(token: str) -> str | None:
    t = _text(token)
    if not t or t in {"unknown", "—", "-", "n/a"}:
        return None
    for family, aliases in _FABRIC_FAMILIES.items():
        if family in t or any(a in t for a in aliases):
            return family
    return None


def material_contradiction(shell_name: str, composition: str) -> str | None:
    name_fam = fabric_family(shell_name)
    comp_fam = fabric_family(composition)
    if name_fam and comp_fam and name_fam != comp_fam:
        return (
            f"Material review: shell described as “{shell_name}” but composition is "
            f"“{composition}”. These look inconsistent — keep the owner values and confirm "
            f"before production."
        )
    return None


def collect_compatibility_warnings(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Additive review warnings (do not delete owner values)."""
    warnings: list[dict[str, Any]] = []
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    pieces = outfit.get("pieces") if isinstance(outfit.get("pieces"), list) else []
    for piece in pieces:
        if not isinstance(piece, dict):
            continue
        pid = piece.get("id")
        illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
        mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
        shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
        name = str(shell.get("name") or shell.get("suggestion") or "")
        composition = str(shell.get("composition") or "")
        contrad = material_contradiction(name, composition)
        if contrad:
            warnings.append(
                {
                    "code": "material_composition_mismatch",
                    "piece_id": pid,
                    "message": contrad,
                    "severity": "warning",
                }
            )

        sleeveless = is_sleeveless_analysis(analysis)
        finished = (
            piece.get("finished_measurements")
            if isinstance(piece.get("finished_measurements"), dict)
            else {}
        )
        if sleeveless:
            sleeve_cell = finished.get("sleeve_length")
            if isinstance(sleeve_cell, dict) and isinstance(sleeve_cell.get("value"), (int, float)):
                warnings.append(
                    {
                        "code": "measurement_garment_mismatch",
                        "piece_id": pid,
                        "pom": "sleeve_length",
                        "value": sleeve_cell.get("value"),
                        "unit": sleeve_cell.get("unit"),
                        "message": (
                            f"{POM_LABELS.get('sleeve_length', 'Sleeve length')} "
                            f"({sleeve_cell.get('value')} {sleeve_cell.get('unit') or 'cm'}) "
                            f"may not apply to a sleeveless garment "
                            f"(AI sleeves: {analysis.get('sleeves')}). "
                            f"Owner value preserved — review before manufacturing."
                        ),
                        "severity": "warning",
                    }
                )
                sleeve_cell["review_status"] = "needs_review"
                sleeve_cell["confidence"] = "low"
    return warnings


def filter_construction_steps(
    steps: list[Any],
    *,
    analysis: dict[str, Any] | None,
) -> list[Any]:
    """Drop or mark sleeve-set instructions when analysis indicates sleeveless."""
    if not steps:
        return steps
    sleeveless = is_sleeveless_analysis(analysis)
    out: list[Any] = []
    for step in steps:
        text = ""
        if isinstance(step, dict):
            text = str(step.get("instruction") or step.get("text") or "")
        else:
            text = str(step)
        lower = text.lower()
        if sleeveless and ("set sleeve" in lower or "set sleeves" in lower):
            if isinstance(step, dict):
                out.append(
                    {
                        **step,
                        "instruction": (
                            "Finish armholes for sleeveless design (do not set sleeves — "
                            f"AI sleeves: {analysis.get('sleeves') if analysis else 'sleeveless'})."
                        ),
                        "review_status": "adjusted_for_garment",
                        "source": step.get("source") or "validated",
                    }
                )
            else:
                out.append(
                    "Finish armholes for sleeveless design (do not set sleeves)."
                )
            continue
        out.append(step)
    return out


def filter_pattern_inventory(
    rows: list[dict[str, Any]],
    *,
    analysis: dict[str, Any] | None,
    ai_suggested: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Keep inventory honest for sleeveless designs; mark AI-only extras as proposed."""
    sleeveless = is_sleeveless_analysis(analysis)
    out: list[dict[str, Any]] = []
    for row in rows:
        name = _text(row.get("name"))
        if sleeveless and "sleeve" in name and "if sleeved" in name:
            out.append(
                {
                    **row,
                    "cut_qty": None,
                    "source": "unresolved",
                    "notes": (
                        (str(row.get("notes") or "") + " ").strip()
                        + "Omitted quantity — garment appears sleeveless; not a validated cut."
                    ).strip(),
                    "review_state": "proposed_unverified",
                }
            )
            continue
        if sleeveless and "sleeve" in name and "if" not in name:
            out.append(
                {
                    **row,
                    "cut_qty": None,
                    "source": "unresolved",
                    "notes": "Sleeve piece not confirmed for sleeveless analysis — review.",
                    "review_state": "proposed_unverified",
                }
            )
            continue
        out.append({**row, "review_state": row.get("review_state") or "approved_template"})

    # Surface AI-suggested extras that are not already listed, as proposed only.
    existing = {_text(r.get("name")) for r in out}
    for sug in ai_suggested or []:
        if not isinstance(sug, dict):
            continue
        nm = str(sug.get("name") or "").strip()
        if not nm or _text(nm) in existing:
            continue
        out.append(
            {
                "id": str(sug.get("id") or f"AI-{len(out)+1}"),
                "name": nm,
                "cut_qty": None,
                "fabric": "shell",
                "grainline": "straight",
                "fold": "none",
                "seam_allowance_cm": 1.0,
                "source": "ai",
                "notes": str(sug.get("notes") or "AI-proposed addition — not a validated cut quantity."),
                "review_state": "proposed_unverified",
            }
        )
    return out
