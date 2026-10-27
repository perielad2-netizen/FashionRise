"""Heuristic (+ optional AI) garment component detection from Magic look evidence."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.services.techpack_garments import default_piece

_TOP_WORDS = ("shirt", "blouse", "top", "tee", "t-shirt", "jacket", "coat", "hoodie", "sweater", "vest")
_BOTTOM_WORDS = ("trouser", "trousers", "pant", "pants", "jeans", "skirt", "shorts", "chino")
_DRESS_WORDS = ("dress", "gown", "frock")
_JUMP_WORDS = ("jumpsuit", "romper", "overall")
_COLOR_WORDS = (
    "black",
    "white",
    "beige",
    "cream",
    "ivory",
    "navy",
    "blue",
    "red",
    "green",
    "grey",
    "gray",
    "brown",
    "pink",
    "tan",
    "khaki",
)


def _colors_near(text: str, keyword: str) -> str:
    idx = text.find(keyword)
    if idx < 0:
        return ""
    window = text[max(0, idx - 24) : idx + len(keyword) + 24]
    for color in _COLOR_WORDS:
        if color in window:
            return color
    return ""


def _pieces_from_identity_components(
    identity: dict[str, Any], *, units: str
) -> list[dict[str, Any]] | None:
    """Prefer explicit multi-piece lists from Magic design_identity when present."""
    raw = identity.get("components") or identity.get("pieces") or identity.get("garment_pieces")
    if not isinstance(raw, list) or not raw:
        return None
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            cat_raw = item
            label = item
            color = ""
        elif isinstance(item, dict):
            cat_raw = str(item.get("category") or item.get("garment_category") or item.get("type") or "")
            label = str(item.get("label") or item.get("name") or cat_raw or "Garment")
            color = str(item.get("color") or item.get("main_colors") or item.get("color_hint") or "")[:40]
        else:
            continue
        cat_l = cat_raw.lower().replace(" ", "_")
        if cat_l in ("pants", "pant", "jeans"):
            cat = "trousers"
        elif cat_l in ("blouse",):
            cat = "shirt"
        elif cat_l in ("tee", "t-shirt", "tshirt"):
            cat = "top"
        elif cat_l in ("coat",):
            cat = "jacket"
        elif cat_l in (
            "dress",
            "shirt",
            "top",
            "jacket",
            "skirt",
            "trousers",
            "shorts",
            "jumpsuit",
            "other",
        ):
            cat = cat_l
        else:
            # Free-text component like "black shirt"
            top = next((w for w in _TOP_WORDS if re.search(rf"\b{re.escape(w)}\b", cat_l.replace("_", " "))), None)
            bottom = next(
                (w for w in _BOTTOM_WORDS if re.search(rf"\b{re.escape(w)}\b", cat_l.replace("_", " "))), None
            )
            if top and not bottom:
                cat = "jacket" if top in ("jacket", "coat") else "shirt" if top in ("shirt", "blouse") else "top"
            elif bottom and not top:
                cat = "skirt" if bottom == "skirt" else "shorts" if bottom == "shorts" else "trousers"
            else:
                continue
        if not color:
            color = _colors_near(f"{color} {label} {cat}".lower(), cat.split("_")[0] if cat else "")
        out.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category=cat,
                label=label.title() if label else cat.title(),
                color_hint=color,
                detection_source="look_identity",
                units=units,
            )
        )
    return out or None


def detect_pieces_from_evidence(
    *,
    look_summary: str | None,
    design_identity: dict[str, Any] | None = None,
    units: str = "cm",
) -> dict[str, Any]:
    """Return outfit detection without paid AI. Never claims guaranteed correctness."""
    text = (look_summary or "").lower()
    identity = design_identity if isinstance(design_identity, dict) else {}
    category_hint = str(identity.get("garment_category") or identity.get("category") or "").lower()
    # When identity names separates, prefer that signal over a stale single-dress word.
    if category_hint:
        text = f"{text} {category_hint}"

    from_components = _pieces_from_identity_components(identity, units=units)
    if from_components is not None and len(from_components) >= 1:
        return {
            "piece_count": len(from_components),
            "pieces": from_components,
            "detection_confidence": "look_identity",
            "needs_user_confirm": True,
            "note": "Detection from Magic design identity — correct categories before production.",
        }

    pieces: list[dict[str, Any]] = []
    has_dress = any(w in text for w in _DRESS_WORDS)
    has_jump = any(w in text for w in _JUMP_WORDS)
    top_hit = next((w for w in _TOP_WORDS if re.search(rf"\b{re.escape(w)}\b", text)), None)
    bottom_hit = next((w for w in _BOTTOM_WORDS if re.search(rf"\b{re.escape(w)}\b", text)), None)
    # Multi-piece category phrases beat a lone "dress" token from migrated metadata.
    if top_hit and bottom_hit:
        has_dress = False

    if has_jump:
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category="jumpsuit",
                label="Jumpsuit",
                detection_source="heuristic",
                units=units,
            )
        )
    elif has_dress and not (top_hit and bottom_hit):
        color = _colors_near(text, "dress") or str(identity.get("main_colors") or "")[:40]
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category="dress",
                label=f"{color.title()} Dress".strip() if color else "Dress",
                color_hint=color if isinstance(color, str) else "",
                detection_source="heuristic",
                units=units,
            )
        )
    elif top_hit and bottom_hit:
        top_cat = "jacket" if top_hit in ("jacket", "coat") else "shirt" if top_hit in ("shirt", "blouse") else "top"
        if bottom_hit in ("skirt",):
            bottom_cat = "skirt"
        elif bottom_hit in ("shorts",):
            bottom_cat = "shorts"
        else:
            bottom_cat = "trousers"
        top_color = _colors_near(text, top_hit)
        bottom_color = _colors_near(text, bottom_hit)
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category=top_cat,
                label=f"{(top_color + ' ' if top_color else '')}{top_hit}".strip().title(),
                color_hint=top_color,
                detection_source="heuristic",
                units=units,
            )
        )
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category=bottom_cat,
                label=f"{(bottom_color + ' ' if bottom_color else '')}{bottom_hit}".strip().title(),
                color_hint=bottom_color,
                detection_source="heuristic",
                units=units,
            )
        )
    elif bottom_hit:
        bottom_cat = "skirt" if bottom_hit == "skirt" else "shorts" if bottom_hit == "shorts" else "trousers"
        color = _colors_near(text, bottom_hit)
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category=bottom_cat,
                label=f"{(color + ' ' if color else '')}{bottom_hit}".strip().title(),
                color_hint=color,
                detection_source="heuristic",
                units=units,
            )
        )
    elif top_hit:
        top_cat = "jacket" if top_hit in ("jacket", "coat") else "shirt" if top_hit in ("shirt", "blouse") else "top"
        color = _colors_near(text, top_hit)
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category=top_cat,
                label=f"{(color + ' ' if color else '')}{top_hit}".strip().title(),
                color_hint=color,
                detection_source="heuristic",
                units=units,
            )
        )
    else:
        pieces.append(
            default_piece(
                piece_id=f"piece-{uuid.uuid4().hex[:8]}",
                category="other",
                label="Garment (confirm category)",
                detection_source="heuristic_fallback",
                units=units,
            )
        )

    return {
        "piece_count": len(pieces),
        "pieces": pieces,
        "detection_confidence": "heuristic",
        "needs_user_confirm": True,
        "note": "Detection is a starting point — correct categories before generating the technical pack.",
    }
