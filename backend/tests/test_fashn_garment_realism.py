"""Offline garment-realism prompt / kwargs — no paid OpenAI."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.fashn_garment_realism import (
    GARMENT_REALISM_PROMPT_VERSION,
    LOCAL_PRODUCT_PROVIDER_ID,
    OpenAIGarmentRealismAdapter,
    compose_studio_on_figure,
    estimate_garment_realism_cents,
    garment_realism_prompt,
    productize_filled_plate,
)
from app.services.personal_croquis_provider import ProviderNotAvailableError


def _plate_png() -> bytes:
    img = Image.new("RGB", (256, 384), (255, 255, 255))
    for y in range(40, 200):
        for x in range(60, 196):
            img.putpixel((x, y), (220, 40, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _transparent_garment_png(*, width: int = 256, height: int = 384) -> bytes:
    """Open-leg style fill: two green columns with a center gap (slit)."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    green = (22, 101, 52, 255)
    for y in range(50, 340):
        for x in range(40, 110):
            img.putpixel((x, y), green)
        for x in range(146, 216):
            img.putpixel((x, y), green)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _croquis_figure_png(*, width: int = 200, height: int = 320) -> bytes:
    """Simple opaque figure silhouette (skin tone) for underlay tests."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    skin = (220, 180, 150, 255)
    for y in range(20, 300):
        for x in range(70, 130):
            img.putpixel((x, y), skin)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_prompt_forbids_person_and_preserves_design():
    text = garment_realism_prompt(category="tops")
    assert "photorealistic commercial clothing product photograph" in text
    assert "No person" in text
    assert "swimsuit top" in text.lower() or "bikini" in text.lower()
    assert GARMENT_REALISM_PROMPT_VERSION.startswith("fashn-garment-realism-v6")
    assert "twist" in text.lower()
    assert "sketch stroke" in text.lower() or "line art" in text.lower()
    assert "realistic" in text.lower() and "fabric" in text.lower()
    assert "COVERAGE FIDELITY" in text
    assert "COLOR FIDELITY" in text
    assert "Avoid photorealism" not in text
    assert "Do not turn a swimsuit" in text or "must not become a mini dress" in garment_realism_prompt(
        category="one-pieces"
    )


def test_croquis_conditioned_prompt_removes_figure_and_protects_slit():
    text = garment_realism_prompt(
        category="one-pieces",
        croquis_conditioned=True,
        design_bits=["garment type: dress or gown with a high fashion slit — not trousers or a jumpsuit"],
    )
    assert "CROQUIS-CONDITIONED" in text
    assert "remove the croquis figure" in text.lower() or "Remove the croquis figure" in text
    assert "not trousers" in text.lower() or "NOT separate trouser" in text
    assert "fashion slit" in text.lower() or "slit" in text.lower()
    # Must not push swimsuit-one-piece language that fights open-leg dresses.
    assert "must not become a mini dress" not in text


def test_compose_studio_on_figure_layers_garment_over_croquis():
    garment = _transparent_garment_png()
    croquis = _croquis_figure_png()
    composed = compose_studio_on_figure(croquis_png=croquis, garment_png=garment)
    img = Image.open(io.BytesIO(composed)).convert("RGBA")
    assert img.size[0] <= 1536 and img.size[1] <= 1536
    # Center gap should still show non-green (figure/paper), not solid green pants.
    cx, cy = img.size[0] // 2, int(img.size[1] * 0.55)
    center = img.getpixel((cx, cy))
    # Left column should include green garment pixels.
    left = img.getpixel((int(img.size[0] * 0.30), cy))
    assert left[1] > 80  # green-ish
    # Center should not be the same solid green fill (slit / figure shows through).
    assert center[:3] != left[:3]


def test_productize_filled_plate_preserves_colors():
    product, meta = productize_filled_plate(_plate_png())
    assert meta["provider"] == LOCAL_PRODUCT_PROVIDER_ID
    assert meta["local_product"] is True
    img = Image.open(io.BytesIO(product)).convert("RGB")
    colors = img.getcolors(maxcolors=100000) or []
    assert any(c[1][0] > 180 and c[1][1] < 80 for c in colors)


def test_estimate_scales_with_pieces(monkeypatch):
    monkeypatch.setenv("FASHN_GARMENT_REALISM_ESTIMATE_CENTS", "8")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert estimate_garment_realism_cents(pieces=1) == 8
    assert estimate_garment_realism_cents(pieces=2) == 16


def test_build_edit_kwargs_uses_single_plate_image(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    from app.core.config import get_settings

    get_settings.cache_clear()
    adapter = OpenAIGarmentRealismAdapter()
    kwargs = adapter.build_edit_kwargs(plate_png=_plate_png(), category="auto")
    assert kwargs["n"] == 1
    assert "No person" in kwargs["prompt"]
    image = kwargs.get("image")
    # Single-input edit: (filename, fileobj, mime) — never a person/photo pair.
    assert isinstance(image, tuple) and len(image) == 3
    assert image[0] == "sketch.png"
    assert image[2] == "image/png"


def test_build_edit_kwargs_attaches_studio_context_as_second_image(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    from app.core.config import get_settings
    from app.services.fashn_garment_realism import downscale_studio_context

    get_settings.cache_clear()
    adapter = OpenAIGarmentRealismAdapter()
    ctx = downscale_studio_context(_plate_png())
    kwargs = adapter.build_edit_kwargs(
        plate_png=_plate_png(),
        category="tops",
        studio_context_png=ctx,
    )
    image = kwargs.get("image")
    assert isinstance(image, list) and len(image) == 2
    assert image[0][0] == "sketch.png"
    assert image[1][0].startswith("textile.")
    assert "Image 2" in kwargs["prompt"] or "STUDIO CONTEXT" in kwargs["prompt"]
    assert "COVERAGE FIDELITY" in kwargs["prompt"]


def test_build_edit_kwargs_croquis_conditioned_puts_on_figure_first(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    from app.core.config import get_settings

    get_settings.cache_clear()
    adapter = OpenAIGarmentRealismAdapter()
    plate = _transparent_garment_png()
    on_figure = compose_studio_on_figure(croquis_png=_croquis_figure_png(), garment_png=plate)
    kwargs = adapter.build_edit_kwargs(
        plate_png=plate,
        category="one-pieces",
        studio_context_png=on_figure,
        croquis_conditioned=True,
    )
    image = kwargs.get("image")
    assert isinstance(image, list) and len(image) == 2
    # Image 1 = on-figure composite; Image 2 = isolated plate (color authority).
    assert image[0][0] == "sketch.png"
    assert image[1][0].startswith("textile.")
    assert "CROQUIS-CONDITIONED" in kwargs["prompt"]
    assert "remove the croquis" in kwargs["prompt"].lower()
    assert "not trousers" in kwargs["prompt"].lower() or "NOT separate trouser" in kwargs["prompt"]


def test_generate_requires_live_http(monkeypatch):
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    from app.core.config import get_settings

    get_settings.cache_clear()
    adapter = OpenAIGarmentRealismAdapter()
    with pytest.raises(ProviderNotAvailableError, match="LIVE_HTTP"):
        adapter.generate_piece(plate_png=_plate_png(), category="tops")
