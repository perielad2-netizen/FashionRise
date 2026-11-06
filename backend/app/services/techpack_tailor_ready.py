"""Tailor / sample-room helpers for dense factory-facing tech packs.

Provides graded POM estimates, fabric swatches from Magic looks, callout-number
overlays on flats, hardware extraction, and ISO-style care icon drawings so the
V4 PDF can approach industry tailor-ready density without inventing sealed
production approvals.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm

from app.services.techpack_designer_spec import (
    FORMAL_DRESS_CALLOUTS,
    GRADE_SIZES,
    finished_pom_rows,
    is_formal_dress_category,
)

# Size steps relative to sample base (EU 38 ≈ M). Proposed grades only.
GRADE_STEP: dict[str, int] = {
    "XS": -2,
    "S": -1,
    "M": 0,
    "L": 1,
    "XL": 2,
    "2XL": 3,
}

# Per-step grade (cm) by measurement family — half measurements for circs.
GRADE_DELTA_CM: dict[str, float] = {
    # Circumference / half-span
    "chest_bust": 1.0,
    "waist": 1.0,
    "hip": 1.0,
    "hem": 1.2,
    "thigh": 0.7,
    "leg_opening": 0.5,
    "waistband": 1.0,
    "cuff": 0.4,
    "knee": 0.6,
    # Length
    "garment_length": 0.7,
    "skirt_length": 0.7,
    "sleeve_length": 0.5,
    "inseam": 0.7,
    "outseam": 0.7,
    # Narrow / depth
    "shoulder_width": 0.35,
    "armhole": 0.4,
    "neckline": 0.25,
    "front_rise": 0.3,
    "back_rise": 0.3,
    "opening": 0.4,
}

HARDWARE_TOKENS = (
    "zip",
    "zipper",
    "hook",
    "eye",
    "button",
    "snap",
    "rivet",
    "buckle",
    "clasp",
    "elastic",
    "tape",
    "boning",
    "cup",
    "stay",
)


def sample_grade_index(sample_size: str) -> int:
    """Map sample size label to grade step (default M / 0)."""
    raw = str(sample_size or "").strip().upper()
    if raw in GRADE_STEP:
        return GRADE_STEP[raw]
    # EU numeric: 34≈XS … 44≈2XL around 38=M
    try:
        n = int("".join(ch for ch in raw if ch.isdigit()) or "0")
    except ValueError:
        n = 0
    if n:
        # 38 → 0; each 2 EU sizes ≈ 1 grade step
        return int(round((n - 38) / 2.0))
    return 0


def grade_value(base: float, *, key: str, size: str, sample_size: str) -> float | None:
    """Proposed finished POM for *size* graded from sample base (cm)."""
    delta = float(GRADE_DELTA_CM.get(key, 0.5))
    step = GRADE_STEP.get(size, 0) - sample_grade_index(sample_size)
    if step == 0:
        return round(float(base), 1)
    return round(float(base) + delta * step, 1)


def graded_pom_rows(
    piece: dict[str, Any],
    *,
    sample_size: str,
) -> list[dict[str, Any]]:
    """Finished POM rows with proposed XS–2XL grades (clearly unverified)."""
    rows = finished_pom_rows(piece)
    out: list[dict[str, Any]] = []
    for row in rows:
        val = row.get("value")
        grades: dict[str, Any] = {}
        if isinstance(val, (int, float)):
            for sz in GRADE_SIZES:
                grades[sz] = grade_value(float(val), key=str(row["key"]), size=sz, sample_size=sample_size)
        else:
            for sz in GRADE_SIZES:
                grades[sz] = None
        out.append({**row, "grades": grades})
    return out


def callout_legend_for_piece(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Numbered construction/design callouts for PDF legend + flat overlay."""
    cat = str(piece.get("category") or "other")
    if is_formal_dress_category(cat):
        callouts = list(FORMAL_DRESS_CALLOUTS)
    else:
        callouts = [
            ("1", "Neckline / collar finish"),
            ("2", "Shoulder / armhole"),
            ("3", "Side seam / closure"),
            ("4", "Hem finish"),
            ("5", "Special feature (pocket / trim / slit)"),
        ]
    analysis = {}
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    if isinstance(illust.get("analysis"), dict):
        analysis = illust["analysis"]
    # Prefer AI-authored callout list when present.
    ai_pts = analysis.get("callout_points") if isinstance(analysis.get("callout_points"), list) else []
    if ai_pts:
        rebuilt: list[tuple[str, str]] = []
        for i, pt in enumerate(ai_pts[:18], start=1):
            if isinstance(pt, dict):
                label = str(pt.get("label") or pt.get("name") or "").strip()
                n = str(pt.get("n") or pt.get("number") or i)
            else:
                label = str(pt).strip()
                n = str(i)
            if label:
                rebuilt.append((n, label[:110]))
        if rebuilt:
            callouts = rebuilt
    else:
        features = analysis.get("distinctive_features") if isinstance(analysis.get("distinctive_features"), list) else []
        n = len(callouts)
        for feat in features[:6]:
            n += 1
            callouts.append((str(n), str(feat)[:90]))
    return callouts


