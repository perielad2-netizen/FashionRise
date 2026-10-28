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


_CONFIRMED_SOURCES = frozenset(
    {"designer", "designer_confirmed", "user", "confirmed", "studio_fill", "studio_fills"}
)
_REJECTED_ART_STATES = frozenset(
    {"rejected_category_mismatch", "excluded_mismatch", "rejected"}
)
_GRADIENT_TEXT_RE = re.compile(r"\b(gradient|ombre|ombr[eé]|blend|ombre)\b", re.I)
_TWO_TONE_TEXT_RE = re.compile(
    r"\b(two[-\s]?tone|color[-\s]?block|hard\s+split|split\s+color)\b", re.I
)
_SINGLE_HUE_RE = re.compile(
    r"^(?:a\s+|the\s+)?"
    r"(red|black|burgundy|navy|blue|green|white|yellow|purple|pink|cream|beige|"
    r"grey|gray|brown|tan|khaki|ivory|maroon|olive|teal|coral|orange)"
    r"(?:\s+(?:solid|color|colour|hue|shade|tone))?$",
    re.I,
)


def normalize_color_treatment(raw: Any) -> dict[str, Any] | None:
    """Normalize per-garment color-treatment intent (gradient / block / solid).

    Preserves designer confirmation + provenance. Returns None when absent.
    Empty/unknown shells become an explicit unconfirmed record only when
    ``mode`` is set to ``unknown`` / ``unconfirmed``.
    """
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or raw.get("type") or "").strip().lower() or None
    provenance = str(raw.get("provenance") or "").strip().lower() or None
    source = str(raw.get("source") or "").strip() or None
    out = {
        "mode": mode,
        "stops": list(raw.get("stops") or raw.get("colors") or [])
        if isinstance(raw.get("stops") or raw.get("colors"), list)
        else [],
        "named_colors": list(raw.get("named_colors") or [])
        if isinstance(raw.get("named_colors"), list)
        else [],
        "direction": str(raw.get("direction") or "").strip() or None,
        "placement": str(raw.get("placement") or "").strip() or None,
        "designer_confirmed": bool(raw.get("designer_confirmed")),
        "source": source,
        "provenance": provenance
        or (
            "confirmed"
            if raw.get("designer_confirmed") or (source or "").lower() in _CONFIRMED_SOURCES
            else ("inferred" if mode and mode not in {"", "unknown", "unconfirmed", "empty"} else "unknown")
        ),
        "notes": str(raw.get("notes") or "").strip() or None,
        "gradient_id": str(raw.get("gradient_id") or "").strip() or None,
        "angle": raw.get("angle") if isinstance(raw.get("angle"), (int, float)) else None,
    }
    # Drop empty shells (no mode and no useful payload).
    if not any(
        [
            out["mode"],
            out["stops"],
            out["named_colors"],
            out["direction"],
            out["placement"],
            out["notes"],
            out["gradient_id"],
        ]
    ):
        return None
    return out


def _angle_to_direction(angle: Any) -> str | None:
    if not isinstance(angle, (int, float)):
        return None
    # Studio: 0 = left→right, 90 = top→bottom (matches web-ui FillStyle).
    a = float(angle) % 360.0
    if 45 <= a < 135:
        return "top-to-bottom"
    if 135 <= a < 225:
        return "right-to-left"
    if 225 <= a < 315:
        return "bottom-to-top"
    return "left-to-right"


def color_treatment_from_studio_fill_style(style: Any) -> dict[str, Any] | None:
    """Map one Studio fill style (real upstream shape) → structured color_treatment.

    Confirmed when ``kind`` is present on a valid fill. Does **not** invent a
    gradient when the style is absent or unknown.
    """
    if not isinstance(style, dict):
        return None
    kind = str(style.get("kind") or "").strip().lower()
    if kind == "gradient":
        raw_colors = style.get("colors")
        colors: list[Any] = list(raw_colors) if isinstance(raw_colors, list) else []
        stops = [str(c) for c in colors if c is not None][:8]
        angle = style.get("angle") if isinstance(style.get("angle"), (int, float)) else None
        return normalize_color_treatment(
            {
                "mode": "gradient",
                "stops": stops,
                "named_colors": stops,
                "direction": _angle_to_direction(angle),
                "placement": "garment_fill",
                "designer_confirmed": True,
                "source": "studio_fill",
                "provenance": "confirmed",
                "gradient_id": str(style.get("gradientId") or style.get("gradient_id") or "") or None,
                "angle": angle,
                "notes": f"studio gradient {style.get('gradientId') or style.get('gradient_id') or ''}".strip(),
            }
        )
    if kind == "solid":
        color = str(style.get("color") or "").strip()
        return normalize_color_treatment(
            {
                "mode": "solid",
                "stops": [color] if color else [],
                "named_colors": [color] if color else [],
                "designer_confirmed": True,
                "source": "studio_fill",
                "provenance": "confirmed",
                "placement": "garment_fill",
            }
        )
    if kind in {"fabric", "uploaded-fabric"}:
        return normalize_color_treatment(
            {
                "mode": "fabric",
                "designer_confirmed": True,
                "source": "studio_fill",
                "provenance": "confirmed",
                "placement": "garment_fill",
                "notes": str(style.get("fabricId") or style.get("assetId") or kind),
            }
        )
    return None


