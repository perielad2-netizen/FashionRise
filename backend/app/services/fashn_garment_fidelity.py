"""Structural silhouette fidelity for FASHN garment pipeline (#161 follow-up).

Owner paid test (job 0df11dea / realism fb55f220): sketch + prep + OpenAI realism
kept a high-cut asymmetric one-piece swimsuit, but FASHN ``category=auto`` produced
an asymmetric mini-dress with a skirt-like hem. This module:

1. Classifies swimsuit-like vs dress-like silhouettes from pixel masks.
2. Maps one-piece swimwear to FASHN category ``one-pieces`` (never rely on ``auto``).
3. Compares source plate vs realism product before any FASHN credit is spent.

A technically valid PNG is not sufficient — the silhouette must remain faithful.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image

FashnCategory = Literal["tops", "bottoms", "one-pieces", "auto"]

FIDELITY_PROMPT_HINT_VERSION = "fashn-silhouette-fidelity-v1"

# Lower-band crotch notch: swimsuit/leotard bottoms taper; skirts stay wide.
_SWIM_NOTCH_MAX = 0.38
_SWIM_FLARE_MAX = 0.72
_DRESS_NOTCH_MIN = 0.22
_DRESS_FLARE_MIN = 0.85


@dataclass(frozen=True)
class SilhouetteFeatures:
    width_profile: tuple[int, ...]  # relative widths at sample heights
    notch_ratio: float  # min/max width in lower 30%
    bottom_flare: float  # width@95% / width@65%
    aspect_h_w: float
    opaque_pixels: int
    swimsuit_like: bool
    dress_like: bool

    def public_dict(self) -> dict[str, Any]:
        return {
            "notch_ratio": round(self.notch_ratio, 4),
            "bottom_flare": round(self.bottom_flare, 4),
            "aspect_h_w": round(self.aspect_h_w, 4),
            "opaque_pixels": self.opaque_pixels,
            "swimsuit_like": self.swimsuit_like,
            "dress_like": self.dress_like,
            "width_profile": list(self.width_profile),
        }


@dataclass(frozen=True)
class FidelityVerdict:
    ok: bool
    code: str
    message: str
    source: SilhouetteFeatures | None
    product: SilhouetteFeatures | None
    recommended_category: FashnCategory

    def public_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "recommended_category": self.recommended_category,
            "source": self.source.public_dict() if self.source else None,
            "product": self.product.public_dict() if self.product else None,
            "version": FIDELITY_PROMPT_HINT_VERSION,
        }


def _load_rgba(png: bytes) -> Image.Image:
    with Image.open(io.BytesIO(png)) as im:
        im.load()
        return im.convert("RGBA")


def _garment_mask(rgba: Image.Image) -> list[list[bool]]:
    """Opaque alpha OR non-near-white RGB (product plates are opaque on light bg)."""
    w, h = rgba.size
    pix = rgba.load()
    assert pix is not None
    mask: list[list[bool]] = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if a > 24:
                mask[y][x] = True
                continue
            # Near-white / light gray background on opaque product photos.
            if r >= 228 and g >= 228 and b >= 228:
                continue
            if r >= 200 and g >= 200 and b >= 200 and abs(r - g) < 14 and abs(g - b) < 14:
                continue
            # Treat saturated / dark pixels as garment even if alpha is 255 already handled.
            if a == 0:
                continue
            mask[y][x] = True
    # For fully opaque RGB product images alpha is 255 everywhere — rebuild from color.
    opaque_alpha = sum(1 for y in range(h) for x in range(w) if pix[x, y][3] > 24)
    if opaque_alpha > 0.92 * w * h:
        for y in range(h):
            for x in range(w):
                r, g, b, _a = pix[x, y]
                if r >= 228 and g >= 228 and b >= 228:
                    mask[y][x] = False
                elif r >= 200 and g >= 200 and b >= 200 and abs(r - g) < 14 and abs(g - b) < 14:
                    mask[y][x] = False
                else:
                    mask[y][x] = True
    return mask


def compute_silhouette_features(png: bytes) -> SilhouetteFeatures:
    rgba = _load_rgba(png)
    mask = _garment_mask(rgba)
    h = len(mask)
    w = len(mask[0]) if h else 0
    xs: list[int] = []
    ys: list[int] = []
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if row[x]:
                xs.append(x)
                ys.append(y)
    if not xs:
        empty = SilhouetteFeatures(
            width_profile=(0, 0, 0, 0, 0, 0, 0),
            notch_ratio=1.0,
            bottom_flare=1.0,
            aspect_h_w=1.0,
            opaque_pixels=0,
            swimsuit_like=False,
            dress_like=False,
        )
        return empty

    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    bh = max(1, y1 - y0 + 1)
    bw = max(1, x1 - x0 + 1)
    samples = (0.15, 0.35, 0.5, 0.65, 0.8, 0.9, 0.95)
    widths: list[int] = []
    for t in samples:
        y = y0 + int(t * (bh - 1))
        widths.append(sum(1 for x in range(x0, x1 + 1) if mask[y][x]))

    band_y0 = y0 + int(0.70 * bh)
    row_widths: list[int] = []
    for y in range(band_y0, y1 + 1):
        row_widths.append(sum(1 for x in range(x0, x1 + 1) if mask[y][x]))
    min_w = min(row_widths) if row_widths else 0
    max_w = max(row_widths) if row_widths else 1
    notch = min_w / max(max_w, 1)
    w95 = widths[-1]
    w65 = max(widths[3], 1)
    flare = w95 / w65
    swim = notch <= _SWIM_NOTCH_MAX and flare <= _SWIM_FLARE_MAX and min_w < max(12, int(0.25 * max_w))
    dress = flare >= _DRESS_FLARE_MIN and notch >= _DRESS_NOTCH_MIN
    return SilhouetteFeatures(
        width_profile=tuple(widths),
        notch_ratio=float(notch),
        bottom_flare=float(flare),
        aspect_h_w=bh / bw,
        opaque_pixels=len(xs),
        swimsuit_like=bool(swim),
        dress_like=bool(dress and not swim),
    )


def recommend_fashn_category(
    *,
    layout: str,
    piece_category: str | None = None,
    features: SilhouetteFeatures | None = None,
) -> FashnCategory:
    """Map FashionRise layout/silhouette → FASHN v1.6 category.

    Never leave one-piece swimwear as ``auto`` — that path rewrote a swimsuit into a dress.
    """
    cat = (piece_category or "").strip().lower()
    if cat in ("tops", "bottoms", "one-pieces"):
        return cat  # type: ignore[return-value]
    if (layout or "").strip().lower() == "two_piece":
        return "auto"  # caller should pass tops/bottoms per piece
    if features and features.swimsuit_like:
        return "one-pieces"
    if (layout or "").strip().lower() == "one_piece":
        return "one-pieces"
    return "one-pieces" if features and not features.dress_like else "auto"


def assert_structural_fidelity(
    *,
    source_png: bytes,
    product_png: bytes,
    layout: str = "one_piece",
    category: str | None = None,
) -> FidelityVerdict:
    """Fail closed when realism product abandons source silhouette class.

    ``category`` (tops/bottoms/one-pieces) scopes gates that only apply to one
    piece class — e.g. neckline must not run on bikini bottoms (waist tip looks
    like an open neckline and false-blocked Max for owner swimwear #181).
    """
    source = compute_silhouette_features(source_png)
    product = compute_silhouette_features(product_png)
    recommended = recommend_fashn_category(
        layout=layout, piece_category=category, features=source
    )
    piece_cat = (category or "").strip().lower()

    if source.opaque_pixels < 64:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_SOURCE_EMPTY",
            message="Source garment plate has no measurable silhouette.",
            source=source,
            product=product,
            recommended_category=recommended,
        )
    if product.opaque_pixels < 64:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_PRODUCT_EMPTY",
            message="Realistic garment image has no measurable silhouette.",
            source=source,
            product=product,
            recommended_category=recommended,
        )

    if source.swimsuit_like and product.dress_like:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_SWIMSUIT_BECAME_DRESS",
            message=(
                "Fidelity check failed: your sketch is a high-cut one-piece / swimsuit "
                "silhouette, but the generated product looks like a dress or skirt. "
                "FASHN was not started. Adjust the sketch or try again — no FASHN credit used."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    if source.swimsuit_like and not product.swimsuit_like and product.bottom_flare > 0.9:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_LEG_OPENINGS_LOST",
            message=(
                "Fidelity check failed: high-cut leg openings from your sketch were not "
                "preserved in the realistic garment. FASHN was not started."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    # Extreme aspect / mass change (product ballooned into a long dress).
    if source.aspect_h_w > 0 and product.aspect_h_w / source.aspect_h_w > 1.55 and product.dress_like:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_SILHOUETTE_STRETCH",
            message=(
                "Fidelity check failed: the realistic garment proportions diverged too far "
                "from your sketch (dress-length stretch). FASHN was not started."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    # #164 — reject OpenAI restyles that invent asymmetry / twist on a symmetric top.
    src_sym = _symmetry_score(source_png)
    prod_sym = _symmetry_score(product_png)
    if src_sym >= 0.82 and prod_sym <= 0.62:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_ASYMMETRY_INVENTED",
            message=(
                "Fidelity check failed: the sketch top/bottom is roughly symmetric, but the "
                "generated product introduced a twisted or asymmetric redesign. FASHN was not started."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    # #164/#167 — deep-V / open neckline filled in (wrapped/twisted tops inflate the top band).
    # width_profile samples at 15%, 35%, 50%, ... of garment height.
    # Separated-cup deep-V plates often have tip widths of only ~7–10px, so soft photoreal
    # fabric edges grow tip ratio 2–4× without filling the V. Owner #164 wrap redesign
    # reached tip_ratio ≈0.25 with growth ≥5. Job 5842e98b (growth ≈3.3, tip ≈0.19) was a
    # borderline relative-only reject with no stored product — require wrap-class evidence.
    # Never apply to bottoms — a narrow waist tip vs hips is normal bikini geometry (#181).
    src_w15, src_w35, src_w50 = source.width_profile[0], source.width_profile[1], source.width_profile[2]
    prod_w15, prod_w35, prod_w50 = (
        product.width_profile[0],
        product.width_profile[1],
        product.width_profile[2],
    )
    src_top_ratio = src_w15 / max(src_w50, 1)
    prod_top_ratio = prod_w15 / max(prod_w50, 1)
    top_growth = prod_top_ratio / max(src_top_ratio, 0.01)
    # Absolute V fill-in, OR wrap-class tip thickening (known #164 restyle band).
    neckline_changed = (
        piece_cat != "bottoms"
        and src_top_ratio <= 0.55
        and (
            prod_top_ratio >= 0.70
            or (prod_top_ratio >= 0.22 and top_growth >= 4.5)
        )
    )
    if neckline_changed:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_NECKLINE_CHANGED",
            message=(
                "Fidelity check failed: the sketch has an open / deep neckline, but the "
                "generated product filled it in (wrap/twist redesign). FASHN was not started."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    # #169 — skimpy triangle bottoms thickened into substantial coverage (owner brown/yellow-dot).
    # width_profile indices: 15%, 35%, 50%, 65%, 75%, 85%, 95%.
    # Catch both relative lower/mid fill-in AND absolute fabric growth (OpenAI often scales
    # the whole piece while adding coverage — ratio-only gates miss that).
    if layout == "two_piece" and len(source.width_profile) >= 7 and len(product.width_profile) >= 7:
        src_lower = (source.width_profile[4] + source.width_profile[5] + source.width_profile[6]) / 3.0
        prod_lower = (
            product.width_profile[4] + product.width_profile[5] + product.width_profile[6]
        ) / 3.0
        src_mid = float(max(src_w50, 1))
        prod_mid = float(max(prod_w50, 1))
        src_lower_ratio = src_lower / src_mid
        prod_lower_ratio = prod_lower / prod_mid
        abs_lower_growth = prod_lower / max(src_lower, 1.0)
        opaque_growth = product.opaque_pixels / max(source.opaque_pixels, 1)
        skimpy_source = src_lower_ratio <= 0.45
        ratio_expanded = prod_lower_ratio >= max(0.55, src_lower_ratio * 1.7)
        absolute_expanded = abs_lower_growth >= 2.8 and opaque_growth >= 2.5
        if skimpy_source and (ratio_expanded or absolute_expanded):
            return FidelityVerdict(
                ok=False,
                code="FIDELITY_COVERAGE_EXPANDED",
                message=(
                    "Fidelity check failed: the sketch bottom has skimpy / high-cut coverage, "
                    "but the generated product added substantial fabric. FASHN was not started."
                ),
                source=source,
                product=product,
                recommended_category=recommended,
            )

    color_corr = _color_correlation(source_png, product_png)
    if color_corr is not None and color_corr < 0.35:
        return FidelityVerdict(
            ok=False,
            code="FIDELITY_COLOR_DRIFT",
            message=(
                "Fidelity check failed: garment colors / gradient placement drifted too far "
                "from your sketch. FASHN was not started."
            ),
            source=source,
            product=product,
            recommended_category=recommended,
        )

    return FidelityVerdict(
        ok=True,
        code="FIDELITY_OK",
        message="Structural silhouette is consistent enough to send to FASHN.",
        source=source,
        product=product,
        recommended_category=recommended,
    )


def _garment_rgb_pixels(png: bytes) -> list[tuple[int, int, int]]:
    rgba = _load_rgba(png)
    mask = _garment_mask(rgba)
    pix = rgba.load()
    assert pix is not None
    out: list[tuple[int, int, int]] = []
    h = len(mask)
    w = len(mask[0]) if h else 0
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            r, g, b, _a = pix[x, y]
            if r < 40 and g < 40 and b < 40:
                continue
            out.append((r, g, b))
    return out


def _symmetry_score(png: bytes) -> float:
    """1.0 = left/right mirror match of garment mask; low = invented asymmetry."""
    rgba = _load_rgba(png)
    mask = _garment_mask(rgba)
    h = len(mask)
    w = len(mask[0]) if h else 0
    if w < 8 or h < 8:
        return 1.0
    # Crop to bbox
    xs = [x for y in range(h) for x in range(w) if mask[y][x]]
    ys = [y for y in range(h) for x in range(w) if mask[y][x]]
    if not xs:
        return 1.0
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    bw = x1 - x0 + 1
    mid = bw // 2
    agree = 0
    total = 0
    for y in range(y0, y1 + 1):
        for dx in range(mid):
            lx = x0 + dx
            rx = x1 - dx
            if lx >= w or rx < 0:
                continue
            total += 1
            if mask[y][lx] == mask[y][rx]:
                agree += 1
    return agree / max(total, 1)


def _color_correlation(source_png: bytes, product_png: bytes) -> float | None:
    """Rough RGB mean proximity in [0,1]; None if insufficient samples."""
    a = _garment_rgb_pixels(source_png)
    b = _garment_rgb_pixels(product_png)
    if len(a) < 32 or len(b) < 32:
        return None

    def mean(px: list[tuple[int, int, int]]) -> tuple[float, float, float]:
        n = len(px)
        return (
            sum(p[0] for p in px) / n,
            sum(p[1] for p in px) / n,
            sum(p[2] for p in px) / n,
        )

    ma, mb = mean(a), mean(b)
    # Distance in RGB cube normalized
    dist = (
        (ma[0] - mb[0]) ** 2 + (ma[1] - mb[1]) ** 2 + (ma[2] - mb[2]) ** 2
    ) ** 0.5
    return max(0.0, 1.0 - dist / (255.0 * (3**0.5)))
