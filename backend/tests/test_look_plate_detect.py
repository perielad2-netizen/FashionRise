"""Server-side recognition of FashionRise look plates (no client tag needed)."""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.services.look_plate_detect import detect_fashionrise_look_plate
from tests.look_test_images import (
    FOREST,
    LOOK_SIZE,
    PAPER,
    look_plate_png,
    person_photo_png,
    product_photo_png,
    tryon_result_png,
)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _paper_with_block(box: tuple[int, int, int, int]) -> bytes:
    im = Image.new("RGB", LOOK_SIZE, PAPER)
    ImageDraw.Draw(im).rectangle(box, fill=FOREST)
    return _png(im)


def test_look_plate_is_recognized_from_layout_alone():
    found = detect_fashionrise_look_plate(look_plate_png())
    assert found["is_look"] is True
    assert found["reason"] == "layout_match"
    assert found["margin_paper"] >= 0.8
    assert found["figure_top"] <= 0.2 and found["figure_bottom"] >= 0.8
    assert abs(found["figure_center_x"] - 0.5) < 0.05


def test_opaque_rgba_canvas_export_is_still_a_look():
    # The web client re-encodes the look through a canvas, which yields RGBA with full alpha.
    with Image.open(io.BytesIO(look_plate_png())) as im:
        rgba = _png(im.convert("RGBA"))
    assert detect_fashionrise_look_plate(rgba)["is_look"] is True


def _transparent_cutout() -> bytes:
    with Image.open(io.BytesIO(look_plate_png())) as im:
        rgba = im.convert("RGBA")
    rgba.putalpha(Image.new("L", LOOK_SIZE, 0))
    return _png(rgba)


@pytest.mark.parametrize(
    ("png", "reason"),
    [
        (b"", "empty"),
        (b"not an image", "undecodable"),
        (person_photo_png(), "size"),
        (look_plate_png(size=(768, 1152)), "size"),
        (tryon_result_png(size=LOOK_SIZE), "background_not_plain"),
        (look_plate_png(background=(120, 120, 120)), "background_not_plain"),
        (_transparent_cutout(), "transparent"),
        (_png(Image.new("RGB", LOOK_SIZE, PAPER)), "content_coverage"),
        (_paper_with_block((300, 480, 724, 980)), "not_full_length"),
        (_paper_with_block((120, 100, 330, 1420)), "off_center"),
        (product_photo_png(), "not_full_length"),
    ],
    ids=[
        "empty",
        "garbage",
        "phone-photo-size",
        "look-layout-other-size",
        "tryon-photo-same-size",
        "dark-backdrop",
        "transparent-cutout",
        "blank-paper",
        "flat-lay",
        "off-center",
        "materialized-product-photo",
    ],
)
def test_non_look_uploads_are_rejected_with_reason(png: bytes, reason: str):
    found = detect_fashionrise_look_plate(png)
    assert found["is_look"] is False
    assert found["reason"] == reason
