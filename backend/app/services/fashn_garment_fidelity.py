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
) -> FidelityVerdict:
    """Fail closed when realism product abandons source silhouette class."""
    source = compute_silhouette_features(source_png)
    product = compute_silhouette_features(product_png)
    recommended = recommend_fashn_category(layout=layout, features=source)

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

    return FidelityVerdict(
        ok=True,
        code="FIDELITY_OK",
        message="Structural silhouette is consistent enough to send to FASHN.",
        source=source,
        product=product,
        recommended_category=recommended,
    )