def collect_studio_fills(design_data: Any) -> list[dict[str, Any]]:
    """Collect front + back Studio fills from design_data (real upstream field)."""
    data: dict[str, Any] = design_data if isinstance(design_data, dict) else {}
    fills: list[dict[str, Any]] = []
    front_fills = data.get("fills")
    if isinstance(front_fills, list):
        for item in front_fills:
            if isinstance(item, dict):
                fills.append(item)
    back_raw = data.get("back")
    back: dict[str, Any] = back_raw if isinstance(back_raw, dict) else {}
    back_fills = back.get("fills")
    if isinstance(back_fills, list):
        for item in back_fills:
            if isinstance(item, dict):
                fills.append(item)
    return fills


def color_treatment_from_studio_fills(fills: Any) -> dict[str, Any] | None:
    """Aggregate Studio fills into a single per-garment structured intent.

    Prefer a confirmed gradient when any fill is a gradient. If fills exist but
    none map, return explicit ``unknown`` rather than inventing a finish.
    """
    rows = fills if isinstance(fills, list) else []
    mapped: list[dict[str, Any]] = []
    for fill in rows:
        if not isinstance(fill, dict):
            continue
        style = fill.get("style") if isinstance(fill.get("style"), dict) else fill
        ct = color_treatment_from_studio_fill_style(style)
        if ct:
            mapped.append(ct)
    if not mapped:
        if rows:
            return normalize_color_treatment(
                {
                    "mode": "unknown",
                    "designer_confirmed": False,
                    "source": "studio_fills",
                    "provenance": "unknown",
                    "notes": "Studio fills present but treatment could not be confirmed",
                }
            )
        return None
    gradients = [m for m in mapped if m.get("mode") == "gradient"]
    if gradients:
        return gradients[0]
    return mapped[0]


def unconfirmed_color_treatment(*, reason: str = "no upstream studio fill") -> dict[str, Any]:
    """Explicit unknown/unconfirmed treatment — never invent a finish."""
    return {
        "mode": "unknown",
        "stops": [],
        "named_colors": [],
        "direction": None,
        "placement": None,
        "designer_confirmed": False,
        "source": None,
        "provenance": "unconfirmed",
        "notes": reason,
        "gradient_id": None,
        "angle": None,
    }


