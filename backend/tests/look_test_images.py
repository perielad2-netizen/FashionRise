"""Synthetic FashionRise look / product / try-on images for Fitting Room tests."""

from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw

PAPER = (248, 246, 240)
SKIN = (224, 180, 150)
OLIVE = (116, 125, 63)
FOREST = (56, 96, 65)
SKY = (120, 160, 215)
GROUND = (150, 142, 132)
NAVY = (45, 55, 95)
# A shaded leg seen through sheer green tulle (measured on a real try-on result).
SHEER_LEG = (84, 77, 54)

LOOK_SIZE = (1024, 1536)

# Garment spans these fractions of the frame height on every synthetic figure.
GARMENT_TOP = 0.15
GARMENT_BOTTOM = 0.72
# Where ``tryon_result_png(sheer_leg=...)`` shows a leg through the skirt (x0, y0, x1, y1).
SHEER_LEG_BOX = (0.44, 0.45, 0.54, 0.7)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _box(size: tuple[int, int], x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int]:
    w, h = size
    return int(w * x0), int(h * y0), int(w * x1), int(h * y1)


def split_row(split: float) -> float:
    """Frame-height fraction where the bodice ends and the skirt starts."""
    return GARMENT_TOP + (GARMENT_BOTTOM - GARMENT_TOP) * split


def _draw_figure(
    draw: ImageDraw.ImageDraw,
    size: tuple[int, int],
    *,
    body: tuple[int, int, int],
    bodice: tuple[int, int, int] | None,
    skirt: tuple[int, int, int] | None,
    split: float,
) -> None:
    draw.ellipse(_box(size, 0.44, 0.03, 0.56, 0.11), fill=body)
    draw.rectangle(_box(size, 0.47, 0.11, 0.53, GARMENT_TOP), fill=body)
    draw.rectangle(_box(size, 0.42, GARMENT_BOTTOM, 0.48, 0.93), fill=body)
    draw.rectangle(_box(size, 0.52, GARMENT_BOTTOM, 0.58, 0.93), fill=body)
    mid = split_row(split)
    if bodice is not None:
        draw.rectangle(_box(size, 0.38, GARMENT_TOP, 0.62, mid), fill=bodice)
    if skirt is not None:
        draw.rectangle(_box(size, 0.28, mid, 0.72, GARMENT_BOTTOM), fill=skirt)


def look_plate_png(
    *,
    bodice: tuple[int, int, int] = OLIVE,
    skirt: tuple[int, int, int] = FOREST,
    size: tuple[int, int] = LOOK_SIZE,
    split: float = 0.26,
    background: tuple[int, int, int] = PAPER,
) -> bytes:
    """Illustrated look plate: full-length drawn model on plain paper."""
    im = Image.new("RGB", size, background)
    _draw_figure(ImageDraw.Draw(im), size, body=SKIN, bodice=bodice, skirt=skirt, split=split)
    return _png(im)


def product_photo_png(
    *,
    bodice: tuple[int, int, int] | None = OLIVE,
    skirt: tuple[int, int, int] | None = FOREST,
    size: tuple[int, int] = LOOK_SIZE,
    split: float = 0.26,
) -> bytes:
    """Studio product photo: garment on a white mannequin, light-grey backdrop."""
    im = Image.new("RGB", size, (214, 214, 214))
    _draw_figure(
        ImageDraw.Draw(im), size, body=(242, 242, 242), bodice=bodice, skirt=skirt, split=split
    )
    return _png(im)


def _scene(size: tuple[int, int], *, textured: bool = False) -> Image.Image:
    im = Image.new("RGB", size, SKY)
    draw = ImageDraw.Draw(im)
    draw.rectangle(_box(size, 0.0, 0.62, 1.0, 1.0), fill=GROUND)
    if textured:
        # Busy, non-repeating background (stonework / foliage): any misregistration
        # between two frames shows up as a large difference almost everywhere.
        rng = random.Random(7)
        w, h = size
        for _ in range(420):
            x, y = rng.randrange(w), rng.randrange(h)
            bw, bh = rng.randrange(8, 44), rng.randrange(8, 44)
            shade = rng.randrange(40, 215)
            draw.rectangle((x, y, x + bw, y + bh), fill=(shade, shade - 12, shade - 28))
    return im


def _crop_to(im: Image.Image, keep_height: float) -> Image.Image:
    """Keep the top ``keep_height`` share of the frame (a waist-up / knee-up photo)."""
    if keep_height >= 1.0:
        return im
    return im.crop((0, 0, im.width, int(im.height * keep_height)))


def person_photo_png(
    *, size: tuple[int, int] = (400, 600), keep_height: float = 1.0, textured: bool = False
) -> bytes:
    """Outdoor person photo wearing a plain navy dress."""
    im = _scene(size, textured=textured)
    draw = ImageDraw.Draw(im)
    _draw_figure(draw, size, body=SKIN, bodice=None, skirt=None, split=0.26)
    draw.rectangle(_box(size, 0.38, GARMENT_TOP, 0.62, 0.6), fill=NAVY)
    return _png(_crop_to(im, keep_height))


def tryon_result_png(
    *,
    bodice: tuple[int, int, int] = OLIVE,
    skirt: tuple[int, int, int] = FOREST,
    size: tuple[int, int] = (400, 600),
    split: float = 0.26,
    keep_height: float = 1.0,
    textured: bool = False,
    sheer_leg: tuple[int, int, int] | None = None,
) -> bytes:
    """Same scene as ``person_photo_png`` with the look garment fitted.

    ``sheer_leg`` paints a leg showing through the lower skirt in that color.
    """
    im = _scene(size, textured=textured)
    draw = ImageDraw.Draw(im)
    _draw_figure(draw, size, body=SKIN, bodice=bodice, skirt=skirt, split=split)
    if sheer_leg is not None:
        draw.rectangle(_box(size, *SHEER_LEG_BOX), fill=sheer_leg)
    return _png(_crop_to(im, keep_height))


def reframe_png(
    png: bytes,
    *,
    size: tuple[int, int],
    scale: tuple[float, float] = (1.0, 1.0),
    shift: tuple[float, float] = (0.0, 0.0),
) -> bytes:
    """Re-render a frame the way a generator does: new size, content scaled and shifted.

    ``scale`` magnifies about the centre; ``shift`` moves content by that fraction of
    the frame (positive = right / down).
    """
    with Image.open(io.BytesIO(png)) as im:
        rgb = im.convert("RGB").resize(size, Image.Resampling.BILINEAR)
    w, h = size
    sx, sy = scale
    tx, ty = shift
    coeffs = (
        1.0 / sx,
        0.0,
        w / 2.0 - w / (2.0 * sx) - tx * w,
        0.0,
        1.0 / sy,
        h / 2.0 - h / (2.0 * sy) - ty * h,
    )
    return _png(rgb.transform(size, Image.Transform.AFFINE, coeffs, Image.Resampling.BILINEAR))


def pixel(png: bytes, fx: float, fy: float) -> tuple[int, int, int]:
    with Image.open(io.BytesIO(png)) as im:
        rgb = im.convert("RGB")
        return rgb.getpixel((int(rgb.width * fx), int(rgb.height * fy)))
