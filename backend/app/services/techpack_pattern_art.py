"""Deterministic high-quality pattern-piece breakdown illustrations.

Used when Professional AI skips ``pattern_sheet`` (multi-garment image budget) so
shirts/jeans still receive dress-benchmark visual piece maps — NOT printable patterns.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any


def _try_font(size: int):
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _piece_shape(
    name: str,
    category: str,
) -> str:
    """Map inventory name → silhouette family for drawing."""
    n = f"{name} {category}".lower()
    if any(t in n for t in ("collar", "stand", "neck")):
        return "collar"
    if "cuff" in n:
        return "cuff"
    if "placket" in n:
        return "placket"
    if "yoke" in n:
        return "yoke"
    if "sleeve" in n:
        return "sleeve"
    if any(t in n for t in ("waistband", "sash", "belt loop", "beltloops")):
        return "band"
    if "pocket" in n:
        return "pocket"
    if "fly" in n or "facing" in n or "shield" in n:
        return "facing"
    if any(t in n for t in ("leg", "trouser", "jean", "pant")):
        return "leg"
    if "skirt" in n or "overlay" in n or "drape" in n:
        return "panel"
    if "bodice" in n or "front" in n or "back" in n or "body" in n:
        return "body"
    if "lining" in n or "interfacing" in n or "stay" in n:
        return "strip"
    return "panel"


def _draw_shape(draw, kind: str, box: tuple[int, int, int, int], fill, outline) -> None:
    """Draw a fashion-pattern-like silhouette inside *box*."""
    left, top, right, bottom = box
    w, h = right - left, bottom - top
    cx, cy = left + w // 2, top + h // 2
    if kind == "sleeve":
        pts = [
            (left + int(w * 0.35), top + 4),
            (right - 4, top + int(h * 0.18)),
            (right - int(w * 0.12), bottom - 4),
            (left + int(w * 0.22), bottom - 4),
            (left + 4, top + int(h * 0.45)),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    elif kind == "leg":
        pts = [
            (left + int(w * 0.15), top + 4),
            (right - int(w * 0.15), top + 4),
            (right - int(w * 0.22), bottom - 4),
            (left + int(w * 0.28), bottom - 4),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    elif kind == "collar":
        pts = [
            (left + 6, bottom - 8),
            (left + int(w * 0.2), top + 6),
            (cx, top + int(h * 0.35)),
            (right - int(w * 0.2), top + 6),
            (right - 6, bottom - 8),
            (cx, bottom - int(h * 0.25)),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    elif kind == "cuff":
        draw.rounded_rectangle([left + 4, top + int(h * 0.25), right - 4, bottom - int(h * 0.25)], radius=6, fill=fill, outline=outline)
    elif kind == "placket":
        draw.rectangle([cx - max(8, w // 8), top + 4, cx + max(8, w // 8), bottom - 4], fill=fill, outline=outline)
    elif kind == "yoke":
        pts = [
            (left + 6, top + int(h * 0.35)),
            (left + int(w * 0.2), top + 6),
            (right - int(w * 0.2), top + 6),
            (right - 6, top + int(h * 0.35)),
            (right - 10, bottom - 6),
            (left + 10, bottom - 6),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    elif kind == "band":
        draw.rounded_rectangle([left + 4, top + int(h * 0.3), right - 4, bottom - int(h * 0.3)], radius=4, fill=fill, outline=outline)
    elif kind == "pocket":
        draw.rounded_rectangle([left + 10, top + 8, right - 10, bottom - 8], radius=8, fill=fill, outline=outline)
    elif kind == "facing":
        pts = [
            (left + 8, top + 6),
            (right - 8, top + 6),
            (right - 14, bottom - 6),
            (left + 14, bottom - 6),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    elif kind == "strip":
        draw.rectangle([left + 8, top + int(h * 0.35), right - 8, bottom - int(h * 0.35)], fill=fill, outline=outline)
    elif kind == "body":
        pts = [
            (left + int(w * 0.22), top + 6),
            (right - int(w * 0.22), top + 6),
            (right - int(w * 0.08), top + int(h * 0.22)),
            (right - int(w * 0.12), bottom - 6),
            (left + int(w * 0.12), bottom - 6),
            (left + int(w * 0.08), top + int(h * 0.22)),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    else:  # panel
        pts = [
            (left + int(w * 0.18), top + 6),
            (right - int(w * 0.18), top + 6),
            (right - 8, bottom - 6),
            (left + 8, bottom - 6),
        ]
        draw.polygon(pts, fill=fill, outline=outline)
    # Grainline arrow
    draw.line([(cx, top + 14), (cx, bottom - 14)], fill=outline, width=1)
    draw.polygon([(cx, top + 10), (cx - 4, top + 18), (cx + 4, top + 18)], fill=outline)


def render_pattern_breakdown_png(
    patterns: list[dict[str, Any]],
    *,
    category: str = "",
    label: str = "",
    width: int = 1600,
    height: int = 2000,
) -> Path | None:
    """Full-page visual piece breakdown matching inventory IDs (temp PNG)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    rows = [p for p in patterns if isinstance(p, dict)][:12]
    if not rows:
        return None

    paper = (248, 244, 236)
    ink = (32, 28, 24)
    muted = (110, 100, 90)
    accent = (140, 50, 40)
    fill = (255, 252, 248)
    outline = (55, 48, 42)

    im = Image.new("RGB", (width, height), paper)
    draw = ImageDraw.Draw(im)
    title_font = _try_font(36)
    sub_font = _try_font(22)
    id_font = _try_font(28)
    small_font = _try_font(18)
    tiny_font = _try_font(15)

    heading = f"PATTERN PIECE BREAKDOWN — {(category or 'garment').upper()}"
    draw.text((48, 36), heading, fill=ink, font=title_font)
    sub = (label or category or "garment").strip()
    draw.text((48, 84), sub[:80], fill=muted, font=sub_font)
    draw.text(
        (48, 118),
        "NOT TO SCALE · NOT a printable sewing pattern · Match each shape to the inventory ID",
        fill=accent,
        font=tiny_font,
    )
    draw.line([(48, 150), (width - 48, 150)], fill=(200, 190, 175), width=2)

    n = len(rows)
    cols = 3 if n > 4 else (2 if n > 1 else 1)
    # Leave margins; compute cell grid.
    margin_x, margin_y = 48, 180
    gap_x, gap_y = 28, 36
    grid_w = width - 2 * margin_x
    grid_h = height - margin_y - 70
    rows_n = (n + cols - 1) // cols
    cell_w = (grid_w - gap_x * (cols - 1)) // cols
    cell_h = (grid_h - gap_y * (rows_n - 1)) // max(1, rows_n)
    shape_h = max(120, cell_h - 70)

    for i, row in enumerate(rows):
        col = i % cols
        r = i // cols
        x0 = margin_x + col * (cell_w + gap_x)
        y0 = margin_y + r * (cell_h + gap_y)
        pid = str(row.get("id") or chr(65 + i))
        name = str(row.get("name") or "Piece")
        cut = row.get("cut_qty")
        cut_txt = "—" if cut is None else str(cut)
        grain = str(row.get("grainline") or "straight")
        fabric = str(row.get("fabric") or "shell")

        # Card frame — avoid overlapping by strict cell bounds.
        draw.rounded_rectangle(
            [x0, y0, x0 + cell_w - 2, y0 + cell_h - 2],
            radius=10,
            outline=(180, 170, 155),
            width=2,
            fill=(255, 255, 252),
        )
        # ID badge
        badge_r = 22
        bx, by = x0 + 28, y0 + 28
        draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r], outline=accent, width=2, fill=(245, 235, 228))
        # Center ID text roughly
        draw.text((bx - 8, by - 12), pid[:3], fill=accent, font=id_font)

        draw.text((x0 + 58, y0 + 14), name[:34], fill=ink, font=small_font)
        meta = f"Cut {cut_txt} · {fabric} · grain {grain[:18]}"
        draw.text((x0 + 58, y0 + 40), meta[:42], fill=muted, font=tiny_font)

        shape_box = (x0 + 18, y0 + 68, x0 + cell_w - 20, y0 + 68 + shape_h)
        kind = _piece_shape(name, category)
        _draw_shape(draw, kind, shape_box, fill=fill, outline=outline)

    draw.text(
        (48, height - 48),
        "FashionRise schematic · tailor drafts the real pattern from customer measurements",
        fill=muted,
        font=tiny_font,
    )

    out = Path(tempfile.mkstemp(prefix="fr_pattern_break_", suffix=".png")[1])
    im.save(out, format="PNG", optimize=True)
    return out
