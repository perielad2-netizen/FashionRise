"""#166 — OpenAI realism required before FASHN; no sketch-plate passthrough."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.fashn_garment_prep import prepare_garment_reference
from app.services.fashn_garment_realism import (
    GARMENT_REALISM_PROMPT_VERSION,
    GARMENT_REALISM_PROVIDER_ID,
    garment_realism_prompt,
)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _two_piece_sketch() -> bytes:
    img = Image.new("RGBA", (400, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [(140, 90), (200, 160), (260, 90), (300, 130), (280, 220), (120, 220), (100, 130)],
        fill=(196, 181, 253, 255),
    )
    draw.polygon(
        [(130, 360), (270, 360), (290, 420), (270, 500), (130, 500), (110, 420)],
        fill=(46, 16, 101, 255),
    )
    return _png(img)


def test_filled_plates_never_prefer_local_product():
    prep = prepare_garment_reference(_two_piece_sketch())
    assert prep.layout == "two_piece"
    assert prep.quality_ok is True
    assert prep.prefer_local_product() is False
    public = prep.public_dict(cents_per_call=8, realism_cents_per_piece=8)
    assert public["prefer_local_product"] is False
    assert public["realism_estimate_cents"] == 16
    assert public["estimate_cents"] == 16
    assert public["combined_estimate_cents"] == 32
    assert public["realism_calls"] == 2
    assert "OpenAI" in public["notes"]
    assert "never sent to FASHN" in public["notes"]


def test_realism_prompt_v4_demands_fabric_not_sketch():
    assert GARMENT_REALISM_PROMPT_VERSION == "fashn-garment-realism-v4"
    assert GARMENT_REALISM_PROVIDER_ID == "openai_garment_realism"
    text = garment_realism_prompt(category="tops", color_hint="#C4B5FD")
    assert "photorealistic commercial clothing product photograph" in text
    assert "Remove sketch stroke outlines" in text or "sketch stroke" in text.lower()
    assert "fabric" in text.lower()
    assert "#C4B5FD" in text
    assert "twist" in text.lower()


def test_two_piece_categories_still_tops_bottoms():
    prep = prepare_garment_reference(_two_piece_sketch())
    assert [p.category for p in prep.pieces] == ["tops", "bottoms"]
