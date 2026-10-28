"""Deterministic technical-flat / pattern schematics for Create Real Design V2.

These are PATTERN DEVELOPMENT SCHEMATICS — NOT TO SCALE. They must match the
structured garment category and never invent an opposite Magic photo.
"""

from __future__ import annotations

from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

INK = colors.HexColor("#1a2233")
MUTED = colors.HexColor("#6b7385")
ACCENT = colors.HexColor("#c45d8c")
FILL = colors.HexColor("#f7f1ea")


def _label(d: Drawing, x: float, y: float, text: str, size: int = 7) -> None:
    d.add(String(x, y, text, fontName="Helvetica", fontSize=size, fillColor=MUTED))


def shirt_flat(*, width: float = 220, height: float = 280, back: bool = False) -> Drawing:
    d = Drawing(width, height)
    # Body
    d.add(Polygon([70, 230, 150, 230, 165, 80, 55, 80], strokeColor=INK, strokeWidth=1.4, fillColor=FILL))
    # Shoulders / neck
    if back:
        d.add(Line(85, 230, 135, 230, strokeColor=INK, strokeWidth=1.2))
        _label(d, 88, 250, "BACK — SHIRT")
    else:
        d.add(Polygon([85, 230, 110, 210, 135, 230], strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
        d.add(Line(110, 210, 110, 100, strokeColor=INK, strokeWidth=0.8, strokeDashArray=[2, 2]))
        _label(d, 78, 250, "FRONT — SHIRT")
    # Sleeves
    d.add(Polygon([70, 230, 35, 200, 50, 175, 75, 195], strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
    d.add(Polygon([150, 230, 185, 200, 170, 175, 145, 195], strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
    # Hem
    d.add(Line(55, 80, 165, 80, strokeColor=INK, strokeWidth=1.2))
    # Grainline
    d.add(Line(110, 195, 110, 110, strokeColor=ACCENT, strokeWidth=1))
    d.add(String(114, 150, "grain", fontName="Helvetica", fontSize=6, fillColor=ACCENT))
    _label(d, 20, 20, "SCHEMATIC — NOT TO SCALE")
    return d


def trousers_flat(*, width: float = 220, height: float = 280, back: bool = False) -> Drawing:
    d = Drawing(width, height)
    # Waistband
    d.add(Rect(70, 230, 80, 12, strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
    # Legs
    d.add(Polygon([70, 230, 105, 230, 115, 50, 55, 50], strokeColor=INK, strokeWidth=1.4, fillColor=FILL))
    d.add(Polygon([115, 230, 150, 230, 165, 50, 105, 50], strokeColor=INK, strokeWidth=1.4, fillColor=FILL))
    # Crotch curve hint
    d.add(Line(105, 230, 110, 180, strokeColor=INK, strokeWidth=1))
    d.add(Line(115, 230, 110, 180, strokeColor=INK, strokeWidth=1))
    if not back:
        d.add(Line(110, 230, 110, 200, strokeColor=INK, strokeWidth=1.2))  # fly
        _label(d, 70, 255, "FRONT — TROUSERS")
    else:
        d.add(Line(95, 220, 125, 220, strokeColor=INK, strokeWidth=0.8))  # yoke hint
        _label(d, 72, 255, "BACK — TROUSERS")
    d.add(Line(110, 210, 110, 90, strokeColor=ACCENT, strokeWidth=1))
    d.add(String(114, 140, "grain", fontName="Helvetica", fontSize=6, fillColor=ACCENT))
    _label(d, 20, 20, "SCHEMATIC — NOT TO SCALE")
    return d


def dress_flat(*, width: float = 220, height: float = 280, back: bool = False) -> Drawing:
    d = Drawing(width, height)
    d.add(Polygon([75, 235, 145, 235, 170, 50, 50, 50], strokeColor=INK, strokeWidth=1.4, fillColor=FILL))
    if back:
        d.add(Line(90, 235, 130, 235, strokeColor=INK, strokeWidth=1.2))
        _label(d, 78, 255, "BACK — DRESS")
    else:
        d.add(Polygon([90, 235, 110, 215, 130, 235], strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
        _label(d, 75, 255, "FRONT — DRESS")
    d.add(Line(60, 150, 160, 150, strokeColor=MUTED, strokeWidth=0.7, strokeDashArray=[2, 2]))
    _label(d, 62, 154, "waist")
    d.add(Line(110, 210, 110, 80, strokeColor=ACCENT, strokeWidth=1))
    _label(d, 20, 20, "SCHEMATIC — NOT TO SCALE")
    return d


def skirt_flat(*, width: float = 220, height: float = 280, back: bool = False) -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(75, 220, 70, 10, strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
    d.add(Polygon([75, 220, 145, 220, 175, 60, 45, 60], strokeColor=INK, strokeWidth=1.4, fillColor=FILL))
    _label(d, 70, 250, "BACK — SKIRT" if back else "FRONT — SKIRT")
    d.add(Line(110, 210, 110, 90, strokeColor=ACCENT, strokeWidth=1))
    _label(d, 20, 20, "SCHEMATIC — NOT TO SCALE")
    return d


def jacket_flat(*, width: float = 220, height: float = 280, back: bool = False) -> Drawing:
    d = shirt_flat(width=width, height=height, back=back)
    # Overwrite title-ish by adding lapel hint
    if not back:
        d.add(Line(110, 210, 95, 170, strokeColor=INK, strokeWidth=1))
        d.add(Line(110, 210, 125, 170, strokeColor=INK, strokeWidth=1))
    return d


def generic_flat(*, width: float = 220, height: float = 280, back: bool = False, title: str = "GARMENT") -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(60, 60, 100, 170, strokeColor=INK, strokeWidth=1.4, fillColor=FILL, rx=8, ry=8))
    d.add(Circle(110, 210, 18, strokeColor=INK, strokeWidth=1.2, fillColor=FILL))
    _label(d, 55, 250, f"{'BACK' if back else 'FRONT'} — {title.upper()}")
    _label(d, 20, 20, "SCHEMATIC — NOT TO SCALE")
    return d


def flat_for_category(category: str, *, back: bool = False) -> Drawing:
    cat = (category or "other").lower()
    if cat in ("shirt", "top"):
        return shirt_flat(back=back)
    if cat in ("trousers", "shorts"):
        return trousers_flat(back=back)
    if cat == "dress":
        return dress_flat(back=back)
    if cat == "skirt":
        return skirt_flat(back=back)
    if cat == "jacket":
        return jacket_flat(back=back)
    if cat == "jumpsuit":
        return dress_flat(back=back)
    return generic_flat(back=back, title=cat)


def pattern_inventory_for_category(category: str) -> list[dict[str, Any]]:
    """Qualified pattern-piece planning rows — not print-to-scale cutters."""
    cat = (category or "other").lower()
    common = {"cut_qty": 1, "grainline": "straight", "fold": "none", "seam_allowance_cm": 1.0, "source": "estimate"}
    if cat in ("shirt", "top"):
        return [
            {**common, "id": "SH-F", "name": "Front", "fabric": "shell", "cut_qty": 1, "fold": "CF on fold or CF seam"},
            {**common, "id": "SH-B", "name": "Back", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "SH-SL", "name": "Sleeve", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "SH-CL", "name": "Collar / neck finish", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "SH-CF", "name": "Cuff / facing (if applicable)", "fabric": "shell", "cut_qty": 2},
        ]
    if cat in ("trousers", "shorts"):
        return [
            {**common, "id": "TR-F", "name": "Front leg", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "TR-B", "name": "Back leg", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "TR-WB", "name": "Waistband", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "TR-PK", "name": "Pocket bag (if applicable)", "fabric": "lining", "cut_qty": 2},
            {**common, "id": "TR-FLY", "name": "Fly / closure facing (if applicable)", "fabric": "shell", "cut_qty": 1},
        ]
    if cat == "dress":
        return [
            {**common, "id": "DR-F", "name": "Front", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "DR-B", "name": "Back", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "DR-SL", "name": "Sleeve (if sleeved)", "fabric": "shell", "cut_qty": 2},
        ]
    if cat == "skirt":
        return [
            {**common, "id": "SK-F", "name": "Front", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "SK-B", "name": "Back", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "SK-WB", "name": "Waistband", "fabric": "shell", "cut_qty": 1},
        ]
    if cat == "jacket":
        return [
            {**common, "id": "JK-F", "name": "Front", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "JK-B", "name": "Back", "fabric": "shell", "cut_qty": 1},
            {**common, "id": "JK-SL", "name": "Sleeve", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "JK-CL", "name": "Collar", "fabric": "shell", "cut_qty": 2},
            {**common, "id": "JK-FC", "name": "Facing", "fabric": "shell", "cut_qty": 2},
        ]
    return [{**common, "id": "GN-1", "name": "Main body", "fabric": "shell", "cut_qty": 1}]


def default_construction_steps(category: str) -> list[dict[str, Any]]:
    cat = (category or "other").lower()
    if cat in ("shirt", "top"):
        steps = [
            "Staystitch neckline and fuse interfacing where required.",
            "Join shoulder seams; finish with overlock or clean finish.",
            "Set sleeves or finish armholes for sleeveless design.",
            "Attach collar/neck finish; topstitch as designed.",
            "Close side seams; finish hems and cuffs.",
            "Install closure (buttons/placket/zipper) and press.",
        ]
    elif cat in ("trousers", "shorts"):
        steps = [
            "Sew darts/pleats if present; assemble pocket bags.",
            "Join front crotch; install fly/closure if designed.",
            "Join back crotch; sew inseams then outseams (or as preferred sequence).",
            "Attach waistband with even ease distribution.",
            "Hem legs; press creases only if design requires.",
            "QC: rise balance, waistband seat, closure function.",
        ]
    elif cat == "dress":
        steps = [
            "Join bust/waist darts or princess seams as designed.",
            "Close shoulders and side seams; finish edges.",
            "Set sleeves or finish armholes; attach neck finish.",
            "Install closure; hem; press.",
            "QC: length, neckline sit, closure alignment.",
        ]
    elif cat == "skirt":
        steps = [
            "Join panels; insert zipper or other closure.",
            "Attach waistband or facing; understitch.",
            "Hem; press; QC hang and opening finish.",
        ]
    else:
        steps = [
            "Confirm panel inventory with patternmaker.",
            "Assemble major seams; install closures.",
            "Finish edges and hem; press; QC fit sample.",
        ]
    return [{"step": i + 1, "instruction": s, "source": "estimate"} for i, s in enumerate(steps)]


def default_bom(
    category: str,
    *,
    color_hint: str = "",
    piece: dict | None = None,
) -> list[dict[str, Any]]:
    shell_name = f"{color_hint} shell".strip() if color_hint else "Shell fabric"
    rows = [
        {"item": shell_name, "qty": "estimate TBD", "unit": "m", "source": "estimate", "notes": "Width/weight unknown until confirmed"},
        {"item": "Thread", "qty": "1", "unit": "cone", "source": "estimate", "notes": "Match shell"},
        {"item": "Care / brand label", "qty": "1", "unit": "set", "source": "estimate", "notes": ""},
    ]
    cat = (category or "").lower()
    closure_row = None
    if isinstance(piece, dict):
        from app.services.techpack_spec_fidelity import closure_bom_row

        closure_row = closure_bom_row(piece)
    if cat in ("shirt", "jacket"):
        rows.insert(
            1,
            closure_row
            or {
                "item": "Buttons or zipper",
                "qty": "TBD",
                "unit": "pcs",
                "source": "estimate",
                "notes": "Confirm closure choice",
            },
        )
        rows.insert(1, {"item": "Interfacing", "qty": "estimate TBD", "unit": "m", "source": "estimate", "notes": "Collar/placket as needed"})
    if cat in ("trousers", "shorts", "skirt"):
        rows.insert(
            1,
            closure_row
            or {
                "item": "Zipper / elastic / closure",
                "qty": "1",
                "unit": "pcs",
                "source": "estimate",
                "notes": "Confirm closure",
            },
        )
    return rows
