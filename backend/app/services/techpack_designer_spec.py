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
    # Design-specific dress callouts (full lengths / depths — not circ).
    "wrap_overlap": "U",
    "slit_start": "S1",
    "overlay_length": "W",
    "sash_width": "X",
    "sash_length": "Y",
    "hem_high": "Z1",
    "hem_low": "Z2",
    # Deep-V depth — distinct from slit_start (was colliding on letter "V").
    "v_depth": "I2",
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
    "wrap_overlap": 0.5,
    "slit_start": 1.0,
    "overlay_length": 1.0,
    "sash_width": 0.3,
    "sash_length": 1.5,
    "hem_high": 1.0,
    "hem_low": 1.0,
}

GRADE_SIZES = ("XS", "S", "M", "L", "XL", "2XL")

# How-to MUST match stored values: finished circ POMs are FULL circumference (body + ease).
# Flat half = stored value ÷ 2 — never store half and label as full (or vice versa).
DRESS_POM_HOW_TO: dict[str, str] = {
    "chest_bust": (
        "FULL bust circumference (cm). Stored value ≈ body bust + ease. "
        "Sample-room flat check: lay garment flat, side seam to side seam 2.5 cm below armhole, "
        "then ×2 must equal this number (±tol)."
    ),
    "waist": (
        "FULL waist circumference (cm) at waist seam / narrowest. "
        "Flat check: edge-to-edge ×2 = this value."
    ),
    "hip": (
        "FULL hip circumference (cm) at fullest seat / stated distance below waist. "
        "Flat check: edge-to-edge ×2 = this value."
    ),
    "garment_length": "Length from HPS — high point of shoulder straight down to longest hem edge.",
    "skirt_length": "Skirt length — waist seam (or intended waist) straight down to hem.",
    "shoulder_width": "Across-back shoulder / strap width at shoulder seam (NOT a circumference).",
    "armhole": "Armhole circumference along the armhole seam (full).",
    "hem": (
        "FULL hem / sweep circumference. Flat check: along hem edge side-to-side ×2 "
        "(or follow curve and ×2)."
    ),
    "sleeve_length": "Sleeve length — shoulder seam to cuff / hem along outer sleeve.",
    "neckline": (
        "Neckline / deep-V DEPTH (cm) — HPS (or stated CF ref) straight down to the lowest "
        "neckline edge / V apex. Same physical measure as v_depth on deep-V wraps. "
        "Not a circumference."
    ),
    "opening": "Opening / slit length (cm) — start point to hem, or zip placket length if zip used.",
    "wrap_overlap": (
        "Wrap OVERLAP at waist (cm) — from CF underlap edge to CF overlap edge when the wrap "
        "is closed as designed. Start: underlap CF; end: overlap CF. Not a circumference."
    ),
    "slit_start": (
        "Slit START height (cm) — from the waist seam (or designed waist join) straight down "
        "the underlayer side seam to the TOP of the thigh slit opening. Start: waist; end: slit apex."
    ),
    "overlay_length": (
        "Asymmetric OVERLAY length (cm) — from the waist attach / catch-in point along the "
        "drape panel to the free pointed hem tip. Start: waist attach; end: tip."
    ),
    "sash_width": "Sash WIDTH (cm) — finished width of the waist sash / tie strip (edge to edge).",
    "sash_length": (
        "Sash LENGTH (cm) — total finished length of the waist sash / tie including both tails "
        "(end to end)."
    ),
    "hem_high": (
        "HEM HIGH (cm) — HPS straight down to the SHORTER / higher finished hem edge "
        "(asymmetric hems). Start: HPS; end: high hem."
    ),
    "hem_low": (
        "HEM LOW (cm) — HPS straight down to the LONGER / lower finished hem edge "
        "(asymmetric hems / overlay tip if that is the longest). Start: HPS; end: low hem."
    ),
    "v_depth": (
        "Deep-V DEPTH (cm) — from HPS (or stated CF reference) straight down to the lowest "
        "point of the V neckline edge. Start: HPS/CF ref; end: V apex. Not a circumference."
    ),
}

# Numbered callout legend for zip-closure formal dresses.
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

