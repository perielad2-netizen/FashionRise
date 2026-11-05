"""Designer-perfect tech pack enrichment — POM codes, tolerances, ISO stitches, formalwear BOM.

Aligned with industry dress tech-pack structure (cover → flats → POM → BOM →
construction → colorways → labels/packing → revision log) so a patternmaker /
atelier can sample from the PDF with minimal guesswork.
"""

from __future__ import annotations

from typing import Any

from app.services.techpack_manufacturing import POM_DEFINITIONS

# Letter codes for factory-facing POM tables (GarmentSpec-style).
POM_CODES: dict[str, str] = {
    "chest_bust": "A",
    "waist": "B",
    "hip": "C",
    "garment_length": "D",
    "shoulder_width": "E",
    "armhole": "F",
    "hem": "G",
    "sleeve_length": "H",
    "neckline": "I",
    "skirt_length": "J",
    "inseam": "K",
    "outseam": "L",
    "front_rise": "M",
    "back_rise": "N",
    "thigh": "O",
    "leg_opening": "P",
    "waistband": "Q",
    "cuff": "R",
    "opening": "S",
    "knee": "T",
}

# Default finished tolerances (cm) when designer has not set pom_tolerances.
DEFAULT_TOLERANCE_CM: dict[str, float] = {
    "chest_bust": 1.0,
    "waist": 1.0,
    "hip": 1.0,
    "garment_length": 1.0,
    "skirt_length": 1.0,
    "shoulder_width": 0.5,
    "sleeve_length": 0.7,
    "armhole": 0.7,
    "hem": 1.5,
    "neckline": 0.5,
    "inseam": 0.7,
    "outseam": 1.0,
    "front_rise": 0.5,
    "back_rise": 0.5,
    "thigh": 0.7,
    "leg_opening": 0.5,
    "waistband": 0.3,
    "cuff": 0.5,
    "opening": 0.5,
    "knee": 0.7,
}

GRADE_SIZES = ("XS", "S", "M", "L", "XL", "2XL")

# Factory-facing how-to text (GarmentSpec / atelier flat measure). Overrides body
# circumference wording so the PDF matches how sample rooms measure dresses.
DRESS_POM_HOW_TO: dict[str, str] = {
    "chest_bust": (
        "1/2 bust — lay flat; side seam to side seam, 2.5 cm (1 in) below the armhole."
    ),
    "waist": (
        "1/2 waist — straight across at the waist seam, or at the narrowest point if no seam."
    ),
    "hip": (
        "1/2 hip — straight across at the stated distance below the waist (e.g. 20 cm)."
    ),
    "garment_length": "Length from HPS — high point of shoulder straight down to hem edge.",
    "skirt_length": "Skirt length — waist seam (or intended waist) straight down to hem.",
    "shoulder_width": "Strap / shoulder width — across shoulder or strap at the shoulder seam.",
    "armhole": "Armhole, straight — shoulder point to underarm point in a straight line.",
    "hem": "1/2 sweep — along the hem edge side seam to side seam, following the curve.",
    "sleeve_length": "Sleeve length — shoulder seam to cuff / hem along outer sleeve.",
    "neckline": "Neckline depth — HPS or CB/CF reference down to neckline edge (state which).",
    "opening": "Opening length — CB or SS zip / placket opening, including stop.",
}

# Numbered callout legend for formal dress flats (designer annotates on AI flat).
FORMAL_DRESS_CALLOUTS: list[tuple[str, str]] = [
    ("1", "Neckline finish (facing / binding / lining bag-out)"),
    ("2", "Bust dart, princess, or empire seam"),
    ("3", "Waist seam or princess continuity"),
    ("4", "Side seam / underarm join"),
    ("5", "Invisible zipper (CB or SS) + hook & eye"),
    ("6", "Armhole finish or sleeve set"),
    ("7", "Hem type (baby / blind / deep turnback)"),
    ("8", "Lining join / hang shorter than shell"),
    ("9", "Support (cups / boning / stay tape) if used"),
    ("10", "Special: slit, train, bustle points, beading zone"),
]

