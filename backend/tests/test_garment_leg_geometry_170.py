"""#170 — trouser/jumpsuit geometry, FASHN fail-closed, OpenAI hint + soft review."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.fashn_garment_prep import prepare_garment_reference
from app.services.garment_leg_geometry import (
    analyze_lower_garment_geometry,
    openai_trouser_design_hints,
    soft_try_on_structure_review,
)
from app.services.personal_try_on_provider import (
    TRY_ON_PROMPT_VERSION,
    build_try_on_prompt,
)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _transparent(w: int = 256, h: int = 512) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _narrow_jumpsuit_png() -> bytes:
    """Deep-V bodice + two narrow trouser legs (owner green case geometry)."""
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    green = (22, 101, 52, 255)
    # Bodice / torso
    draw.polygon([(110, 40), (170, 40), (190, 200), (90, 200)], fill=green)
    # Left leg
    draw.rectangle([95, 200, 125, 520], fill=green)
    # Right leg (clear gap)
    draw.rectangle([155, 200, 185, 520], fill=green)
    return _png(img)


def _wide_trousers_png() -> bytes:
    img = _transparent(300, 520)
    draw = ImageDraw.Draw(img)
    c = (40, 40, 120, 255)
    draw.rectangle([90, 60, 210, 180], fill=c)  # top
    draw.polygon([(70, 180), (140, 180), (120, 500), (40, 500)], fill=c)
    draw.polygon([(160, 180), (230, 180), (260, 500), (180, 500)], fill=c)
    return _png(img)


def _dress_with_slit_png() -> bytes:
    """Continuous skirt with a hem slit — must NOT count as trousers."""
    img = _transparent(260, 520)
    draw = ImageDraw.Draw(img)
    c = (180, 40, 80, 255)
    draw.rectangle([90, 40, 170, 160], fill=c)
    # Wide continuous skirt; slit only near hem
    for y in range(160, 480):
        # full width until last 40px where a center gap appears
        if y < 440:
            draw.rectangle([60, y, 200, y], fill=c)
        else:
            draw.rectangle([60, y, 115, y], fill=c)
            draw.rectangle([145, y, 200, y], fill=c)
    return _png(img)


def _high_slit_dress_png() -> bytes:
    """Thigh-high fashion slit (owner green dress case) — must NOT be jumpsuit hints."""
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    green = (22, 101, 52, 255)
    draw.polygon([(120, 50), (160, 50), (190, 180), (90, 180)], fill=green)
    for y in range(180, 520):
        if y < 250:
            # Connected hip / upper skirt
            draw.rectangle([70, y, 210, y], fill=green)
        else:
            # Main dress panel + thinner hanging edge beside the slit
            draw.rectangle([70, y, 155, y], fill=green)
            draw.rectangle([175, y, 205, y], fill=green)
    return _png(img)


def _swimsuit_png() -> bytes:
    img = _transparent(220, 420)
    draw = ImageDraw.Draw(img)
    c = (20, 120, 160, 255)
    # High-cut one-piece triangle-ish
    draw.polygon([(110, 50), (150, 50), (180, 220), (160, 300), (60, 300), (40, 220)], fill=c)
    return _png(img)


def _top_shorts_png() -> bytes:
    img = _transparent(240, 440)
    draw = ImageDraw.Draw(img)
    draw.rectangle([70, 40, 170, 140], fill=(200, 80, 40, 255))
    draw.rectangle([80, 220, 160, 300], fill=(40, 40, 40, 255))
    return _png(img)


def _ambiguous_lower_png() -> bytes:
    img = _transparent(200, 400)
    draw = ImageDraw.Draw(img)
    # Single blob mid-body — no clear legs
    draw.ellipse([60, 120, 140, 260], fill=(90, 90, 90, 255))
    return _png(img)


def test_narrow_jumpsuit_detected():
    geo = analyze_lower_garment_geometry(_narrow_jumpsuit_png())
    assert geo.looks_like_trousers is True
    assert geo.looks_like_jumpsuit is True
    assert geo.looks_like_narrow_legs is True
    hints = openai_trouser_design_hints(geo)
    assert any("jumpsuit" in h.lower() for h in hints)
    assert any("not a dress" in h.lower() for h in hints)
    assert any("flare" in h.lower() or "narrow" in h.lower() for h in hints)


def test_wide_trousers_detected():
    geo = analyze_lower_garment_geometry(_wide_trousers_png())
    assert geo.looks_like_trousers is True
    assert geo.looks_like_wide_legs is True


def test_dress_slit_not_trousers():
    geo = analyze_lower_garment_geometry(_dress_with_slit_png())
    assert geo.looks_like_trousers is False
    assert geo.looks_like_high_slit_dress is False
    assert openai_trouser_design_hints(geo) == []


def test_high_slit_dress_not_jumpsuit_hints():
    """#174 — thigh-high slit must not inject 'jumpsuit — not a dress'."""
    geo = analyze_lower_garment_geometry(_high_slit_dress_png())
    assert geo.looks_like_trousers is False
    assert geo.looks_like_jumpsuit is False
    assert geo.looks_like_high_slit_dress is True
    hints = openai_trouser_design_hints(geo)
    assert hints
    assert any("slit" in h.lower() for h in hints)
    assert any("dress" in h.lower() for h in hints)
    assert not any("not a dress" in h.lower() for h in hints)
    assert not any("jumpsuit with trousers" in h.lower() for h in hints)
    prompt = build_try_on_prompt(hints)
    assert "slit" in prompt.lower()
    assert "jumpsuit" in prompt.lower()  # "not … a jumpsuit"


