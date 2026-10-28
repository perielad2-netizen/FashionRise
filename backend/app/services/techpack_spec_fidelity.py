"""Deterministic designer-spec ↔ generated-text fidelity checks (offline, $0).

These checks compare structured garment decisions (closures, color treatments)
to generated textual captions/annotations/analysis fields. They do **not** prove
pixels are correct — contradictions only force review / strip manufacturing
evidence.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


_BUTTON_TOKENS = (
    "button",
    "buttons",
    "buttoned",
    "button-front",
    "button front",
    "placket",
    "snap",
    "snaps",
)
_ZIPPER_TOKENS = (
    "zipper",
    "zippered",
    "zip",
    "fly (zipper)",
    "fly(zipper)",
    "zip fly",
    "zipper fly",
)
_FLY_ZIP_PATTERNS = (
    re.compile(r"\bfly\s*\(\s*zipper\s*\)", re.I),
    re.compile(r"\bzipper\s*fly\b", re.I),
    re.compile(r"\bzip\s*fly\b", re.I),
    re.compile(r"\bfly\b.*\bzipper\b", re.I),
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text_blob(*parts: Any) -> str:
    bits: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple)):
            bits.extend(str(x) for x in part if x is not None)
        else:
            bits.append(str(part))
    return " ".join(bits).strip().lower()


def normalize_color_treatment(raw: Any) -> dict[str, Any] | None:
    """Normalize per-garment color-treatment intent (gradient / block / solid).

    Preserves designer confirmation + provenance. Returns None when absent.
    """
    if not isinstance(raw, dict):
        return None
    out = {
        "mode": str(raw.get("mode") or raw.get("type") or "").strip().lower() or None,
        "stops": list(raw.get("stops") or raw.get("colors") or [])
        if isinstance(raw.get("stops") or raw.get("colors"), list)
        else [],
        "named_colors": list(raw.get("named_colors") or [])
        if isinstance(raw.get("named_colors"), list)
        else [],
        "direction": str(raw.get("direction") or "").strip() or None,
        "placement": str(raw.get("placement") or "").strip() or None,
        "designer_confirmed": bool(raw.get("designer_confirmed")),
        "source": str(raw.get("source") or "").strip() or None,
        "notes": str(raw.get("notes") or "").strip() or None,
    }
    # Drop empty shells.
    if not any(
        [
            out["mode"],
            out["stops"],
            out["named_colors"],
            out["direction"],
            out["placement"],
            out["notes"],
        ]
    ):
        return None
    return out


def piece_color_treatment(piece: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve color-treatment from piece materials / explicit field / color_hint."""
    direct = normalize_color_treatment(piece.get("color_treatment"))
    if direct:
        return direct
    mats = _as_dict(piece.get("materials"))
    shell = _as_dict(mats.get("shell"))
    nested = normalize_color_treatment(shell.get("color_treatment") or mats.get("color_treatment"))
    if nested:
        return nested
    hint = str(piece.get("color_hint") or "").strip()
    lower = hint.lower()
    if "gradient" in lower or "ombre" in lower or "ombré" in lower:
        return {
            "mode": "gradient",
            "stops": [],
            "named_colors": [hint] if hint else [],
            "direction": None,
            "placement": None,
            "designer_confirmed": False,
            "source": str(piece.get("color_hint_source") or "color_hint"),
            "notes": hint or None,
        }
    if "two-tone" in lower or "two tone" in lower or "color-block" in lower or "color block" in lower:
        return {
            "mode": "color_block",
            "stops": [],
            "named_colors": [hint] if hint else [],
            "direction": None,
            "placement": None,
            "designer_confirmed": False,
            "source": str(piece.get("color_hint_source") or "color_hint"),
            "notes": hint or None,
        }
    return None