def piece_color_treatment(piece: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve color-treatment from structured fields, studio fills, or color_hint.

    Priority: designer-confirmed structured → studio/upstream fills → nested
    materials → color_hint keywords. A red-only ``color_hint`` must not hide an
    upstream confirmed gradient.
    """
    direct = normalize_color_treatment(piece.get("color_treatment"))
    if direct and direct.get("mode") not in {None, "", "unknown", "unconfirmed", "empty"}:
        # Upstream gradient wins over a flattened red-only structured solid when
        # the solid was not designer-confirmed.
        if (
            direct.get("mode") in {"solid", "flat"}
            and not direct.get("designer_confirmed")
            and str(direct.get("provenance") or "") in {"inferred", "unknown", "unconfirmed", ""}
        ):
            upstream = color_treatment_from_studio_fills(
                piece.get("studio_fills") or piece.get("upstream_fills")
            )
            if upstream and upstream.get("mode") == "gradient":
                return upstream
        return direct

    upstream = color_treatment_from_studio_fills(
        piece.get("studio_fills") or piece.get("upstream_fills")
    )
    if upstream and upstream.get("mode") not in {None, "", "unknown", "unconfirmed"}:
        return upstream

    mats = _as_dict(piece.get("materials"))
    shell = _as_dict(mats.get("shell"))
    nested = normalize_color_treatment(shell.get("color_treatment") or mats.get("color_treatment"))
    if nested and nested.get("mode") not in {None, "", "unknown", "unconfirmed", "empty"}:
        return nested

    # Spec-level / piece-attached studio source dict (already structured).
    for key in ("studio_color_treatment", "upstream_color_treatment"):
        attached = normalize_color_treatment(piece.get(key))
        if attached and attached.get("mode") not in {None, "", "unknown", "unconfirmed", "empty"}:
            return attached

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
            "provenance": "inferred",
            "notes": hint or None,
            "gradient_id": None,
            "angle": None,
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
            "provenance": "inferred",
            "notes": hint or None,
            "gradient_id": None,
            "angle": None,
        }
    # Red-only hint with upstream gradient already handled above. Without
    # upstream evidence, do not invent a treatment from a single hue word.
    if direct and direct.get("mode") in {"unknown", "unconfirmed"}:
        return direct
    return None


def apply_studio_fills_to_piece(
    piece: dict[str, Any],
    fills: Any,
    *,
    overwrite_unconfirmed: bool = True,
) -> dict[str, Any]:
    """Stamp Studio-fill-derived color_treatment onto a piece (non-destructive)."""
    out = deepcopy(piece)
    if isinstance(fills, list) and fills:
        out["studio_fills"] = fills
    derived = color_treatment_from_studio_fills(fills)
    if not derived:
        # Expose unknown rather than inventing when caller asked and no source.
        existing = normalize_color_treatment(out.get("color_treatment"))
        if not existing and overwrite_unconfirmed:
            # Leave absent — unknown only when we know fills were empty/missing
            # is handled by callers that want an explicit record.
            return out
        return out

    existing = normalize_color_treatment(out.get("color_treatment"))
    locked = bool(
        existing
        and existing.get("designer_confirmed")
        and str(existing.get("source") or "").lower() in _CONFIRMED_SOURCES - {"studio_fill", "studio_fills"}
        and existing.get("mode") not in {None, "", "unknown", "unconfirmed", "empty"}
    )
    if locked:
        out["upstream_color_treatment"] = derived
        return out
    if existing and existing.get("mode") not in {None, "", "unknown", "unconfirmed", "empty", "solid", "flat"}:
        if not overwrite_unconfirmed and existing.get("designer_confirmed"):
            out["upstream_color_treatment"] = derived
            return out
    # Prefer confirmed studio gradient over flattened red-only / empty shells.
    out["color_treatment"] = derived
    out["upstream_color_treatment"] = derived
    return out


def apply_studio_fills_to_spec(spec: dict[str, Any], design_data: Any) -> dict[str, Any]:
    """Propagate Studio fills → each outfit piece color_treatment (draft create/autosave)."""
    out = deepcopy(spec) if isinstance(spec, dict) else {}
    fills = collect_studio_fills(design_data)
    if not fills:
        # Record that upstream was inspected and empty — do not invent finishes.
        out["studio_color_treatment_source"] = {
            "inspected": True,
            "fill_count": 0,
            "provenance": "unconfirmed",
        }
        return out
    derived = color_treatment_from_studio_fills(fills)
    out["studio_color_treatment_source"] = {
        "inspected": True,
        "fill_count": len(fills),
        "provenance": (derived or {}).get("provenance") or "unknown",
        "mode": (derived or {}).get("mode"),
        "gradient_id": (derived or {}).get("gradient_id"),
    }
    outfit = _as_dict(out.get("outfit"))
    pieces_out: list[Any] = []
    for piece in outfit.get("pieces") or []:
        if not isinstance(piece, dict):
            pieces_out.append(piece)
            continue
        pieces_out.append(apply_studio_fills_to_piece(piece, fills))
    outfit["pieces"] = pieces_out
    out["outfit"] = outfit
    return out


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
    nested_raw = meta.get("analysis")
    nested: dict[str, Any] = nested_raw if isinstance(nested_raw, dict) else {}
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

    if req == "buttons" and _caption_implies_zipper_fly(text):
        # Forbidden zipper-fly references flag even when button tokens also appear
        # on the same sheet (e.g. "WAISTBAND & BUTTON" + "FLY (ZIPPER)").
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
        # Conflicting button-only evidence when designer requires zipper.
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
    """Flag when structured gradient intent is flattened or misdescribed in text.

    Catches single-hue labels **and** two-tone / color-block descriptive text that
    evade the older exact-color-word check when the source treatment is a
    structured gradient.
    """
    ct = piece_color_treatment(piece)
    if not ct or ct.get("mode") not in {"gradient", "ombre", "ombré"}:
        return None
    # Do NOT fold piece.color_hint into the blob — a correct designer hint
    # (e.g. "… gradient") must not mask flattened rendered/PDF color text.
    blob = _text_blob(
        rendered_color_text,
        (analysis or {}).get("colors") if isinstance(analysis, dict) else None,
        (analysis or {}).get("color_treatment") if isinstance(analysis, dict) else None,
        piece.get("garment_color"),
    )
    if not blob:
        return None
    if _GRADIENT_TEXT_RE.search(blob):
        return None

    rendered = blob.strip()
    # Two-tone / hard-split language without gradient terms — still a mismatch
    # when the designer/source treatment is a structured gradient.
    if _TWO_TONE_TEXT_RE.search(rendered):
        return {
            "code": "color_treatment_simplified",
            "designer_mode": ct.get("mode"),
            "rendered": rendered[:160],
            "message": (
                f"Designer color treatment is {ct.get('mode')}, but rendered/spec color "
                f"text describes a two-tone/color-block finish (“{rendered[:80]}”) without "
                "gradient language. Flag for manual review — do not silently accept a "
                "different finish."
            ),
            "manufacturing_evidence": False,
            "review_state": "proposed_unverified",
        }

    # Flattened single hue (optionally with filler words) and no gradient language.
    if _SINGLE_HUE_RE.fullmatch(rendered) or re.fullmatch(
        r"red|black|burgundy|navy|blue|green|white|yellow|purple", rendered
    ):
        return {
            "code": "color_treatment_simplified",
            "designer_mode": ct.get("mode"),
            "rendered": rendered,
            "message": (
                f"Designer color treatment is {ct.get('mode')}, but rendered/spec color "
                f"text simplified to “{rendered}”. Flag for manual review — "
                "do not silently accept a different finish."
            ),
            "manufacturing_evidence": False,
            "review_state": "proposed_unverified",
        }

    # Multi-word color lists without gradient language still count as flattened
    # when upstream gradient was confirmed (e.g. "near-black, burgundy").
    if ct.get("designer_confirmed") or str(ct.get("provenance") or "") == "confirmed":
        if "," in rendered or " and " in rendered:
            return {
                "code": "color_treatment_simplified",
                "designer_mode": ct.get("mode"),
                "rendered": rendered[:160],
                "message": (
                    f"Designer color treatment is confirmed {ct.get('mode')}, but rendered/"
                    f"spec color text (“{rendered[:80]}”) omits gradient language. "
                    "Flag for manual review."
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
    prior = str(out.get("review_state") or "").strip().lower()
    already_rejected = prior in _REJECTED_ART_STATES or out.get("preview_include") is False
    if already_rejected:
        # Rejection is authoritative — never revive preview_include.
        out["preview_include"] = False
        if prior not in _REJECTED_ART_STATES and out.get("preview_include") is False:
            # Keep existing rejected-ish review_state when present.
            pass
    else:
        # Keep include=True so owners can see and review; never claim manufacturing evidence.
        out["review_state"] = "proposed_unverified"
        out["preview_include"] = True
    out["review_message"] = mismatches[0]["message"]
    return out


def stamp_color_treatment_onto_piece(piece: dict[str, Any]) -> dict[str, Any]:
    """Ensure color_treatment is explicitly present when inferable (non-destructive).

    Prefer studio/upstream fills over a flattened red-only hint. Never invent a
    finish when no source exists.
    """
    out = deepcopy(piece)
    if out.get("studio_fills") or out.get("upstream_fills"):
        out = apply_studio_fills_to_piece(
            out, out.get("studio_fills") or out.get("upstream_fills")
        )
    existing = normalize_color_treatment(out.get("color_treatment"))
    if existing and existing.get("mode") not in {None, "", "empty"}:
        # Re-resolve so upstream gradient can replace flattened solid.
        resolved = piece_color_treatment(out)
        if resolved:
            out["color_treatment"] = resolved
        else:
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
        if hint:
            return f"{hint} · provenance: unconfirmed (no structured treatment)"
        return "— · provenance: unconfirmed"
    mode = ct.get("mode") or "unspecified"
    named = ", ".join(str(x) for x in (ct.get("named_colors") or ct.get("stops") or [])[:8]) or "—"
    direction = ct.get("direction") or "—"
    placement = ct.get("placement") or "—"
    provenance = ct.get("provenance") or (
        "confirmed" if ct.get("designer_confirmed") else (ct.get("source") or "unconfirmed")
    )
    confirmed = (
        "designer-confirmed"
        if ct.get("designer_confirmed")
        else str(provenance)
    )
    line = (
        f"{mode} · colors: {named} · direction: {direction} · placement: {placement} · {confirmed}"
    )
    if ct.get("gradient_id"):
        line += f" · gradient_id: {ct['gradient_id']}"
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
