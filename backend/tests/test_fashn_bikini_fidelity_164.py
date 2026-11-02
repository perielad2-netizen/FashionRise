"""#164 — purple two-piece bikini fidelity (offline; no paid OpenAI/FASHN).

Owner incident on App a3ca2221: OpenAI realism restyled a deep-V bikini top into a
twisted wrap and altered bottoms/gradient. Dense filled plates must prefer local
productization; fidelity must reject invented asymmetry / color drift / unrelated
garments.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.fashn_garment_fidelity import assert_structural_fidelity
from app.services.fashn_garment_prep import prepare_garment_reference
from app.services.fashn_garment_realism import (
    GARMENT_REALISM_PROMPT_VERSION,
    LOCAL_PRODUCT_PROVIDER_ID,
    dominant_color_hint,
    garment_realism_prompt,
    productize_filled_plate,
)

_ARTIFACTS = Path("/tmp/fr164-bikini-artifacts")


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _purple_bikini_sketch() -> bytes:
    """Synthetic deep-V two-piece with purple gradient (transparent canvas)."""
    img = Image.new("RGBA", (400, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Deep-V structured top (symmetric cups, open neckline).
    draw.polygon(
        [
            (140, 90),
            (200, 160),  # deep V point
            (260, 90),
            (300, 130),
            (280, 220),
            (220, 210),
            (200, 175),
            (180, 210),
            (120, 220),
            (100, 130),
        ],
        fill=(196, 181, 253, 255),  # #C4B5FD light purple
    )
    # Darker purple toward lower cups (gradient placement).
    draw.polygon(
        [
            (130, 180),
            (200, 175),
            (270, 180),
            (275, 215),
            (200, 205),
            (125, 215),
        ],
        fill=(76, 29, 149, 255),  # #4C1D95
    )
    # Bottoms — mid waist, moderate coverage.
    draw.polygon(
        [
            (130, 360),
            (270, 360),
            (290, 420),
            (270, 500),
            (200, 470),
            (130, 500),
            (110, 420),
        ],
        fill=(46, 16, 101, 255),  # #2E1065
    )
    return _png(img)


def _twisted_top_product() -> bytes:
    """Asymmetric twisted/wrapped top — the #164 restyle failure mode."""
    img = Image.new("RGB", (512, 768), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    # Diagonal wrap — heavily left-heavy asymmetry.
    draw.polygon(
        [
            (80, 80),
            (420, 40),
            (400, 160),
            (220, 280),
            (100, 220),
        ],
        fill=(180, 100, 220),
    )
    draw.polygon(
        [
            (300, 100),
            (450, 180),
            (380, 320),
            (200, 260),
        ],
        fill=(90, 30, 140),
    )
    return _png(img)


def _unrelated_dress_product() -> bytes:
    img = Image.new("RGB", (512, 768), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (220, 40),
            (300, 40),
            (360, 300),
            (400, 720),
            (120, 720),
            (160, 300),
        ],
        fill=(40, 180, 80),  # unrelated green dress
    )
    return _png(img)


def test_two_piece_bikini_requires_openai_realism_and_keeps_categories():
    prep = prepare_garment_reference(_purple_bikini_sketch())
    assert prep.layout == "two_piece"
    assert [p.category for p in prep.pieces] == ["tops", "bottoms"]
    assert prep.quality_ok is True
    # #166 — local plate skip disabled; OpenAI realism is required before FASHN.
    assert prep.prefer_local_product() is False
    public = prep.public_dict(cents_per_call=8, realism_cents_per_piece=8)
    assert public["prefer_local_product"] is False
    assert public["realism_estimate_cents"] == 16
    assert public["realism_calls"] == 2
    assert public["estimate_cents"] == 16
    assert public["combined_estimate_cents"] == 32
    assert "never sent to FASHN" in public["notes"]


def test_bikini_top_neckline_preserved_by_local_productize():
    prep = prepare_garment_reference(_purple_bikini_sketch())
    top = prep.pieces[0]
    assert top.category == "tops"
    product, meta = productize_filled_plate(top.png_bytes)
    assert meta["provider"] == LOCAL_PRODUCT_PROVIDER_ID
    assert meta["local_product"] is True
    # Local productize must not invent a new silhouette — fidelity vs plate must pass.
    verdict = assert_structural_fidelity(
        source_png=top.png_bytes,
        product_png=product,
        layout="two_piece",
    )
    assert verdict.ok is True
    # Plate and product share purple tones (gradient retention).
    hint = dominant_color_hint(top.png_bytes)
    assert hint
    assert any(tok.startswith("#") for tok in hint.split(", "))


def test_bikini_bottom_coverage_preserved_by_local_productize():
    prep = prepare_garment_reference(_purple_bikini_sketch())
    bottom = prep.pieces[1]
    assert bottom.category == "bottoms"
    product, _meta = productize_filled_plate(bottom.png_bytes)
    verdict = assert_structural_fidelity(
        source_png=bottom.png_bytes,
        product_png=product,
        layout="two_piece",
    )
    assert verdict.ok is True


