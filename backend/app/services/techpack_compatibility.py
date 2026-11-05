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
_DESIGNER_AUTHOR_SOURCES = frozenset(
    {
        "designer",
        "user",
        "designer_confirmed",
        "confirmed",
    }
)
_ESTIMATE_SOURCES = frozenset(
    {
        "",
        "estimate",
        "ai",
        "heuristic",
        "proposed",
        "unverified",
        "validated",
        "system",
    }
)

_CLOSURE_ANTI_INVENTION_INSTRUCTION = (
    "Confirm closure with designer — do not invent zipper, buttons, or drawstring "
    "when none is verified on the source design. Finish openings as designed; press."
)


def _review_status_of(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("review_status") or value.get("review_state") or "").strip().lower()


def _is_explicitly_confirmed_meta(value: Any) -> bool:
    """Match manufacturing semantics: source=designer alone is provenance, not approval."""
    if not isinstance(value, dict):
        return False
    status = _review_status_of(value)
    if status in _UNRESOLVED_REVIEW:
        return False
    if value.get("designer_confirmed") is True:
        return True
    return status in _CONFIRMED_REVIEW


def _is_designer_authored(value: Any) -> bool:
    """True for designer-entered content that must not be silently rewritten."""
    if not isinstance(value, dict):
        return False
    if _is_explicitly_confirmed_meta(value):
        return True
    source = str(value.get("source") or "").strip().lower()
    return source in _DESIGNER_AUTHOR_SOURCES


def _mentions_closure_hardware(text: str) -> bool:
    lower = text.lower()
    return any(tok in lower for tok in _CLOSURE_HARDWARE_TOKENS)


def _already_anti_invention_text(text: str) -> bool:
    lower = text.lower()
    return "do not invent zipper" in lower or "do not invent zipper/buttons" in lower