def color_treatment_prompt_contract(piece: dict[str, Any]) -> str:
    """Garment-specific color-treatment instruction fragment for image prompts."""
    ct = piece_color_treatment(piece)
    if not ct:
        hint = str(piece.get("color_hint") or "").strip()
        if hint:
            return (
                f"Designer color hint: {hint}. Preserve the reference photo color treatment; "
                "do not invent a hard two-tone split or simplify a gradient to a single flat color."
            )
        return (
            "Preserve the reference photo color treatment faithfully. "
            "Do not invent a hard two-tone split or flatten a gradient to a single named color."
        )
    mode = ct.get("mode") or "unspecified"
    stops = ", ".join(str(s) for s in (ct.get("stops") or [])[:8])
    named = ", ".join(str(s) for s in (ct.get("named_colors") or [])[:8])
    direction = ct.get("direction") or "as in reference"
    placement = ct.get("placement") or "as in reference"
    confirmed = "designer-confirmed" if ct.get("designer_confirmed") else "designer-specified"
    return (
        f"COLOR TREATMENT ({confirmed}): mode={mode}; stops=[{stops}]; named=[{named}]; "
        f"direction={direction}; placement={placement}. "
        "Honor this structured intent over generic model defaults. "
        "If mode=gradient, render a continuous blend — never a hard color-block split. "
        "If mode=color_block/two-tone, keep the declared placement. "
        "Do not simplify the garment colorway to a single unrelated flat color (e.g. 'red')."
    )


def designer_closure_requirement(piece: dict[str, Any]) -> str | None:
    """Return a normalized designer closure family when explicitly specified."""
    closures = _as_dict(piece.get("closures"))
    blob = _text_blob(
        closures.get("type"),
        closures.get("display_type"),
        closures.get("notes"),
        closures.get("hardware"),
    )
    if not blob:
        return None
    if any(tok in blob for tok in _BUTTON_TOKENS) and not any(
        tok in blob for tok in ("zipper", "zip fly", "fly (zipper)")
    ):
        # Prefer buttons when designer named buttons (zip mention only as secondary).
        if "zipper" in blob and "button" not in blob:
            return "zipper"
        return "buttons"
    if any(tok in blob for tok in _ZIPPER_TOKENS) or any(p.search(blob) for p in _FLY_ZIP_PATTERNS):
        return "zipper"
    if "elastic" in blob or "drawcord" in blob or "drawstring" in blob:
        return "elastic_or_drawcord"
    if "hook" in blob and "eye" in blob:
        return "hook_and_eye"
    # Unrecognized but present — keep raw for prompt contract.
    raw = str(closures.get("display_type") or closures.get("type") or "").strip()
    return raw.lower() or None


def closure_prompt_contract(piece: dict[str, Any]) -> str:
    """Strong garment-specific closure instruction for flats/details."""
    req = designer_closure_requirement(piece)
    closures = _as_dict(piece.get("closures"))
    display = str(
        closures.get("display_type") or closures.get("type") or req or "unspecified"
    ).strip()
    if not req:
        return (
            f"Closure: {display}. If the designer specification is empty, omit invented "
            "zipper/fly/button callouts rather than defaulting to a generic fly zipper."
        )
    if req == "buttons":
        return (
            f"DESIGNER CLOSURE REQUIREMENT (authoritative): {display} — BUTTONS. "
            "Do NOT draw or label a zipper fly / FLY (ZIPPER). "
            "Show button / buttonhole / placket construction consistent with the designer spec. "
            "Generic bottoms defaults must not override this explicit decision."
        )
    if req == "zipper":
        return (
            f"DESIGNER CLOSURE REQUIREMENT (authoritative): {display} — ZIPPER. "
            "Do NOT substitute buttons when a zipper is specified."
        )
    return (
        f"DESIGNER CLOSURE REQUIREMENT (authoritative): {display} ({req}). "
        "Do not substitute a different closure family from generic category defaults."
    )


