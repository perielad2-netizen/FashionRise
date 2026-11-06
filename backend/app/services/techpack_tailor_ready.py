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

# Per-step grade (cm) — stored circ POMs are FULL circumference.
GRADE_DELTA_CM: dict[str, float] = {
    # Full circumference
    "chest_bust": 2.0,
    "waist": 2.0,
    "hip": 2.0,
    "hem": 2.4,
    "thigh": 1.4,
    "leg_opening": 1.0,
    "waistband": 0.3,  # height, not circ
    "cuff": 0.8,
    "knee": 1.2,
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


def enrich_tailor_analysis_fields(analysis: dict[str, Any], piece: dict[str, Any]) -> None:
    """Ensure tailor-facing analysis keys exist even when the model omits them."""
    if not isinstance(analysis, dict):
        return
    if not isinstance(analysis.get("callout_points"), list) or not analysis.get("callout_points"):
        probe = dict(piece)
        probe["illustrations"] = {
            **(piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}),
            "analysis": {**analysis, "callout_points": []},
        }
        analysis["callout_points"] = [
            {"n": n, "label": label, "region": "garment"}
            for n, label in callout_legend_for_piece(probe)
        ]
    if not isinstance(analysis.get("hardware"), list) or not analysis.get("hardware"):
        hw: list[dict[str, Any]] = []
        closure = str(analysis.get("closure_visible") or "")
        if closure and closure.lower() not in {"none", "n/a", "—", "-", ""}:
            hw.append(
                {
                    "item": "Closure",
                    "spec": closure[:120],
                    "placement": "As visible / proposed",
                    "qty": "1",
                    "unit": "pcs",
                    "color": str(piece.get("color_hint") or "match"),
                }
            )
        for feat in (analysis.get("distinctive_features") or [])[:6]:
            text = str(feat)
            low = text.lower()
            if any(t in low for t in ("zip", "hook", "button", "sash", "tie", "belt", "boning", "cup")):
                hw.append(
                    {
                        "item": text[:80],
                        "spec": "From distinctive features — confirm",
                        "placement": "As designed",
                        "qty": "1",
                        "unit": "pcs",
                        "color": str(piece.get("color_hint") or "match"),
                    }
                )
        if hw:
            analysis["hardware"] = hw
    if not isinstance(analysis.get("care_recommendation"), dict):
        analysis["care_recommendation"] = care_recommendation(
            {"illustrations": {"analysis": analysis}, "color_hint": piece.get("color_hint")}
        )
    if not analysis.get("pantone_estimate"):
        colors = analysis.get("colors")
        if isinstance(colors, list) and colors:
            analysis["pantone_estimate"] = f"{colors[0]} — confirm Pantone TCX / lab dip"
        elif piece.get("color_hint"):
            analysis["pantone_estimate"] = (
                f"{piece.get('color_hint')} — confirm Pantone TCX / lab dip"
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


_CIRC_GRADE_KEYS = {"chest_bust", "waist", "hip", "hem", "thigh", "leg_opening", "cuff", "knee"}


def _pom_basis_confirmed(row: dict[str, Any]) -> bool:
    """Grades require a confirmed base — AI/open/estimated circs must not auto-grade."""
    review = str(row.get("review_status") or "").lower()
    source = str(row.get("source") or "").lower()
    if review in {"confirmed", "approved", "designer_confirmed"}:
        return True
    if source in {"designer", "confirmed", "user"} and review not in {
        "needs_review",
        "proposed",
        "open",
        "ai",
    }:
        return True
    return False


def graded_pom_rows(
    piece: dict[str, Any],
    *,
    sample_size: str,
) -> list[dict[str, Any]]:
    """Finished POM rows with proposed XS–2XL grades (suppressed until base is confirmed)."""
    rows = finished_pom_rows(piece)
    out: list[dict[str, Any]] = []
    for row in rows:
        val = row.get("value")
        key = str(row.get("key") or "")
        grades: dict[str, Any] = {sz: None for sz in GRADE_SIZES}
        # Never auto-grade AI / open / estimated values — circ or length.
        allow_grade = isinstance(val, (int, float)) and _pom_basis_confirmed(row)
        if allow_grade:
            for sz in GRADE_SIZES:
                grades[sz] = grade_value(float(val), key=key, size=sz, sample_size=sample_size)
        out.append(
            {
                **row,
                "grades": grades,
                "grades_suppressed": (not allow_grade) and isinstance(val, (int, float)),
            }
        )
    return out


def callout_legend_for_piece(piece: dict[str, Any]) -> list[tuple[str, str]]:
    """Numbered construction/design callouts for PDF legend + flat overlay."""
    from app.services.techpack_designer_spec import callouts_for_piece, detect_closure_family

    cat = str(piece.get("category") or "other")
    wrap = detect_closure_family(piece) == "wrap"
    if is_formal_dress_category(cat):
        callouts = list(callouts_for_piece(piece))
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

    def _zip_label(label: str) -> bool:
        low = label.lower()
        return "zip" in low or "zipper" in low

    # Prefer AI-authored callouts only when they don't contradict wrap closure.
    ai_pts = analysis.get("callout_points") if isinstance(analysis.get("callout_points"), list) else []
    if ai_pts and not wrap:
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
        # Wrap: keep wrap legend as authority; append distinctive non-zip features only.
        features = analysis.get("distinctive_features") if isinstance(analysis.get("distinctive_features"), list) else []
        n = len(callouts)
        for feat in features[:6]:
            label = str(feat).strip()
            if not label:
                continue
            if wrap and _zip_label(label):
                continue
            n += 1
            callouts.append((str(n), label[:90]))
        if wrap:
            callouts = [(n, lab) for n, lab in callouts if not _zip_label(lab)]
            # Re-number after scrub.
            callouts = [(str(i), lab) for i, (_n, lab) in enumerate(callouts, start=1)]
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
    # Wrap dresses must not surface invented zipper hardware.
    from app.services.techpack_designer_spec import detect_closure_family

    if detect_closure_family(piece) == "wrap":
        cleaned_hw: list[dict[str, Any]] = []
        for r in rows:
            blob = f"{r.get('item','')} {r.get('spec','')} {r.get('placement','')}".lower()
            if "zip" in blob:
                continue
            if "hook" in blob and "eye" in blob and "zip" in blob:
                continue
            # Optional snaps/hooks must not appear as confirmed qty 1.
            if any(tok in blob for tok in ("snap", "hook", "press stud", "hook and eye")):
                r = {
                    **r,
                    "item": f"{r.get('item','Optional fastener')} · OPTIONAL / UNCONFIRMED",
                    "spec": (
                        "DESIGN DECISION — not confirmed. Do not cut or sew until designer approves."
                    ),
                    "qty": "TBD",
                    "unit": "—",
                }
            cleaned_hw.append(r)
        rows = cleaned_hw
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


_ZIP_LABEL_TOKENS = ("zip", "zipper", "zippers")
_ZIP_CONTEXT_TOKENS = ("center", "back", "cb", "invisible", "concealed", "hidden")


def _tesseract_word_boxes(source: Path) -> list[dict[str, Any]]:
    """Return word-level OCR boxes via tesseract TSV (empty if OCR unavailable)."""
    import shutil
    import subprocess

    if not shutil.which("tesseract"):
        return []
    try:
        proc = subprocess.run(
            ["tesseract", str(source), "stdout", "tsv"],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout:
        return []
    words: list[dict[str, Any]] = []
    lines = proc.stdout.splitlines()
    if len(lines) < 2:
        return []
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) < 12:
            continue
        try:
            conf = float(cols[10])
            left, top, width, height = (int(cols[6]), int(cols[7]), int(cols[8]), int(cols[9]))
        except (TypeError, ValueError):
            continue
        text = str(cols[11] or "").strip()
        if not text or conf < 40 or width <= 0 or height <= 0:
            continue
        words.append(
            {
                "text": text,
                "low": text.lower().strip(".,;:()[]{}"),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "conf": conf,
            }
        )
    return words


def _merge_label_boxes(boxes: list[tuple[int, int, int, int]], *, pad: int = 6) -> list[tuple[int, int, int, int]]:
    """Merge overlapping / nearby rectangles so multi-word labels become one patch."""
    if not boxes:
        return []
    rects = sorted(boxes, key=lambda b: (b[1], b[0]))
    merged: list[list[int]] = []
    for left, top, right, bottom in rects:
        hit = None
        for cur in merged:
            if left <= cur[2] + pad * 3 and right >= cur[0] - pad * 3 and top <= cur[3] + pad * 4 and bottom >= cur[1] - pad * 4:
                hit = cur
                break
        if hit is None:
            merged.append([left, top, right, bottom])
        else:
            hit[0] = min(hit[0], left)
            hit[1] = min(hit[1], top)
            hit[2] = max(hit[2], right)
            hit[3] = max(hit[3], bottom)
    return [(a - pad, b - pad, c + pad, d + pad) for a, b, c, d in merged]


def _is_callout_red(rgb: tuple[int, int, int]) -> bool:
    """True for saturated red marker ink typical of AI flat callout dots/numbers."""
    r, g, b = rgb
    return r >= 150 and r - g >= 55 and r - b >= 55 and g < 140 and b < 140


def _local_fill_color(
    px,
    *,
    w: int,
    h: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    paper: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Sample a ring around the wipe box so fabric areas are not patched with paper white."""
    samples: list[tuple[int, int, int]] = []
    ring = max(4, min(18, (right - left + bottom - top) // 8))
    for y in range(max(0, top - ring), min(h, bottom + ring)):
        for x in range(max(0, left - ring), min(w, right + ring)):
            inside = left <= x < right and top <= y < bottom
            if inside:
                continue
            # Only the ring, not a huge neighborhood.
            if not (
                left - ring <= x < right + ring and top - ring <= y < bottom + ring
            ):
                continue
            if left - 1 <= x < right + 1 and top - 1 <= y < bottom + 1:
                # Skip immediate edge (often still marker ink).
                if left <= x < right or top <= y < bottom:
                    continue
            c = px[x, y]
            if isinstance(c, int):
                c = (c, c, c)
            if _is_callout_red(c[:3]):
                continue
            samples.append(c[:3])
    if len(samples) < 8:
        return paper
    # Median per channel — robust against leftover ink speckles.
    rs = sorted(s[0] for s in samples)
    gs = sorted(s[1] for s in samples)
    bs = sorted(s[2] for s in samples)
    mid = len(samples) // 2
    return (rs[mid], gs[mid], bs[mid])


def _red_marker_boxes(px, *, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Find compact red callout blobs (circles / digits) burned into AI flats."""
    visited = bytearray(w * h)
    boxes: list[tuple[int, int, int, int]] = []
    min_area = max(12, (w * h) // 90000)
    max_area = max(400, (w * h) // 900)
    max_span = max(28, min(w, h) // 18)
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            idx = y * w + x
            if visited[idx]:
                continue
            c = px[x, y]
            if isinstance(c, int):
                c = (c, c, c)
            if not _is_callout_red(c[:3]):
                continue
            # Flood-fill compact red component.
            stack = [(x, y)]
            visited[idx] = 1
            cells: list[tuple[int, int]] = []
            while stack and len(cells) < max_area + 20:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in (
                    (cx - 2, cy),
                    (cx + 2, cy),
                    (cx, cy - 2),
                    (cx, cy + 2),
                    (cx - 2, cy - 2),
                    (cx + 2, cy + 2),
                ):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    nidx = ny * w + nx
                    if visited[nidx]:
                        continue
                    visited[nidx] = 1
                    nc = px[nx, ny]
                    if isinstance(nc, int):
                        nc = (nc, nc, nc)
                    if _is_callout_red(nc[:3]):
                        stack.append((nx, ny))
            if not cells:
                continue
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            left, right = min(xs), max(xs) + 1
            top, bottom = min(ys), max(ys) + 1
            bw, bh = right - left, bottom - top
            area = len(cells)
            if area < min_area or area > max_area:
                continue
            if bw > max_span or bh > max_span:
                continue
            # Prefer roughly circular / digit-sized blobs.
            if max(bw, bh) > 0 and min(bw, bh) / max(bw, bh) < 0.35:
                continue
            boxes.append((left, top, right, bottom))
    return boxes


def _soft_cover_patch(
    im,
    px,
    *,
    w: int,
    h: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    paper: tuple[int, int, int],
) -> None:
    """Fill a small patch using local neighbour colour (no hard white rectangles)."""
    from PIL import ImageDraw

    left = max(0, left)
    top = max(0, top)
    right = min(w, right)
    bottom = min(h, bottom)
    if right - left < 3 or bottom - top < 3:
        return
    # Reject huge patches — those create unfinished-looking slabs on the garment.
    if (right - left) * (bottom - top) > (w * h) // 18:
        return
    fill = _local_fill_color(
        px, w=w, h=h, left=left, top=top, right=right, bottom=bottom, paper=paper
    )
    # Prefer a slightly inset cover so fabric edges stay intact.
    pad_in = 1 if min(right - left, bottom - top) > 10 else 0
    ImageDraw.Draw(im).rectangle(
        [left + pad_in, top + pad_in, right - pad_in, bottom - pad_in], fill=fill
    )


def scrub_contradictory_flat_labels(
    source: Path | None,
    *,
    forbidden_tokens: tuple[str, ...] = _ZIP_LABEL_TOKENS,
    replacement_note: str | None = None,
    always_banner: bool = False,
    wipe_all_text: bool = False,
    wipe_callout_markers: bool = False,
    wipe_small_labels: bool = False,
) -> Path | None:
    """Silently cover burned-in AI text / red callout markers that clutter the brief.

    Customer-facing MTM behaviour:
    - Prefer removing compact red markers + short callout labels only.
    - Avoid blanket OCR wipes that leave visible white / cream rectangles.
    - Fill from local neighbourhood colour, never paper white on fabric.
    Returns a temp PNG, or None if the source cannot be opened.
    """
    if source is None or not source.exists():
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    try:
        with Image.open(source) as im0:
            im = im0.convert("RGB")
            w, h = im.size
            draw = ImageDraw.Draw(im)
            px = im.load()
            words = _tesseract_word_boxes(source)
            forbid = {t.lower() for t in forbidden_tokens}
            hit_idxs: set[int] = set()
            for i, word in enumerate(words):
                token = word["low"]
                wh = max(1, int(word.get("height") or 1))
                ww = max(1, int(word.get("right", 0) - word.get("left", 0)))
                if wipe_all_text:
                    if len(token) >= 1 and any(ch.isalnum() for ch in token):
                        hit_idxs.add(i)
                    continue
                if token in forbid or any(tok in token for tok in forbid):
                    hit_idxs.add(i)
                    continue
                if wipe_small_labels:
                    # Callout digits / short stamps only — skip long body copy OCR noise
                    # that would require large cover rectangles.
                    is_digit = token.isdigit() and len(token) <= 2
                    is_short = 1 <= len(token) <= 12 and wh <= max(28, h // 28) and ww <= max(120, w // 8)
                    looks_label = is_digit or (
                        is_short
                        and any(ch.isalpha() for ch in token)
                        and token
                        not in {
                            "front",
                            "back",
                            "left",
                            "right",
                            "view",
                            "flat",
                            "cm",
                        }
                    )
                    # Prefer tokens near image margins (typical annotation columns).
                    near_margin = (
                        word["left"] < w * 0.12
                        or word["right"] > w * 0.88
                        or word["top"] < h * 0.08
                        or word["bottom"] > h * 0.92
                    )
                    if is_digit or (looks_label and near_margin):
                        hit_idxs.add(i)
            # Expand zip hits to same-line context (CENTER BACK ZIPPER…).
            if hit_idxs and not wipe_all_text:
                expanded = set(hit_idxs)
                for i in list(hit_idxs):
                    base = words[i]
                    base_is_zip = base["low"] in forbid or any(tok in base["low"] for tok in forbid)
                    if not base_is_zip:
                        continue
                    for j, other in enumerate(words):
                        if j in expanded:
                            continue
                        if other["low"] not in _ZIP_CONTEXT_TOKENS and other["low"] not in forbid:
                            continue
                        same_band = abs(other["top"] - base["top"]) <= max(18, int(base["height"] * 1.6))
                        near_x = abs(other["left"] - base["left"]) <= max(220, int(w * 0.28))
                        if same_band and near_x:
                            expanded.add(j)
                hit_idxs = expanded
            boxes = [
                (words[i]["left"], words[i]["top"], words[i]["right"], words[i]["bottom"])
                for i in sorted(hit_idxs)
            ]
            pad = max(6, w // 220)
            if wipe_all_text:
                pad = max(10, w // 140)
            patches = _merge_label_boxes(boxes, pad=pad)

            paper = im.getpixel((min(8, w - 1), min(8, h - 1)))
            if isinstance(paper, int):
                paper = (paper, paper, paper)
            if sum(paper[:3]) < 500:
                paper = (245, 240, 232)

            redacted = 0
            for left, top, right, bottom in patches:
                _soft_cover_patch(
                    im, px, w=w, h=h, left=left, top=top, right=right, bottom=bottom, paper=paper
                )
                redacted += 1

            # Red callout dots / digits — always for MTM marker mode.
            if wipe_callout_markers or wipe_all_text:
                for left, top, right, bottom in _red_marker_boxes(px, w=w, h=h):
                    pad_r = max(2, min(8, (right - left + bottom - top) // 5))
                    _soft_cover_patch(
                        im,
                        px,
                        w=w,
                        h=h,
                        left=left - pad_r,
                        top=top - pad_r,
                        right=right + pad_r,
                        bottom=bottom + pad_r,
                        paper=paper,
                    )
                    redacted += 1

            # Optional legacy banner — off by default so corrections stay invisible.
            if always_banner:
                try:
                    banner_font = ImageFont.truetype(
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        max(14, min(28, w // 42)),
                    )
                except Exception:
                    banner_font = ImageFont.load_default()
                note = replacement_note or "UNVERIFIED concept illustration — follow written brief"
                bh = max(28, h // 36)
                draw.rectangle([0, 0, w, bh], fill=(255, 236, 210))
                draw.text((max(8, w // 80), max(4, bh // 6)), note, fill=(120, 40, 20), font=banner_font)

            out = Path(tempfile.mkstemp(prefix="fr_flat_scrub_", suffix=".png")[1])
            im.save(out, format="PNG")
            return out
    except Exception:
        return None


def prepare_mtm_flat(source: Path | None) -> Path | None:
    """Clean MTM flats without leaving visible white erasure patches.

    Strategy (customer-facing):
    - Remove compact red callout markers via local neighbour fill.
    - Remove only small OCR tokens that look like callout numbers / short labels,
      plus forbidden zip stamps — never blanket-cover the whole drawing.
    - Prefer leaving a clean garment over rectangular paper patches.
    """
    return scrub_contradictory_flat_labels(
        source,
        wipe_all_text=False,
        wipe_callout_markers=True,
        wipe_small_labels=True,
        always_banner=False,
        replacement_note=None,
    )


def pattern_inventory_schematic(patterns: list[dict[str, Any]], *, category: str = "") -> Drawing:
    """Labeled piece cards matching inventory IDs — used when pattern_sheet art is missing."""
    d = Drawing(500, 280)
    d.add(Rect(0, 0, 500, 280, strokeColor=colors.Color(0.75, 0.72, 0.68), strokeWidth=0.6, fillColor=colors.Color(0.98, 0.96, 0.93)))
    title = f"PATTERN PIECE MAP — {(category or 'garment').upper()} (schematic IDs only · NOT a cutting pattern)"
    d.add(String(12, 258, title, fontName="Helvetica-Bold", fontSize=9, fillColor=colors.Color(0.15, 0.12, 0.1)))
    d.add(
        String(
            12,
            242,
            "Each card matches an inventory ID. FashionRise did not generate a full-page piece illustration for this run.",
            fontName="Helvetica",
            fontSize=7,
            fillColor=colors.Color(0.35, 0.32, 0.28),
        )
    )
    rows = [p for p in patterns if isinstance(p, dict)][:12]
    if not rows:
        d.add(String(12, 140, "No pattern pieces listed.", fontName="Helvetica", fontSize=9, fillColor=colors.Color(0.4, 0.2, 0.15)))
        return d
    cols = 4 if len(rows) > 4 else max(2, len(rows))
    card_w = 110
    card_h = 70
    gap_x = 12
    gap_y = 12
    origin_x = 16
    origin_y = 160
    for i, row in enumerate(rows):
        col = i % cols
        r = i // cols
        x = origin_x + col * (card_w + gap_x)
        y = origin_y - r * (card_h + gap_y) - card_h
        pid = str(row.get("id") or chr(65 + i))
        name = str(row.get("name") or "Piece")[:28]
        cut = row.get("cut_qty")
        cut_txt = "—" if cut is None else str(cut)
        grain = str(row.get("grainline") or "straight")[:16]
        d.add(Rect(x, y, card_w, card_h, strokeColor=colors.Color(0.25, 0.22, 0.2), strokeWidth=1.1, fillColor=colors.white))
        d.add(Circle(x + 16, y + card_h - 16, 11, strokeColor=colors.Color(0.55, 0.15, 0.12), strokeWidth=1.2, fillColor=colors.Color(0.92, 0.88, 0.84)))
        d.add(String(x + 12, y + card_h - 20, pid[:3], fontName="Helvetica-Bold", fontSize=9, fillColor=colors.Color(0.45, 0.1, 0.08)))
        d.add(String(x + 32, y + card_h - 22, name, fontName="Helvetica", fontSize=7, fillColor=colors.Color(0.12, 0.1, 0.08)))
        d.add(String(x + 10, y + 28, f"Cut qty: {cut_txt}", fontName="Helvetica", fontSize=6.5, fillColor=colors.Color(0.25, 0.22, 0.2)))
        d.add(String(x + 10, y + 14, f"Grain: {grain}", fontName="Helvetica", fontSize=6.5, fillColor=colors.Color(0.35, 0.32, 0.28)))
        d.add(Line(x + 10, y + 40, x + card_w - 10, y + 40, strokeColor=colors.Color(0.8, 0.78, 0.74), strokeWidth=0.5))
    d.add(
        String(
            12,
            10,
            "NOT TO SCALE · Use Magic look + flats + this ID map until a full piece-breakdown illustration is available",
            fontName="Helvetica",
            fontSize=6.5,
            fillColor=colors.Color(0.4, 0.35, 0.3),
        )
    )
    return d


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
        ("301 lockstitch", "3.5–4 /cm", "Seams, staystitch, labels"),
        ("504 overlock 3-th", "3–4 /cm", "Edge finish (wovens)"),
        ("514 overlock 4-th", "3–4 /cm", "Knit seams / clean finish"),
        ("Blind hem", "per fabric", "Dress / formal hems"),
        ("Invisible zip", "3–3.5 /cm", "CB / SS concealed opening — only if zip confirmed"),
    ]
