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
    TRY_ON_PROMPT_V2_4,
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
    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.4"
    prompt = build_try_on_prompt(None)
    assert prompt == TRY_ON_PROMPT_V2_4
    assert "pale cream" in prompt.lower() or "ivory" in prompt.lower()
    assert "matte" in prompt.lower()
    assert "plunging" in prompt.lower() or "deep-v" in prompt.lower()
    assert "both sleeves" in prompt.lower()
    assert "swimwear" not in prompt.lower()
    assert "lingerie" not in prompt.lower()


def test_magic_sketch_visibility_lifts_pale_off_white_paper():
    from app.services.garment_upper_geometry import (
        MAGIC_PAPER_RGB,
        prepare_magic_sketch_visibility,
    )

    # White paper + cream dress panel.
    im = Image.new("RGBA", (120, 160), (255, 255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle([30, 20, 90, 140], fill=(248, 244, 240, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    out, meta = prepare_magic_sketch_visibility(buf.getvalue())
    assert meta["paper_adjusted"] is True
    assert meta["pale_pixels_deepened"] > 0
    with Image.open(io.BytesIO(out)) as rgb:
        assert rgb.mode == "RGB"
        assert rgb.getpixel((5, 5)) == MAGIC_PAPER_RGB
        cream = rgb.getpixel((60, 80))
        assert sum(cream) / 3 < 248  # deepened vs source cream
        assert sum(cream) / 3 > 170  # still pale bridal, not charcoal


def test_magic_coverage_contract_mentions_pale_neckline_sleeves():
    from app.services import sketch_openai

    prompt = sketch_openai._build_image_prompt(
        {"summary": "cream gown", "image_prompt": "long dress"},
        "cream gown",
    )
    assert "plunging" in prompt.lower()
    assert "drop a sleeve" in prompt.lower()
    assert "pale cream" in prompt.lower()
    assert "darkened" in prompt.lower() or "paper" in prompt.lower()
