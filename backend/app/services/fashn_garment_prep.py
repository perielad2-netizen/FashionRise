"""Offline garment-reference preparation for FASHN Virtual Try-On.

FashionRise Studio captures a transparent garment-only sketch. FASHN expects a
product / flat-lay style ``garment_image``. This module converts the sketch into
one or more recognizable flat-lay plates **without** inventing colors or
redesigning topology — only background, framing, and component grouping.

Two-piece detection is geometric (vertically separated opaque clusters). When
two pieces are found, FASHN v1.6 category docs require selecting **one** item per
request from a multi-item flat-lay, so FashionRise plans **two sequential calls**
(tops → bottoms) rather than guessing that a single ``auto`` call applies both.

#161: morphological closing + band merging keep filled regions with their
contours so plates are not outline-only rings. Fill quality is fail-closed.
"""

from __future__ import annotations

import base64
import hashlib
import io
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image, ImageFilter

from app.services.fashn_garment_fidelity import (
    compute_silhouette_features,
    recommend_fashn_category,
)
from app.services.garment_leg_geometry import analyze_lower_garment_geometry

PieceCategory = Literal["tops", "bottoms", "one-pieces", "auto"]
PieceLayout = Literal["one_piece", "two_piece"]

_ALPHA_THRESHOLD = 24
_MIN_COMPONENT_FRACTION = 0.015  # ignore speckles < 1.5% of opaque mass
_MIN_COMPONENT_PIXELS = 64
_VERTICAL_GAP_MIN_FRAC = 0.04  # gap between clusters relative to canvas height
_PLATE_W = 768
_PLATE_H = 1024
_PAD = 48
# Morphological close radius (px) to bridge stroke↔fill gaps before CC.
_CLOSE_RADIUS = 2
# Fail closed when a selected piece is mostly perimeter ink (outline-only).
_MAX_OUTLINE_EDGE_RATIO = 0.78
_MIN_FILL_COLOR_PIXELS = 40
_NEAR_BLACK = 36  # RGB max channel below this ≈ stroke ink on white plates
# Completeness: prepared opaque mass vs source (reject silent leg discard).
_MIN_PREP_OPAQUE_RETENTION = 0.72
_MIN_PREP_Y_SPAN_RETENTION = 0.82


@dataclass(frozen=True)
class PreparedPiece:
    category: PieceCategory
    png_bytes: bytes
    bbox: tuple[int, int, int, int]  # x0,y0,x1,y1 on source
    opaque_pixels: int
    fill_ratio: float
    edge_ratio: float

    def data_url(self) -> str:
        return "data:image/png;base64," + base64.b64encode(self.png_bytes).decode("ascii")


@dataclass(frozen=True)
class GarmentPrepResult:
    layout: PieceLayout
    pieces: tuple[PreparedPiece, ...]
    composite_png: bytes
    source_fingerprint: str
    fashn_calls: int
    quality_ok: bool
    quality_notes: str

    def estimate_cents(self, cents_per_call: int) -> int:
        return max(1, int(cents_per_call)) * int(self.fashn_calls)

    def prefer_local_product(self) -> bool:
        """Always False — local plate re-encode is not a FASHN garment (#164 follow-up).

        Owner App ``c2d0ba41`` run ``9b837e89``→``6f4c8c36``: skipping OpenAI realism left
        sketch-like plates (hard outlines, flat fill) as FASHN inputs. Photoreal try-on
        requires a paid OpenAI product image before FASHN.
        """
        return False

    def public_dict(self, *, cents_per_call: int, realism_cents_per_piece: int = 8) -> dict[str, Any]:
        realism_calls = len(self.pieces)
        realism_estimate = max(1, int(realism_cents_per_piece)) * max(1, realism_calls)
        fashn_estimate = self.estimate_cents(cents_per_call)
        return {
            "layout": self.layout,
            "fashn_calls": self.fashn_calls,
            "estimate_cents": fashn_estimate,
            "realism_calls": realism_calls,
            "realism_estimate_cents": realism_estimate,
            "combined_estimate_cents": realism_estimate + fashn_estimate,
            "prefer_local_product": False,
            "garment_fingerprint": self.source_fingerprint,
            "quality_ok": self.quality_ok,
            "quality_notes": self.quality_notes,
            "composite_preview_base64": (
                "data:image/png;base64," + base64.b64encode(self.composite_png).decode("ascii")
            ),
            "pieces": [
                {
                    "category": p.category,
                    "image_base64": p.data_url(),
                    "bbox": list(p.bbox),
                    "opaque_pixels": p.opaque_pixels,
                    "fill_ratio": round(p.fill_ratio, 4),
                    "edge_ratio": round(p.edge_ratio, 4),
                }
                for p in self.pieces
            ],
            "notes": (
                "Two-piece swimwear: paid OpenAI realistic product images, then sequential "
                "FASHN calls (tops then bottoms) only if fidelity passes. Sketch plates are "
                "never sent to FASHN."
                if self.layout == "two_piece"
                else "One-piece uses FASHN category one-pieces after paid OpenAI product "
                "image + fidelity. Sketch plates are never sent to FASHN."
            ),
        }