FORMAL_DRESS_QC: list[str] = [
    "Neckline sits clean on form without gaping; depth matches Magic reference.",
    "Bust apex / princess balance left–right; no twisting at CF.",
    "Invisible zip smooth; hook & eye at top; no show-through of zip teeth.",
    "Lining hangs 1–2 cm shorter; no lining peek at hem when walking.",
    "Hem even on form; sweep allows walk without hitching.",
    "If sleeveless: armhole edge lies flat with no gaping; bias finish if specified.",
    "If train/slit: length and start height match design intent; bustle points marked.",
    "Surface (sequin / lace / metallic): placement zones match callouts; no random fill.",
    "Press quality appropriate to fabric (cloth on satin/metallic; no shine marks).",
    "Labels, hanger loops, and care content present before sample ship.",
]

# Formal / evening / bridal construction with ISO stitch classes.
FORMAL_DRESS_CONSTRUCTION: list[dict[str, Any]] = [
    {
        "step": 1,
        "operation": "Staystitch neckline / armholes",
        "stitch_type": "301 lockstitch",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Stabilize bias edges before shaping; press lightly.",
        "source": "estimate",
    },
    {
        "step": 2,
        "operation": "Bust / waist darts or princess seams",
        "stitch_type": "301 lockstitch",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Match apex; press darts toward CF/CB or seam open as designed.",
        "source": "estimate",
    },
    {
        "step": 3,
        "operation": "Join shoulder seams",
        "stitch_type": "301 + 504 overlock",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Clean-finish or French seam on sheer shell.",
        "source": "estimate",
    },
    {
        "step": 4,
        "operation": "Side seams / waist join",
        "stitch_type": "301 + 504",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.5,
        "notes": "Balance ease; understitch facings where used.",
        "source": "estimate",
    },
    {
        "step": 5,
        "operation": "Install CB or SS invisible zipper",
        "stitch_type": "301 / invisible zipper foot",
        "spi": "3–3.5 /cm",
        "seam_allowance_cm": 1.5,
        "notes": "Confirm length vs sample size; add hook & eye at top.",
        "source": "estimate",
    },
    {
        "step": 6,
        "operation": "Attach lining / facing",
        "stitch_type": "301",
        "spi": "3.5 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Bag lining 1–2 cm shorter; bag-out or hang-loop finish.",
        "source": "estimate",
    },
    {
        "step": 7,
        "operation": "Set sleeves or finish armholes",
        "stitch_type": "301 + 504",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Ease sleeve head; bias bind if sleeveless.",
        "source": "estimate",
    },
    {
        "step": 8,
        "operation": "Hem shell (+ lining)",
        "stitch_type": "Blind hem / baby hem / 301",
        "spi": "per fabric",
        "seam_allowance_cm": 2.5,
        "notes": "Chiffon/sheer → baby hem; satin/crepe → blind or deep turnback.",
        "source": "estimate",
    },
    {
        "step": 9,
        "operation": "Labels + hanger loops",
        "stitch_type": "301",
        "spi": "3 /cm",
        "seam_allowance_cm": 0,
        "notes": "Care + size at CB lining; hanger loops at shoulder seams.",
        "source": "estimate",
    },
    {
        "step": 10,
        "operation": "Final press + QC",
        "stitch_type": "—",
        "spi": "—",
        "seam_allowance_cm": 0,
        "notes": "Steam with cloth on satin/metallic; check zip, hem evenness, neckline sit.",
        "source": "estimate",
    },
]


