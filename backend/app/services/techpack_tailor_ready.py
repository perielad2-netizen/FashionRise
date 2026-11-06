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


def scrub_contradictory_flat_labels(
    source: Path | None,
    *,
    forbidden_tokens: tuple[str, ...] = _ZIP_LABEL_TOKENS,
    replacement_note: str | None = None,
    always_banner: bool = False,
    wipe_all_text: bool = False,
) -> Path | None:
    """Silently cover burned-in AI text that contradicts / clutters the brief.

    Default behaviour for MTM wrap packs:
    - Cover forbidden tokens (zip…) and optionally *all* OCR text so the garment
      drawing stays clean — no \"REMOVED\" stamps and no correction banners in-image.
    - The PDF page caption states that illustrations are unverified concepts.
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
            words = _tesseract_word_boxes(source)
            forbid = {t.lower() for t in forbidden_tokens}
            hit_idxs: set[int] = set()
            for i, word in enumerate(words):
                token = word["low"]
                if wipe_all_text:
                    # Drop tiny OCR noise / single punctuation.
                    if len(token) >= 1 and any(ch.isalnum() for ch in token):
                        hit_idxs.add(i)
                    continue
                if token in forbid or any(tok in token for tok in forbid):
                    hit_idxs.add(i)
            # Expand zip hits to same-line context (CENTER BACK ZIPPER…).
            if hit_idxs and not wipe_all_text:
                expanded = set(hit_idxs)
                for i in list(hit_idxs):
                    base = words[i]
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
            # Slightly larger pad when wiping all text so leader lines / callout
            # numbers near labels disappear with the words.
            pad = max(10 if wipe_all_text else 8, w // (140 if wipe_all_text else 180))
            patches = _merge_label_boxes(boxes, pad=pad)

            # Prefer the page paper color over sampling near labels (callout
            # circles / white leader pads produce ugly white correction patches).
            paper = im.getpixel((min(8, w - 1), min(8, h - 1)))
            if isinstance(paper, int):
                paper = (paper, paper, paper)
            # Soft cream fallback typical of FashionRise flats.
            if sum(paper[:3]) < 500:
                paper = (245, 240, 232)

            def _cover(left: int, top: int, right: int, bottom: int) -> None:
                left = max(0, left)
                top = max(0, top)
                right = min(w, right)
                bottom = min(h, bottom)
                if right - left < 4 or bottom - top < 4:
                    return
                draw.rectangle([left, top, right, bottom], fill=paper)

            redacted = 0
            for left, top, right, bottom in patches:
                _cover(left, top, right, bottom)
                redacted += 1

            # Second pass for residual forbidden tokens only (not full wipe — OCR
            # after a full wipe often invents noise).
            if redacted and not wipe_all_text:
                tmp_pass = Path(tempfile.mkstemp(prefix="fr_flat_scrub_pass_", suffix=".png")[1])
                im.save(tmp_pass, format="PNG")
                try:
                    residual = _tesseract_word_boxes(tmp_pass)
                    residual_boxes: list[tuple[int, int, int, int]] = []
                    for word in residual:
                        token = word["low"]
                        if token in forbid or any(tok in token for tok in forbid):
                            residual_boxes.append(
                                (word["left"], word["top"], word["right"], word["bottom"])
                            )
                    for left, top, right, bottom in _merge_label_boxes(
                        residual_boxes, pad=max(10, w // 160)
                    ):
                        _cover(left, top, right, bottom)
                        redacted += 1
                finally:
                    try:
                        tmp_pass.unlink(missing_ok=True)
                    except Exception:
                        pass

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
    """Clean garment flat for made-to-measure briefs: wipe burned-in AI text silently."""
    return scrub_contradictory_flat_labels(
        source,
        wipe_all_text=True,
        always_banner=False,
        replacement_note=None,
    )


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
