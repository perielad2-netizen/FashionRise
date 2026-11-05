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
        sleeve_cell = finished.get("sleeve_length")
        sleeves_txt = _text(analysis.get("sleeves"))
        if sleeveless and isinstance(sleeve_cell, dict) and isinstance(
            sleeve_cell.get("value"), (int, float)
        ):
            warnings.append(
                {
                    "code": "measurement_garment_mismatch",
                    "piece_id": pid,
                    "pom": "sleeve_length",
                    "value": sleeve_cell.get("value"),
                    "unit": sleeve_cell.get("unit"),
                    "message": (
                        f"REVIEW: {POM_LABELS.get('sleeve_length', 'Sleeve length')} "
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
            note = str(sleeve_cell.get("note") or "")
            if "REVIEW" not in note:
                sleeve_cell["note"] = (
                    (note + " · " if note else "")
                    + "REVIEW: sleeveless analysis — sleeve length may not apply"
                ).strip(" ·")
        elif isinstance(sleeve_cell, dict) and isinstance(sleeve_cell.get("value"), (int, float)):
            assumptions = sleeve_cell.get("assumptions")
            assumption_blob = " ".join(str(a) for a in assumptions) if isinstance(assumptions, list) else ""
            note_blob = f"{sleeve_cell.get('note') or ''} {assumption_blob}".lower()
            three_q = any(
                tok in sleeves_txt for tok in ("three-quarter", "3/4", "three quarter", "elbow")
            )
            long_assumed = "long-sleeve" in note_blob or "long sleeve" in note_blob
            if three_q and long_assumed:
                warnings.append(
                    {
                        "code": "measurement_sleeve_length_assumption",
                        "piece_id": pid,
                        "pom": "sleeve_length",
                        "value": sleeve_cell.get("value"),
                        "unit": sleeve_cell.get("unit"),
                        "message": (
                            "REVIEW: sleeve length used a long-sleeve assumption while analysis "
                            f"describes three-quarter sleeves ({analysis.get('sleeves')}). "
                            "Owner/calculated value preserved — confirm length before manufacturing."
                        ),
                        "severity": "warning",
                    }
                )
                sleeve_cell["review_status"] = "needs_review"
                sleeve_cell["confidence"] = "low"
    return warnings


_CLOSURE_NONE_TOKENS = (
    "none",
    "n/a",
    "na",
    "not visible",
    "not verified",
    "no closure",
    "no buttons",
    "no zipper",
    "pull-on",
    "pull on",
    "open",
    "—",
    "-",
)

_CLOSURE_HARDWARE_TOKENS = (
    "zipper",
    "zip ",
    " zip",
    "button",
    "placket",
    "drawstring",
    "drawcord",
    "snap",
    "hook-and-eye",
    "hook and eye",
)


def closure_hardware_unverified(
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> bool:
    """True when no verified zipper/buttons/drawstring should be asserted."""
    closures = piece.get("closures") if isinstance(piece, dict) else None
    closures_d = closures if isinstance(closures, dict) else {}
    type_txt = _text(closures_d.get("type"))
    notes_txt = _text(closures_d.get("notes"))
    visible = _text(analysis.get("closure_visible") if isinstance(analysis, dict) else "")
    blob = f"{type_txt} {notes_txt} {visible}".strip()
    if not blob:
        return True
    if any(tok in blob for tok in _CLOSURE_HARDWARE_TOKENS):
        # Explicit hardware named — keep (may still be estimate; readiness gate handles that).
        if any(tok in blob for tok in _CLOSURE_NONE_TOKENS) and not any(
            hw in type_txt for hw in ("zip", "button", "draw", "snap", "hook")
        ):
            return True
        return False
    if any(tok in blob for tok in _CLOSURE_NONE_TOKENS):
        return True
    # Boolean-ish leftovers (legacy “True”/“False” closure strings) are not hardware.
    if type_txt in {"true", "false", "1", "0"}:
        return True
    return False


def filter_construction_steps(
    steps: list[Any],
    *,
    analysis: dict[str, Any] | None,
    piece: dict[str, Any] | None = None,
) -> list[Any]:
    """Adjust sleeve-set / invented-closure steps to match verified garment evidence."""
    if not steps:
        return steps
    sleeveless = is_sleeveless_analysis(analysis)
    no_hw = closure_hardware_unverified(analysis=analysis, piece=piece)
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
        if no_hw and any(tok in lower for tok in _CLOSURE_HARDWARE_TOKENS):
            replacement = (
                "Confirm closure with designer — do not invent zipper, buttons, or drawstring "
                "when none is verified on the source design. Finish openings as designed; press."
            )
            if isinstance(step, dict):
                out.append(
                    {
                        **step,
                        "instruction": replacement,
                        "review_status": "adjusted_for_garment",
                        "source": step.get("source") or "validated",
                    }
                )
            else:
                out.append(replacement)
            continue
        out.append(step)
    return out


def filter_bom_rows(
    rows: list[dict[str, Any]],
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Drop invented closure hardware BOM lines when no closure is verified."""
    if not rows:
        return rows
    if not closure_hardware_unverified(analysis=analysis, piece=piece):
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        item = _text(row.get("item"))
        notes = _text(row.get("notes"))
        blob = f"{item} {notes}"
        if any(tok in blob for tok in _CLOSURE_HARDWARE_TOKENS):
            out.append(
                {
                    **row,
                    "item": "Closure hardware (if designed)",
                    "qty": "UNVERIFIED",
                    "notes": (
                        "Do not invent zipper/buttons/drawstring — confirm with designer "
                        "before cutting."
                    ),
                    "source": "unverified",
                    "review_state": "proposed_unverified",
                }
            )
            continue
        out.append(row)
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
        # Preserve explicit operator/reviewer states; never invent approvals for AI/estimate rows.
        existing_review = row.get("review_state")
        if existing_review:
            out.append(dict(row))
            continue
        source = _text(row.get("source"))
        if source in {"template", "approved", "designer", "validated"}:
            out.append({**row, "review_state": "approved_template"})
        else:
            out.append({**row, "review_state": "proposed_unverified"})

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