def test_fidelity_rejects_twisted_asymmetric_top_restyle():
    prep = prepare_garment_reference(_purple_bikini_sketch())
    top = prep.pieces[0].png_bytes
    twisted = _twisted_top_product()
    verdict = assert_structural_fidelity(
        source_png=top,
        product_png=twisted,
        layout="two_piece",
    )
    assert verdict.ok is False
    assert verdict.code in {
        "FIDELITY_NECKLINE_CHANGED",
        "FIDELITY_ASYMMETRY_INVENTED",
        "FIDELITY_COLOR_DRIFT",
    }


def test_fidelity_rejects_unrelated_clothing_conversion():
    prep = prepare_garment_reference(_purple_bikini_sketch())
    # Compare full sketch mass against a long green dress product using one-piece layout.
    one_piece_like = prepare_garment_reference(_purple_bikini_sketch())
    # Force a one-piece silhouette source for dress conversion check.
    source = one_piece_like.pieces[0].png_bytes
    verdict = assert_structural_fidelity(
        source_png=source,
        product_png=_unrelated_dress_product(),
        layout="one_piece",
    )
    # Dress conversion or color drift — either blocks FASHN.
    assert verdict.ok is False
    assert verdict.code in {
        "FIDELITY_SWIMSUIT_BECAME_DRESS",
        "FIDELITY_COLOR_DRIFT",
        "FIDELITY_SILHOUETTE_STRETCH",
        "FIDELITY_LEG_OPENINGS_LOST",
        "FIDELITY_ASYMMETRY_INVENTED",
    }


def test_realism_prompt_v5_reuses_fm_coverage_not_illustration_style():
    assert GARMENT_REALISM_PROMPT_VERSION == "fashn-garment-realism-v5"
    tops = garment_realism_prompt(category="tops", color_hint="#C4B5FD, #2E1065")
    assert "twists" in tops.lower() or "twist" in tops.lower()
    assert "deep-V" in tops or "neckline" in tops.lower()
    assert "#C4B5FD" in tops
    assert "fabric" in tops.lower()
    assert "COVERAGE FIDELITY" in tops
    assert "COLOR FIDELITY" in tops
    assert "exposed midriff" in tops.lower() or "midriff" in tops.lower()
    # Must stay photoreal product — never Fashion Magic illustration style.
    assert "Avoid photorealism" not in tops
    assert "non-photorealistic fashion illustration" not in tops.lower()
    bottoms = garment_realism_prompt(category="bottoms")
    assert "waistline" in bottoms.lower()
    assert "coverage" in bottoms.lower()


def test_owner_artifact_openai_restyle_still_fails_neckline_gate():
    """When owner #164 artifacts are present: twisted OpenAI product fails neckline fidelity."""
    sketch = _ARTIFACTS / "00_source_sketch.png"
    plate_top = _ARTIFACTS / "01_plate_0_tops.png"
    openai_top = _ARTIFACTS / "02_approved_0_tops.png"
    if not sketch.exists() or not plate_top.exists() or not openai_top.exists():
        return
    prep = prepare_garment_reference(sketch.read_bytes())
    assert prep.layout == "two_piece"
    assert prep.prefer_local_product() is False
    openai_verdict = assert_structural_fidelity(
        source_png=plate_top.read_bytes(),
        product_png=openai_top.read_bytes(),
        layout="two_piece",
    )
    assert openai_verdict.ok is False
    assert openai_verdict.code == "FIDELITY_NECKLINE_CHANGED"


def _soft_edge_product_from_plate(plate_png: bytes) -> bytes:
    """Mild soft-edge productization that keeps the deep open V (5842e98b-class).

    Tip growth ~2–3× from soft edges — must pass calibrated neckline gate (#167).
    Known wrap redesign (#164) sits nearer tip ≥0.22 with growth ≥4.5.
    """
    from PIL import ImageFilter

    im = Image.open(io.BytesIO(plate_png)).convert("RGBA")
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    px = rgb.load()
    ap = im.split()[-1].load()
    assert mp is not None and px is not None and ap is not None
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if ap[x, y] < 20:
                continue
            if r >= 230 and g >= 230 and b >= 230:
                continue
            if r < 40 and g < 40 and b < 40:
                continue
            mp[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(radius=1.5))
    out = Image.new("RGB", (w, h), (250, 250, 250))
    op = out.load()
    mp = mask.load()
    assert op is not None and mp is not None
    for y in range(h):
        for x in range(w):
            m = mp[x, y]
            if m < 40:
                continue
            r, g, b = px[x, y]
            if r >= 230 and g >= 230 and b >= 230 or r < 40 and g < 40 and b < 40:
                r, g, b = (160, 120, 210)
            t = m / 255.0
            op[x, y] = (
                int(r * t + 250 * (1 - t)),
                int(g * t + 250 * (1 - t)),
                int(b * t + 250 * (1 - t)),
            )
    return _png(out)


def test_soft_edge_deep_v_photoreal_passes_calibrated_neckline_gate():
    plate_path = _ARTIFACTS / "01_plate_0_tops.png"
    if plate_path.exists():
        top = plate_path.read_bytes()
    else:
        top = prepare_garment_reference(_purple_bikini_sketch()).pieces[0].png_bytes
    soft = _soft_edge_product_from_plate(top)
    verdict = assert_structural_fidelity(
        source_png=top,
        product_png=soft,
        layout="two_piece",
    )
    assert verdict.code != "FIDELITY_NECKLINE_CHANGED"
    assert verdict.ok is True