def formal_dress_bom(*, color_hint: str = "") -> list[dict[str, Any]]:
    shell = f"{color_hint} shell fabric".strip() if color_hint else "Shell fabric (fashion face)"
    return [
        {
            "item": shell,
            "description": "Fashion face — confirm fibre, weight (GSM), hand, stretch",
            "qty": "TBD",
            "unit": "m",
            "placement": "Body / skirt / sleeves as designed",
            "color_code": color_hint or "lab dip TBD",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Do not invent composition — confirm before sample.",
        },
        {
            "item": "Lining",
            "description": "Acetate / cupro / poly lining suitable for formalwear",
            "qty": "TBD",
            "unit": "m",
            "placement": "Bodice + skirt (hang shorter than shell)",
            "color_code": "match or nude",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Required for opaque evening / bridal shells unless designer waives.",
        },
        {
            "item": "Fusing / interfacing",
            "description": "Lightweight fusible for facings / zip shield",
            "qty": "TBD",
            "unit": "m",
            "placement": "Neck facing, zip tape, strap stabilizers",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Invisible zipper",
            "description": "Concealed zip — length to match sample size opening",
            "qty": "1",
            "unit": "pcs",
            "placement": "Center back (default) or side seam if designed",
            "color_code": "match shell",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Confirm length after sample size locked.",
        },
        {
            "item": "Hook and eye",
            "description": "Metal / covered",
            "qty": "1",
            "unit": "set",
            "placement": "Top of zipper",
            "color_code": "match",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Sewing thread",
            "description": "Poly / silk match — specialty metallic if shell is metallic",
            "qty": "1",
            "unit": "cone",
            "placement": "All seams",
            "color_code": "match shell",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Hanger loops",
            "description": "Soft tape or self-fabric",
            "qty": "2",
            "unit": "pcs",
            "placement": "Shoulder seams inside",
            "color_code": "match",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Main / size / care labels",
            "description": "Brand + size + fibre/care (ISO 3758 symbols)",
            "qty": "1",
            "unit": "set",
            "placement": "CB lining neck / side seam",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Market language TBD",
        },
        {
            "item": "Hangtag + fastener",
            "description": "Brand hangtag",
            "qty": "1",
            "unit": "set",
            "placement": "Side seam or hang loop",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Polybag",
            "description": "Clear bag with warning text as market requires",
            "qty": "1",
            "unit": "pcs",
            "placement": "Packed garment",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Bust cups / support (optional)",
            "description": "Sew-in or foam cups / soft boning if design requires",
            "qty": "TBD",
            "unit": "set",
            "placement": "Bodice lining as designed",
            "color_code": "nude / match",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Omit if design is soft / unlined support-free.",
        },
        {
            "item": "Stay tape / clear elastic",
            "description": "Stabilize neckline / strap / zipper opening",
            "qty": "TBD",
            "unit": "m",
            "placement": "Bias edges and strap joins",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Critical on bias evening necklines.",
        },
    ]


def formal_dress_pattern_inventory() -> list[dict[str, Any]]:
    base = {
        "cut_qty": 1,
        "grainline": "straight",
        "fold": "none",
        "seam_allowance_cm": 1.0,
        "source": "estimate",
        "review_state": "proposed_unverified",
    }
    return [
        {**base, "id": "DR-F", "name": "Front shell", "fabric": "shell", "cut_qty": 1, "notes": "Include neckline / dart shaping as designed"},
        {**base, "id": "DR-B", "name": "Back shell", "fabric": "shell", "cut_qty": 1, "notes": "CB zip seam if applicable"},
        {**base, "id": "DR-SL", "name": "Sleeve (if sleeved)", "fabric": "shell", "cut_qty": 2, "notes": "Omit if sleeveless"},
        {**base, "id": "DR-LF", "name": "Front lining", "fabric": "lining", "cut_qty": 1, "notes": "1–2 cm shorter at hem"},
        {**base, "id": "DR-LB", "name": "Back lining", "fabric": "lining", "cut_qty": 1, "notes": "Zip shield / facing as needed"},
        {**base, "id": "DR-FC", "name": "Neck / armhole facing", "fabric": "shell or lining", "cut_qty": 1, "notes": "Fuse lightly"},
        {**base, "id": "DR-ZS", "name": "Zipper shield", "fabric": "lining", "cut_qty": 1, "notes": "Optional"},
    ]