def _caption_implies_zipper_fly(text: str) -> bool:
    lower = text.lower()
    if any(p.search(lower) for p in _FLY_ZIP_PATTERNS):
        return True
    if "fly" in lower and "zipper" in lower:
        return True
    if "fly (zipper)" in lower:
        return True
    return False


def _caption_implies_buttons(text: str) -> bool:
    lower = text.lower()
    return any(tok in lower for tok in _BUTTON_TOKENS)


def collect_generated_caption_text(
    *,
    artifact_meta: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
) -> str:
    """Gather textual captions/annotations from artifact metadata + vision analysis."""
    meta = artifact_meta if isinstance(artifact_meta, dict) else {}
    ana = analysis if isinstance(analysis, dict) else {}
    parts = [
        meta.get("caption"),
        meta.get("captions"),
        meta.get("annotations"),
        meta.get("labels"),
        meta.get("callouts"),
        meta.get("closure_visible"),
        meta.get("review_message"),
        ana.get("closure_visible"),
        ana.get("distinctive_features"),
        ana.get("construction_notes"),
        ana.get("panels_seams"),
        ana.get("assumptions"),
    ]
    # Nested illustration analysis often lives under meta["analysis"].
    nested = meta.get("analysis") if isinstance(meta.get("analysis"), dict) else {}
    parts.extend(
        [
            nested.get("closure_visible"),
            nested.get("distinctive_features"),
            nested.get("construction_notes"),
        ]
    )
    return _text_blob(*parts)


def detect_closure_caption_mismatch(
    piece: dict[str, Any],
    *,
    artifact_meta: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    caption_text: str | None = None,
) -> dict[str, Any] | None:
    """Compare structured designer closure to generated caption/analysis text.

    Returns a mismatch descriptor or None. Text agreement does **not** prove
    correct pixels — only flags contradictions for human review.
    """
    req = designer_closure_requirement(piece)
    if not req:
        return None
    text = (caption_text or "").strip().lower()
    if not text:
        text = collect_generated_caption_text(artifact_meta=artifact_meta, analysis=analysis)
    if not text:
        return None

    if req == "buttons" and _caption_implies_zipper_fly(text) and not _caption_implies_buttons(text):
        return {
            "code": "closure_caption_mismatch",
            "designer_requirement": "buttons",
            "generated_implies": "zipper_fly",
            "message": (
                "Structured designer closure requires buttons, but generated captions/"
                "annotations describe a zipper fly (e.g. FLY (ZIPPER)). "
                "Artwork must be reviewed — text checks do not prove pixels."
            ),
            "manufacturing_evidence": False,
            "review_state": "proposed_unverified",
        }
    if req == "zipper" and _caption_implies_buttons(text) and not _caption_implies_zipper_fly(text):
        # Soft: buttons mentioned without zipper when zipper required.
        if "button" in text and "zipper" not in text and "zip" not in text:
            return {
                "code": "closure_caption_mismatch",
                "designer_requirement": "zipper",
                "generated_implies": "buttons",
                "message": (
                    "Structured designer closure requires a zipper, but generated "
                    "captions/annotations describe buttons instead. "
                    "Artwork must be reviewed — text checks do not prove pixels."
                ),
                "manufacturing_evidence": False,
                "review_state": "proposed_unverified",
            }
    return None


