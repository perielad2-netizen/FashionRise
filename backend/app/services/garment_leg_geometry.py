"""Deterministic lower-garment geometry for try-on fidelity (#170).

Detects separate trouser-leg columns from opaque Studio / plate pixels.
Used to:
- fail-closed FASHN prep for jumpsuits (unsupported as swimsuit one-pieces)
- add narrow OpenAI V2 design hints when two legs are clear
- soft post-generation silhouette review (major type mismatch only)

Never invents clothing details. Ambiguous silhouettes return looks_like_trousers=False.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

_ALPHA_THRESHOLD = 24
_NEAR_WHITE = 228


@dataclass(frozen=True)
class LowerGarmentGeometry:
    opaque_pixels: int
    bbox: tuple[int, int, int, int]  # x0,y0,x1,y1 inclusive max
    coverage_y_span_frac: float  # bbox height / image height
    hem_y_frac: float  # bbox.y1 / image height
    two_lobe_sample_ratio: float  # fraction of lower samples with exactly 2 runs
    avg_leg_width_frac: float  # mean run width / bbox width when two lobes
    avg_gap_frac: float
    mid_body_connected: bool
    looks_like_trousers: bool
    looks_like_jumpsuit: bool
    looks_like_narrow_legs: bool
    looks_like_wide_legs: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "opaque_pixels": self.opaque_pixels,
            "bbox": list(self.bbox),
            "coverage_y_span_frac": round(self.coverage_y_span_frac, 4),
            "hem_y_frac": round(self.hem_y_frac, 4),
            "two_lobe_sample_ratio": round(self.two_lobe_sample_ratio, 4),
            "avg_leg_width_frac": round(self.avg_leg_width_frac, 4),
            "avg_gap_frac": round(self.avg_gap_frac, 4),
            "mid_body_connected": self.mid_body_connected,
            "looks_like_trousers": self.looks_like_trousers,
            "looks_like_jumpsuit": self.looks_like_jumpsuit,
            "looks_like_narrow_legs": self.looks_like_narrow_legs,
            "looks_like_wide_legs": self.looks_like_wide_legs,
        }


def _load_rgba(png: bytes) -> Image.Image:
    with Image.open(io.BytesIO(png)) as im:
        im.load()
        return im.convert("RGBA")


def _opaque_mask(rgba: Image.Image) -> list[list[bool]]:
    """Treat alpha OR non-near-white RGB as garment (plates are opaque on white)."""
    w, h = rgba.size
    pix = rgba.load()
    assert pix is not None
    mask = [[False] * w for _ in range(h)]
    opaque_alpha = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if a >= _ALPHA_THRESHOLD:
                opaque_alpha += 1
                # Transparent garment PNGs: any opaque alpha is ink.
                if a < 250 or r < _NEAR_WHITE or g < _NEAR_WHITE or b < _NEAR_WHITE:
                    mask[y][x] = True
                    continue
                # Near-white opaque pixel on garment-only capture is usually empty paper bleed.
                if max(r, g, b) >= _NEAR_WHITE and abs(r - g) < 12 and abs(g - b) < 12:
                    continue
                mask[y][x] = True
    # Fully opaque product plates: rebuild from color (drop near-white bg).
    if opaque_alpha > 0.92 * w * h:
        for y in range(h):
            for x in range(w):
                r, g, b, _a = pix[x, y]
                if r >= _NEAR_WHITE and g >= _NEAR_WHITE and b >= _NEAR_WHITE or r >= 200 and g >= 200 and b >= 200 and abs(r - g) < 14 and abs(g - b) < 14:
                    mask[y][x] = False
                else:
                    mask[y][x] = True
    return mask


def _runs(row: list[bool]) -> list[tuple[int, int]]:
    """Inclusive-exclusive [start, end) opaque runs."""
    out: list[tuple[int, int]] = []
    x = 0
    n = len(row)
    while x < n:
        if not row[x]:
            x += 1
            continue
        s = x
        while x < n and row[x]:
            x += 1
        out.append((s, x))
    return out


def analyze_lower_garment_geometry(png: bytes) -> LowerGarmentGeometry:
    rgba = _load_rgba(png)
    mask = _opaque_mask(rgba)
    h = len(mask)
    w = len(mask[0]) if h else 0
    xs: list[int] = []
    ys: list[int] = []
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                xs.append(x)
                ys.append(y)
    empty = LowerGarmentGeometry(
        opaque_pixels=0,
        bbox=(0, 0, 0, 0),
        coverage_y_span_frac=0.0,
        hem_y_frac=0.0,
        two_lobe_sample_ratio=0.0,
        avg_leg_width_frac=0.0,
        avg_gap_frac=0.0,
        mid_body_connected=False,
        looks_like_trousers=False,
        looks_like_jumpsuit=False,
        looks_like_narrow_legs=False,
        looks_like_wide_legs=False,
    )
    if not xs:
        return empty

    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    bw = max(1, x1 - x0 + 1)
    bh = max(1, y1 - y0 + 1)
    coverage = bh / max(h, 1)
    hem = (y1 + 1) / max(h, 1)

    # Sample lower 40% of the garment bbox (not full canvas) for leg columns.
    sample_y0 = y0 + int(0.55 * bh)
    sample_y1 = y1
    two_lobe = 0
    samples = 0
    width_fracs: list[float] = []
    gap_fracs: list[float] = []
    for y in range(sample_y0, sample_y1 + 1, max(1, bh // 40)):
        runs = _runs(mask[y][x0 : x1 + 1])
        # Ignore speckles < 3% of bbox width.
        min_run = max(2, int(0.03 * bw))
        runs = [(a, b) for a, b in runs if (b - a) >= min_run]
        samples += 1
        if len(runs) == 2:
            two_lobe += 1
            left_w = runs[0][1] - runs[0][0]
            right_w = runs[1][1] - runs[1][0]
            gap = runs[1][0] - runs[0][1]
            if gap >= max(2, int(0.04 * bw)):
                width_fracs.append(((left_w + right_w) / 2.0) / bw)
                gap_fracs.append(gap / bw)

    ratio = two_lobe / max(samples, 1)
    avg_w = sum(width_fracs) / len(width_fracs) if width_fracs else 0.0
    avg_gap = sum(gap_fracs) / len(gap_fracs) if gap_fracs else 0.0

    # Mid/upper torso connected? (jumpsuit bodice) — sample upper third of bbox, not crotch.
    mid_connected = False
    for t in (0.22, 0.30, 0.38):
        mid_y = y0 + int(t * bh)
        mid_runs = _runs(mask[mid_y][x0 : x1 + 1])
        mid_runs = [(a, b) for a, b in mid_runs if (b - a) >= max(2, int(0.08 * bw))]
        if len(mid_runs) == 1:
            mid_connected = True
            break

    # Trousers: persistent dual lobes across lower samples + meaningful gap + hem not high-cut.
    # High-cut swimsuits can show a crotch notch but rarely sustain two full columns.
    trousers = (
        ratio >= 0.55
        and len(width_fracs) >= max(3, samples // 3)
        and avg_gap >= 0.06
        and hem >= 0.62
        and coverage >= 0.35
    )
    # Slit dresses: dual lobes only near the hem — reject when upper-lower samples lack lobes.
    if trousers and sample_y0 < y1:
        upper_lower_y0 = y0 + int(0.55 * bh)
        upper_lower_y1 = y0 + int(0.72 * bh)
        early = 0
        early_n = 0
        for y in range(upper_lower_y0, min(upper_lower_y1, y1) + 1, max(1, bh // 40)):
            runs = _runs(mask[y][x0 : x1 + 1])
            min_run = max(2, int(0.03 * bw))
            runs = [(a, b) for a, b in runs if (b - a) >= min_run]
            early_n += 1
            if len(runs) == 2 and (runs[1][0] - runs[0][1]) >= max(2, int(0.04 * bw)):
                early += 1
        if early_n and (early / early_n) < 0.35:
            trousers = False

    jumpsuit = trousers and mid_connected and coverage >= 0.45 and y0 < int(0.45 * h)
    narrow = trousers and avg_w > 0 and avg_w <= 0.32
    wide = trousers and avg_w >= 0.33

    return LowerGarmentGeometry(
        opaque_pixels=len(xs),
        bbox=(x0, y0, x1, y1),
        coverage_y_span_frac=float(coverage),
        hem_y_frac=float(hem),
        two_lobe_sample_ratio=float(ratio),
        avg_leg_width_frac=float(avg_w),
        avg_gap_frac=float(avg_gap),
        mid_body_connected=bool(mid_connected),
        looks_like_trousers=bool(trousers),
        looks_like_jumpsuit=bool(jumpsuit),
        looks_like_narrow_legs=bool(narrow),
        looks_like_wide_legs=bool(wide),
    )


def openai_trouser_design_hints(geometry: LowerGarmentGeometry) -> list[str]:
    """Additive V2 hints only when trouser geometry is clear. Empty when ambiguous."""
    if not geometry.looks_like_trousers:
        return []
    hints: list[str] = []
    if geometry.looks_like_jumpsuit:
        hints.append(
            "garment type: one-piece jumpsuit with trousers — not a dress, skirt, or swimsuit"
        )
    else:
        hints.append("garment type: trousers / pant legs — not a dress or skirt")
    hints.append(
        "keep both leg openings separate; preserve each hem position from image 2"
    )
    if geometry.looks_like_narrow_legs:
        hints.append(
            "preserve narrow leg width — do not flare, widen, or lengthen the legs"
        )
    elif geometry.looks_like_wide_legs:
        hints.append(
            "preserve the existing wide/flared leg width — do not narrow or merge the legs"
        )
    else:
        hints.append("preserve original leg width and length — do not flare or merge legs")
    hints.append("do not connect the legs into a continuous skirt panel")
    return hints


def classify_structure_image_role(png: bytes) -> str:
    """Classify PNG as isolated garment plate vs full photographic scene (#171).

    Returns ``isolated_garment``, ``full_scene``, or ``unknown``.
    Full try-on person photographs must not be measured as garment masks.
    """
    rgba = _load_rgba(png)
    w, h = rgba.size
    pix = rgba.load()
    assert pix is not None
    total = max(w * h, 1)
    transparent = 0
    near_white = 0
    other = 0
    skinish = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if a < _ALPHA_THRESHOLD:
                transparent += 1
                continue
            if r >= _NEAR_WHITE and g >= _NEAR_WHITE and b >= _NEAR_WHITE:
                near_white += 1
                continue
            if r >= 200 and g >= 200 and b >= 200 and abs(r - g) < 14 and abs(g - b) < 14:
                near_white += 1
                continue
            other += 1
            # Rough skin-tone band (not a classifier — only a full-scene hint).
            if 60 <= r <= 245 and 40 <= g <= 210 and 30 <= b <= 190 and r >= g >= b - 10 and (r - b) >= 15:
                skinish += 1
    transparent_frac = transparent / total
    near_white_frac = near_white / total
    other_frac = other / total
    skin_frac = skinish / max(other, 1)

    # Studio transparent garment captures (no person photo alpha).
    if transparent_frac >= 0.22 and other_frac <= 0.70:
        return "isolated_garment"
    # Photoreal try-on photographs often have studio near-white backgrounds + skin.
    # Detect these BEFORE flat-lay plate heuristics so skin/body is never a garment mask.
    if transparent_frac < 0.08 and skin_frac >= 0.08 and other_frac >= 0.12:
        return "full_scene"
    if transparent_frac < 0.08 and other_frac >= 0.40 and (skin_frac >= 0.04 or other_frac >= 0.55):
        return "full_scene"
    if transparent_frac < 0.05 and near_white_frac < 0.25 and other_frac >= 0.50:
        return "full_scene"
    # Flat-lay / white-plate products with substantial empty background and no skin.
    if (
        near_white_frac >= 0.30
        and other_frac <= 0.55
        and transparent_frac < 0.08
        and skin_frac < 0.05
    ):
        return "isolated_garment"
    return "unknown"


def soft_try_on_structure_review(
    *,
    source_png: bytes,
    result_png: bytes,
) -> dict[str, Any]:
    """Soft post-generation check for major lower-garment type mismatch (#170/#171).

    Only compares like-for-like **isolated garment** plates. Full photoreal person
    images are never treated as garment masks. Non-trouser sources skip the check
    without downgrading ordinary Try On results.

    States:
    - ``not_applicable`` — trousers check does not apply (ordinary outfits).
    - ``inconclusive`` — cannot compare (e.g. person photo vs garment plate).
    - ``failed`` — confirmed mismatch between two isolated garment images.
    - ``passed_soft`` — soft consistency only (not a fidelity certificate).
    """
    src = analyze_lower_garment_geometry(source_png)
    src_role = classify_structure_image_role(source_png)
    out_role = classify_structure_image_role(result_png)
    base: dict[str, Any] = {
        "version": "try-on-structure-review-v2",
        "source": src.public_dict(),
        "source_role": src_role,
        "result_role": out_role,
        "result": None,
    }
    if not src.looks_like_trousers:
        return {
            **base,
            "state": "not_applicable",
            "code": "STRUCTURE_CHECK_NOT_APPLICABLE",
            "message": (
                "Trousers/jumpsuit structure check does not apply to this sketch. "
                "Ordinary Try On preview is unchanged (concept preview — not a fit guarantee)."
            ),
            "faithful": None,
        }
    # Result is a full person photograph (or unknown scene) — not a garment plate.
    if out_role != "isolated_garment":
        return {
            **base,
            "state": "inconclusive",
            "code": "STRUCTURE_INCOMPARABLE_RESULT",
            "message": (
                "Automated garment-mask comparison cannot be applied to a full try-on "
                "photograph (skin, body, hair, and background are not the designed garment). "
                "No automated pass/fail is claimed."
            ),
            "faithful": None,
        }
    if src_role != "isolated_garment":
        return {
            **base,
            "state": "inconclusive",
            "code": "STRUCTURE_INCOMPARABLE_SOURCE",
            "message": (
                "Source image is not an isolated garment plate — structure check inconclusive."
            ),
            "faithful": None,
        }

    out = analyze_lower_garment_geometry(result_png)
    base["result"] = out.public_dict()

    # Source has clear trousers; isolated result lost dual lobes / continuous panel.
    if out.two_lobe_sample_ratio < 0.25 and out.avg_gap_frac < 0.04:
        return {
            **base,
            "state": "failed",
            "code": "STRUCTURE_LEGS_MERGED_OR_LOST",
            "message": (
                "Try On changed the lower garment: separate trouser legs from your sketch "
                "are missing or merged. Preview kept for review — not a faithful try-on."
            ),
            "faithful": False,
        }
    if (
        src.looks_like_narrow_legs
        and out.looks_like_wide_legs
        and out.avg_leg_width_frac >= src.avg_leg_width_frac + 0.12
    ):
        return {
            **base,
            "state": "failed",
            "code": "STRUCTURE_NARROW_LEGS_FLARED",
            "message": (
                "Try On widened narrow trouser legs into a flare. Preview kept for review "
                "— not a faithful try-on."
            ),
            "faithful": False,
        }
    if out.looks_like_trousers and abs(out.hem_y_frac - src.hem_y_frac) <= 0.12:
        return {
            **base,
            "state": "passed_soft",
            "code": "STRUCTURE_SOFT_OK",
            "message": "Lower-garment leg separation is roughly consistent (soft check only).",
            "faithful": None,
        }
    return {
        **base,
        "state": "inconclusive",
        "code": "STRUCTURE_INCONCLUSIVE_COMPARE",
        "message": (
            "Could not confidently verify lower-garment fidelity from plate geometry alone. "
            "No automated pass/fail is claimed."
        ),
        "faithful": None,
    }
