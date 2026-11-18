"""Server-side recognition of FashionRise look plates (no paid AI).

Social "Try on me" plants a published look into the Fitting Room. The server used
to trust a client tag (``source: fashionrise_look``) to pick the look pipeline.
Clients that never sent the tag (older app bundles, pieces persisted on-device
before the tag existed) silently fell through to the generic product-photo path,
which pastes the illustration onto the person. This module recognizes a look from
the image itself so the tag is no longer load-bearing.

A look plate is what the Magic look renderer emits: exactly 1024×1536, one
full-length figure centred on a plain light paper backdrop. The exact size is the
strong prior — phone photos and store images virtually never match it — and the
layout checks reject same-sized photos with real backgrounds.

Honesty: this is a layout heuristic, not an illustration classifier. A 1024×1536
full-length studio shot on a white backdrop is also accepted; it then takes the
materialize path, which costs one extra image edit and still yields a product
photo reference.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

LOOK_PLATE_SIZES: frozenset[tuple[int, int]] = frozenset({(1024, 1536)})

_GRID_W = 96
_GRID_H = 144
_PAPER_MIN_LUMA = 196
_PAPER_MAX_SPREAD = 0.14
_MARGIN_COLS = 6
_MIN_MARGIN_PAPER = 0.8
_MIN_CORNER_PAPER = 0.9
_MIN_CONTENT = 0.05
_MAX_CONTENT = 0.62
_MAX_FIGURE_TOP = 0.2
_MIN_FIGURE_BOTTOM = 0.8
_MIN_FIGURE_HEIGHT = 0.66
_CENTER_TOLERANCE = 0.15


def detect_fashionrise_look_plate(png: bytes) -> dict[str, Any]:
    """Return ``{"is_look": bool, "reason": str, ...signals}`` for a garment upload."""
    out: dict[str, Any] = {"is_look": False}
    if not png:
        out["reason"] = "empty"
        return out
    try:
        with Image.open(io.BytesIO(png)) as im:
            size = im.size
            if size not in LOOK_PLATE_SIZES:
                out["reason"] = "size"
                out["size"] = list(size)
                return out
            im.load()
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA")
                if rgba.getextrema()[3][0] < 250:
                    # Look plates are opaque; cut-outs are product images.
                    out["reason"] = "transparent"
                    return out
            grid = im.convert("RGB").resize((_GRID_W, _GRID_H), Image.Resampling.BILINEAR)
    except Exception:  # noqa: BLE001
        out["reason"] = "undecodable"
        return out

    px = grid.load()
    paper = [bytearray(_GRID_W) for _ in range(_GRID_H)]
    for y in range(_GRID_H):
        row = paper[y]
        for x in range(_GRID_W):
            r, g, b = px[x, y]
            mx = max(r, g, b)
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            if luma >= _PAPER_MIN_LUMA and (mx - min(r, g, b)) <= _PAPER_MAX_SPREAD * mx:
                row[x] = 1

    margin_total = 2 * _MARGIN_COLS * _GRID_H
    margin_paper = sum(
        sum(row[:_MARGIN_COLS]) + sum(row[_GRID_W - _MARGIN_COLS :]) for row in paper
    )
    corner_w = _GRID_W // 4
    corner_h = _GRID_H // 16
    corner_total = 2 * corner_w * corner_h
    corner_paper = sum(
        sum(row[:corner_w]) + sum(row[_GRID_W - corner_w :]) for row in paper[:corner_h]
    )
    content_rows = [_GRID_W - sum(row) for row in paper]
    content = sum(content_rows)
    figure_rows = [y for y, n in enumerate(content_rows) if n >= 3]
    signals = {
        "margin_paper": round(margin_paper / float(margin_total), 3),
        "corner_paper": round(corner_paper / float(corner_total), 3),
        "content": round(content / float(_GRID_W * _GRID_H), 3),
    }
    out.update(signals)
    if signals["margin_paper"] < _MIN_MARGIN_PAPER or signals["corner_paper"] < _MIN_CORNER_PAPER:
        out["reason"] = "background_not_plain"
        return out
    if not (_MIN_CONTENT <= signals["content"] <= _MAX_CONTENT) or not figure_rows:
        out["reason"] = "content_coverage"
        return out
    top = figure_rows[0] / float(_GRID_H)
    bottom = (figure_rows[-1] + 1) / float(_GRID_H)
    centroid = sum(
        x for row in paper for x in range(_GRID_W) if not row[x]
    ) / float(content * _GRID_W)
    out.update(
        {
            "figure_top": round(top, 3),
            "figure_bottom": round(bottom, 3),
            "figure_center_x": round(centroid, 3),
        }
    )
    if top > _MAX_FIGURE_TOP or bottom < _MIN_FIGURE_BOTTOM or (bottom - top) < _MIN_FIGURE_HEIGHT:
        out["reason"] = "not_full_length"
        return out
    if abs(centroid - 0.5) > _CENTER_TOLERANCE:
        out["reason"] = "off_center"
        return out
    out["is_look"] = True
    out["reason"] = "layout_match"
    return out
