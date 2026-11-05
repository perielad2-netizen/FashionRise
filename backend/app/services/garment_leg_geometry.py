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
    looks_like_high_slit_dress: bool

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
            "looks_like_high_slit_dress": self.looks_like_high_slit_dress,
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
        looks_like_high_slit_dress=False,
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

    # High-slit / open-leg dress: connected hip/waist panel that opens lower into a gap.
    # True trousers already show two legs at the hip (high hip_dual_ratio).
    # Important (#180 owner open-leg): do NOT require trousers=True first — many open-leg
    # dresses never meet the trousers bar (low two_lobe ratio) but still need dress hints
    # so Max/realism do not invent pant legs.
    high_slit_dress = False
    hip_dual_ratio = 1.0
    asymmetric = False
    if mid_connected and (trousers or ratio >= 0.15):
        hip_dual = 0
        hip_n = 0
        for t in (0.32, 0.38, 0.44, 0.50):
            hip_y = y0 + int(t * bh)
            if hip_y > y1:
                continue
            runs = _runs(mask[hip_y][x0 : x1 + 1])
            min_run = max(2, int(0.03 * bw))
            runs = [(a, b) for a, b in runs if (b - a) >= min_run]
            hip_n += 1
            if len(runs) == 2 and (runs[1][0] - runs[0][1]) >= max(2, int(0.04 * bw)):
                hip_dual += 1
        hip_dual_ratio = hip_dual / max(hip_n, 1)
        if width_fracs:
            left_ws: list[float] = []
            right_ws: list[float] = []
            for y in range(sample_y0, sample_y1 + 1, max(1, bh // 40)):
                runs = _runs(mask[y][x0 : x1 + 1])
                min_run = max(2, int(0.03 * bw))
                runs = [(a, b) for a, b in runs if (b - a) >= min_run]
                if len(runs) == 2 and (runs[1][0] - runs[0][1]) >= max(2, int(0.04 * bw)):
                    left_ws.append((runs[0][1] - runs[0][0]) / bw)
                    right_ws.append((runs[1][1] - runs[1][0]) / bw)
            if left_ws and right_ws:
                lw = sum(left_ws) / len(left_ws)
                rw = sum(right_ws) / len(right_ws)
                lo, hi = (lw, rw) if lw <= rw else (rw, lw)
                asymmetric = lo > 0 and (hi / lo) >= 1.55
        if trousers and coverage >= 0.45:
            # Connected hip + later dual lobes ⇒ fashion slit, not pant crotch.
            if hip_dual_ratio < 0.40:
                high_slit_dress = True
                trousers = False
            elif asymmetric and hip_dual_ratio < 0.75:
                high_slit_dress = True
                trousers = False
        elif (
            not trousers
            and ratio >= 0.18
            and avg_gap >= 0.035
            and len(width_fracs) >= 2
            and (
                hip_dual_ratio < 0.45
                or (asymmetric and hip_dual_ratio < 0.75)
            )
        ):
            # Open-leg dress that never tripped the trousers classifier
            # (connected/asymmetric opening near the hem — not two pant columns).
            high_slit_dress = True

        # #180 — photoreal jumpsuits: connected crotch (hip_dual low) but nearly
        # continuous dual columns (ratio≈1) with a tight symmetric gap. Do not leave
        # these labeled as high_slit_dress or dress→pants contradictions never fire.
        if (
            high_slit_dress
            and ratio >= 0.95
            and avg_gap < 0.12
            and not asymmetric
        ):
            high_slit_dress = False
            trousers = True

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
        looks_like_high_slit_dress=bool(high_slit_dress),
    )


def looks_like_one_piece_full_coverage(geometry: LowerGarmentGeometry) -> bool:
    """Continuous torso→hip opaque garment (one-piece / dress / bodysuit) — not trousers or a crop top.

    Used so OpenAI Try On replaces photo jeans under the design instead of treating the
    artwork as a shirt layered over street bottoms.
    """
    if geometry.looks_like_trousers:
        return False
    if not geometry.mid_body_connected:
        return False
    if geometry.opaque_pixels < 400:
        return False
    if geometry.coverage_y_span_frac < 0.28:
        return False
    # Must cover through the seat/hips (waist-length tops stay false).
    if geometry.hem_y_frac < 0.50:
        return False
    # Top of bbox should sit in upper/mid torso, not a skirt-only panel.
    top_frac = geometry.hem_y_frac - geometry.coverage_y_span_frac
    if top_frac > 0.48:
        return False
    return True


def looks_like_high_cut_one_piece(geometry: LowerGarmentGeometry) -> bool:
    """One-piece whose hem ends above mid-thigh (bodysuit / high-cut), not a midi/floor dress.

    Owner back try-on (job abc05c51): OpenAI lengthened a hem_y≈0.53 one-piece into a
    knee dress. High-cut hems need an explicit "do not lengthen" contract.
    """
    if not looks_like_one_piece_full_coverage(geometry):
        return False
    return geometry.hem_y_frac < 0.72


def openai_one_piece_coverage_hints(geometry: LowerGarmentGeometry) -> list[str]:
    """Additive hints so continuous one-piece coverage replaces photo jeans/trousers."""
    if not looks_like_one_piece_full_coverage(geometry):
        return []
    hints = [
        "garment type: continuous one-piece covering torso through hips — not a separate top over trousers",
        "replace photo clothing wherever image 2's opaque garment covers; do not leave jeans, trousers, or shorts under this one-piece",
        "match the designed hem and leg openings from image 2 — photo lower garments must not remain below that hem",
    ]
    if looks_like_high_cut_one_piece(geometry):
        hints.append(
            "hem: high-cut one-piece as drawn — end at the designed leg openings; "
            "do not lengthen into a dress, skirt, or midi gown"
        )
    # Mid-thigh / high-cut one-piece (not floor gown): do not keep photo boots.
    if geometry.hem_y_frac < 0.88:
        hints.append(
            "footwear: image 2 has no shoes drawn — remove photo boots/shoes completely; "
            "show bare feet matching image 1 — never keep tall boots from image 1"
        )
    return hints


def openai_trouser_design_hints(geometry: LowerGarmentGeometry) -> list[str]:
    """Additive V2 hints for clear trouser OR high-slit dress geometry. Empty when ambiguous."""
    if geometry.looks_like_high_slit_dress and not geometry.looks_like_trousers:
        # Still remind the model to replace street bottoms under the dress panel.
        return [
            "garment type: dress or gown with a high fashion slit — not trousers or a jumpsuit",
            "Preserve this as a dress with an intentional leg opening/slit. Maintain the "
            "original skirt panels, silhouette, hemline, opening and fabric coverage. "
            "Do not reinterpret the garment as separate trousers or a jumpsuit.",
            "preserve the designed leg opening/slit from the Studio/plate geometry; "
            "do not close it into pant legs",
            "keep one continuous skirt/dress panel beside the slit; do not invent a second pant leg",
            "match the slit height and which side opens from the source design",
            "a white gap in an isolated plate is negative space / slit — not two trouser legs",
            *openai_one_piece_coverage_hints(geometry)[:1],
        ]
    if not geometry.looks_like_trousers:
        # One-piece swimsuit / bodysuit / closed dress — coverage replacement only.
        return openai_one_piece_coverage_hints(geometry)
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


def garment_structure_contradiction(
    *,
    source_png: bytes,
    product_png: bytes,
) -> dict[str, Any] | None:
    """Detect dress↔trousers category flips between Studio/source and realistic product (#179).

    Returns a contradiction dict when geometry is confident on both sides and they disagree.
    Ambiguous geometry returns None (do not silently certify fidelity).
    """
    if not source_png or not product_png:
        return None
    try:
        src = analyze_lower_garment_geometry(source_png)
        prod = analyze_lower_garment_geometry(product_png)
    except Exception:
        return None

    # Source: confident open-leg dress → product must not become trousers/jumpsuit.
    if src.looks_like_high_slit_dress and not src.looks_like_trousers:
        if prod.looks_like_trousers or prod.looks_like_jumpsuit:
            return {
                "code": "STRUCTURE_CATEGORY_CONTRADICTION",
                "reason": "source_high_slit_dress_product_trousers",
                "message": (
                    "Realistic product reinterpreted an open-leg dress as trousers/jumpsuit. "
                    "FASHN Try-On was not started."
                ),
                "source": src.public_dict(),
                "product": prod.public_dict(),
            }
        return None

    # Source: confident separate trouser legs → product must not become a slit dress.
    if src.looks_like_trousers and not src.looks_like_high_slit_dress:
        if prod.looks_like_high_slit_dress and not prod.looks_like_trousers:
            return {
                "code": "STRUCTURE_CATEGORY_CONTRADICTION",
                "reason": "source_trousers_product_slit_dress",
                "message": (
                    "Realistic product reinterpreted trousers as a dress/slit. "
                    "FASHN Try-On was not started."
                ),
                "source": src.public_dict(),
                "product": prod.public_dict(),
            }
    return None


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


# Trusted server-side provenance for structure review (#172).
# Pixel heuristics must never authorize plate comparison for photoreal try-on photos.
RESULT_KIND_OPENAI_TRY_ON_PHOTO = "openai_try_on_photo"
RESULT_KIND_ISOLATED_GARMENT_PLATE = "isolated_garment_plate"
SOURCE_KIND_ISOLATED_GARMENT_PLATE = "isolated_garment_plate"


def soft_try_on_structure_review(
    *,
    source_png: bytes,
    result_png: bytes,
    result_kind: str | None = None,
    source_kind: str | None = None,
) -> dict[str, Any]:
    """Soft post-generation check for major lower-garment type mismatch (#170/#171/#172).

    OpenAI Try On completion must pass ``result_kind=openai_try_on_photo``. That
    provenance alone establishes the output is a photoreal try-on photograph —
    never authorize garment-mask comparison from white background / skin / opacity
    heuristics on those outputs.

    Plate↔plate comparison runs only when both sides are explicitly trusted as
    isolated garment plates (``result_kind`` / ``source_kind`` =
    ``isolated_garment_plate``), or when callers omit provenance and both images
    classify as isolated plates (offline plate-fixture tests only).

    States:
    - ``not_applicable`` — trousers check does not apply (ordinary outfits).
    - ``inconclusive`` — cannot compare (e.g. person photo; no garment isolation).
    - ``failed`` — confirmed mismatch between two trusted isolated garment images.
    - ``passed_soft`` — soft consistency only (not a fidelity certificate).
    """
    src = analyze_lower_garment_geometry(source_png)
    kind = (result_kind or "").strip().lower() or None
    src_kind = (source_kind or "").strip().lower() or None

    # Diagnostic roles only — never the sole gate for OpenAI photo outputs (#172).
    src_role = classify_structure_image_role(source_png)
    out_role = (
        "full_scene"
        if kind == RESULT_KIND_OPENAI_TRY_ON_PHOTO
        else classify_structure_image_role(result_png)
    )
    base: dict[str, Any] = {
        "version": "try-on-structure-review-v3",
        "source": src.public_dict(),
        "source_role": src_role,
        "result_role": out_role,
        "result_kind": kind,
        "source_kind": src_kind,
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

    # Trusted OpenAI full-photo provenance: never plate-compare result pixels.
    if kind == RESULT_KIND_OPENAI_TRY_ON_PHOTO:
        return {
            **base,
            "state": "inconclusive",
            "code": "STRUCTURE_INCOMPARABLE_RESULT",
            "message": (
                "Automated garment-mask comparison cannot be applied to an OpenAI try-on "
                "photograph until garment-region isolation exists. "
                "No automated pass/fail is claimed."
            ),
            "faithful": None,
        }

    # Explicit trusted isolated plates — or legacy plate fixtures without provenance.
    result_trusted_plate = kind == RESULT_KIND_ISOLATED_GARMENT_PLATE or (
        kind is None and out_role == "isolated_garment"
    )
    source_trusted_plate = src_kind == SOURCE_KIND_ISOLATED_GARMENT_PLATE or (
        src_kind is None and src_role == "isolated_garment"
    )
    if not result_trusted_plate:
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
    if not source_trusted_plate:
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


def merge_openai_design_hints(
    studio_hints: list[str],
    geometry_hints: list[str],
    *,
    max_hints: int = 8,
) -> list[str]:
    """Merge Studio + trouser geometry hints with geometry priority (#172).

    Trouser/jumpsuit geometry hints must not silently disappear when the
    eight-hint budget is already filled by lower-priority color/print hints.
    """
    geo: list[str] = []
    for item in geometry_hints:
        text = " ".join(str(item).split())[:120]
        if text and text not in geo:
            geo.append(text)
    studio: list[str] = []
    for item in studio_hints:
        text = " ".join(str(item).split())[:120]
        if not text or text in geo or text in studio:
            continue
        studio.append(text)
    # Geometry first, then fill remaining slots with Studio evidence.
    merged = list(geo)
    for text in studio:
        if len(merged) >= max_hints:
            break
        merged.append(text)
    return merged[:max_hints]