def _png_bytes(img: Image.Image) -> bytes:
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _alpha_mask(src: Image.Image) -> list[list[bool]]:
    w, h = src.size
    alpha = src.getchannel("A")
    pix = alpha.load()
    assert pix is not None
    return [[pix[x, y] >= _ALPHA_THRESHOLD for x in range(w)] for y in range(h)]


def _close_mask(mask: list[list[bool]], radius: int = _CLOSE_RADIUS) -> list[list[bool]]:
    """Binary morphological close so filled interiors reconnect with nearby strokes."""
    if radius <= 0 or not mask:
        return mask
    h = len(mask)
    w = len(mask[0]) if h else 0
    # Encode as 0/255 image for PIL MaxFilter/MinFilter.
    im = Image.new("L", (w, h), 0)
    px = im.load()
    assert px is not None
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                px[x, y] = 255
    size = radius * 2 + 1
    closed = im.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    cpx = closed.load()
    assert cpx is not None
    return [[cpx[x, y] >= 128 for x in range(w)] for y in range(h)]


def _connected_components(mask: list[list[bool]]) -> list[tuple[set[tuple[int, int]], int]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    visited = [[False] * w for _ in range(h)]
    comps: list[tuple[set[tuple[int, int]], int]] = []
    for y in range(h):
        for x in range(w):
            if not mask[y][x] or visited[y][x]:
                continue
            q: deque[tuple[int, int]] = deque([(x, y)])
            visited[y][x] = True
            cells: set[tuple[int, int]] = set()
            while q:
                cx, cy = q.popleft()
                cells.add((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        q.append((nx, ny))
            comps.append((cells, len(cells)))
    return comps


def _bbox(cells: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def _edge_ratio(cells: set[tuple[int, int]]) -> float:
    """Fraction of opaque cells that touch a non-opaque 4-neighbor (outline-ish)."""
    if not cells:
        return 1.0
    cell_set = cells
    edge = 0
    for x, y in cell_set:
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (nx, ny) not in cell_set:
                edge += 1
                break
    return edge / max(len(cell_set), 1)


def _fill_color_stats(src: Image.Image, cells: set[tuple[int, int]]) -> tuple[float, int]:
    """Return (fill_ratio, colored_pixels) where fill_ratio = non-near-black / opaque."""
    if not cells:
        return 0.0, 0
    px = src.load()
    assert px is not None
    colored = 0
    for x, y in cells:
        r, g, b, a = px[x, y]
        if a < _ALPHA_THRESHOLD:
            continue
        if max(r, g, b) >= _NEAR_BLACK:
            colored += 1
    return colored / max(len(cells), 1), colored


def _flat_lay_plate(src: Image.Image, cells: set[tuple[int, int]]) -> bytes:
    """Paste masked garment pixels onto a white flat-lay canvas (design unchanged)."""
    x0, y0, x1, y1 = _bbox(cells)
    crop = src.crop((x0, y0, x1, y1)).convert("RGBA")
    # Zero alpha outside this component so neighboring pieces don't bleed.
    px = crop.load()
    assert px is not None
    cell_local = {(x - x0, y - y0) for x, y in cells}
    cw, ch = crop.size
    for y in range(ch):
        for x in range(cw):
            if (x, y) not in cell_local:
                r, g, b, _a = px[x, y]
                px[x, y] = (r, g, b, 0)

    gw, gh = crop.size
    scale = min((_PLATE_W - 2 * _PAD) / max(gw, 1), (_PLATE_H - 2 * _PAD) / max(gh, 1), 1.0)
    nw, nh = max(1, int(round(gw * scale))), max(1, int(round(gh * scale)))
    if (nw, nh) != (gw, gh):
        crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)

    plate = Image.new("RGB", (_PLATE_W, _PLATE_H), (255, 255, 255))
    ox = (_PLATE_W - nw) // 2
    oy = (_PLATE_H - nh) // 2
    plate.paste(crop, (ox, oy), crop)
    return _png_bytes(plate)


def _composite_preview(pieces: list[PreparedPiece]) -> bytes:
    """Stack prepared plates vertically for owner inspection (not sent to FASHN)."""
    if not pieces:
        return _png_bytes(Image.new("RGB", (_PLATE_W, _PLATE_H), (255, 255, 255)))
    imgs = [Image.open(io.BytesIO(p.png_bytes)).convert("RGB") for p in pieces]
    gap = 16
    total_h = sum(im.height for im in imgs) + gap * (len(imgs) - 1)
    width = max(im.width for im in imgs)
    canvas = Image.new("RGB", (width, total_h), (245, 245, 245))
    y = 0
    for im in imgs:
        canvas.paste(im, ((width - im.width) // 2, y))
        y += im.height + gap
    return _png_bytes(canvas)


def _union_in_band(
    significant: list[tuple[set[tuple[int, int]], int]],
    y0: int,
    y1: int,
    *,
    canvas_h: int,
) -> set[tuple[int, int]]:
    """Merge every significant component whose centroid falls in [y0, y1)."""
    merged: set[tuple[int, int]] = set()
    for cells, _n in significant:
        bx0, by0, bx1, by1 = _bbox(cells)
        cy = (by0 + by1) / 2.0
        # Inclusive band with small slack so near-edge fills join the piece.
        slack = max(4, int(canvas_h * 0.02))
        if (y0 - slack) <= cy < (y1 + slack):
            merged |= cells
    return merged


def _is_footwear_component(cells: set[tuple[int, int]], canvas_h: int, canvas_w: int) -> bool:
    """True for shoe-sized blobs in the foot band (not a bottoms garment).

    Owner incident 2026-11-05: one-piece swimsuit + drawn shoes was split into
    two_piece tops/bottoms; black shoe fills failed the bottoms fill-color gate
    and Max fallback died after OpenAI output moderation. Footwear is not a
    FASHN bottoms plate — keep the torso garment as one_piece.
    """
    if not cells or canvas_h <= 0:
        return False
    _x0, y0, _x1, y1 = _bbox(cells)
    h = max(1, y1 - y0)
    w = max(1, _x1 - _x0)
    # Must sit primarily in the lower ~28% of the canvas.
    if y0 < canvas_h * 0.72:
        return False
    # Shoe height, not a pant/skirt panel.
    if h > canvas_h * 0.28:
        return False
    # Narrow-ish relative to canvas (full-width hems are not shoes).
    if w > canvas_w * 0.55:
        return False
    return True


def _piece_from_cells(
    src: Image.Image,
    cells: set[tuple[int, int]],
    category: PieceCategory,
) -> PreparedPiece:
    # Prefer original alpha cells (not morphologically dilated) when overlapping.
    raw_mask = _alpha_mask(src)
    refined = {(x, y) for x, y in cells if 0 <= y < len(raw_mask) and 0 <= x < len(raw_mask[0]) and raw_mask[y][x]}
    if not refined:
        refined = set(cells)
    fill_ratio, colored = _fill_color_stats(src, refined)
    edge = _edge_ratio(refined)
    return PreparedPiece(
        category=category,
        png_bytes=_flat_lay_plate(src, refined),
        bbox=_bbox(refined),
        opaque_pixels=len(refined),
        fill_ratio=fill_ratio,
        edge_ratio=edge,
    )


def _quality_gate(pieces: list[PreparedPiece]) -> tuple[bool, str]:
    problems: list[str] = []
    for p in pieces:
        if p.opaque_pixels < _MIN_COMPONENT_PIXELS:
            problems.append(f"{p.category}: too few visible pixels")
            continue
        if p.edge_ratio >= _MAX_OUTLINE_EDGE_RATIO and p.fill_ratio < 0.35:
            problems.append(
                f"{p.category}: looks outline-only (edge={p.edge_ratio:.2f}, fill={p.fill_ratio:.2f})"
            )
        colored_est = int(round(p.fill_ratio * p.opaque_pixels))
        if colored_est < _MIN_FILL_COLOR_PIXELS and p.opaque_pixels >= _MIN_COMPONENT_PIXELS:
            # Thin black line-only garments fail closed — legitimate neon/black fills still pass via fill_ratio.
            if p.fill_ratio < 0.2:
                problems.append(f"{p.category}: missing filled garment color")
    if problems:
        return False, (
            "Prepared garment plate is not a recognizable filled design — "
            + "; ".join(problems)
            + ". Adjust the sketch fill/colors, then retry. FASHN is blocked until plates look like clothing."
        )
    return True, "Prepared plates retain filled garment regions suitable for product generation."


def _completeness_gate(
    *,
    source_opaque: int,
    source_bbox: tuple[int, int, int, int],
    source_h: int,
    pieces: list[PreparedPiece],
    discarded_opaque: int,
) -> tuple[bool, str]:
    """Fail closed when prep drops meaningful garment mass (e.g. trouser legs)."""
    if source_opaque <= 0 or not pieces:
        return False, "Prepared plates are empty — FASHN is blocked."
    kept = sum(p.opaque_pixels for p in pieces)
    retention = kept / max(source_opaque, 1)
    sy0, sy1 = source_bbox[1], source_bbox[3]
    source_span = max(1, sy1 - sy0)
    # Union vertical span across pieces (two-piece tops+bottoms must cover together).
    union_y0 = min(p.bbox[1] for p in pieces)
    union_y1 = max(p.bbox[3] for p in pieces)
    span_retention = max(1, union_y1 - union_y0) / source_span
    if discarded_opaque >= max(_MIN_COMPONENT_PIXELS, int(source_opaque * 0.08)):
        return False, (
            "Garment preparation dropped substantial regions of your design "
            f"(≈{discarded_opaque} opaque pixels). Long trouser legs or separate panels "
            "must stay in the plate. Adjust the fill so legs stay connected and solid, "
            "then retry. No paid realism or FASHN call was started."
        )
    if retention < _MIN_PREP_OPAQUE_RETENTION:
        return False, (
            "Prepared plates are missing large parts of your original garment silhouette "
            f"(kept {retention:.0%}). FASHN is blocked until the full design is preserved."
        )
    if source_span >= int(0.35 * max(source_h, 1)) and span_retention < _MIN_PREP_Y_SPAN_RETENTION:
        return False, (
            "Prepared plates shortened your garment height vs the Studio capture "
            f"(kept {span_retention:.0%} of the original vertical span). "
            "Trouser legs or long hems appear truncated — FASHN is blocked."
        )
    return True, ""


def _unsupported_silhouette_gate(
    *,
    source_png: bytes,
    layout: PieceLayout,
    pieces: list[PreparedPiece],
) -> tuple[bool, str]:
    """Fail closed for jumpsuit/trousers — do not reclassify as swimsuit one-pieces."""
    if layout == "two_piece":
        return True, ""
    geo = analyze_lower_garment_geometry(source_png)
    if geo.looks_like_jumpsuit or geo.looks_like_trousers:
        return False, (
            "This design looks like a jumpsuit or trousers with separate leg openings. "
            "FASHN Try On currently supports swimwear / two-piece plates only — "
            "it must not rewrite trousers into a swimsuit or bodysuit. "
            "Use Try On Person (OpenAI) for this silhouette, or redesign as supported swimwear. "
            "No paid realism or FASHN call was started."
        )
    return True, ""


def prep_from_approved_product_pieces(
    *,
    pieces: list[tuple[PieceCategory, bytes]],
    source_fingerprint: str,
) -> GarmentPrepResult:
    """Build a prep result from owner-accepted realistic product PNGs (not sketch plates)."""
    if not pieces:
        raise ValueError("approved garment pieces required")
    built: list[PreparedPiece] = []
    for cat, png in pieces:
        if not png:
            raise ValueError(f"empty approved piece for {cat}")
        with Image.open(io.BytesIO(png)) as im:
            im.load()
            rgb = im.convert("RGB")
            # Normalize to plate size for FASHN consistency.
            fitted = Image.new("RGB", (_PLATE_W, _PLATE_H), (245, 245, 245))
            scale = min(_PLATE_W / max(rgb.width, 1), _PLATE_H / max(rgb.height, 1), 1.0)
            nw = max(1, int(round(rgb.width * scale)))
            nh = max(1, int(round(rgb.height * scale)))
            resized = rgb.resize((nw, nh), Image.Resampling.LANCZOS) if (nw, nh) != rgb.size else rgb
            ox = (_PLATE_W - nw) // 2
            oy = (_PLATE_H - nh) // 2
            fitted.paste(resized, (ox, oy))
            built.append(
                PreparedPiece(
                    category=cat,
                    png_bytes=_png_bytes(fitted),
                    bbox=(0, 0, nw, nh),
                    opaque_pixels=nw * nh,
                    fill_ratio=1.0,
                    edge_ratio=0.0,
                )
            )
    layout: PieceLayout = "two_piece" if len(built) >= 2 else "one_piece"
    return GarmentPrepResult(
        layout=layout,
        pieces=tuple(built),
        composite_png=_composite_preview(built),
        source_fingerprint=source_fingerprint,
        fashn_calls=len(built),
        quality_ok=True,
        quality_notes="Owner-accepted realistic product garment reference.",
    )


def prepare_garment_reference(garment_png: bytes) -> GarmentPrepResult:
    """Convert transparent Studio garment PNG → FASHN-ready flat-lay plate(s)."""
    if not garment_png:
        raise ValueError("Empty garment artwork")
    src = Image.open(io.BytesIO(garment_png)).convert("RGBA")
    src.load()
    raw_mask = _alpha_mask(src)
    opaque = sum(1 for row in raw_mask for v in row if v)
    if opaque < _MIN_COMPONENT_PIXELS:
        raise ValueError("Garment artwork has no visible design pixels")

    source_cells = {(x, y) for y, row in enumerate(raw_mask) for x, v in enumerate(row) if v}
    source_bbox = _bbox(source_cells) if source_cells else (0, 0, 0, 0)

    fp = hashlib.sha256(garment_png).hexdigest()
    # Close small gaps so stroke contours reconnect to their fills before CC.
    mask = _close_mask(raw_mask, _CLOSE_RADIUS)
    comps = _connected_components(mask)
    min_px = max(_MIN_COMPONENT_PIXELS, int(opaque * _MIN_COMPONENT_FRACTION))
    significant = [(cells, n) for cells, n in comps if n >= min_px]
    # Tiny foot-band crumbs (eraser leftovers after deleting shoes) must not count
    # as "dropped garment mass" — they only inflate vertical span / discarded totals.
    discarded_opaque = sum(
        n
        for cells, n in comps
        if n < min_px and not _is_footwear_component(cells, src.height, src.width)
    )
    if not significant:
        significant = sorted(comps, key=lambda t: t[1], reverse=True)[:1]
        discarded_opaque = sum(
            n
            for cells, n in comps
            if cells is not significant[0][0]
            and not _is_footwear_component(cells, src.height, src.width)
        )

    # Sort top → bottom by bbox y0.
    significant.sort(key=lambda t: _bbox(t[0])[1])

    # Drawn shoes near the croquis feet are not a bottoms garment. Split them out
    # so one-piece swimsuits are not misclassified as two_piece tops+bottoms.
    apparel_significant: list[tuple[set[tuple[int, int]], int]] = []
    footwear_opaque = 0
    footwear_cells: set[tuple[int, int]] = set()
    for cells, n in significant:
        if _is_footwear_component(cells, src.height, src.width):
            footwear_opaque += n
            footwear_cells |= cells
        else:
            apparel_significant.append((cells, n))
    if not apparel_significant:
        apparel_significant = list(significant)
        footwear_opaque = 0
        footwear_cells = set()

    layout: PieceLayout = "one_piece"
    top_band: tuple[int, int] | None = None
    bot_band: tuple[int, int] | None = None

    if len(apparel_significant) >= 2:
        top_cells, _top_n = apparel_significant[0]
        top_box = _bbox(top_cells)
        below = [
            (cells, n)
            for cells, n in apparel_significant[1:]
            if _bbox(cells)[1] >= top_box[3]
        ]
        if below:
            bot_cells, _bot_n = max(below, key=lambda t: t[1])
            bot_box = _bbox(bot_cells)
            gap = bot_box[1] - top_box[3]
            if gap >= max(8, int(src.height * _VERTICAL_GAP_MIN_FRAC)):
                top_cy = (top_box[1] + top_box[3]) / 2.0 / src.height
                bot_cy = (bot_box[1] + bot_box[3]) / 2.0 / src.height
                if top_cy < 0.55 and bot_cy > 0.40 and bot_cy > top_cy + 0.08:
                    # #179 — a high fashion slit / open-leg dress can look like two
                    # vertically stacked components. Prefer one continuous dress plate
                    # when geometry confidently says high-slit dress (not trousers).
                    geo_probe = analyze_lower_garment_geometry(garment_png)
                    if geo_probe.looks_like_high_slit_dress and not geo_probe.looks_like_trousers:
                        layout = "one_piece"
                        top_band = None
                        bot_band = None
                    else:
                        layout = "two_piece"
                        mid = (top_box[3] + bot_box[1]) // 2
                        top_band = (0, mid)
                        bot_band = (mid, src.height)

    pieces: list[PreparedPiece] = []
    if layout == "two_piece" and top_band and bot_band:
        top_merged = _union_in_band(apparel_significant, top_band[0], top_band[1], canvas_h=src.height)
        bot_merged = _union_in_band(apparel_significant, bot_band[0], bot_band[1], canvas_h=src.height)
        if not top_merged or not bot_merged:
            layout = "one_piece"
        else:
            pieces.append(_piece_from_cells(src, top_merged, "tops"))
            pieces.append(_piece_from_cells(src, bot_merged, "bottoms"))
            fashn_calls = 2
            # Components outside the two bands still count as discarded mass.
            # Footwear discarded above is intentional and not counted here.
            kept_cells = top_merged | bot_merged
            extra = sum(n for cells, n in apparel_significant if not cells.issubset(kept_cells))
            discarded_opaque += extra

    if layout == "one_piece":
        merged: set[tuple[int, int]] = set()
        for cells, _n in apparel_significant:
            merged |= cells
        if not merged:
            merged = set(source_cells) - footwear_cells
        if not merged:
            merged = set(source_cells)
        # Owner incident: category=auto let FASHN turn a high-cut swimsuit into a dress.
        # Classify silhouette and prefer explicit one-pieces for swimsuit-like one-piece art.
        # #170: never quietly map jumpsuit/trousers → swimsuit one-pieces (fail closed below).
        probe = _piece_from_cells(src, merged, "auto")
        feats = compute_silhouette_features(probe.png_bytes)
        geo = analyze_lower_garment_geometry(garment_png)
        if geo.looks_like_jumpsuit or geo.looks_like_trousers:
            cat = "auto"  # placeholder; unsupported gate blocks paid path
        else:
            cat = recommend_fashn_category(layout="one_piece", features=feats)
        pieces = [_piece_from_cells(src, merged, cat)]  # type: ignore[arg-type]
        fashn_calls = 1

    # Completeness compares against significant apparel components only.
    # Foot-band speckles left after deleting shoes sit in source_cells but are
    # below min_px — including them inflated vertical span to ~40% retention
    # (owner incident 2026-11-05 deleted-shoes FASHN block).
    apparel_cells: set[tuple[int, int]] = set()
    for cells, _n in apparel_significant:
        apparel_cells |= cells
    if not apparel_cells:
        apparel_cells = set(source_cells) - footwear_cells
    apparel_opaque = max(1, sum(n for _c, n in apparel_significant)) if apparel_significant else max(
        1, opaque - footwear_opaque
    )
    apparel_bbox = _bbox(apparel_cells) if apparel_cells else source_bbox

    quality_ok, quality_notes = _quality_gate(pieces)
    if quality_ok:
        ok_c, note_c = _completeness_gate(
            source_opaque=apparel_opaque,
            source_bbox=apparel_bbox,
            source_h=src.height,
            pieces=pieces,
            discarded_opaque=discarded_opaque,
        )
        if not ok_c:
            quality_ok = False
            quality_notes = note_c
    if quality_ok:
        ok_s, note_s = _unsupported_silhouette_gate(
            source_png=garment_png,
            layout=layout,
            pieces=pieces,
        )
        if not ok_s:
            quality_ok = False
            quality_notes = note_s
    return GarmentPrepResult(
        layout=layout,
        pieces=tuple(pieces),
        composite_png=_composite_preview(pieces),
        source_fingerprint=fp,
        fashn_calls=fashn_calls,
        quality_ok=quality_ok,
        quality_notes=quality_notes,
    )
