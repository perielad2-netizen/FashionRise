"""Deterministic design-palette extraction + color lock for Social look try-ons.

FashionRise looks are illustrated design specs. Generative stages (OpenAI
materialize, FASHN Max) drift hue/depth and can collapse multi-tone panels. This
module measures the garment palette of the look plate in vertical bands and
re-imposes it on later images as a smooth, low-frequency color grade:

* chroma is rotated + scaled per band (hue and saturation return to the design while
  neutral highlights, shadows and skin seen through sheer layers stay neutral);
* luma is scaled per band (partial strength) so depth matches without flattening;
* panel boundaries are aligned first, so a longer torso or a cropped photo does not
  smear one panel's color into the next;
* the photographic texture (local detail) is left untouched.

Pillow only — the API host has no numpy.

Scope / honesty: only *chromatic* garment pixels that are distinguishable from
skin tones are measured and corrected. White / grey / black / nude garments yield
no palette and every lock becomes a no-op (prompt-only color guidance).
"""

from __future__ import annotations

import colorsys
import io
import logging
import math
from collections import deque
from typing import Any

from PIL import Image, ImageChops, ImageFilter

logger = logging.getLogger(__name__)

PALETTE_VERSION = 3
PALETTE_BANDS = 16

_WORK_H = 288
_MIN_SAT = 0.18
_MIN_VALUE = 30
_MIN_BAND_PIXELS = 24
_MIN_COVERAGE = 0.012
_MIN_VALID_BANDS = 3

# Correction clamps: keep the grade plausible even when a mask is imperfect.
_MAX_CHROMA_SHIFT = 56.0
_MIN_CHROMA_SCALE = 0.5
_MAX_CHROMA_SCALE = 2.4
_MAX_HUE_ROTATION = 1.4  # radians in the Cb/Cr plane
_NEUTRAL_CHROMA = 5.0
_MIN_LUMA_GAIN = 0.62
_MAX_LUMA_GAIN = 1.5
# Panels closer than this in Cb/Cr are one color for alignment purposes.
_MIN_PANEL_CONTRAST = 9.0
# A boundary found in a generated image counts when it keeps this share of the
# design's panel contrast (weaker = treated as a collapsed two-tone).
_MIN_BOUNDARY_CONTRAST_RATIO = 0.25
# Garment bbox bottom at/after this frame fraction = cut off by the photo edge.
_FRAME_EDGE = 0.97
_MIN_PANEL_WEIGHT = 0.1

# Final-photo lock: person photo vs result must overlay before we trust a diff mask.
_MAX_ASPECT_MISMATCH = 0.06
_MAX_MEDIAN_DIFF = 18
_CHANGED_THRESHOLD = 30
_MIN_CHANGED_FRACTION = 0.01
_MAX_CHANGED_FRACTION = 0.9


def _is_skin_like(r: int, g: int, b: int) -> bool:
    from app.services.fitting_room import _is_skin_like_rgb

    return _is_skin_like_rgb(r, g, b)


def _load_rgb(png: bytes) -> Image.Image | None:
    if not png:
        return None
    try:
        with Image.open(io.BytesIO(png)) as im:
            im.load()
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA")
                bg = Image.new("RGBA", rgba.size, (244, 244, 244, 255))
                return Image.alpha_composite(bg, rgba).convert("RGB")
            return im.convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def _work_size(size: tuple[int, int]) -> tuple[int, int]:
    w, h = size
    wh = min(_WORK_H, max(16, h))
    ww = max(8, int(round(w * wh / float(max(h, 1)))))
    return ww, wh


def _rgb_to_ycc(r: float, g: float, b: float) -> tuple[float, float, float]:
    """JFIF full-range YCbCr — matches Pillow's ``convert("YCbCr")``."""
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128.0 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128.0 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return y, cb, cr


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"


def describe_color(rgb: tuple[int, int, int] | list[int]) -> str:
    """Plain-language color name — image models follow words better than hex codes."""
    r, g, b = (max(0, min(255, int(c))) for c in rgb[:3])
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    deg = h * 360.0
    if s < 0.12:
        if v > 0.85:
            return "white"
        if v < 0.22:
            return "black"
        return "grey"
    if deg < 15 or deg >= 345:
        base = "red"
    elif deg < 40:
        base = "orange" if v > 0.55 else "brown"
    elif deg < 58:
        base = "golden yellow" if v > 0.6 else "mustard"
    elif deg < 100:
        base = "olive moss green" if (v < 0.75 or s < 0.75) else "lime green"
    elif deg < 165:
        base = "forest green" if v < 0.5 else "green"
    elif deg < 195:
        base = "teal"
    elif deg < 255:
        base = "navy blue" if v < 0.45 else "blue"
    elif deg < 290:
        base = "purple"
    else:
        base = "magenta pink" if v > 0.5 else "plum"
    if v < 0.3:
        tone = "very dark "
    elif v < 0.45:
        tone = "deep "
    elif v > 0.8 and s < 0.45:
        tone = "pale "
    elif s < 0.3:
        tone = "muted "
    else:
        tone = ""
    return f"{tone}{base}"