def hardware_rows(piece: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract hardware / trim rows from BOM + AI analysis for a dedicated table."""
    rows: list[dict[str, Any]] = []
    bom = piece.get("bom") if isinstance(piece.get("bom"), list) else []
    for row in bom:
        if not isinstance(row, dict):
            continue
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("item", "name", "description", "placement", "notes")
        ).lower()
        if any(tok in blob for tok in HARDWARE_TOKENS):
            rows.append(
                {
                    "item": str(row.get("item") or row.get("name") or "—"),
                    "spec": str(row.get("description") or row.get("notes") or "—")[:120],
                    "placement": str(row.get("placement") or "—")[:80],
                    "color": str(row.get("color_code") or piece.get("color_hint") or "match")[:40],
                    "qty": str(row.get("qty") or "—"),
                    "unit": str(row.get("unit") or "pcs"),
                    "supplier": str(row.get("supplier_ref") or "TBD"),
                }
            )
    analysis = {}
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    if isinstance(illust.get("analysis"), dict):
        analysis = illust["analysis"]
    ai_hw = analysis.get("hardware") if isinstance(analysis.get("hardware"), list) else []
    for hw in ai_hw[:12]:
        if isinstance(hw, dict):
            rows.append(
                {
                    "item": str(hw.get("item") or hw.get("name") or "—"),
                    "spec": str(hw.get("spec") or hw.get("description") or "—")[:120],
                    "placement": str(hw.get("placement") or "—")[:80],
                    "color": str(hw.get("color") or piece.get("color_hint") or "match")[:40],
                    "qty": str(hw.get("qty") or "1"),
                    "unit": str(hw.get("unit") or "pcs"),
                    "supplier": str(hw.get("supplier_ref") or "TBD"),
                }
            )
        elif str(hw).strip():
            rows.append(
                {
                    "item": str(hw)[:80],
                    "spec": "AI-suggested — confirm",
                    "placement": "—",
                    "color": str(piece.get("color_hint") or "match")[:40],
                    "qty": "1",
                    "unit": "pcs",
                    "supplier": "TBD",
                }
            )
    # Deduplicate by item+placement
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for r in rows:
        key = f"{r['item'].lower()}|{r['placement'].lower()}"
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)
    return uniq[:20]


def care_recommendation(piece: dict[str, Any]) -> dict[str, str]:
    """Propose ISO 3758 care text from fabric estimate (designer must confirm)."""
    analysis = {}
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    if isinstance(illust.get("analysis"), dict):
        analysis = illust["analysis"]
    fab = analysis.get("fabric_estimate") if isinstance(analysis.get("fabric_estimate"), dict) else {}
    fiber = str(fab.get("likely_fiber") or "").lower()
    hand = str(fab.get("hand") or "").lower()
    custom = analysis.get("care_recommendation") if isinstance(analysis.get("care_recommendation"), dict) else {}
    if custom:
        return {
            "wash": str(custom.get("wash") or "Confirm"),
            "bleach": str(custom.get("bleach") or "Do not bleach"),
            "dry": str(custom.get("dry") or "Confirm"),
            "iron": str(custom.get("iron") or "Confirm"),
            "dry_clean": str(custom.get("dry_clean") or "Confirm"),
        }
    delicate = any(x in fiber or x in hand for x in ("silk", "satin", "chiffon", "crepe", "lace", "metallic", "sequin"))
    if delicate:
        return {
            "wash": "Do not wash / professional wet clean",
            "bleach": "Do not bleach",
            "dry": "Do not tumble dry — hang/lay flat",
            "iron": "Cool iron with cloth · or none",
            "dry_clean": "Dry clean (P) preferred",
        }
    if "knit" in fiber or "jersey" in fiber or "spandex" in fiber or "elastane" in fiber:
        return {
            "wash": "Machine wash cold · gentle",
            "bleach": "Do not bleach",
            "dry": "Tumble low or hang dry",
            "iron": "Cool iron · no steam stretch",
            "dry_clean": "Dry clean optional",
        }
    return {
        "wash": "Gentle wash or dry clean — confirm fibre",
        "bleach": "Do not bleach",
        "dry": "Line dry / low tumble — confirm",
        "iron": "Medium iron · cloth on face",
        "dry_clean": "Dry clean if structured / lined",
    }


def pantone_or_color_code(piece: dict[str, Any]) -> str:
    mats = piece.get("materials") if isinstance(piece.get("materials"), dict) else {}
    shell = mats.get("shell") if isinstance(mats.get("shell"), dict) else {}
    for key in ("pantone", "color_code", "lab_dip"):
        val = shell.get(key)
        if val:
            return str(val)
    analysis = {}
    illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
    if isinstance(illust.get("analysis"), dict):
        analysis = illust["analysis"]
    est = analysis.get("pantone_estimate") or analysis.get("color_code_estimate")
    if est:
        return f"{est} (proposed · confirm lab dip)"
    hint = str(piece.get("color_hint") or "").strip()
    return f"{hint} — Pantone TCX / lab dip TBD" if hint else "Pantone TCX / lab dip TBD"


def extract_fabric_swatch(source: Path | None, *, size: int = 220) -> Path | None:
    """Crop a fabric-like swatch from the Magic look (torso center)."""
    if source is None or not source.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(source) as im:
            im = im.convert("RGB")
            w, h = im.size
            # Center torso band — avoid face/feet.
            left = int(w * 0.28)
            right = int(w * 0.72)
            top = int(h * 0.32)
            bottom = int(h * 0.62)
            crop = im.crop((left, top, max(left + 8, right), max(top + 8, bottom)))
            crop = crop.resize((size, size), Image.Resampling.LANCZOS)
            out = Path(tempfile.mkstemp(prefix="fr_swatch_", suffix=".png")[1])
            crop.save(out, format="PNG")
            return out
    except Exception:
        return None


def annotate_flat_callouts(
    source: Path | None,
    callouts: list[tuple[str, str]],
    *,
    side: str = "left",
) -> Path | None:
    """Stamp numbered callout dots + short leaders onto a flat (temp PNG).

    Approximate garment-side placement — patternmaker still annotates precisely.
    """
    if source is None or not source.exists() or not callouts:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    try:
        with Image.open(source) as im:
            im = im.convert("RGBA")
            w, h = im.size
            overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(14, w // 42))
            except Exception:
                font = ImageFont.load_default()
            n = min(len(callouts), 16)
            margin_x = int(w * (0.06 if side == "left" else 0.94))
            y0 = int(h * 0.12)
            y1 = int(h * 0.88)
            for i in range(n):
                num, _label = callouts[i]
                t = i / max(n - 1, 1)
                cy = int(y0 + (y1 - y0) * t)
                cx = margin_x
                tip_x = int(w * (0.28 if side == "left" else 0.72))
                # Leader
                draw.line([(cx, cy), (tip_x, cy)], fill=(180, 30, 30, 220), width=max(2, w // 400))
                r = max(12, w // 55)
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(180, 30, 30, 235), outline=(255, 255, 255, 255))
                text = str(num)
                # Center text in circle
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except Exception:
                    tw, th = 8, 10
                draw.text((cx - tw / 2, cy - th / 2 - 1), text, fill=(255, 255, 255, 255), font=font)
            composed = Image.alpha_composite(im, overlay).convert("RGB")
            out = Path(tempfile.mkstemp(prefix="fr_flat_ann_", suffix=".png")[1])
            composed.save(out, format="PNG")
            return out
    except Exception:
        return None


def care_icons_drawing(*, width: float = 170 * mm, height: float = 18 * mm) -> Drawing:
    """Simple ISO-3758-style care icon strip (schematic, not a standards facsimile)."""
    d = Drawing(width, height)
    labels = ["Wash", "Bleach", "Dry", "Iron", "Dry clean"]
    slot = width / 5.0
    for i, lab in enumerate(labels):
        x = i * slot + slot * 0.18
        y = height * 0.35
        s = min(slot * 0.45, height * 0.7)
        # Tub / triangle / square / iron / circle approximations
        if i == 0:  # wash tub
            d.add(Rect(x, y, s, s * 0.7, strokeColor=colors.black, fillColor=colors.white, strokeWidth=0.8))
            d.add(Line(x + s * 0.2, y + s * 0.85, x + s * 0.8, y + s * 0.85, strokeColor=colors.black, strokeWidth=0.8))
        elif i == 1:  # bleach triangle
            d.add(
                Line(x + s / 2, y + s * 0.9, x, y, strokeColor=colors.black, strokeWidth=0.8)
            )
            d.add(Line(x, y, x + s, y, strokeColor=colors.black, strokeWidth=0.8))
            d.add(Line(x + s, y, x + s / 2, y + s * 0.9, strokeColor=colors.black, strokeWidth=0.8))
            d.add(Line(x + s * 0.3, y + s * 0.35, x + s * 0.7, y + s * 0.35, strokeColor=colors.black, strokeWidth=1.2))
        elif i == 2:  # dry square
            d.add(Rect(x, y, s, s, strokeColor=colors.black, fillColor=colors.white, strokeWidth=0.8))
            d.add(Circle(x + s / 2, y + s / 2, s * 0.22, strokeColor=colors.black, fillColor=None, strokeWidth=0.8))
        elif i == 3:  # iron
            d.add(Rect(x, y + s * 0.15, s, s * 0.55, strokeColor=colors.black, fillColor=colors.white, strokeWidth=0.8))
            d.add(Line(x, y + s * 0.15, x + s * 0.25, y + s * 0.7, strokeColor=colors.black, strokeWidth=0.8))
        else:  # dry clean circle
            d.add(Circle(x + s / 2, y + s / 2, s * 0.42, strokeColor=colors.black, fillColor=None, strokeWidth=0.8))
            d.add(String(x + s / 2 - 3, y + s / 2 - 3, "P", fontSize=7, fillColor=colors.black))
        d.add(String(x, 1, lab, fontSize=6, fillColor=colors.Color(0.25, 0.25, 0.25)))
    return d


def seam_allowance_standards() -> list[tuple[str, str]]:
    return [
        ("Straight seams (woven)", "1.0–1.5 cm"),
        ("Zipper insertion", "1.5–2.0 cm"),
        ("Hem (dress / formal)", "2.5–4.0 cm (or baby hem)"),
        ("Neckline / armhole facing", "0.7–1.0 cm"),
        ("Knit overlock join", "0.7–1.0 cm (4-thread)"),
    ]


def thread_spi_defaults() -> list[tuple[str, str, str]]:
    return [
        ("301 lockstitch", "3.5–4 /cm", "Seams, staystitch, zip, labels"),
        ("504 overlock 3-th", "3–4 /cm", "Edge finish (wovens)"),
        ("514 overlock 4-th", "3–4 /cm", "Knit seams / clean finish"),
        ("Blind hem", "per fabric", "Dress / formal hems"),
        ("Invisible zip", "3–3.5 /cm", "CB / SS concealed opening"),
    ]
