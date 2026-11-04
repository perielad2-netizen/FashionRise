"""#182 — pale bridal visibility + open neckline / sleeve geometry for OpenAI Try On."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.garment_upper_geometry import (
    OPENAI_TRY_ON_GARMENT_MATTE_RGB,
    analyze_upper_garment_geometry,
    openai_upper_design_hints,
    prepare_openai_try_on_garment_visibility,
)
from app.services.personal_try_on_provider import (
    TRY_ON_PROMPT_V2_2,
    TRY_ON_PROMPT_VERSION,
    build_try_on_prompt,
)


def _pale_vneck_two_sleeve_png() -> bytes:
    """Cream dress with deep V + both sleeves on transparent bg (owner 50f80224-class)."""
    im = Image.new("RGBA", (384, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    cream = (248, 244, 240, 255)
    # Bodice with deep V: left and right panels leaving a center gap.
    draw.polygon([(120, 80), (170, 80), (190, 220), (140, 420), (100, 220)], fill=cream)
    draw.polygon([(214, 80), (264, 80), (284, 220), (244, 420), (194, 220)], fill=cream)
    # Skirt
    draw.polygon([(100, 300), (284, 300), (300, 500), (84, 500)], fill=cream)
    # Left + right sleeves
    draw.ellipse([40, 100, 120, 280], fill=cream)
    draw.ellipse([264, 100, 344, 280], fill=cream)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _dark_high_neck_png() -> bytes:
    im = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([80, 40, 176, 360], fill=(20, 80, 160, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_pale_vneck_two_sleeve_geometry():
    geo = analyze_upper_garment_geometry(_pale_vneck_two_sleeve_png())
    assert geo.pale_dominant is True
    assert geo.open_neckline is True
    assert geo.bilateral_sleeves is True
    hints = openai_upper_design_hints(geo)
    assert any("pale" in h.lower() or "cream" in h.lower() for h in hints)
    assert any("neckline" in h.lower() or "plunging" in h.lower() for h in hints)
    assert any("both" in h.lower() and "sleeve" in h.lower() for h in hints)


def test_dark_high_neck_skips_bridal_hints():
    geo = analyze_upper_garment_geometry(_dark_high_neck_png())
    assert geo.pale_dominant is False
    assert geo.open_neckline is False
    hints = openai_upper_design_hints(geo)
    assert not any("pale" in h.lower() for h in hints)
    assert not any("plunging" in h.lower() for h in hints)


def test_visibility_matte_composites_pale_garment():
    raw = _pale_vneck_two_sleeve_png()
    out, meta = prepare_openai_try_on_garment_visibility(raw)
    assert meta["matte_applied"] is True
    assert meta["matte_rgb"] == list(OPENAI_TRY_ON_GARMENT_MATTE_RGB)
    with Image.open(io.BytesIO(out)) as im:
        assert im.mode == "RGB"
        px = im.getpixel((10, 10))
        assert px == OPENAI_TRY_ON_GARMENT_MATTE_RGB
        # Cream fabric pixel still pale (not crushed to matte).
        cream = im.getpixel((150, 350))
        assert sum(cream) / 3 > 180


def test_try_on_prompt_v2_2_bridal_rules():
    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.2"
    prompt = build_try_on_prompt(None)
    assert prompt == TRY_ON_PROMPT_V2_2
    assert "pale cream" in prompt.lower() or "ivory" in prompt.lower()
    assert "matte" in prompt.lower()
    assert "plunging" in prompt.lower() or "deep-v" in prompt.lower()
    assert "both sleeves" in prompt.lower()
    assert "swimwear" not in prompt.lower()
    assert "lingerie" not in prompt.lower()
