"""Structural fidelity + one-piece category mapping (owner swimsuit→dress incident)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.fashn_garment_fidelity import (
    assert_structural_fidelity,
    compute_silhouette_features,
    recommend_fashn_category,
)
from app.services.fashn_garment_prep import prepare_garment_reference

_ARTIFACTS = Path("/tmp/fr161-owner-artifacts")


def _swimsuit_sketch_png() -> bytes:
    """Synthetic high-cut one-piece with crotch notch (transparent bg)."""
    img = Image.new("RGBA", (400, 700), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Asymmetric top + high-cut bottom (two leg lobes).
    draw.polygon(
        [
            (180, 40),
            (320, 20),
            (300, 120),
            (280, 280),
            (310, 420),
            (250, 520),
            (200, 620),
            (200, 560),
            (160, 620),
            (110, 520),
            (90, 420),
            (120, 280),
            (140, 120),
        ],
        fill=(14, 165, 233, 255),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dress_product_png() -> bytes:
    """Dress-like product: wide continuous hem, no crotch notch."""
    img = Image.new("RGB", (512, 768), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (220, 40),
            (300, 40),
            (340, 200),
            (360, 400),
            (400, 700),
            (120, 700),
            (160, 400),
            (180, 200),
        ],
        fill=(180, 40, 160),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_recommend_one_pieces_for_swimsuit_silhouette():
    feats = compute_silhouette_features(_swimsuit_sketch_png())
    assert feats.swimsuit_like is True
    assert feats.dress_like is False
    assert recommend_fashn_category(layout="one_piece", features=feats) == "one-pieces"


def test_prep_assigns_one_pieces_not_auto_for_one_piece_swimsuit():
    prep = prepare_garment_reference(_swimsuit_sketch_png())
    assert prep.layout == "one_piece"
    assert prep.pieces[0].category == "one-pieces"


def test_fidelity_blocks_swimsuit_to_dress():
    source = _swimsuit_sketch_png()
    product = _dress_product_png()
    verdict = assert_structural_fidelity(source_png=source, product_png=product, layout="one_piece")
    assert verdict.ok is False
    assert verdict.code == "FIDELITY_SWIMSUIT_BECAME_DRESS"


def test_fidelity_passes_matching_swimsuit_product():
    source = _swimsuit_sketch_png()
    # Product with same silhouette family (high-cut).
    img = Image.new("RGB", (512, 768), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (200, 60),
            (340, 40),
            (320, 140),
            (300, 300),
            (330, 450),
            (260, 560),
            (210, 660),
            (210, 600),
            (170, 660),
            (120, 560),
            (100, 450),
            (130, 300),
            (150, 140),
        ],
        fill=(14, 165, 233),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    product = buf.getvalue()
    verdict = assert_structural_fidelity(source_png=source, product_png=product, layout="one_piece")
    assert verdict.ok is True
    assert verdict.recommended_category == "one-pieces"


def test_owner_artifact_pipeline_category_and_fidelity():
    """Regression on the paid owner incident artifacts when present on disk."""
    sketch = _ARTIFACTS / "00_source_sketch.png"
    product = _ARTIFACTS / "02_approved_realistic_0_auto.png"
    final = _ARTIFACTS / "03_final_tryon.png"
    if not sketch.exists() or not product.exists():
        return
    prep = prepare_garment_reference(sketch.read_bytes())
    assert prep.pieces[0].category == "one-pieces"
    ok = assert_structural_fidelity(
        source_png=prep.pieces[0].png_bytes,
        product_png=product.read_bytes(),
        layout="one_piece",
    )
    assert ok.ok is True
    if final.exists():
        bad = assert_structural_fidelity(
            source_png=prep.pieces[0].png_bytes,
            product_png=final.read_bytes(),
            layout="one_piece",
        )
        assert bad.ok is False
        assert bad.code == "FIDELITY_SWIMSUIT_BECAME_DRESS"