def test_swimsuit_not_trousers():
    geo = analyze_lower_garment_geometry(_swimsuit_png())
    assert geo.looks_like_trousers is False


def test_top_shorts_two_piece_still_preps():
    prep = prepare_garment_reference(_top_shorts_png())
    assert prep.layout == "two_piece"
    assert prep.quality_ok is True
    assert [p.category for p in prep.pieces] == ["tops", "bottoms"]


def test_bikini_two_piece_unchanged():
    img = _transparent(220, 440)
    draw = ImageDraw.Draw(img)
    draw.rectangle([70, 40, 150, 100], fill=(160, 40, 200, 255))
    draw.rectangle([75, 240, 145, 310], fill=(160, 40, 200, 255))
    prep = prepare_garment_reference(_png(img))
    assert prep.layout == "two_piece"
    assert prep.quality_ok is True


def test_jumpsuit_fashn_prep_fail_closed():
    prep = prepare_garment_reference(_narrow_jumpsuit_png())
    assert prep.quality_ok is False
    assert "jumpsuit" in prep.quality_notes.lower() or "trousers" in prep.quality_notes.lower()
    assert "swimsuit" in prep.quality_notes.lower() or "FASHN" in prep.quality_notes
    # Must not silently ship as one-pieces swimsuit category for paid realism.
    public = prep.public_dict(cents_per_call=8)
    assert public["quality_ok"] is False


def test_swimsuit_one_piece_still_ok():
    prep = prepare_garment_reference(_swimsuit_png())
    assert prep.layout == "one_piece"
    assert prep.pieces[0].category == "one-pieces"
    assert prep.quality_ok is True


def test_discarded_leg_component_fails_completeness():
    """Completeness gate rejects when substantial opaque mass was dropped."""
    from app.services.fashn_garment_prep import PreparedPiece, _completeness_gate

    piece = PreparedPiece(
        category="one-pieces",
        png_bytes=_swimsuit_png(),
        bbox=(100, 40, 180, 220),
        opaque_pixels=8000,
        fill_ratio=0.9,
        edge_ratio=0.2,
    )
    ok, note = _completeness_gate(
        source_opaque=20000,
        source_bbox=(90, 40, 190, 520),
        source_h=560,
        pieces=[piece],
        discarded_opaque=9000,
    )
    assert ok is False
    assert "dropped substantial" in note.lower() or "opaque pixels" in note.lower()


def test_openai_v2_prompt_unchanged_without_hints():
    prompt = build_try_on_prompt(None)
    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.1"
    # Base V2 text present; no trouser appendix when hints empty.
    assert "Studio design evidence" not in prompt
    with_hints = build_try_on_prompt(openai_trouser_design_hints(analyze_lower_garment_geometry(_narrow_jumpsuit_png())))
    assert with_hints.startswith(prompt)
    assert "jumpsuit" in with_hints.lower()
    assert "Studio design evidence" in with_hints


def test_soft_review_flags_merged_legs():
    src = _narrow_jumpsuit_png()
    # Result: continuous skirt panel (merged legs)
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    draw.rectangle([90, 40, 190, 520], fill=(22, 101, 52, 255))
    review = soft_try_on_structure_review(source_png=src, result_png=_png(img))
    assert review["state"] == "failed"
    assert review["faithful"] is False
    assert "STRUCTURE_LEGS_MERGED_OR_LOST" == review["code"]


def test_soft_review_not_applicable_for_ambiguous_source():
    """#171 — non-trouser sources skip the check without downgrading ordinary Try On."""
    review = soft_try_on_structure_review(
        source_png=_ambiguous_lower_png(),
        result_png=_ambiguous_lower_png(),
    )
    assert review["state"] == "not_applicable"
    assert review["faithful"] is None


def test_nginx_accept_matrix_includes_post_accept():
    """Regression for owner Accept 403 — verifier matrix must allow POST accept."""
    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_ai_allowlist.py"
    proc = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "allow_regex_fashn_garment_realism_accept" in proc.stdout
