"""Offline garment-reference preparation for FASHN Virtual Try-On.

FashionRise Studio captures a transparent garment-only sketch. FASHN expects a
product / flat-lay style ``garment_image``. This module converts the sketch into
one or more recognizable flat-lay plates **without** changing colors, shapes, or
design topology — only background and framing.

Two-piece detection is geometric (vertically separated opaque clusters). When
two pieces are found, FASHN v1.6 category docs require selecting **one** item per
request from a multi-item flat-lay, so FashionRise plans **two sequential calls**
(tops → bottoms) rather than guessing that a single ``auto`` call applies both.
"""

from __future__ import annotations

import base64
import hashlib
import io
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image

PieceCategory = Literal["tops", "bottoms", "one-pieces", "auto"]
PieceLayout = Literal["one_piece", "two_piece"]

_ALPHA_THRESHOLD = 24
_MIN_COMPONENT_FRACTION = 0.02  # ignore speckles < 2% of opaque mass
_MIN_COMPONENT_PIXELS = 80
_VERTICAL_GAP_MIN_FRAC = 0.04  # gap between clusters relative to canvas height
_PLATE_W = 768
_PLATE_H = 1024
_PAD = 48


@dataclass(frozen=True)
class PreparedPiece:
    category: PieceCategory
    png_bytes: bytes
    bbox: tuple[int, int, int, int]  # x0,y0,x1,y1 on source
    opaque_pixels: int

    def data_url(self) -> str:
        return "data:image/png;base64," + base64.b64encode(self.png_bytes).decode("ascii")


@dataclass(frozen=True)
class GarmentPrepResult:
    layout: PieceLayout
    pieces: tuple[PreparedPiece, ...]
    composite_png: bytes
    source_fingerprint: str
    fashn_calls: int

    def estimate_cents(self, cents_per_call: int) -> int:
        return max(1, int(cents_per_call)) * int(self.fashn_calls)

    def public_dict(self, *, cents_per_call: int) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "fashn_calls": self.fashn_calls,
            "estimate_cents": self.estimate_cents(cents_per_call),
            "garment_fingerprint": self.source_fingerprint,
            "composite_preview_base64": (
                "data:image/png;base64," + base64.b64encode(self.composite_png).decode("ascii")
            ),
            "pieces": [
                {
                    "category": p.category,
                    "image_base64": p.data_url(),
                    "bbox": list(p.bbox),
                    "opaque_pixels": p.opaque_pixels,
                }
                for p in self.pieces
            ],
            "notes": (
                "Two-piece swimwear uses sequential FASHN calls (tops then bottoms) — "
                "v1.6 applies one category per garment_image."
                if self.layout == "two_piece"
                else "Single garment plate → one FASHN call (category auto)."
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


def prepare_garment_reference(garment_png: bytes) -> GarmentPrepResult:
    """Convert transparent Studio garment PNG → FASHN-ready flat-lay plate(s)."""
    if not garment_png:
        raise ValueError("Empty garment artwork")
    src = Image.open(io.BytesIO(garment_png)).convert("RGBA")
    src.load()
    mask = _alpha_mask(src)
    opaque = sum(1 for row in mask for v in row if v)
    if opaque < _MIN_COMPONENT_PIXELS:
        raise ValueError("Garment artwork has no visible design pixels")

    fp = hashlib.sha256(garment_png).hexdigest()
    comps = _connected_components(mask)
    min_px = max(_MIN_COMPONENT_PIXELS, int(opaque * _MIN_COMPONENT_FRACTION))
    significant = [(cells, n) for cells, n in comps if n >= min_px]
    if not significant:
        significant = sorted(comps, key=lambda t: t[1], reverse=True)[:1]

    # Sort top → bottom by bbox y0.
    significant.sort(key=lambda t: _bbox(t[0])[1])
    layout: PieceLayout = "one_piece"
    selected: list[tuple[set[tuple[int, int]], int]] = significant

    if len(significant) >= 2:
        top_cells, _top_n = significant[0]
        top_box = _bbox(top_cells)
        below = [
            (cells, n)
            for cells, n in significant[1:]
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
                    layout = "two_piece"
                    selected = [(top_cells, len(top_cells)), (bot_cells, len(bot_cells))]

    pieces: list[PreparedPiece] = []
    if layout == "two_piece":
        cats: list[PieceCategory] = ["tops", "bottoms"]
        for (cells, n), cat in zip(selected, cats, strict=True):
            pieces.append(
                PreparedPiece(
                    category=cat,
                    png_bytes=_flat_lay_plate(src, cells),
                    bbox=_bbox(cells),
                    opaque_pixels=n,
                )
            )
        fashn_calls = 2
    else:
        merged: set[tuple[int, int]] = set()
        for cells, _n in significant:
            merged |= cells
        if not merged:
            merged = {(x, y) for y, row in enumerate(mask) for x, v in enumerate(row) if v}
        pieces.append(
            PreparedPiece(
                category="auto",
                png_bytes=_flat_lay_plate(src, merged),
                bbox=_bbox(merged),
                opaque_pixels=len(merged),
            )
        )
        fashn_calls = 1

    return GarmentPrepResult(
        layout=layout,
        pieces=tuple(pieces),
        composite_png=_composite_preview(pieces),
        source_fingerprint=fp,
        fashn_calls=fashn_calls,
    )