def detect_color_treatment_text_mismatch(
    piece: dict[str, Any],
    *,
    rendered_color_text: str | None = None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Flag when structured gradient intent is flattened to a single unrelated color label."""
    ct = piece_color_treatment(piece)
    if not ct or ct.get("mode") not in {"gradient", "ombre", "ombré"}:
        return None
    blob = _text_blob(
        rendered_color_text,
        (analysis or {}).get("colors") if isinstance(analysis, dict) else None,
        piece.get("garment_color"),
    )
    if not blob:
        return None
    # Flattened single hue with no gradient language while designer required gradient.
    if "gradient" not in blob and "ombre" not in blob and "ombré" not in blob:
        if re.fullmatch(r"red|black|burgundy|navy|blue|green|white|yellow|purple", blob.strip()):
            return {
                "code": "color_treatment_simplified",
                "designer_mode": ct.get("mode"),
                "rendered": blob.strip(),
                "message": (
                    f"Designer color treatment is {ct.get('mode')}, but rendered/spec color "
                    f"text simplified to “{blob.strip()}”. Flag for manual review — "
                    "do not silently accept a different finish."
                ),
                "manufacturing_evidence": False,
                "review_state": "proposed_unverified",
            }
    return None


def apply_fidelity_gates_to_artifact_meta(
    piece: dict[str, Any],
    *,
    kind: str,
    artifact_meta: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Annotate artifact metadata when deterministic text contradictions are found."""
    out = dict(artifact_meta)
    mismatches: list[dict[str, Any]] = []
    if kind == "detail_callouts" or kind.startswith("flat"):
        closure_hit = detect_closure_caption_mismatch(
            piece, artifact_meta=out, analysis=analysis
        )
        if closure_hit:
            mismatches.append(closure_hit)
    color_hit = detect_color_treatment_text_mismatch(
        piece,
        rendered_color_text=str(out.get("garment_color") or out.get("colors") or ""),
        analysis=analysis,
    )
    if color_hit:
        mismatches.append(color_hit)

    if not mismatches:
        return out

    out["fidelity_mismatches"] = mismatches
    out["manufacturing_evidence"] = False
    # Keep include=True so owners can see and review; never claim manufacturing evidence.
    prior = str(out.get("review_state") or "").strip().lower()
    if prior not in {"rejected_category_mismatch", "excluded_mismatch", "rejected"}:
        out["review_state"] = "proposed_unverified"
    out["review_message"] = mismatches[0]["message"]
    out["preview_include"] = True
    return out


def stamp_color_treatment_onto_piece(piece: dict[str, Any]) -> dict[str, Any]:
    """Ensure color_treatment is explicitly present when inferable (non-destructive)."""
    out = deepcopy(piece)
    existing = normalize_color_treatment(out.get("color_treatment"))
    if existing:
        out["color_treatment"] = existing
        return out
    inferred = piece_color_treatment(out)
    if inferred:
        out["color_treatment"] = inferred
    return out


def format_color_treatment_for_pdf(piece: dict[str, Any]) -> str:
    """Human-readable color-treatment line for PDF assembly (structured intent)."""
    ct = piece_color_treatment(piece)
    if not ct:
        hint = str(piece.get("color_hint") or "").strip()
        return hint or "—"
    mode = ct.get("mode") or "unspecified"
    named = ", ".join(str(x) for x in (ct.get("named_colors") or ct.get("stops") or [])[:8]) or "—"
    direction = ct.get("direction") or "—"
    placement = ct.get("placement") or "—"
    confirmed = "designer-confirmed" if ct.get("designer_confirmed") else (ct.get("source") or "specified")
    line = (
        f"{mode} · colors: {named} · direction: {direction} · placement: {placement} · {confirmed}"
    )
    if ct.get("notes"):
        line += f" · {ct['notes'][:120]}"
    return line


def format_closure_for_pdf(piece: dict[str, Any]) -> tuple[str, str | None]:
    """Return (display_type, optional fidelity warning) for PDF materials block."""
    from app.services.techpack_manufacturing import normalize_closure_display

    closures = normalize_closure_display(_as_dict(piece.get("closures")))
    display = str(closures.get("display_type") or closures.get("type") or "—")
    warning = None
    fidelity = _as_dict(piece.get("fidelity"))
    closure_check = _as_dict(fidelity.get("closure_check"))
    if closure_check.get("mismatch"):
        warning = str(closure_check.get("message") or "")
    return display, warning or None


def closure_bom_row(piece: dict[str, Any]) -> dict[str, Any]:
    """BOM hardware row that mirrors structured closure (not a generic zipper guess)."""
    req = designer_closure_requirement(piece)
    closures = _as_dict(piece.get("closures"))
    raw = str(closures.get("display_type") or closures.get("type") or "").strip()
    designer = str(closures.get("source") or "").lower() in {
        "designer",
        "designer_confirmed",
        "user",
        "confirmed",
    } or closures.get("designer_confirmed") is True
    if req == "buttons":
        return {
            "item": raw or "Buttons",
            "qty": "TBD",
            "unit": "pcs",
            "source": "designer" if designer else "estimate",
            "notes": "Designer/structured buttons — do not substitute zipper",
        }
    if req == "zipper":
        return {
            "item": raw or "Zipper",
            "qty": "1",
            "unit": "pcs",
            "source": "designer" if designer else "estimate",
            "notes": "Designer/structured zipper — confirm length/type",
        }
    if req == "elastic_or_drawcord":
        return {
            "item": raw or "Elastic / drawcord",
            "qty": "1",
            "unit": "pcs",
            "source": "designer" if designer else "estimate",
            "notes": "Confirm elastic width / drawcord",
        }
    if req == "hook_and_eye":
        return {
            "item": raw or "Hook-and-eye",
            "qty": "TBD",
            "unit": "pcs",
            "source": "designer" if designer else "estimate",
            "notes": "Confirm count/placement",
        }
    return {
        "item": "Closure — NOT CONFIRMED",
        "qty": "TBD",
        "unit": "pcs",
        "source": "estimate",
        "notes": "Confirm zipper/button/elastic before cutting",
        "review_status": "needs_review",
    }


def preserve_designer_closure(piece: dict[str, Any], analysis: dict[str, Any] | None) -> dict[str, Any]:
    """Never overwrite designer-confirmed closure with AI vision guesses."""
    out = dict(piece)
    closures = _as_dict(out.get("closures"))
    designer_locked = bool(
        closures.get("designer_confirmed") is True
        or str(closures.get("source") or "").lower()
        in {"designer", "designer_confirmed", "user", "confirmed"}
        or str(closures.get("provenance") or "").lower()
        in {"designer", "designer_confirmed", "user_confirmed"}
    )
    if designer_locked and str(closures.get("type") or closures.get("display_type") or "").strip():
        # Keep designer type; record AI observation for mismatch gates only.
        ana = analysis if isinstance(analysis, dict) else {}
        if ana.get("closure_visible"):
            closures = {
                **closures,
                "ai_observed_closure_visible": str(ana.get("closure_visible"))[:120],
            }
            out["closures"] = closures
        return out
    return out


def apply_piece_fidelity_summary(piece: dict[str, Any]) -> dict[str, Any]:
    """Attach piece-level fidelity summary from illustrations/captions (non-destructive)."""
    out = stamp_color_treatment_onto_piece(piece)
    ill = _as_dict(out.get("illustrations"))
    analysis = _as_dict(ill.get("analysis"))
    arts = _as_dict(ill.get("artifacts"))
    detail = arts.get("detail_callouts") if isinstance(arts.get("detail_callouts"), dict) else {}
    closure_hit = detect_closure_caption_mismatch(
        out, artifact_meta=detail or None, analysis=analysis
    )
    color_hit = detect_color_treatment_text_mismatch(
        out,
        rendered_color_text=str(out.get("color_hint") or ""),
        analysis=analysis,
    )
    out["fidelity"] = {
        **_as_dict(out.get("fidelity")),
        "closure_check": closure_hit,
        "color_treatment_check": color_hit,
        "pixel_proof": False,
    }
    return out


def garment_fidelity_instruction_contract(piece: dict[str, Any]) -> str:
    """Combined designer fidelity contract for vision + illustration prompts."""
    return f"{closure_prompt_contract(piece)} {color_treatment_prompt_contract(piece)}"