def _keep_major_components(
    cells: list[bytearray], w: int, h: int, *, keep_fraction: float = 0.12
) -> int:
    """Drop small disconnected blobs (lips, hair accents, shoes) in-place. Returns kept count."""
    seen = [bytearray(w) for _ in range(h)]
    components: list[list[tuple[int, int]]] = []
    for y in range(h):
        row = cells[y]
        seen_row = seen[y]
        for x in range(w):
            if not row[x] or seen_row[x]:
                continue
            comp: list[tuple[int, int]] = []
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen_row[x] = 1
            while queue:
                cx, cy = queue.popleft()
                comp.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and cells[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = 1
                        queue.append((nx, ny))
            components.append(comp)
    if not components:
        return 0
    largest = max(len(c) for c in components)
    floor = max(12, int(largest * keep_fraction))
    kept = 0
    for comp in components:
        if len(comp) >= floor:
            kept += len(comp)
            continue
        for cx, cy in comp:
            cells[cy][cx] = 0
    return kept


def _chromatic_cells(
    work: Image.Image,
    *,
    restrict: Image.Image | None = None,
) -> list[bytearray]:
    """Per-pixel garment candidates: saturated, not skin-like, optionally restricted."""
    w, h = work.size
    px = work.load()
    rs = restrict.load() if restrict is not None else None
    cells = [bytearray(w) for _ in range(h)]
    for y in range(h):
        row = cells[y]
        for x in range(w):
            if rs is not None and not rs[x, y]:
                continue
            r, g, b = px[x, y]
            mx = max(r, g, b)
            if mx < _MIN_VALUE:
                continue
            mn = min(r, g, b)
            if (mx - mn) < _MIN_SAT * mx:
                continue
            if _is_skin_like(r, g, b):
                continue
            row[x] = 1
    return cells


def _band_stats(
    work: Image.Image, cells: list[bytearray], *, bands: int = PALETTE_BANDS
) -> dict[str, Any] | None:
    """Vertical band means (top→bottom of the garment bbox) over mask pixels."""
    w, h = work.size
    row_counts = [sum(row) for row in cells]
    total = sum(row_counts)
    if total < _MIN_BAND_PIXELS * 2:
        return None
    # Percentile-trimmed vertical extent so a stray speck cannot stretch the bbox.
    lo_target, hi_target = total * 0.01, total * 0.99
    acc = 0
    y0, y1 = 0, h - 1
    found_lo = False
    for y, n in enumerate(row_counts):
        acc += n
        if not found_lo and acc >= lo_target:
            y0 = y
            found_lo = True
        if acc >= hi_target:
            y1 = y
            break
    if y1 - y0 < bands:
        return None
    xs = [x for row in cells[y0 : y1 + 1] for x, v in enumerate(row) if v]
    x0, x1 = (min(xs), max(xs)) if xs else (0, w - 1)

    px = work.load()
    span = float(y1 - y0 + 1)
    sums = [[0.0, 0.0, 0.0, 0] for _ in range(bands)]
    for y in range(y0, y1 + 1):
        k = min(bands - 1, int((y - y0) * bands / span))
        row = cells[y]
        acc_band = sums[k]
        for x in range(w):
            if row[x]:
                r, g, b = px[x, y]
                acc_band[0] += r
                acc_band[1] += g
                acc_band[2] += b
                acc_band[3] += 1
    out_bands: list[dict[str, Any] | None] = []
    for acc_band in sums:
        n = int(acc_band[3])
        if n < _MIN_BAND_PIXELS:
            out_bands.append(None)
            continue
        rgb = (acc_band[0] / n, acc_band[1] / n, acc_band[2] / n)
        yy, cb, cr = _rgb_to_ycc(*rgb)
        rgb_i = (int(round(rgb[0])), int(round(rgb[1])), int(round(rgb[2])))
        out_bands.append(
            {
                "rgb": list(rgb_i),
                "hex": _hex(rgb_i),
                "ycc": [round(yy, 2), round(cb, 2), round(cr, 2)],
                "n": n,
            }
        )
    valid = sum(1 for b in out_bands if b)
    if valid < _MIN_VALID_BANDS:
        return None
    return {
        "bands": out_bands,
        "bbox": [
            round(x0 / float(w), 4),
            round(y0 / float(h), 4),
            round((x1 + 1) / float(w), 4),
            round((y1 + 1) / float(h), 4),
        ],
        "coverage": round(total / float(w * h), 4),
        "valid_bands": valid,
    }


def _panels_from_bands(bands: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    """Merge adjacent bands with similar chroma into named panels (for prompts)."""
    panels: list[dict[str, Any]] = []
    total = len(bands)
    current: dict[str, Any] | None = None
    for idx, band in enumerate(bands):
        if not band:
            continue
        _, cb, cr = band["ycc"]
        yy = band["ycc"][0]
        if current is not None:
            dist = ((cb - current["cb"]) ** 2 + (cr - current["cr"]) ** 2) ** 0.5
            if dist < 11.0 and abs(yy - current["y"]) < 34.0:
                n = band["n"]
                tot = current["n"] + n
                for key, val in (("r", band["rgb"][0]), ("g", band["rgb"][1]), ("b", band["rgb"][2])):
                    current[key] = (current[key] * current["n"] + val * n) / tot
                current["cb"] = (current["cb"] * current["n"] + cb * n) / tot
                current["cr"] = (current["cr"] * current["n"] + cr * n) / tot
                current["y"] = (current["y"] * current["n"] + yy * n) / tot
                current["n"] = tot
                current["end"] = idx + 1
                continue
            panels.append(current)
        current = {
            "start": idx,
            "end": idx + 1,
            "r": float(band["rgb"][0]),
            "g": float(band["rgb"][1]),
            "b": float(band["rgb"][2]),
            "cb": float(cb),
            "cr": float(cr),
            "y": float(yy),
            "n": int(band["n"]),
        }
    if current is not None:
        panels.append(current)
    out: list[dict[str, Any]] = []
    for panel in panels:
        rgb = (int(round(panel["r"])), int(round(panel["g"])), int(round(panel["b"])))
        out.append(
            {
                "from": round(panel["start"] / float(total), 2),
                "to": round(panel["end"] / float(total), 2),
                "rgb": list(rgb),
                "hex": _hex(rgb),
                "name": describe_color(rgb),
                "weight": int(panel["n"]),
            }
        )
    return out


def measure_garment_bands(
    png: bytes, *, restrict: Image.Image | None = None
) -> dict[str, Any] | None:
    """Band stats for any plate (look illustration or studio product)."""
    rgb = _load_rgb(png)
    if rgb is None:
        return None
    work = rgb.resize(_work_size(rgb.size), Image.Resampling.BILINEAR)
    cells = _chromatic_cells(work, restrict=restrict)
    if not _keep_major_components(cells, *work.size):
        return None
    return _band_stats(work, cells)


def _major_panels(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Panels big enough to name: drops thin transition slivers and sheer hems."""
    total = float(sum(int(p.get("weight") or 0) for p in panels)) or 1.0
    major = [p for p in panels if int(p.get("weight") or 0) / total >= _MIN_PANEL_WEIGHT]
    if not major:
        major = [max(panels, key=lambda p: int(p.get("weight") or 0))]
    merged: list[dict[str, Any]] = []
    for panel in major:
        if merged and merged[-1]["name"] == panel["name"]:
            # Same plain-language name twice reads as one color; keep the heavier swatch.
            if int(panel.get("weight") or 0) > int(merged[-1].get("weight") or 0):
                merged[-1] = {**panel, "from": merged[-1]["from"]}
            else:
                merged[-1] = {**merged[-1], "to": panel["to"]}
            continue
        merged.append(dict(panel))
    return merged


def extract_design_palette(look_png: bytes) -> dict[str, Any] | None:
    """Garment palette of a FashionRise look plate (no paid AI).

    Returns ``None`` for achromatic / skin-toned garments — callers must treat the
    lock as unavailable instead of inventing a palette.
    """
    stats = measure_garment_bands(look_png)
    if not stats or float(stats.get("coverage") or 0.0) < _MIN_COVERAGE:
        return None
    panels = _panels_from_bands(stats["bands"])
    if not panels:
        return None
    major = _major_panels(panels)
    return {
        "version": PALETTE_VERSION,
        "bands": stats["bands"],
        "bbox": stats["bbox"],
        "coverage": stats["coverage"],
        "panels": major,
        "multi_tone": len(major) >= 2,
    }


def palette_summary(palette: dict[str, Any] | None) -> dict[str, Any] | None:
    """Compact, JSON-safe palette description for job results / logs."""
    if not isinstance(palette, dict):
        return None
    return {
        "version": palette.get("version"),
        "multi_tone": bool(palette.get("multi_tone")),
        "coverage": palette.get("coverage"),
        "panels": [
            {"from": p.get("from"), "to": p.get("to"), "hex": p.get("hex"), "name": p.get("name")}
            for p in (palette.get("panels") or [])
        ],
    }


def palette_prompt_clause(palette: dict[str, Any] | None, *, max_panels: int = 3) -> str:
    """Short COLOR LOCK sentence naming each panel top→bottom."""
    if not isinstance(palette, dict):
        return ""
    panels = palette.get("panels")
    if not isinstance(panels, list) or not panels:
        return ""
    major = sorted(panels, key=lambda p: -int(p.get("weight") or 0))[:max_panels]
    major.sort(key=lambda p: float(p.get("from") or 0.0))
    if len(major) == 1:
        only = major[0]
        return f" COLOR LOCK: garment color is {only['name']} ({only['hex']}); keep that exact hue and depth."
    parts: list[str] = []
    for idx, panel in enumerate(major):
        where = "top" if idx == 0 else ("bottom" if idx == len(major) - 1 else "middle")
        parts.append(f"{where} {panel['name']} ({panel['hex']})")
    return (
        " COLOR LOCK top to bottom: "
        + ", ".join(parts)
        + ". Keep every panel its own hue and depth; never blend panels into one color."
    )


def _chroma(band: dict[str, Any]) -> tuple[float, float]:
    return float(band["ycc"][1]) - 128.0, float(band["ycc"][2]) - 128.0


def _interp_band(bands: list[dict[str, Any] | None], pos: float) -> tuple[float, float, float] | None:
    """Linear interpolation of band YCbCr at fractional band index ``pos`` (valid bands only)."""
    n = len(bands)
    if n == 0:
        return None
    pos = max(0.0, min(float(n - 1), pos))
    lo = int(pos)
    hi = min(n - 1, lo + 1)
    frac = pos - lo

    def _nearest(idx: int, step: int) -> dict[str, Any] | None:
        j = idx
        while 0 <= j < n:
            if bands[j]:
                return bands[j]
            j += step
        return None

    a = bands[lo] or _nearest(lo, -1) or _nearest(lo, 1)
    b = bands[hi] or _nearest(hi, 1) or _nearest(hi, -1)
    if not a or not b:
        return None
    return (
        a["ycc"][0] * (1 - frac) + b["ycc"][0] * frac,
        a["ycc"][1] * (1 - frac) + b["ycc"][1] * frac,
        a["ycc"][2] * (1 - frac) + b["ycc"][2] * frac,
    )


def _split_point(bands: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Strongest top/bottom color boundary: weighted two-segment change point in Cb/Cr."""
    total = len(bands)
    valid = [(idx, _chroma(band), float(band["n"])) for idx, band in enumerate(bands) if band]
    if len(valid) < 4:
        return None
    weight_all = sum(w for _, _, w in valid)
    best: dict[str, Any] | None = None
    for cut in range(1, len(valid)):
        upper = valid[:cut]
        lower = valid[cut:]
        wu = sum(w for _, _, w in upper)
        wl = sum(w for _, _, w in lower)
        if min(wu, wl) / weight_all < 0.06:
            continue
        mu = (sum(c[0] * w for _, c, w in upper) / wu, sum(c[1] * w for _, c, w in upper) / wu)
        ml = (sum(c[0] * w for _, c, w in lower) / wl, sum(c[1] * w for _, c, w in lower) / wl)
        sse = sum(w * ((c[0] - mu[0]) ** 2 + (c[1] - mu[1]) ** 2) for _, c, w in upper) + sum(
            w * ((c[0] - ml[0]) ** 2 + (c[1] - ml[1]) ** 2) for _, c, w in lower
        )
        if best is None or sse < best["sse"]:
            best = {
                "sse": sse,
                "position": lower[0][0] / float(total),
                "step": (ml[0] - mu[0], ml[1] - mu[1]),
                "upper": mu,
                "lower": ml,
            }
    if best is None:
        return None
    best["contrast"] = (best["step"][0] ** 2 + best["step"][1] ** 2) ** 0.5
    return best


def _design_positions(
    design: list[dict[str, Any] | None],
    target: list[dict[str, Any] | None],
    *,
    runs_off_frame: bool = False,
) -> tuple[list[float], str]:
    """Design band position (fractional index) for every target band.

    A person is not shaped like a nine-heads croquis and photos are often cropped,
    so matching by plain vertical fraction smears panels. When the design has a
    real top/bottom color boundary we find the same boundary in the target and map
    each side separately. If the target shows no boundary:

    * garment cut off by the bottom of the frame → the photo only shows the upper
      panel, so only that panel's color applies;
    * whole garment in frame → a panel was lost (two-tone collapse) and the design
      layout is restored by position.
    """
    k = len(target)
    kd = len(design)

    def _linear(lo: float, hi: float) -> list[float]:
        return [(lo + (hi - lo) * ((idx + 0.5) / k)) * kd - 0.5 for idx in range(k)]

    split_d = _split_point(design)
    if not split_d or split_d["contrast"] < _MIN_PANEL_CONTRAST:
        return _linear(0.0, 1.0), "linear"
    bd = float(split_d["position"])
    split_t = _split_point(target)
    if split_t:
        agree = split_t["step"][0] * split_d["step"][0] + split_t["step"][1] * split_d["step"][1]
        if agree > 0 and split_t["contrast"] >= _MIN_BOUNDARY_CONTRAST_RATIO * split_d["contrast"]:
            bt = min(0.92, max(0.08, float(split_t["position"])))
            out: list[float] = []
            for idx in range(k):
                t = (idx + 0.5) / k
                u = t * bd / bt if t < bt else bd + (t - bt) * (1.0 - bd) / (1.0 - bt)
                out.append(u * kd - 0.5)
            return out, "boundary"
    if runs_off_frame:
        return _linear(0.0, max(bd - 0.5 / kd, 1.0 / kd)), "upper_panel"
    return _linear(0.0, 1.0), "restore_by_position"


def _band_drift(
    design: list[dict[str, Any] | None],
    target: list[dict[str, Any] | None],
    positions: list[float],
) -> tuple[list[tuple[tuple[float, float, float], tuple[float, float, float]] | None], dict[str, float]]:
    """Pair every target band with its design color and score hue/saturation drift.

    Drift is exposure-invariant: target chroma is rescaled to the design luma first,
    so a correctly colored dress in darker light scores ~0.
    """
    pairs: list[tuple[tuple[float, float, float], tuple[float, float, float]] | None] = []
    weight_sum = 0.0
    chroma_sum = 0.0
    luma_sum = 0.0
    for idx, band in enumerate(target):
        want = _interp_band(design, positions[idx]) if band else None
        if not band or want is None:
            pairs.append(None)
            continue
        ty = max(float(band["ycc"][0]), 1.0)
        cb, cr = _chroma(band)
        pairs.append((want, (ty, cb, cr)))
        scale = want[0] / ty
        weight = float(band["n"])
        weight_sum += weight
        chroma_sum += weight * (
            ((want[1] - 128.0) - cb * scale) ** 2 + ((want[2] - 128.0) - cr * scale) ** 2
        ) ** 0.5
        luma_sum += weight * abs(scale - 1.0)
    if weight_sum <= 0:
        return pairs, {"chroma_drift": 0.0, "luma_drift": 0.0}
    return pairs, {
        "chroma_drift": round(chroma_sum / weight_sum, 2),
        "luma_drift": round(luma_sum / weight_sum, 3),
    }


# (luma gain, chroma a, chroma b, Cb offset, Cr offset): C' = (a + ib)·C + offset.
_Grade = tuple[float, float, float, float, float]
_IDENTITY: _Grade = (1.0, 1.0, 0.0, 0.0, 0.0)


def _band_grade(
    want: tuple[float, float, float],
    have: tuple[float, float, float],
    *,
    chroma_strength: float,
    luma_strength: float,
) -> _Grade:
    """Correction for one band: exposure gain + hue rotation / saturation scale."""
    ty, cb, cr = have
    gain = max(_MIN_LUMA_GAIN, min(_MAX_LUMA_GAIN, want[0] / max(ty, 1.0)))
    gain = 1.0 + (gain - 1.0) * luma_strength
    # Saturation follows the design at whatever exposure the band ends up with.
    exposure = (ty * gain) / max(want[0], 1.0)
    want_cb = (want[1] - 128.0) * exposure
    want_cr = (want[2] - 128.0) * exposure
    have_mag = math.hypot(cb, cr)
    if have_mag < _NEUTRAL_CHROMA:
        d_cb, d_cr = want_cb - cb * gain, want_cr - cr * gain
        mag = math.hypot(d_cb, d_cr)
        if mag > _MAX_CHROMA_SHIFT:
            d_cb, d_cr = d_cb * _MAX_CHROMA_SHIFT / mag, d_cr * _MAX_CHROMA_SHIFT / mag
        return gain, gain, 0.0, d_cb * chroma_strength, d_cr * chroma_strength
    scale = math.hypot(want_cb, want_cr) / have_mag
    scale = max(_MIN_CHROMA_SCALE, min(_MAX_CHROMA_SCALE, scale))
    angle = math.atan2(want_cr, want_cb) - math.atan2(cr, cb)
    angle = (angle + math.pi) % (2.0 * math.pi) - math.pi
    angle = max(-_MAX_HUE_ROTATION, min(_MAX_HUE_ROTATION, angle))
    # Geometric interpolation toward identity (chroma already carries the exposure gain).
    scale = gain * ((scale / gain) ** chroma_strength) if scale > 0 else gain
    angle *= chroma_strength
    return gain, scale * math.cos(angle), scale * math.sin(angle), 0.0, 0.0


def _smooth_grades(grades: list[_Grade | None]) -> list[_Grade]:
    """Fill gaps from neighbours and lightly smooth so bands never show seams."""
    n = len(grades)
    filled: list[_Grade] = []
    for idx in range(n):
        if grades[idx]:
            filled.append(grades[idx])  # type: ignore[arg-type]
            continue
        near = None
        for off in range(1, n):
            for j in (idx - off, idx + off):
                if 0 <= j < n and grades[j]:
                    near = grades[j]
                    break
            if near:
                break
        filled.append(near or _IDENTITY)
    out: list[_Grade] = []
    for idx in range(n):
        prev = filled[max(0, idx - 1)]
        cur = filled[idx]
        nxt = filled[min(n - 1, idx + 1)]
        out.append(tuple(0.2 * prev[c] + 0.6 * cur[c] + 0.2 * nxt[c] for c in range(5)))  # type: ignore[arg-type]
    return out


def _grade_matrix(grade: _Grade) -> tuple[float, ...]:
    """RGB→RGB affine matrix equal to the YCbCr-space grade (for ``Image.convert``)."""
    gain, a, b, off_cb, off_cr = grade
    to_ycc = (
        (0.299, 0.587, 0.114),
        (-0.168736, -0.331264, 0.5),
        (0.5, -0.418688, -0.081312),
    )
    rows = (
        tuple(gain * v for v in to_ycc[0]),
        tuple(a * to_ycc[1][i] - b * to_ycc[2][i] for i in range(3)),
        tuple(b * to_ycc[1][i] + a * to_ycc[2][i] for i in range(3)),
    )
    to_rgb = ((1.0, 0.0, 1.402), (1.0, -0.344136, -0.714136), (1.0, 1.772, 0.0))
    out: list[float] = []
    for row in to_rgb:
        out.extend(sum(row[j] * rows[j][i] for j in range(3)) for i in range(3))
        out.append(row[1] * off_cb + row[2] * off_cr)
    return tuple(out)


def _apply_band_grade(
    rgb: Image.Image,
    soft_mask: Image.Image,
    *,
    bbox_rows: tuple[int, int],
    grades: list[_Grade],
) -> Image.Image:
    """Apply per-band grades as a smooth vertical blend inside ``soft_mask``."""
    w, h = rgb.size
    y0, y1 = bbox_rows
    k = len(grades)
    span = float(max(1, y1 - y0))
    centers = [int(round(y0 + span * (idx + 0.5) / k)) for idx in range(k)]
    graded = rgb.copy()

    def _paste(top: int, bottom: int, upper: _Grade, lower: _Grade | None) -> None:
        top, bottom = max(0, top), min(h, bottom)
        if bottom <= top:
            return
        strip = rgb.crop((0, top, w, bottom))
        out = strip.convert("RGB", _grade_matrix(upper))
        if lower is not None and bottom - top > 1:
            ramp = Image.linear_gradient("L").resize((w, bottom - top), Image.Resampling.BILINEAR)
            out = Image.composite(strip.convert("RGB", _grade_matrix(lower)), out, ramp)
        graded.paste(out, (0, top))

    _paste(0, centers[0], grades[0], None)
    for idx in range(k - 1):
        _paste(centers[idx], centers[idx + 1], grades[idx], grades[idx + 1])
    _paste(centers[-1], h, grades[-1], None)
    return Image.composite(graded, rgb, soft_mask)


def _cells_to_soft_mask(
    cells: list[bytearray], work_size: tuple[int, int], full_size: tuple[int, int]
) -> Image.Image:
    w, h = work_size
    mask = Image.frombytes("L", (w, h), b"".join(bytes(255 if v else 0 for v in row) for row in cells))
    # Close pinholes, then feather so the grade never draws a visible edge.
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    full = mask.resize(full_size, Image.Resampling.BILINEAR)
    return full.filter(ImageFilter.GaussianBlur(max(1.0, full_size[1] / 700.0)))


def _encode_png(rgb: Image.Image) -> bytes:
    out = io.BytesIO()
    rgb.save(out, format="PNG")
    return out.getvalue()


def _grade_toward_design(
    rgb: Image.Image,
    work: Image.Image,
    cells: list[bytearray],
    stats: dict[str, Any],
    palette: dict[str, Any],
    *,
    chroma_strength: float,
    luma_strength: float,
    tolerance: float,
) -> tuple[Image.Image | None, dict[str, Any]]:
    design_bands = palette.get("bands") or []
    positions, alignment = _design_positions(
        design_bands,
        stats["bands"],
        runs_off_frame=float(stats["bbox"][3]) >= _FRAME_EDGE,
    )
    pairs, drift = _band_drift(design_bands, stats["bands"], positions)
    meta: dict[str, Any] = {
        "chroma_drift_before": drift["chroma_drift"],
        "luma_drift_before": drift["luma_drift"],
        "alignment": alignment,
        "coverage": stats["coverage"],
    }
    if drift["chroma_drift"] < tolerance and drift["luma_drift"] * luma_strength < 0.04:
        meta["reason"] = "within_tolerance"
        return None, meta
    grades = _smooth_grades(
        [
            _band_grade(p[0], p[1], chroma_strength=chroma_strength, luma_strength=luma_strength)
            if p
            else None
            for p in pairs
        ]
    )
    h_full = rgb.size[1]
    bbox = stats["bbox"]
    graded = _apply_band_grade(
        rgb,
        _cells_to_soft_mask(cells, work.size, rgb.size),
        bbox_rows=(int(bbox[1] * h_full), int(bbox[3] * h_full)),
        grades=grades,
    )
    after = _band_stats(graded.resize(work.size, Image.Resampling.BILINEAR), cells)
    if after:
        _, drift_after = _band_drift(design_bands, after["bands"], positions)
        meta["chroma_drift_after"] = drift_after["chroma_drift"]
        meta["luma_drift_after"] = drift_after["luma_drift"]
        if drift_after["chroma_drift"] > drift["chroma_drift"]:
            # Never ship a grade that measurably moved away from the design.
            meta["reason"] = "no_improvement"
            return None, meta
    meta["applied"] = True
    return graded, meta


def lock_plate_to_palette(
    plate_png: bytes,
    palette: dict[str, Any] | None,
    *,
    chroma_strength: float = 0.92,
    luma_strength: float = 0.7,
) -> tuple[bytes, dict[str, Any]]:
    """Re-impose the design palette on a studio product plate (plain backdrop)."""
    meta: dict[str, Any] = {"stage": "product", "applied": False}
    if not isinstance(palette, dict) or not palette.get("bands"):
        meta["reason"] = "no_palette"
        return plate_png, meta
    rgb = _load_rgb(plate_png)
    if rgb is None:
        meta["reason"] = "undecodable"
        return plate_png, meta
    work = rgb.resize(_work_size(rgb.size), Image.Resampling.BILINEAR)
    cells = _chromatic_cells(work)
    if not _keep_major_components(cells, *work.size):
        meta["reason"] = "no_garment_pixels"
        return plate_png, meta
    stats = _band_stats(work, cells)
    if not stats or float(stats["coverage"]) < _MIN_COVERAGE:
        meta["reason"] = "no_garment_bands"
        return plate_png, meta
    graded, grade_meta = _grade_toward_design(
        rgb,
        work,
        cells,
        stats,
        palette,
        chroma_strength=chroma_strength,
        luma_strength=luma_strength,
        tolerance=2.0,
    )
    meta.update(grade_meta)
    if graded is None:
        return plate_png, meta
    return _encode_png(graded), meta


def _changed_region(
    result_rgb: Image.Image, person_rgb: Image.Image, work_size: tuple[int, int]
) -> tuple[Image.Image | None, dict[str, Any]]:
    """Where the try-on changed the person photo (≈ the new garment)."""
    meta: dict[str, Any] = {}
    rw, rh = result_rgb.size
    pw, ph = person_rgb.size
    aspect_gap = abs((rw / float(rh)) - (pw / float(ph))) / (pw / float(ph))
    meta["aspect_gap"] = round(aspect_gap, 4)
    if aspect_gap > _MAX_ASPECT_MISMATCH:
        meta["reason"] = "aspect_mismatch"
        return None, meta
    a = result_rgb.resize(work_size, Image.Resampling.BILINEAR)
    b = person_rgb.resize(work_size, Image.Resampling.BILINEAR)
    r, g, bl = ImageChops.difference(a, b).split()
    diff = ImageChops.lighter(ImageChops.lighter(r, g), bl).filter(ImageFilter.GaussianBlur(1.5))
    hist = diff.histogram()
    total = sum(hist)
    acc = 0
    median = 0
    for value, count in enumerate(hist):
        acc += count
        if acc >= total / 2:
            median = value
            break
    meta["median_diff"] = median
    changed_px = sum(hist[_CHANGED_THRESHOLD:])
    fraction = changed_px / float(max(total, 1))
    meta["changed_fraction"] = round(fraction, 4)
    if median > _MAX_MEDIAN_DIFF:
        # Result does not overlay the person photo (crop / reframing) — cannot localize.
        meta["reason"] = "misaligned"
        return None, meta
    if fraction < _MIN_CHANGED_FRACTION or fraction > _MAX_CHANGED_FRACTION:
        meta["reason"] = "changed_region_out_of_range"
        return None, meta
    # One-pixel dilation only: a wider ring would pull the unchanged background next
    # to the garment into the measurement.
    changed = diff.point(lambda v: 255 if v >= _CHANGED_THRESHOLD else 0).filter(
        ImageFilter.MaxFilter(3)
    )
    return changed, meta


def _reject_chroma_outliers(
    work: Image.Image, cells: list[bytearray], *, max_distance: float = 52.0
) -> None:
    """Drop candidates far from their band's median chroma (revealed sky / grass)."""
    w, h = work.size
    rows = [y for y in range(h) if any(cells[y])]
    if not rows:
        return
    y0, y1 = rows[0], rows[-1]
    span = float(y1 - y0 + 1)
    bands = PALETTE_BANDS
    px = work.load()
    samples: list[list[tuple[float, float]]] = [[] for _ in range(bands)]
    for y in range(y0, y1 + 1):
        k = min(bands - 1, int((y - y0) * bands / span))
        row = cells[y]
        for x in range(0, w, 2):
            if row[x]:
                _, cb, cr = _rgb_to_ycc(*px[x, y])
                samples[k].append((cb, cr))
    centers: list[tuple[float, float] | None] = []
    for band in samples:
        if len(band) < 8:
            centers.append(None)
            continue
        cbs = sorted(p[0] for p in band)
        crs = sorted(p[1] for p in band)
        centers.append((cbs[len(cbs) // 2], crs[len(crs) // 2]))
    limit = max_distance * max_distance
    for y in range(y0, y1 + 1):
        k = min(bands - 1, int((y - y0) * bands / span))
        center = centers[k]
        if center is None:
            continue
        row = cells[y]
        for x in range(w):
            if row[x]:
                _, cb, cr = _rgb_to_ycc(*px[x, y])
                if (cb - center[0]) ** 2 + (cr - center[1]) ** 2 > limit:
                    row[x] = 0


def lock_result_to_palette(
    result_png: bytes,
    person_png: bytes,
    palette: dict[str, Any] | None,
    *,
    chroma_strength: float = 0.85,
    luma_strength: float = 0.3,
) -> tuple[bytes, dict[str, Any]]:
    """Re-impose the design palette on the final try-on photo.

    The garment is localized as *pixels the try-on changed* ∩ chromatic non-skin,
    so background, skin, hair and accessories are never recolored. Luma is only
    nudged: the scene's own light is real and must survive. Fail-safe: any doubt
    (misaligned frames, tiny region, no palette) returns the input untouched.
    """
    meta: dict[str, Any] = {"stage": "result", "applied": False}
    if not isinstance(palette, dict) or not palette.get("bands"):
        meta["reason"] = "no_palette"
        return result_png, meta
    result_rgb = _load_rgb(result_png)
    person_rgb = _load_rgb(person_png)
    if result_rgb is None or person_rgb is None:
        meta["reason"] = "undecodable"
        return result_png, meta
    work_size = _work_size(result_rgb.size)
    changed, region_meta = _changed_region(result_rgb, person_rgb, work_size)
    meta.update(region_meta)
    if changed is None:
        return result_png, meta
    work = result_rgb.resize(work_size, Image.Resampling.BILINEAR)
    cells = _chromatic_cells(work, restrict=changed)
    _reject_chroma_outliers(work, cells)
    if not _keep_major_components(cells, *work_size):
        meta["reason"] = "no_garment_pixels"
        return result_png, meta
    stats = _band_stats(work, cells)
    if not stats or float(stats["coverage"]) < _MIN_COVERAGE:
        meta["reason"] = "no_garment_bands"
        return result_png, meta
    graded, grade_meta = _grade_toward_design(
        result_rgb,
        work,
        cells,
        stats,
        palette,
        chroma_strength=chroma_strength,
        luma_strength=luma_strength,
        tolerance=3.0,
    )
    meta.update(grade_meta)
    if graded is None:
        return result_png, meta
    return _encode_png(graded), meta
