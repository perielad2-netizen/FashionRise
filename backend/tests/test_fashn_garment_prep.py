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
    # One-piece plates map to FASHN category one-pieces (never auto — swimsuit→dress incident).
    assert prep.pieces[0].category == "one-pieces"
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
    assert prep.quality_ok is True
    # #166 — OpenAI realism is always required before FASHN (no local plate skip).
    assert prep.prefer_local_product() is False
    public = prep.public_dict(cents_per_call=8, realism_cents_per_piece=8)
    assert public["estimate_cents"] == 16
    assert public["prefer_local_product"] is False
    assert public["realism_estimate_cents"] == 16
    assert public["combined_estimate_cents"] == 32
    assert "never sent to FASHN" in public["notes"]
    assert public["composite_preview_base64"].startswith("data:image/png;base64,")
    assert len(public["pieces"]) == 2


def test_outline_plus_disconnected_fill_keeps_color():
    """Stroke contour + separate fill blob must not yield an outline-only plate."""
    img = _transparent_canvas(200, 320)
    # Hollow-ish black contour (top ring)
    for y in range(40, 120):
        for x in range(60, 140):
            on_edge = x in (60, 139) or y in (40, 119)
            if on_edge:
                img.putpixel((x, y), (10, 10, 10, 255))
    # Interior orange fill (slightly inset, originally a separate component)
    for y in range(50, 110):
        for x in range(70, 130):
            img.putpixel((x, y), (255, 100, 30, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.layout == "one_piece"
    assert prep.quality_ok is True
    plate = Image.open(io.BytesIO(prep.pieces[0].png_bytes)).convert("RGB")
    colors = plate.getcolors(maxcolors=100000) or []
    assert any(c[1][0] > 200 and c[1][1] < 140 for c in colors), "expected orange fill retained"


def test_outline_only_fails_quality_gate():
    img = _transparent_canvas(180, 280)
    # Thin black rectangle outline only
    for y in range(40, 200):
        for x in range(50, 130):
            if x in (50, 129) or y in (40, 199):
                img.putpixel((x, y), (0, 0, 0, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.quality_ok is False
    assert "outline" in prep.quality_notes.lower() or "fill" in prep.quality_notes.lower()
    public = prep.public_dict(cents_per_call=8)
    assert public["quality_ok"] is False


def test_one_piece_with_drawn_shoes_stays_one_piece():
    """Swimsuit + foot-band shoes must not become two_piece tops/bottoms.

    Owner incident: OpenAI output-moderated deep-V swimsuit; Max fallback prep
    treated black shoes as bottoms (fill_ratio=0) and blocked with quality_ok=false.
    """
    img = _transparent_canvas(220, 440)
    # One-piece torso→hip fill
    for y in range(40, 220):
        for x in range(70, 150):
            img.putpixel((x, y), (185, 28, 28, 255))
    # Drawn black shoes near the feet (separate component, foot band)
    for y in range(360, 410):
        for x in range(80, 110):
            img.putpixel((x, y), (17, 17, 17, 255))
    for y in range(360, 410):
        for x in range(120, 150):
            img.putpixel((x, y), (17, 17, 17, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.layout == "one_piece"
    assert prep.fashn_calls == 1
    assert len(prep.pieces) == 1
    assert prep.pieces[0].category == "one-pieces"
    assert prep.quality_ok is True
    # Red swimsuit fill retained; shoes omitted from the FASHN plate.
    plate = Image.open(io.BytesIO(prep.pieces[0].png_bytes)).convert("RGB")
    colors = plate.getcolors(maxcolors=100000) or []
    assert any(c[1][0] > 150 and c[1][1] < 80 for c in colors)