def pom_code(key: str) -> str:
    return POM_CODES.get(key, key[:1].upper() if key else "—")


def pom_how_to(key: str, *, category: str | None = None) -> str:
    if category and is_formal_dress_category(category) and key in DRESS_POM_HOW_TO:
        return DRESS_POM_HOW_TO[key]
    meta = POM_DEFINITIONS.get(key) or {}
    return str(meta.get("method") or "Confirm measuring method with patternmaker.")


def pom_label(key: str) -> str:
    meta = POM_DEFINITIONS.get(key) or {}
    return str(meta.get("label") or key.replace("_", " ").title())


def pom_tolerance_cm(piece: dict[str, Any], key: str) -> float:
    tol = piece.get("pom_tolerances") if isinstance(piece.get("pom_tolerances"), dict) else {}
    cell = tol.get(key) if isinstance(tol, dict) else None
    if isinstance(cell, dict) and isinstance(cell.get("value"), (int, float)):
        return float(cell["value"])
    if isinstance(cell, (int, float)):
        return float(cell)
    return float(DEFAULT_TOLERANCE_CM.get(key, 1.0))


def finished_pom_rows(piece: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten finished_measurements into designer table rows."""
    finished = piece.get("finished_measurements") if isinstance(piece.get("finished_measurements"), dict) else {}
    cat = str(piece.get("category") or "")
    rows: list[dict[str, Any]] = []
    for key, cell in finished.items():
        if not isinstance(cell, dict):
            continue
        value = cell.get("value")
        rows.append(
            {
                "key": key,
                "code": pom_code(key),
                "label": pom_label(key),
                "how_to": pom_how_to(key, category=cat),
                "value": value,
                "unit": cell.get("unit") or "cm",
                "source": cell.get("source") or "empty",
                "review_status": cell.get("review_status") or "",
                "tolerance_cm": pom_tolerance_cm(piece, key),
            }
        )
    # Stable factory order by code then label.
    rows.sort(key=lambda r: (r["code"], r["label"]))
    return rows


def is_formal_dress_category(category: str) -> bool:
    cat = (category or "").lower().strip()
    return cat in {"dress", "gown", "evening", "bridal", "wedding", "formal"}


def enrich_piece_for_designer_pdf(piece: dict[str, Any]) -> dict[str, Any]:
    """Non-destructive copy with formalwear defaults filled when empty."""
    out = dict(piece)
    cat = str(out.get("category") or "other")
    color = str(out.get("color_hint") or "")
    if is_formal_dress_category(cat):
        bom = out.get("bom") if isinstance(out.get("bom"), list) else []
        if not bom:
            out["bom"] = formal_dress_bom(color_hint=color)
        steps = out.get("construction_steps") if isinstance(out.get("construction_steps"), list) else []
        ai_sourced = any(
            isinstance(s, dict)
            and str(s.get("source") or "").lower() in {"ai", "ai_vision", "ai_inferred"}
            for s in (steps or [])
        )
        if ai_sourced:
            # Keep look-specific AI sew steps — do not overwrite with generic formal defaults.
            pass
        elif not steps:
            out["construction_steps"] = list(FORMAL_DRESS_CONSTRUCTION)
        # Prefer richer formal construction when steps are plain strings / short defaults.
        elif steps and all(
            isinstance(s, dict) and not s.get("stitch_type") for s in steps
        ):
            out["construction_steps"] = list(FORMAL_DRESS_CONSTRUCTION)
        patterns = out.get("pattern_pieces") if isinstance(out.get("pattern_pieces"), list) else []
        if not patterns:
            out["pattern_pieces"] = formal_dress_pattern_inventory()
    return out