def closure_hardware_named(
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> bool:
    """True when zipper/buttons/drawstring are named on the piece or analysis."""
    closures = piece.get("closures") if isinstance(piece, dict) else None
    closures_d = closures if isinstance(closures, dict) else {}
    type_txt = _text(closures_d.get("type") or closures_d.get("display_type"))
    notes_txt = _text(closures_d.get("notes"))
    visible = _text(analysis.get("closure_visible") if isinstance(analysis, dict) else "")
    blob = f"{type_txt} {notes_txt} {visible}".strip()
    if not blob:
        return False
    if type_txt in {"true", "false", "1", "0", "yes", "no"}:
        return False
    if any(tok in type_txt for tok in ("zip", "button", "draw", "snap", "hook", "placket")):
        return True
    if any(tok in blob for tok in _CLOSURE_HARDWARE_TOKENS) and not any(
        tok in blob for tok in _CLOSURE_NONE_TOKENS
    ):
        return True
    return False


def closure_lacks_hardware_evidence(
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> bool:
    """True for pull-on / none / empty — inventing zipper install is unsupported."""
    return not closure_hardware_named(analysis=analysis, piece=piece)


def closure_hardware_confirmed(
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> bool:
    """True only when closures are explicitly confirmed AND name hardware."""
    closures = piece.get("closures") if isinstance(piece, dict) else None
    if not _is_explicitly_confirmed_meta(closures):
        return False
    return closure_hardware_named(analysis=analysis, piece=piece)


def closure_hardware_unverified(
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> bool:
    """True when zipper/buttons/drawstring must not be asserted as manufacturing fact."""
    return not closure_hardware_confirmed(analysis=analysis, piece=piece)


def filter_construction_steps(
    steps: list[Any],
    *,
    analysis: dict[str, Any] | None,
    piece: dict[str, Any] | None = None,
    warnings_out: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Adjust AI/estimate sleeve/closure boilerplate; never destroy designer-authored steps."""
    if not steps:
        return steps
    sleeveless = is_sleeveless_analysis(analysis)
    lacks_hw = closure_lacks_hardware_evidence(analysis=analysis, piece=piece)
    hw_confirmed = closure_hardware_confirmed(analysis=analysis, piece=piece)
    out: list[Any] = []
    for step in steps:
        text = ""
        if isinstance(step, dict):
            text = str(step.get("instruction") or step.get("text") or "")
        else:
            text = str(step)
        lower = text.lower()
        protected = _is_designer_authored(step)

        if sleeveless and ("set sleeve" in lower or "set sleeves" in lower):
            if protected:
                if isinstance(step, dict):
                    note = str(step.get("note") or step.get("review_message") or "")
                    msg = (
                        "REVIEW: sleeveless analysis conflicts with sleeve-set instruction — "
                        "designer text preserved."
                    )
                    if "REVIEW: sleeveless analysis conflicts" in note:
                        out.append(step)
                    else:
                        out.append(
                            {
                                **step,
                                "review_status": step.get("review_status")
                                if _is_explicitly_confirmed_meta(step)
                                else "needs_review",
                                "review_message": msg,
                                "note": ((note + " · " if note else "") + msg).strip(" ·"),
                            }
                        )
                        if warnings_out is not None:
                            warnings_out.append(
                                {
                                    "code": "construction_sleeve_conflict",
                                    "piece_id": (piece or {}).get("id")
                                    if isinstance(piece, dict)
                                    else None,
                                    "message": msg,
                                    "severity": "warning",
                                }
                            )
                else:
                    out.append(step)
                continue
            if isinstance(step, dict) and (
                _review_status_of(step) == "adjusted_for_garment"
                or "do not set sleeves" in lower
            ):
                out.append(step)
                continue
            if isinstance(step, dict):
                out.append(
                    {
                        **step,
                        "instruction": (
                            "Finish armholes for sleeveless design (do not set sleeves — "
                            f"AI sleeves: {analysis.get('sleeves') if analysis else 'sleeveless'})."
                        ),
                        "review_status": "adjusted_for_garment",
                        "source": step.get("source") or "estimate",
                    }
                )
            else:
                out.append(
                    "Finish armholes for sleeveless design (do not set sleeves)."
                )
            continue

        if _mentions_closure_hardware(text):
            if _already_anti_invention_text(text) or (
                isinstance(step, dict)
                and _review_status_of(step) == "adjusted_for_garment"
            ):
                out.append(step)
                continue
            if protected:
                if lacks_hw:
                    msg = (
                        "REVIEW: construction mentions zipper/buttons/drawstring while closure "
                        "field is unverified or pull-on — designer instruction preserved."
                    )
                    if isinstance(step, dict):
                        note = str(step.get("note") or step.get("review_message") or "")
                        if "construction mentions zipper" in note:
                            out.append(step)
                        else:
                            out.append(
                                {
                                    **step,
                                    "review_status": step.get("review_status")
                                    if _is_explicitly_confirmed_meta(step)
                                    else "needs_review",
                                    "review_message": msg,
                                    "note": ((note + " · " if note else "") + msg).strip(
                                        " ·"
                                    ),
                                }
                            )
                            if warnings_out is not None:
                                warnings_out.append(
                                    {
                                        "code": "construction_closure_conflict",
                                        "piece_id": (piece or {}).get("id")
                                        if isinstance(piece, dict)
                                        else None,
                                        "message": msg,
                                        "severity": "warning",
                                    }
                                )
                    else:
                        out.append(step)
                else:
                    out.append(step)
                continue
            # AI / estimate boilerplate only.
            if lacks_hw:
                if isinstance(step, dict):
                    out.append(
                        {
                            **step,
                            "instruction": _CLOSURE_ANTI_INVENTION_INSTRUCTION,
                            "review_status": "adjusted_for_garment",
                            "source": step.get("source") or "estimate",
                        }
                    )
                else:
                    out.append(_CLOSURE_ANTI_INVENTION_INSTRUCTION)
                continue
            if not hw_confirmed and isinstance(step, dict):
                # Named but unconfirmed hardware → keep text, mark UNVERIFIED (idempotent).
                if _review_status_of(step) == "proposed_unverified":
                    out.append(step)
                else:
                    out.append(
                        {
                            **step,
                            "review_status": "proposed_unverified",
                            "review_message": (
                                "UNVERIFIED closure hardware — confirm zipper/buttons "
                                "before manufacturing."
                            ),
                        }
                    )
                continue
        out.append(step)
    return out


def filter_bom_rows(
    rows: list[dict[str, Any]],
    *,
    analysis: dict[str, Any] | None = None,
    piece: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Preserve confirmed BOM hardware; mark unverified estimate lines only."""
    if not rows:
        return rows
    lacks_hw = closure_lacks_hardware_evidence(analysis=analysis, piece=piece)
    hw_confirmed = closure_hardware_confirmed(analysis=analysis, piece=piece)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = _text(row.get("item"))
        notes = _text(row.get("notes"))
        blob = f"{item} {notes}"
        if not any(tok in blob for tok in _CLOSURE_HARDWARE_TOKENS):
            out.append(row)
            continue
        if _is_designer_authored(row) or _is_explicitly_confirmed_meta(row):
            out.append(row)
            continue
        if hw_confirmed:
            out.append(row)
            continue
        # Idempotent unverified marker.
        if str(row.get("review_state") or row.get("review_status") or "").lower() in {
            "proposed_unverified",
            "unverified",
        } and str(row.get("qty") or "").upper() == "UNVERIFIED":
            out.append(row)
            continue
        label = str(row.get("item") or "Closure hardware")
        if lacks_hw:
            label = "Closure hardware (if designed)"
        out.append(
            {
                **row,
                "item": label,
                "qty": "UNVERIFIED",
                "notes": (
                    str(row.get("notes") or "").strip()
                    + (" · " if str(row.get("notes") or "").strip() else "")
                    + "UNVERIFIED — confirm zipper/buttons/drawstring before cutting."
                ).strip(" ·"),
                "source": row.get("source") or "unverified",
                "review_state": "proposed_unverified",
                "review_status": "proposed_unverified",
            }
        )
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
