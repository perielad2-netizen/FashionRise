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
    "slit_start": "V",
    "overlay_length": "W",
    "sash_width": "X",
    "sash_length": "Y",
    "hem_high": "Z1",
    "hem_low": "Z2",
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
        "Neckline DEPTH (cm) — HPS (or stated CF/CB ref) straight down to neckline edge. "
        "Not a circumference. State reference point in notes."
    ),
    "opening": "Opening / slit length (cm) — start point to hem, or zip placket length if zip used.",
    "wrap_overlap": "Wrap overlap at waist (cm) — CF underlap amount when wrapped closed.",
    "slit_start": "Slit start from waist (cm) — waist seam down to top of thigh slit.",
    "overlay_length": "Asymmetric overlay / drape length (cm) — attach point to free hem tip.",
    "sash_width": "Waist sash / tie finished width (cm).",
    "sash_length": "Waist sash / tie total length (cm), including both tails.",
    "hem_high": "Higher hem length from HPS (cm) when hem is asymmetric.",
    "hem_low": "Lower / longest hem length from HPS (cm) when hem is asymmetric.",
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
    """Return 'wrap' | 'zip' | 'unknown' from closures + AI analysis text."""
    closures = piece.get("closures") if isinstance(piece.get("closures"), dict) else {}
    blob_parts = [
        str(closures.get("type") or ""),
        str(closures.get("display_type") or ""),
        str(closures.get("display") or ""),
        str(piece.get("label") or ""),
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
    wrap_tokens = ("wrap", "sash", "tie", "crossover", "overlap", "kimono")
    zip_tokens = ("zip", "zipper", "invisible zip", "hook and eye at zip")
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
    # Zip tokens in analysis "closure_visible" only — ignore BOM boilerplate not in blob.
    has_zip = any(t in blob for t in zip_tokens) and not denies_zip
    if has_wrap and (denies_zip or not has_zip):
        return "wrap"
    if has_zip and not has_wrap:
        return "zip"
    if has_wrap:
        return "wrap"
    if has_zip:
        return "zip"
    return "unknown"


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
        if not bom:
            out["bom"] = formal_dress_bom(color_hint=color, closure_family=closure_family)
        else:
            # Scrub zip rows that contradict a detected wrap (legacy estimate BOM).
            out["bom"] = scrub_conflicting_closure_bom(list(bom), closure_family=closure_family)
            if closure_family == "wrap" and not any(
                "sash" in str(r.get("item") or "").lower() or "tie" in str(r.get("item") or "").lower()
                for r in out["bom"]
                if isinstance(r, dict)
            ):
                # Ensure wrap hardware decision row exists.
                sash_rows = [
                    r
                    for r in formal_dress_bom(color_hint=color, closure_family="wrap")
                    if "sash" in str(r.get("item") or "").lower()
                    or "hook / snap" in str(r.get("item") or "").lower()
                    or "closure (unresolved)" in str(r.get("item") or "").lower()
                ]
                out["bom"] = list(out["bom"]) + sash_rows
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
                flagged.append(r)
            out["pattern_pieces"] = flagged
        # Ensure design-specific POM skeleton keys exist (empty until AI/designer fills).
        finished = out.get("finished_measurements") if isinstance(out.get("finished_measurements"), dict) else {}
        for key in (
            "wrap_overlap",
            "slit_start",
            "overlay_length",
            "sash_width",
            "sash_length",
            "hem_high",
            "hem_low",
        ):
            if key not in finished:
                finished[key] = {
                    "value": None,
                    "unit": "cm",
                    "source": "empty",
                    "confidence": "unknown",
                    "review_status": "open",
                    "assumptions": ["Missing design-specific POM — required for faithful sample"],
                    "note": "MISSING — designer / AI should fill before sample cut",
                }
        out["finished_measurements"] = finished
    return out


def callouts_for_piece(piece: dict[str, Any]) -> list[tuple[str, str]]:
    if detect_closure_family(piece) == "wrap":
        return list(WRAP_DRESS_CALLOUTS)
    return list(FORMAL_DRESS_CALLOUTS)


def qc_for_piece(piece: dict[str, Any]) -> list[str]:
    if detect_closure_family(piece) == "wrap":
        return list(WRAP_DRESS_QC)
    return list(FORMAL_DRESS_QC)
