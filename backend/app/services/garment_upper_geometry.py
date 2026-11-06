"""Upper-garment geometry + OpenAI visibility prep for pale / bridal designs (#182).

Pale cream/ivory/peach fills on transparent PNGs flatten toward white inside
images.edit — deep V openings and under-filled sleeves disappear, and the model
fills cleavage or drops a sleeve. This module:

1. Detects pale-dominant fabric, open/plunging necklines, and bilateral sleeves
   from opaque Studio garment pixels.
2. Composites the garment onto a charcoal matte for OpenAI Try On only so pale
   fabric and negative-space openings stay readable.
3. Emits additive design hints (same budget rules as trouser geometry).

Never invents clothing. Ambiguous geometry returns empty hints.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

_ALPHA_THRESHOLD = 24
_PALE_MEAN_BRIGHTNESS = 185.0
_PALE_PIXEL_BRIGHTNESS = 200.0
# Charcoal matte — clearly not bridal fabric; only used for OpenAI edit input.
OPENAI_TRY_ON_GARMENT_MATTE_RGB = (42, 42, 48)
OPENAI_TRY_ON_VISIBILITY_VERSION = "openai-try-on-garment-visibility-v1"
# Magic keeps the croquis underlay — only lift pale fills off near-white paper (#183).
MAGIC_SKETCH_VISIBILITY_VERSION = "magic-sketch-visibility-v1"
MAGIC_PAPER_RGB = (200, 198, 204)
_MAGIC_PAPER_THRESHOLD = 248
_MAGIC_PALE_DEEPEN = 0.12  # lerp toward slightly deeper cream for contrast


@dataclass(frozen=True)
class UpperGarmentGeometry:
    opaque_pixels: int
    bbox: tuple[int, int, int, int]
    mean_brightness: float
    pale_pixel_frac: float
    pale_dominant: bool
    open_neckline: bool
    neckline_gap_frac: float
    left_sleeve: bool
    right_sleeve: bool
    bilateral_sleeves: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "opaque_pixels": self.opaque_pixels,
            "bbox": list(self.bbox),
            "mean_brightness": round(self.mean_brightness, 2),
            "pale_pixel_frac": round(self.pale_pixel_frac, 4),
            "pale_dominant": self.pale_dominant,
            "open_neckline": self.open_neckline,
            "neckline_gap_frac": round(self.neckline_gap_frac, 4),
            "left_sleeve": self.left_sleeve,
            "right_sleeve": self.right_sleeve,
            "bilateral_sleeves": self.bilateral_sleeves,
        }


def analyze_upper_garment_geometry(png: bytes) -> UpperGarmentGeometry:
    """Measure pale fabric + chest opening + sleeve masses from an isolated garment PNG."""
    empty = UpperGarmentGeometry(
        opaque_pixels=0,
        bbox=(0, 0, 0, 0),
        mean_brightness=0.0,
        pale_pixel_frac=0.0,
        pale_dominant=False,
        open_neckline=False,
        neckline_gap_frac=0.0,
        left_sleeve=False,
        right_sleeve=False,
        bilateral_sleeves=False,
    )
    if not png:
        return empty
    with Image.open(io.BytesIO(png)) as opened:
        rgba = opened.convert("RGBA")
    w, h = rgba.size
    if w < 8 or h < 8:
        return empty
    px = rgba.load()
    assert px is not None

    xs: list[int] = []
    ys: list[int] = []
    bright_sum = 0.0
    pale_count = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < _ALPHA_THRESHOLD:
                continue
            xs.append(x)
            ys.append(y)
            br = (r + g + b) / 3.0
            bright_sum += br
            if br >= _PALE_PIXEL_BRIGHTNESS:
                pale_count += 1
    if not xs:
        return empty

    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    opaque = len(xs)
    mean_br = bright_sum / opaque
    pale_frac = pale_count / opaque
    pale_dominant = mean_br >= _PALE_MEAN_BRIGHTNESS or pale_frac >= 0.55

    bw = max(x1 - x0 + 1, 1)
    bh = max(y1 - y0 + 1, 1)
    # Upper chest only (deep V lives near the top; lower torso closes and dilutes).
    chest_y0 = y0 + int(0.02 * bh)
    chest_y1 = y0 + int(0.28 * bh)
    gap_widths: list[float] = []
    for y in range(max(0, chest_y0), min(h, max(chest_y0 + 1, chest_y1))):
        left = right = None
        mid = (x0 + x1) // 2
        for x in range(x0, x1 + 1):
            if px[x, y][3] < _ALPHA_THRESHOLD:
                continue
            if x <= mid:
                left = x
            elif right is None:
                right = x
        if left is not None and right is not None and right > left:
            gap_widths.append(float(right - left) / float(bw))
        else:
            gap_widths.append(0.0)
    max_gap = max(gap_widths) if gap_widths else 0.0
    open_rows = sum(1 for g in gap_widths if g >= 0.04)
    open_row_frac = open_rows / len(gap_widths) if gap_widths else 0.0
    # Owner bridal dress (50f80224): max gap ≈0.17 of bbox in the upper chest.
    # High-neck solids stay near 0. Strong max gap alone is enough for plunging V.
    open_neckline = max_gap >= 0.10 or (max_gap >= 0.06 and open_row_frac >= 0.12)

    # Sleeve bands: outer quarters of upper/mid garment height.
    sleeve_y0 = y0 + int(0.08 * (y1 - y0 + 1))
    sleeve_y1 = y0 + int(0.55 * (y1 - y0 + 1))
    left_hits = right_hits = 0
    rows = 0
    left_limit = x0 + int(0.22 * bw)
    right_limit = x1 - int(0.22 * bw)
    for y in range(max(0, sleeve_y0), min(h, max(sleeve_y0 + 1, sleeve_y1))):
        rows += 1
        row_l = row_r = False
        for x in range(x0, x1 + 1):
            if px[x, y][3] < _ALPHA_THRESHOLD:
                continue
            if x <= left_limit:
                row_l = True
            if x >= right_limit:
                row_r = True
        if row_l:
            left_hits += 1
        if row_r:
            right_hits += 1
    left_sleeve = rows > 0 and (left_hits / rows) >= 0.18
    right_sleeve = rows > 0 and (right_hits / rows) >= 0.18

    return UpperGarmentGeometry(
        opaque_pixels=opaque,
        bbox=(x0, y0, x1, y1),
        mean_brightness=float(mean_br),
        pale_pixel_frac=float(pale_frac),
        pale_dominant=bool(pale_dominant),
        open_neckline=bool(open_neckline),
        neckline_gap_frac=float(max_gap),
        left_sleeve=bool(left_sleeve),
        right_sleeve=bool(right_sleeve),
        bilateral_sleeves=bool(left_sleeve and right_sleeve),
    )


def prepare_openai_try_on_garment_visibility(png: bytes) -> tuple[bytes, dict[str, Any]]:
    """Composite transparent garment onto charcoal matte for OpenAI images.edit.

    Always applied for OpenAI Try On garment input. Pale bridal fills and open
    neckline holes stay readable instead of vanishing into a white flatten.
    FASHN / Max paths must keep the original transparent PNG.
    """
    meta: dict[str, Any] = {
        "version": OPENAI_TRY_ON_VISIBILITY_VERSION,
        "matte_applied": False,
        "matte_rgb": list(OPENAI_TRY_ON_GARMENT_MATTE_RGB),
    }
    if not png:
        return png, meta
    with Image.open(io.BytesIO(png)) as opened:
        rgba = opened.convert("RGBA")
    matte = Image.new("RGBA", rgba.size, (*OPENAI_TRY_ON_GARMENT_MATTE_RGB, 255))
    composed = Image.alpha_composite(matte, rgba).convert("RGB")
    out = io.BytesIO()
    composed.save(out, format="PNG", optimize=True)
    meta["matte_applied"] = True
    return out.getvalue(), meta


def openai_upper_design_hints(geometry: UpperGarmentGeometry) -> list[str]:
    """Additive V2 hints for pale fabric / open neckline / two sleeves. Empty when N/A."""
    if geometry.opaque_pixels < 64:
        return []
    hints: list[str] = []
    if geometry.pale_dominant:
        hints.append(
            "intentional pale/cream/ivory/peach fabric — not empty paper; keep that light color opaque"
        )
        hints.append(
            "image 2 may sit on a dark matte for readability; the matte is NOT clothing"
        )
    if geometry.open_neckline:
        hints.append(
            "neckline: deep open / plunging V as drawn — keep cleavage opening; do not fill or raise to a high neck"
        )
    if geometry.bilateral_sleeves:
        hints.append(
            "sleeves: both arms have sleeves in image 2 — keep both; do not invent one-shoulder or drop a sleeve"
        )
    elif geometry.left_sleeve or geometry.right_sleeve:
        hints.append(
            "preserve the drawn sleeve placement from image 2 — do not add or remove sleeves"
        )
    return hints


def prepare_magic_sketch_visibility(png: bytes) -> tuple[bytes, dict[str, Any]]:
    """Lift pale bridal fills off near-white Studio paper for Magic images.edit (#183).

    Magic sketches include the croquis underlay — do NOT charcoal-matte the whole
    frame (that would wipe pose reference). Instead:
    - replace near-white paper with soft slate paper
    - slightly deepen pale fabric pixels so cream/ivory separates from paper/croquis
    - leave dark linework and saturated fills unchanged

    Output remains an opaque RGB PNG. Edit prompt still requests a clean light
    illustration background in the *result*.
    """
    meta: dict[str, Any] = {
        "version": MAGIC_SKETCH_VISIBILITY_VERSION,
        "paper_adjusted": False,
        "pale_pixels_deepened": 0,
        "paper_rgb": list(MAGIC_PAPER_RGB),
    }
    if not png:
        return png, meta
    with Image.open(io.BytesIO(png)) as opened:
        rgba = opened.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    assert px is not None
    paper = MAGIC_PAPER_RGB
    deepened = 0
    paper_hits = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < _ALPHA_THRESHOLD:
                # Transparent → soft paper (export usually already opaque).
                px[x, y] = (*paper, 255)
                paper_hits += 1
                continue
            if r >= _MAGIC_PAPER_THRESHOLD and g >= _MAGIC_PAPER_THRESHOLD and b >= _MAGIC_PAPER_THRESHOLD:
                px[x, y] = (*paper, 255)
                paper_hits += 1
                continue
            br = (r + g + b) / 3.0
            # Pale fabric band — deepen slightly for contrast; skip near-black ink.
            if br >= _PALE_MEAN_BRIGHTNESS and br < _MAGIC_PAPER_THRESHOLD:
                # Keep hue; pull toward a slightly deeper cream of the same channels.
                nr = int(r * (1.0 - _MAGIC_PALE_DEEPEN) + max(0, r - 28) * _MAGIC_PALE_DEEPEN)
                ng = int(g * (1.0 - _MAGIC_PALE_DEEPEN) + max(0, g - 32) * _MAGIC_PALE_DEEPEN)
                nb = int(b * (1.0 - _MAGIC_PALE_DEEPEN) + max(0, b - 36) * _MAGIC_PALE_DEEPEN)
                if (nr, ng, nb) != (r, g, b):
                    px[x, y] = (nr, ng, nb, a)
                    deepened += 1
    meta["paper_adjusted"] = paper_hits > 0
    meta["pale_pixels_deepened"] = deepened
    rgb = rgba.convert("RGB")
    out = io.BytesIO()
    rgb.save(out, format="PNG", optimize=True)
    return out.getvalue(), meta


def magic_upper_design_hints(geometry: UpperGarmentGeometry) -> list[str]:
    """Magic edit-brief hints (sketch is image 1 — wording differs from Try On)."""
    if geometry.opaque_pixels < 64:
        return []
    hints: list[str] = []
    if geometry.pale_dominant:
        hints.append(
            "intentional pale/cream/ivory/peach fabric in the sketch — opaque garment, not empty paper"
        )
        hints.append(
            "sketch paper may be slightly darkened for pale-fabric readability; paper is NOT clothing"
        )
    if geometry.open_neckline:
        hints.append(
            "neckline: deep open / plunging V as drawn — keep cleavage opening; do not fill or raise to a high neck"
        )
    if geometry.bilateral_sleeves:
        hints.append(
            "sleeves: both arms have sleeves as drawn — keep both; do not invent one-shoulder or drop a sleeve"
        )
    elif geometry.left_sleeve or geometry.right_sleeve:
        hints.append(
            "preserve the drawn sleeve placement — do not add or remove sleeves"
        )
    return hints