WRAP_DRESS_CALLOUTS: list[tuple[str, str]] = [
    ("1", "Deep-V / wrap neckline finish + stay tape"),
    ("2", "Wrap crossover / underlap at bust"),
    ("3", "Waist sash / tie anchorage"),
    ("4", "Side seam / underarm join (no CB zip assumed)"),
    ("5", "Sleeve set / armhole finish"),
    ("6", "Waist seam or wrap continuous bodice"),
    ("7", "Thigh slit reinforcement + underlap"),
    ("8", "Asymmetric draped overlay attach + free edges"),
    ("9", "Hem finishes (high vs low / overlay tip)"),
    ("10", "Lining / facing hang (if used)"),
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

WRAP_DRESS_QC: list[str] = [
    "Wrap overlap at waist matches specified depth; underlap covers when walking.",
    "Deep-V neckline stable — no gaping; stay tape present; depth matches Magic.",
    "Waist sash / tie secures wrap; knot/bow position matches design intent.",
    "Thigh slit start height and walk ease match Magic; reinforcement clean.",
    "Asymmetric overlay / drape hangs balanced; free edges finished; tip length confirmed.",
    "Sleeve set smooth; armhole no gaping; cuff/wrist length matches sample.",
    "High vs low hem lengths match design (not accidental uneven hem).",
    "No zipper QC unless a zip is an explicit designer-confirmed closure.",
    "Press quality appropriate to fabric; no shine marks on crepe/satin.",
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


WRAP_DRESS_CONSTRUCTION: list[dict[str, Any]] = [
    {
        "step": 1,
        "operation": "Staystitch deep-V / wrap neckline + armholes",
        "stitch_type": "301 lockstitch",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Stabilize bias wrap edges before shaping; press lightly.",
        "source": "estimate",
    },
    {
        "step": 2,
        "operation": "Join wrap fronts / underlap + shoulder seams",
        "stitch_type": "301 + 504 overlock",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Preserve designed wrap overlap; stay-tape V apex.",
        "source": "estimate",
    },
    {
        "step": 3,
        "operation": "Side seams / underarm join (no CB zip assumed)",
        "stitch_type": "301 + 504",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.5,
        "notes": "Leave wrap opening free; balance ease at bust/waist.",
        "source": "estimate",
    },
    {
        "step": 4,
        "operation": "Set sleeves or finish armholes",
        "stitch_type": "301 + 504",
        "spi": "3.5–4 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Ease sleeve head; confirm armhole depth vs sample.",
        "source": "estimate",
    },
    {
        "step": 5,
        "operation": "Attach draped overlay / waist sash anchorage",
        "stitch_type": "301",
        "spi": "3.5 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Match overlay balance; confirm sash width/length POMs before cut.",
        "source": "estimate",
    },
    {
        "step": 6,
        "operation": "Reinforce thigh slit + finish wrap edges",
        "stitch_type": "301 / bar-tack",
        "spi": "3.5 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Bar-tack slit apex; clean-finish wrap edges with stay tape where needed.",
        "source": "estimate",
    },
    {
        "step": 7,
        "operation": "Attach lining / facing (if used)",
        "stitch_type": "301",
        "spi": "3.5 /cm",
        "seam_allowance_cm": 1.0,
        "notes": "Bag lining shorter; do not block wrap opening.",
        "source": "estimate",
    },
    {
        "step": 8,
        "operation": "Hem shell (+ lining) — asymmetric lengths if designed",
        "stitch_type": "Blind hem / baby hem / 301",
        "spi": "per fabric",
        "seam_allowance_cm": 2.5,
        "notes": "Record hem_high / hem_low; keep asymmetric hem intentional.",
        "source": "estimate",
    },
    {
        "step": 9,
        "operation": "Labels + hanger loops",
        "stitch_type": "301",
        "spi": "3 /cm",
        "seam_allowance_cm": 0,
        "notes": "Care + size at side seam or CB lining (no zip); hanger loops at shoulders.",
        "source": "estimate",
    },
    {
        "step": 10,
        "operation": "Final press + wrap QC",
        "stitch_type": "—",
        "spi": "—",
        "seam_allowance_cm": 0,
        "notes": "Check wrap overlap, neckline sit, slit movement, drape balance, sleeve fit — no zipper QC.",
        "source": "estimate",
    },
]


def construction_defaults_for_closure(closure_family: str) -> list[dict[str, Any]]:
    if closure_family == "wrap":
        return list(WRAP_DRESS_CONSTRUCTION)
    return list(FORMAL_DRESS_CONSTRUCTION)


def _drop_zip_construction_steps(steps: list[Any]) -> list[Any]:
    cleaned: list[Any] = []
    for step in steps:
        blob = (
            " ".join(
                str(step.get(k) or "")
                for k in ("operation", "instruction", "notes", "stitch_type")
            ).lower()
            if isinstance(step, dict)
            else str(step).lower()
        )
        if "zip" in blob or "zipper" in blob:
            continue
        cleaned.append(step)
    return cleaned


def detect_closure_family(piece: dict[str, Any]) -> str:
    """Return 'wrap' | 'zip' | 'button' | 'fly' | 'unknown' from closures + AI analysis."""
    closures = piece.get("closures") if isinstance(piece.get("closures"), dict) else {}
    blob_parts = [
        str(closures.get("type") or ""),
        str(closures.get("display_type") or ""),
        str(closures.get("display") or ""),
        str(piece.get("label") or ""),
        str(piece.get("category") or ""),
    ]
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else {}
    if isinstance(analysis, dict):
        blob_parts.append(str(analysis.get("closure_visible") or ""))
        blob_parts.append(str(analysis.get("silhouette") or ""))
        blob_parts.append(str(analysis.get("neckline") or ""))
        feats = analysis.get("distinctive_features") if isinstance(analysis.get("distinctive_features"), list) else []
        blob_parts.extend(str(f) for f in feats[:12])
        blob_parts.append(str(analysis.get("back_construction_proposal") or ""))
    blob = " ".join(blob_parts).lower()
    cat = str(piece.get("category") or "").lower()
    wrap_tokens = ("wrap", "sash", "tie", "crossover", "overlap", "kimono")
    zip_tokens = ("zip", "zipper", "invisible zip", "hook and eye at zip")
    button_tokens = ("button", "placket", "button-front", "button front", "buttons")
    fly_tokens = ("fly", "jean fly", "trouser fly", "concealed center-front fly")
    has_wrap = any(t in blob for t in wrap_tokens)
    denies_zip = any(
        t in blob
        for t in (
            "no closure",
            "no zip",
            "no zipper",
            "without zip",
            "no visible zipper",
            "no visible closure",
            "no closure hardware",
        )
    )
    has_zip = any(t in blob for t in zip_tokens) and not denies_zip
    has_button = any(t in blob for t in button_tokens)
    has_fly = any(t in blob for t in fly_tokens) or (
        has_zip and cat in {"trousers", "shorts", "jeans"}
    )
    # Category-aware priority: don't let dress wrap tokens win on shirts/jeans.
    if cat in {"shirt", "top", "blouse", "jacket"} and has_button and not has_wrap:
        return "button"
    if cat in {"trousers", "shorts", "jeans"} and (has_fly or has_zip) and not has_wrap:
        return "fly" if has_fly or cat in {"trousers", "shorts", "jeans"} else "zip"
    if has_wrap and (denies_zip or not has_zip):
        return "wrap"
    if has_button and not has_wrap:
        return "button"
    if has_fly and not has_wrap:
        return "fly"
    if has_zip and not has_wrap:
        return "zip"
    if has_wrap:
        return "wrap"
    if has_zip:
        return "zip"
    return "unknown"


# Design-dim keys shown on the MTM "starting points" table (subset of FINISHED_POM).
_DRESS_ONLY_DIM_KEYS = (
    "wrap_overlap",
    "slit_start",
    "overlay_length",
    "sash_width",
    "sash_length",
    "hem_high",
    "hem_low",
    "v_depth",
)


def mtm_design_dim_keys(category: str) -> tuple[str, ...]:
    """Category-aware design-dimension keys for the tailor brief."""
    from app.services.techpack_garments import FINISHED_POM

    cat = (category or "other").lower().strip()
    if cat in {"jeans", "pants", "pant"}:
        cat = "trousers"
    if is_formal_dress_category(cat):
        return (
            "neckline",
            "v_depth",
            "wrap_overlap",
            "slit_start",
            "overlay_length",
            "sash_width",
            "sash_length",
            "hem_high",
            "hem_low",
            "garment_length",
        )
    keys = FINISHED_POM.get(cat) or FINISHED_POM.get("other") or ()
    # Prefer design/fit keys first; exclude pure body circ duplicates later in UI if needed.
    return tuple(k for k in keys if k not in _DRESS_ONLY_DIM_KEYS)


def mtm_dim_priority_note(category: str) -> str:
    cat = (category or "other").lower().strip()
    if cat in {"jeans", "pants", "pant"}:
        cat = "trousers"
    if is_formal_dress_category(cat):
        return (
            "Prioritise neckline depth, wrap overlap, slit start, sash size, and "
            "asymmetric hem lengths — these define the look."
        )
    if cat in {"shirt", "top", "blouse"}:
        return (
            "Prioritise chest, shoulder width, shirt length, sleeve length, collar / neckline "
            "depth, and cuff — these define the shirt fit."
        )
    if cat in {"trousers", "shorts", "jeans"}:
        return (
            "Prioritise waist, hip, rise, inseam, outseam, thigh, knee, and leg opening — "
            "these define the jeans / trouser fit. Note stripe / grain direction when cutting."
        )
    if cat == "skirt":
        return "Prioritise waist, hip, skirt length, waistband, and opening / slit if present."
    if cat == "jacket":
        return "Prioritise chest, shoulder, length, sleeve length, and neckline / collar."
    return "Confirm the key finished measurements that define this garment’s look and fit."


def mtm_closure_statement(piece: dict[str, Any]) -> tuple[str, str]:
    """Return (severity, body_html) for the fastening section."""
    family = detect_closure_family(piece)
    cat = str(piece.get("category") or "garment").lower()
    if family == "wrap":
        return (
            "warn",
            "<b>Appears to be a WRAP / TIE dress</b> (no visible zipper in the Magic look). "
            "Final fastening — sash/tie only, optional hidden snap, or another method — "
            "<b>must be agreed with the tailor</b>. Do not assume an invisible zipper "
            "unless the customer and tailor explicitly choose one.",
        )
    if family == "button":
        return (
            "body",
            f"<b>Appears to be a BUTTON-FRONT {cat}</b> from the Magic look. "
            "Confirm button count, placket type, collar construction, and sleeve finish "
            "with the tailor. Closure is <b>proposed from visual evidence</b> until confirmed.",
        )
    if family == "fly":
        return (
            "body",
            f"<b>Appears to use a FRONT FLY</b> (proposed from the Magic look). "
            "Confirm fly zipper length, waistband, and waistband button / rivets with the tailor "
            "before cutting. Keep this as <b>proposed</b> until the appointment confirms it.",
        )
    if family == "zip":
        return (
            "body",
            "Design appears to use a zipper closure. Confirm type, length, and placement "
            "with the tailor before cutting.",
        )
    return (
        "warn",
        "Closure is unresolved. Customer and tailor must agree fastening before the first toile.",
    )


def mtm_consultation_decisions(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """(Decision label, agreed-value prompt) rows for the consultation table."""
    family = detect_closure_family(piece)
    cat = str(piece.get("category") or "other").lower()
    if cat in {"jeans", "pants", "pant"}:
        cat = "trousers"
    if is_formal_dress_category(cat) or family == "wrap":
        return [
            ("Fastening", "wrap/tie only · optional snap · other: ______"),
            ("Back construction", "cut on fold (cut 1) · CB seam (cut 2) · other: ______"),
            ("Sash width × length", "______ cm × ______ cm"),
            ("Neckline / V depth", "______ cm"),
            ("Wrap overlap / slit / hems", "notes: ________________________"),
            ("Fabric / lining choice", "______________________________"),
            ("Other changes this visit", "______________________________"),
        ]
    if cat in {"shirt", "top", "blouse"}:
        return [
            ("Collar", "standing · convertible · other: ______"),
            ("Front closure", "buttons (qty ___) · placket style: ______"),
            ("Shirt length / hem", "______ cm · curved / straight hem"),
            ("Sleeve", "full · rolled · cuff: ______"),
            ("Fit / ease", "slim · regular · notes: ______"),
            ("Fabric / interfacing", "______________________________"),
            ("Other changes this visit", "______________________________"),
        ]
    if cat in {"trousers", "shorts", "jeans"}:
        return [
            ("Waistband / rise", "______ cm rise · belt loops yes/no"),
            ("Fly / closure", "zip fly (proposed) · button · other: ______"),
            ("Pocket style", "5-pocket · other: ______"),
            ("Leg shape / taper", "slim · tapered · notes: ______"),
            ("Finished length / hem", "inseam ______ cm · hem finish ______"),
            ("Denim / stripe direction", "match grain / stripes: ______"),
            ("Other changes this visit", "______________________________"),
        ]
    if cat == "skirt":
        return [
            ("Waistband / facing", "______"),
            ("Closure", "zip · buttons · other: ______"),
            ("Length / hem", "______ cm"),
            ("Opening / slit", "______"),
            ("Fabric choice", "______________________________"),
            ("Other changes this visit", "______________________________"),
        ]
    return [
        ("Fastening", "confirm type / placement: ______"),
        ("Key dimensions", "notes: ________________________"),
        ("Fabric choice", "______________________________"),
        ("Other changes this visit", "______________________________"),
    ]


def mtm_worksheet_rows(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Blank tailor measurement worksheet rows for this garment category."""
    cat = str(piece.get("category") or "other").lower()
    shared = [("Date / tailor", ""), ("Customer name", "")]
    if cat in {"jeans", "pants", "pant"}:
        cat = "trousers"
    if cat in {"shirt", "top", "blouse", "jacket"}:
        return shared + [
            ("Height", "cm"),
            ("Chest / bust (body circ)", "cm"),
            ("Neck / collar size", "cm"),
            ("Shoulder width", "cm"),
            ("Across back", "cm"),
            ("Shirt / jacket length (HPS→hem)", "cm"),
            ("Sleeve length (shoulder→cuff)", "cm"),
            ("Upper arm circ", "cm"),
            ("Wrist / cuff", "cm"),
            ("Preferred ease / fit notes", ""),
        ]
    if cat in {"trousers", "shorts", "jeans"}:
        return shared + [
            ("Height", "cm"),
            ("Waist (body circ)", "cm"),
            ("Hip (body circ)", "cm"),
            ("Front rise", "cm"),
            ("Back rise", "cm"),
            ("Thigh", "cm"),
            ("Knee", "cm"),
            ("Inseam", "cm"),
            ("Outseam", "cm"),
            ("Leg opening / hem", "cm"),
            ("Preferred ease / fit notes", ""),
        ]
    if cat == "skirt":
        return shared + [
            ("Height", "cm"),
            ("Waist (body circ)", "cm"),
            ("Hip (body circ)", "cm"),
            ("Skirt length (waist→hem)", "cm"),
            ("Preferred ease / fit notes", ""),
        ]
    # Dress / default MTM body sheet.
    return shared + [
        ("Height", "cm"),
        ("Bust (body circ)", "cm"),
        ("Underbust (if needed)", "cm"),
        ("Waist (body circ)", "cm"),
        ("High hip", "cm"),
        ("Hip (body circ)", "cm"),
        ("Across front", "cm"),
        ("Across back", "cm"),
        ("Back width / back length (nape→waist)", "cm"),
        ("Shoulder width", "cm"),
        ("Arm length (shoulder→wrist)", "cm"),
        ("Upper arm circ", "cm"),
        ("Wrist / cuff", "cm"),
        ("Waist → knee", "cm"),
        ("Waist → floor / preferred hem", "cm"),
        ("Preferred finished length (HPS→hem)", "cm"),
        ("Ease / fit preference notes", ""),
    ]


def mtm_detail_focus(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Close-up explanation rows that must match the garment (not a dress template)."""
    cat = str(piece.get("category") or "other").lower()
    if cat in {"jeans", "pants", "pant"}:
        cat = "trousers"
    family = detect_closure_family(piece)
    if is_formal_dress_category(cat) or family == "wrap":
        return [
            ("Deep V / wrap overlap", "Neckline depth and crossover at bust/waist — stay-tape as needed."),
            ("Sash at waist", "How the sash anchors and finishes; width × length from agreed dims."),
            ("Asymmetric overlay", "Where the draped panel attaches and how the pointed hem falls."),
            ("High slit", "Start height from waist, finish, and stride/sit check."),
            ("Sleeve & hem finish", "Set-in sleeve clean finish; underlayer vs overlay hem lengths."),
        ]
    if cat in {"shirt", "top", "blouse"}:
        return [
            ("Collar / neck", "Standing or designed collar stand; roll and topstitch."),
            ("Front placket / buttons", "Button spacing, placket width, top/bottom finish."),
            ("Sleeve treatment", "Set-in sleeve, roll-up, cuff or clean hem as designed."),
            ("Shirt-tail / hem", "Curved vs straight hem; side-seam vents if present."),
            ("Fit / silhouette", "Chest ease, waist shaping, shoulder slope."),
        ]
    if cat in {"trousers", "shorts", "jeans"}:
        return [
            ("Waistband / belt loops", "Height, ease, and loop placement."),
            ("Fly / front closure", "Fly length and finish — proposed until confirmed."),
            ("Pockets", "Front/back pocket style and placement."),
            ("Leg taper / stripe", "Grain and stripe/pattern direction — match both legs."),
            ("Hem finish", "Finished inseam length and hem depth."),
        ]
    if cat == "skirt":
        return [
            ("Waistband / facing", "Finish and ease at waist."),
            ("Closure", "Zip or other fastening placement."),
            ("Hem / opening", "Length and any slit / vent."),
            ("Drape / hang", "Grain and panel balance."),
        ]
    return [
        ("Primary design detail", "Confirm the distinctive feature from the Magic look."),
        ("Closure", "Confirm fastening type and placement."),
        ("Hem / finish", "Confirm length and edge finish."),
        ("Fabric behaviour", "Drape, stretch, and pattern direction if relevant."),
    ]


def mtm_checklist_rows_for_piece(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Per-garment final checklist decision rows."""
    cat = str(piece.get("category") or "garment")
    label = str(piece.get("label") or cat).strip()
    family = detect_closure_family(piece)
    heading = f"{(piece.get('role') or cat).upper()}: {label}"
    rows: list[tuple[str, str]] = [(heading, "Approve this garment’s interpretation")]
    if family == "wrap":
        rows.append(("Fastening", "Wrap/tie only, optional snap — no zipper unless chosen"))
        rows.append(("Design dims", "Neckline/V, wrap, slit, sash, hems — one value each"))
    elif family == "button":
        rows.append(("Fastening", "Button count / placket / collar confirmed"))
        rows.append(("Design dims", "Chest, shoulder, length, sleeve, collar — starting points agreed"))
    elif family == "fly":
        rows.append(("Fastening", "Fly zip / waistband — keep proposed until confirmed"))
        rows.append(("Design dims", "Waist, rise, inseam, taper, hem — starting points agreed"))
        rows.append(("Pattern / grain", "Stripe or denim direction matched across pieces"))
    else:
        rows.append(("Fastening", "Confirm closure type and placement"))
        rows.append(("Design dims", "Key finished measurements agreed"))
    rows.append(("Fabric", "Shell characteristics agreed with tailor"))
    rows.append(("Illustrations", "Flats / details treated as unverified visual references"))
    return rows


def formal_dress_bom(*, color_hint: str = "", closure_family: str = "unknown") -> list[dict[str, Any]]:
    shell = f"{color_hint} shell fabric".strip() if color_hint else "Shell fabric (fashion face)"
    proposed = "PROPOSED / UNRESOLVED — confirm fibre, GSM, hand before sample cut."
    rows: list[dict[str, Any]] = [
        {
            "item": shell,
            "description": "Fashion face — confirm fibre, weight (GSM), hand, stretch",
            "qty": "TBD",
            "unit": "m",
            "placement": "Body / skirt / sleeves as designed",
            "color_code": color_hint or "lab dip TBD",
            "supplier_ref": "TBD",
            "source": "estimate",
            "review_status": "needs_review",
            "notes": proposed,
        },
        {
            "item": "Lining",
            "description": "Acetate / cupro / poly lining — confirm if required",
            "qty": "TBD",
            "unit": "m",
            "placement": "Bodice + skirt (hang shorter than shell) if used",
            "color_code": "match or nude",
            "supplier_ref": "TBD",
            "source": "estimate",
            "review_status": "needs_review",
            "notes": "PROPOSED — waive only if designer confirms unlined shell.",
        },
        {
            "item": "Fusing / interfacing",
            "description": "Lightweight fusible for facings / stabilizers",
            "qty": "TBD",
            "unit": "m",
            "placement": "Neck facing, wrap edges, strap stabilizers",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "PROPOSED",
        },
        {
            "item": "Sewing thread",
            "description": "Poly / silk match",
            "qty": "1",
            "unit": "cone",
            "placement": "All seams",
            "color_code": "match shell",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "",
        },
        {
            "item": "Stay tape / clear elastic",
            "description": "Stabilize neckline / wrap edges / slit",
            "qty": "TBD",
            "unit": "m",
            "placement": "Bias edges, V neckline, slit top",
            "color_code": "—",
            "supplier_ref": "TBD",
            "source": "estimate",
            "notes": "Critical on bias / deep-V wrap necklines.",
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
            "description": "Brand + size + fibre/care (ISO 3758) — fibre TBD until material locked",
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
    ]
    if closure_family == "wrap":
        rows[2:2] = [
            {
                "item": "Self-fabric waist sash / tie",
                "description": "Width + length TBD — match shell; finish ends",
                "qty": "1",
                "unit": "pcs",
                "placement": "Waist wrap anchorage",
                "color_code": "match shell",
                "supplier_ref": "TBD",
                "source": "estimate",
                "review_status": "needs_review",
                "notes": "PROPOSED from wrap design — confirm dimensions (POMs sash_width / sash_length).",
            },
            {
                "item": "Optional inner hook / snap (designer decision)",
                "description": "NOT confirmed — only if wrap needs hidden security",
                "qty": "TBD",
                "unit": "set",
                "placement": "Wrap underlap at bust/waist — if approved",
                "color_code": "match",
                "supplier_ref": "TBD",
                "source": "estimate",
                "review_status": "needs_review",
                "notes": "DESIGN DECISION REQUIRED — do not treat as confirmed hardware.",
            },
        ]
        # Explicit: no invisible zipper row for wrap family.
    elif closure_family == "zip":
        rows[2:2] = [
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
        ]
    else:
        rows.insert(
            2,
            {
                "item": "Closure (UNRESOLVED)",
                "description": "Zip vs wrap/tie vs pull-on — designer must choose before sample",
                "qty": "TBD",
                "unit": "—",
                "placement": "TBD",
                "color_code": "—",
                "supplier_ref": "TBD",
                "source": "estimate",
                "review_status": "needs_review",
                "notes": "DESIGN DECISION REQUIRED — do not cut until closure is confirmed.",
            },
        )
    return rows


def scrub_conflicting_closure_bom(bom: list[Any], *, closure_family: str) -> list[dict[str, Any]]:
    """Drop zipper rows when wrap is detected; mark residual conflicts for review."""
    out: list[dict[str, Any]] = []
    for row in bom:
        if not isinstance(row, dict):
            continue
        item = str(row.get("item") or row.get("name") or "").lower()
        desc = str(row.get("description") or "").lower()
        blob = f"{item} {desc}"
        is_zip = "zip" in blob or "zipper" in blob
        is_hook_at_zip = "hook" in blob and "eye" in blob and ("zip" in blob or "zipper" in (row.get("placement") or "").lower())
        if closure_family == "wrap" and (is_zip or is_hook_at_zip):
            # Do not keep confirmed-looking zip qty on a wrap dress.
            continue
        cleaned = dict(row)
        if closure_family == "wrap" and "zip" in str(cleaned.get("placement") or "").lower():
            cleaned["placement"] = "N/A — wrap closure (no zip)"
            cleaned["review_status"] = "needs_review"
        out.append(cleaned)
    return out


def formal_dress_pattern_inventory(*, closure_family: str = "unknown") -> list[dict[str, Any]]:
    base = {
        "cut_qty": 1,
        "grainline": "straight",
        "fold": "none",
        "seam_allowance_cm": 1.0,
        "source": "estimate",
        "review_state": "proposed_unverified",
        "notes": "ILLUSTRATIVE INVENTORY — not a print-to-cut sewing pattern.",
    }
    if closure_family == "wrap":
        return [
            {
                **base,
                "id": "WR-LF",
                "name": "Left wrap front",
                "fabric": "shell",
                "cut_qty": 1,
                "notes": "Deep-V wrap panel + underlap — NOT TO SCALE inventory",
            },
            {
                **base,
                "id": "WR-RF",
                "name": "Right wrap front / underlayer",
                "fabric": "shell",
                "cut_qty": 1,
                "notes": "Supports wrap overlap — NOT TO SCALE inventory",
            },
            {
                **base,
                "id": "WR-B",
                "name": "Back shell",
                "fabric": "shell",
                "cut_qty": 1,
                "fold": "none",
                "notes": (
                    "PROPOSED back — do NOT cut on fold if a CB seam is later approved; "
                    "current pack assumes NO CB zipper. Designer must confirm."
                ),
            },
            {
                **base,
                "id": "WR-SK",
                "name": "Skirt / overlay panels",
                "fabric": "shell",
                "cut_qty": "TBD",
                "notes": "Slit + asymmetric drape panels — patternmaker drafts from POMs",
            },
            {
                **base,
                "id": "WR-SL",
                "name": "Sleeve",
                "fabric": "shell",
                "cut_qty": 2,
                "notes": "Omit if sleeveless",
            },
            {
                **base,
                "id": "WR-SASH",
                "name": "Waist sash / tie",
                "fabric": "shell",
                "cut_qty": 1,
                "notes": "From sash_width × sash_length POMs when filled",
            },
            {
                **base,
                "id": "WR-FC",
                "name": "Neck / wrap facing",
                "fabric": "shell or lining",
                "cut_qty": 1,
                "notes": "Stabilize deep-V; fuse lightly",
            },
        ]
    rows = [
        {**base, "id": "DR-F", "name": "Front shell", "fabric": "shell", "cut_qty": 1, "notes": "Include neckline / dart shaping as designed — NOT TO SCALE"},
        {**base, "id": "DR-B", "name": "Back shell", "fabric": "shell", "cut_qty": 1, "notes": "CB seam only if zip confirmed — NOT cut-on-fold with zip"},
        {**base, "id": "DR-SL", "name": "Sleeve (if sleeved)", "fabric": "shell", "cut_qty": 2, "notes": "Omit if sleeveless"},
        {**base, "id": "DR-LF", "name": "Front lining", "fabric": "lining", "cut_qty": 1, "notes": "1–2 cm shorter at hem"},
        {**base, "id": "DR-LB", "name": "Back lining", "fabric": "lining", "cut_qty": 1, "notes": "Facing as needed"},
        {**base, "id": "DR-FC", "name": "Neck / armhole facing", "fabric": "shell or lining", "cut_qty": 1, "notes": "Fuse lightly"},
    ]
    if closure_family == "zip":
        rows.append(
            {
                **base,
                "id": "DR-ZS",
                "name": "Zipper shield",
                "fabric": "lining",
                "cut_qty": 1,
                "notes": "Only when CB/SS invisible zip is confirmed",
            }
        )
    return rows


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
    # Synthesize tailor analysis fields for PDF-only rebuilds of older runs.
    illust = out.get("illustrations") if isinstance(out.get("illustrations"), dict) else {}
    analysis = illust.get("analysis") if isinstance(illust.get("analysis"), dict) else None
    if isinstance(analysis, dict):
        from app.services.techpack_tailor_ready import enrich_tailor_analysis_fields

        enrich_tailor_analysis_fields(analysis, out)
        out["illustrations"] = {**illust, "analysis": analysis}
    cat = str(out.get("category") or "other")
    color = str(out.get("color_hint") or "")
    closure_family = detect_closure_family(out)
    out["_closure_family"] = closure_family
    if closure_family == "wrap":
        # Redact invented CB-zip wording from AI back proposals so every page stays consistent.
        illust2 = out.get("illustrations") if isinstance(out.get("illustrations"), dict) else {}
        analysis2 = illust2.get("analysis") if isinstance(illust2.get("analysis"), dict) else None
        if isinstance(analysis2, dict):
            import re as _re

            prop = str(analysis2.get("back_construction_proposal") or "")
            if prop:
                prop = _re.sub(
                    r"[^.]*\b(?:invisible\s+)?zip(?:per)?\b[^.]*\.",
                    "",
                    prop,
                    flags=_re.I,
                ).strip()
                prop = " ".join(prop.split())
                if prop and not prop.endswith("."):
                    prop += "."
                prop = (
                    f"{prop} WRAP CLOSURE: do not introduce a CB zipper unless the designer "
                    "explicitly confirms one — pack assumes sash/tie wrap only."
                ).strip()
                analysis2 = {**analysis2, "back_construction_proposal": prop}
                out["illustrations"] = {**illust2, "analysis": analysis2}
    if is_formal_dress_category(cat):
        bom = out.get("bom") if isinstance(out.get("bom"), list) else []
        if closure_family == "wrap":
            # Replace estimated BOM entirely so AI zipper qty rows cannot survive scrub misses.
            base_wrap = formal_dress_bom(color_hint=color, closure_family="wrap")
            # Keep any non-closure designer-confirmed rows (supplier refs, custom trims).
            kept = [
                r
                for r in (bom or [])
                if isinstance(r, dict)
                and str(r.get("source") or "").lower() in {"designer", "confirmed", "user"}
                and "zip" not in f"{r.get('item','')} {r.get('description','')}".lower()
            ]
            out["bom"] = scrub_conflicting_closure_bom(base_wrap + kept, closure_family="wrap")
        elif not bom:
            out["bom"] = formal_dress_bom(color_hint=color, closure_family=closure_family)
        else:
            out["bom"] = scrub_conflicting_closure_bom(list(bom), closure_family=closure_family)
        steps = out.get("construction_steps") if isinstance(out.get("construction_steps"), list) else []
        if closure_family == "wrap" and steps:
            steps = _drop_zip_construction_steps(list(steps))
            out["construction_steps"] = steps
        ai_sourced = any(
            isinstance(s, dict)
            and str(s.get("source") or "").lower() in {"ai", "ai_vision", "ai_inferred"}
            for s in (steps or [])
        )
        defaults = construction_defaults_for_closure(closure_family)
        if ai_sourced:
            # Keep look-specific AI sew steps — do not overwrite with generic formal defaults.
            pass
        elif not steps:
            out["construction_steps"] = defaults
        elif steps and all(
            isinstance(s, dict) and not s.get("stitch_type") for s in steps
        ):
            out["construction_steps"] = defaults
        if closure_family == "wrap":
            out["construction_steps"] = _drop_zip_construction_steps(
                list(out.get("construction_steps") or [])
            )
        patterns = out.get("pattern_pieces") if isinstance(out.get("pattern_pieces"), list) else []
        if not patterns:
            out["pattern_pieces"] = formal_dress_pattern_inventory(closure_family=closure_family)
        else:
            # Flag cut-on-fold + zip conflicts on existing inventory.
            flagged: list[dict[str, Any]] = []
            for row in patterns:
                if not isinstance(row, dict):
                    continue
                r = dict(row)
                fold = str(r.get("fold") or "").lower()
                notes = str(r.get("notes") or "")
                name = str(r.get("name") or "").lower()
                if closure_family == "wrap" and ("zip" in notes.lower() or "zipper" in notes.lower()):
                    r["notes"] = (
                        notes + " · CONFLICT: wrap closure — ignore zip seam notes until designer confirms."
                    ).strip(" ·")
                    r["review_state"] = "needs_review"
                if closure_family == "zip" and "fold" in fold and "cb" in (fold + notes.lower()):
                    r["notes"] = (
                        notes
                        + " · CONFLICT: CB zip cannot be cut on fold — patternmaker must draft a CB seam."
                    ).strip(" ·")
                    r["review_state"] = "needs_review"
                # Wrap / MTM: cut-on-fold vs center-back seam is a real choice — do not
                # present both as settled facts in the same pack.
                if closure_family == "wrap" and (
                    "back" in name
                    or "back" in notes.lower()
                ):
                    says_fold = "cut on fold" in notes.lower() or "on fold" in fold or fold == "cb"
                    says_cb_seam = (
                        "center-back seam" in notes.lower()
                        or "centre-back seam" in notes.lower()
                        or "cb seam" in notes.lower()
                        or "center back seam" in notes.lower()
                    )
                    # Also compare against the written back proposal on the piece.
                    analysis_blob = ""
                    illust = out.get("illustrations") if isinstance(out.get("illustrations"), dict) else {}
                    if isinstance(illust.get("analysis"), dict):
                        analysis_blob = str(
                            illust["analysis"].get("back_construction_proposal") or ""
                        ).lower()
                    proposal_cb = any(
                        tok in analysis_blob
                        for tok in ("center-back seam", "centre-back seam", "cb seam", "center back seam")
                    )
                    if says_fold and (says_cb_seam or proposal_cb):
                        r["fold"] = "CHOICE — fold OR CB seam"
                        r["cut_qty"] = "1 if fold / 2 if CB seam"
                        r["notes"] = (
                            "CHOICE REQUIRED: cut-on-fold → cut qty 1; center-back seam → cut qty 2 "
                            "(mirror pair). Customer + tailor must pick one before the toile — "
                            "FashionRise does not decide. "
                            + notes
                        )
                        r["review_state"] = "needs_review"
                    elif says_fold and not says_cb_seam:
                        # Soften absolute fold language so it is not mistaken for a lock.
                        if "choice" not in notes.lower():
                            r["notes"] = (
                                "PROPOSED cut-on-fold (no CB zipper assumed) — tailor may draft a "
                                "CB seam instead if preferred for fit/shape. " + notes
                            )
                flagged.append(r)
            out["pattern_pieces"] = flagged
        # Ensure design-specific POM skeleton keys exist (empty until AI/designer fills).
        finished = out.get("finished_measurements") if isinstance(out.get("finished_measurements"), dict) else {}
        missing_note = "MISSING — designer / AI should fill before sample cut"
        for key in _DRESS_ONLY_DIM_KEYS:
            cell = finished.get(key) if isinstance(finished.get(key), dict) else None
            if cell is None:
                finished[key] = {
                    "value": None,
                    "unit": "cm",
                    "source": "empty",
                    "confidence": "unknown",
                    "review_status": "open",
                    "assumptions": ["Missing design-specific POM — required for faithful sample"],
                    "note": missing_note,
                }
            elif cell.get("value") in (None, "", "—"):
                # Present empty cells as missing rather than quiet blanks.
                upgraded = dict(cell)
                upgraded.setdefault("unit", "cm")
                upgraded["source"] = upgraded.get("source") or "empty"
                upgraded["review_status"] = upgraded.get("review_status") or "open"
                if "missing" not in str(upgraded.get("note") or "").lower():
                    upgraded["note"] = missing_note
                finished[key] = upgraded

        # Deep-V: neckline depth and v_depth are the same HPS→apex measure — keep one value.
        neck = finished.get("neckline") if isinstance(finished.get("neckline"), dict) else None
        vdep = finished.get("v_depth") if isinstance(finished.get("v_depth"), dict) else None
        neck_val = neck.get("value") if isinstance(neck, dict) else None
        v_val = vdep.get("value") if isinstance(vdep, dict) else None
        if isinstance(neck_val, (int, float)) and v_val in (None, "", "—"):
            finished["v_depth"] = {
                **(vdep or {}),
                "value": float(neck_val),
                "unit": str((neck or {}).get("unit") or "cm"),
                "source": str((neck or {}).get("source") or "ai"),
                "review_status": str((neck or {}).get("review_status") or "proposed"),
                "note": "Same measure as neckline depth (HPS → V apex) — not a second dimension.",
            }
        elif isinstance(v_val, (int, float)) and neck_val in (None, "", "—"):
            finished["neckline"] = {
                **(neck or {}),
                "value": float(v_val),
                "unit": str((vdep or {}).get("unit") or "cm"),
                "source": str((vdep or {}).get("source") or "ai"),
                "review_status": str((vdep or {}).get("review_status") or "proposed"),
                "note": "Same measure as v_depth (HPS → V apex).",
            }

        # Longest hem: garment_length must match hem_low when both are present.
        glen = finished.get("garment_length") if isinstance(finished.get("garment_length"), dict) else None
        hlow = finished.get("hem_low") if isinstance(finished.get("hem_low"), dict) else None
        g_val = glen.get("value") if isinstance(glen, dict) else None
        hl_val = hlow.get("value") if isinstance(hlow, dict) else None
        if isinstance(g_val, (int, float)) and isinstance(hl_val, (int, float)):
            longest = max(float(g_val), float(hl_val))
            if float(g_val) != longest:
                finished["garment_length"] = {
                    **glen,
                    "value": longest,
                    "note": (
                        f"Aligned to longest hem (was {g_val:g} cm; hem_low {hl_val:g} cm). "
                        "Garment length = HPS → longest finished hem."
                    ),
                }
            if float(hl_val) != longest:
                finished["hem_low"] = {
                    **hlow,
                    "value": longest,
                    "note": (
                        f"Aligned to garment length longest hem ({longest:g} cm). "
                        "hem_low is the longer asymmetric hem from HPS."
                    ),
                }

        # Flow sash POMs into sash BOM rows so tables agree.
        sw = finished.get("sash_width") if isinstance(finished.get("sash_width"), dict) else {}
        sl = finished.get("sash_length") if isinstance(finished.get("sash_length"), dict) else {}
        sw_v, sl_v = sw.get("value"), sl.get("value")
        if isinstance(out.get("bom"), list) and (
            isinstance(sw_v, (int, float)) or isinstance(sl_v, (int, float))
        ):
            synced_bom: list[Any] = []
            for row in out["bom"]:
                if not isinstance(row, dict):
                    continue
                item = str(row.get("item") or "").lower()
                if "sash" in item or ("tie" in item and "waist" in item):
                    width_txt = f"{float(sw_v):g} cm" if isinstance(sw_v, (int, float)) else "width TBD"
                    length_txt = f"{float(sl_v):g} cm" if isinstance(sl_v, (int, float)) else "length TBD"
                    src = str(sw.get("source") or sl.get("source") or "ai")
                    status = str(sw.get("review_status") or sl.get("review_status") or "proposed")
                    synced_bom.append(
                        {
                            **row,
                            "description": f"Finished sash {width_txt} × {length_txt} — match shell; finish ends",
                            "notes": (
                                f"From POM sash_width/sash_length · source={src} · status={status} "
                                "— AI/proposed until designer confirms."
                            ),
                            "review_status": "needs_review"
                            if status not in {"confirmed", "approved", "designer_confirmed"}
                            else row.get("review_status"),
                        }
                    )
                else:
                    synced_bom.append(row)
            out["bom"] = synced_bom

        # Same sash dimensions must appear in pattern-piece notes (no 4 cm vs 6 cm drift).
        if isinstance(sw_v, (int, float)) or isinstance(sl_v, (int, float)):
            import re as _re

            width_txt = f"{float(sw_v):g} cm" if isinstance(sw_v, (int, float)) else "width TBD"
            length_txt = f"{float(sl_v):g} cm" if isinstance(sl_v, (int, float)) else "length TBD"
            status = str(sw.get("review_status") or sl.get("review_status") or "proposed")
            synced_patterns: list[Any] = []
            for row in out.get("pattern_pieces") or []:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").lower()
                notes = str(row.get("notes") or "")
                if "sash" in name or "tie" in name or "sash" in notes.lower():
                    cleaned = _re.sub(
                        r"\s*\(from sash_width POM\)",
                        "",
                        notes,
                        flags=_re.I,
                    )
                    cleaned = _re.sub(
                        r"approx\.?\s*\d+(?:\.\d+)?\s*cm\s*wide",
                        f"{width_txt} wide",
                        cleaned,
                        flags=_re.I,
                    )
                    cleaned = _re.sub(
                        r"\b\d+(?:\.\d+)?\s*cm\s*wide\b",
                        f"{width_txt} wide",
                        cleaned,
                        flags=_re.I,
                    )
                    if width_txt not in cleaned:
                        cleaned = (
                            f"Finished sash {width_txt} × {length_txt} · status={status}. " + cleaned
                        ).strip()
                    elif "sash_width" not in cleaned.lower():
                        cleaned = f"{cleaned} · from sash_width POM ({status})"
                    synced_patterns.append({**row, "notes": cleaned})
                else:
                    synced_patterns.append(row)
            if synced_patterns:
                out["pattern_pieces"] = synced_patterns

        out["finished_measurements"] = finished

    # Non-dress pieces must not carry dress-only POMs (wrap/sash/slit) into the brief.
    if not is_formal_dress_category(cat):
        finished_nd = out.get("finished_measurements") if isinstance(out.get("finished_measurements"), dict) else {}
        if finished_nd:
            cleaned_fm = {
                k: v
                for k, v in finished_nd.items()
                if k not in _DRESS_ONLY_DIM_KEYS
            }
            out["finished_measurements"] = cleaned_fm
    return out


def humanize_readiness_gap(item: str) -> str:
    """Turn internal readiness tokens into designer-facing checklist language."""
    raw = str(item or "").strip()
    if not raw:
        return raw
    low = raw.lower()
    # Strip piece UUID prefixes: piece-aa3dd7b4:closures_specified → closures_specified
    if ":" in raw:
        raw = raw.split(":", 1)[-1]
        low = raw.lower()
    mapping = {
        "designer_confirmation_checklist": "Complete the designer confirmation checklist before sample cut.",
        "closures_specified": "Confirm the fastening method for this garment (visible design evidence first).",
        "construction_decisions": "Approve the construction / sew-order instructions for this garment.",
        "finished_poms_confirmed": "Verify and approve the final finished garment measurements.",
        "fit_ease_reviewed": "Review fit and ease against the sample size body measurements.",
        "material_specified": "Approve the shell fabric (fibre, composition, GSM / stretch) — color alone is not enough.",
        "pom_tolerances": "Confirm measurement tolerances for the sample.",
        "named_sample_size": "Confirm the named sample size.",
        "outfit_pieces": "Confirm garment pieces / components on the outfit.",
        "garment_identity": "Confirm garment category and identity for this piece.",
        "chest_and_length_poms": "Confirm bust / chest and length measurements.",
        "waist_hip_inseam_poms": "Confirm waist, hip, and inseam measurements.",
        "back_artwork_unverified": "Review the proposed back design (no Magic back image was provided).",
        "detail_artwork_unverified": "Review detail callout artwork against the design.",
    }
    if low in mapping:
        return mapping[low]
    # Soft fallback: readable words from snake_case
    return raw.replace("_", " ").strip().capitalize() + "."


SHIRT_CALLOUTS: list[tuple[str, str]] = [
    ("1", "Standing / designed collar + collar stand"),
    ("2", "Front placket / button spacing"),
    ("3", "Shoulder seam / yoke if present"),
    ("4", "Sleeve set / armhole"),
    ("5", "Sleeve roll-up or cuff finish"),
    ("6", "Side seam / waist shaping"),
    ("7", "Shirt-tail / curved hem"),
    ("8", "Back yoke / CB seam or fold"),
]

TROUSER_CALLOUTS: list[tuple[str, str]] = [
    ("1", "Waistband height + ease"),
    ("2", "Belt loops placement"),
    ("3", "Front fly / closure (proposed until confirmed)"),
    ("4", "Front pockets"),
    ("5", "Back pockets"),
    ("6", "Outseam / inseam balance"),
    ("7", "Leg taper / stripe or grain direction"),
    ("8", "Hem finish / finished inseam"),
]

SKIRT_CALLOUTS: list[tuple[str, str]] = [
    ("1", "Waistband / facing"),
    ("2", "Closure placement"),
    ("3", "Side seams / panels"),
    ("4", "Hem finish"),
    ("5", "Opening / slit if present"),
    ("6", "Grain / drape hang"),
]

SHIRT_QC: list[str] = [
    "Collar sits clean; stand height matches Magic look.",
    "Button spacing even; placket lies flat when worn.",
    "Sleeve set smooth; roll-up or cuff matches design.",
    "Shirt length / curved hem matches Magic proportions.",
    "Shoulder width and chest ease feel correct on the customer.",
]

TROUSER_QC: list[str] = [
    "Waistband sits at agreed rise; belt loops aligned.",
    "Fly (if used) operates cleanly — confirm before locking as approved.",
    "Pocket placement matches Magic look left/right.",
    "Stripe / grain direction matched across both legs.",
    "Inseam / outseam / hem length agreed with customer.",
]


def callouts_for_piece(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Category-aware discussion callouts — never reuse dress labels on shirts/jeans."""
    cat = str(piece.get("category") or "other").lower()
    family = detect_closure_family(piece)
    if is_formal_dress_category(cat) or family == "wrap":
        return list(WRAP_DRESS_CALLOUTS if family == "wrap" else FORMAL_DRESS_CALLOUTS)
    if cat in {"shirt", "top", "blouse"}:
        return list(SHIRT_CALLOUTS)
    if cat in {"trousers", "shorts", "jeans", "pants"}:
        return list(TROUSER_CALLOUTS)
    if cat == "skirt":
        return list(SKIRT_CALLOUTS)
    if cat == "jacket":
        return list(SHIRT_CALLOUTS)
    # Generic — still not dress-specific zipper/train callouts.
    return [
        ("1", "Primary silhouette / fit"),
        ("2", "Neckline / collar or waist finish"),
        ("3", "Closure (confirm type)"),
        ("4", "Sleeve or armhole if present"),
        ("5", "Hem / length"),
        ("6", "Distinctive design detail from Magic look"),
    ]


def qc_for_piece(piece: dict[str, Any]) -> list[str]:
    cat = str(piece.get("category") or "other").lower()
    family = detect_closure_family(piece)
    if family == "wrap" or is_formal_dress_category(cat):
        return list(WRAP_DRESS_QC if family == "wrap" else FORMAL_DRESS_QC)
    if cat in {"shirt", "top", "blouse", "jacket"}:
        return list(SHIRT_QC)
    if cat in {"trousers", "shorts", "jeans", "pants"}:
        return list(TROUSER_QC)
    return [
        "Key design details match the Magic look.",
        "Closure type and placement confirmed with customer.",
        "Finished length and fit ease agreed before cutting fashion fabric.",
    ]
