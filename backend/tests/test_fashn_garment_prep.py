"""Offline FASHN garment preparation — no network, no paid calls."""

from __future__ import annotations

import io

from PIL import Image

from app.services.fashn_garment_prep import prepare_garment_reference


def _transparent_canvas(w: int = 200, h: int = 400) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_one_piece_flat_lay_preserves_color():
    img = _transparent_canvas()
    # Solid dress-like blob
    for y in range(40, 320):
        for x in range(60, 140):
            img.putpixel((x, y), (200, 40, 80, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.layout == "one_piece"
    assert prep.fashn_calls == 1
    assert len(prep.pieces) == 1
    assert prep.pieces[0].category == "auto"
    plate = Image.open(io.BytesIO(prep.pieces[0].png_bytes)).convert("RGB")
    # White background plate with red garment present
    assert plate.size == (768, 1024)
    colors = plate.getcolors(maxcolors=50000) or []
    assert any(c[1][0] > 150 and c[1][1] < 80 for c in colors)


def test_two_piece_detects_vertical_separation():
    img = _transparent_canvas(220, 440)
    # Top
    for y in range(30, 120):
        for x in range(70, 150):
            img.putpixel((x, y), (255, 120, 40, 255))
    # Bottom (clear vertical gap)
    for y in range(220, 340):
        for x in range(75, 145):
            img.putpixel((x, y), (255, 120, 40, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.layout == "two_piece"
    assert prep.fashn_calls == 2
    assert [p.category for p in prep.pieces] == ["tops", "bottoms"]
    public = prep.public_dict(cents_per_call=8)
    assert public["estimate_cents"] == 16
    assert public["composite_preview_base64"].startswith("data:image/png;base64,")
    assert len(public["pieces"]) == 2
