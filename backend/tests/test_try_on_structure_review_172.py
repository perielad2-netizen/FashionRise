"""#172 — provenance gate: OpenAI try-on photos never enter plate comparison via pixels."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.garment_leg_geometry import (
    RESULT_KIND_ISOLATED_GARMENT_PLATE,
    RESULT_KIND_OPENAI_TRY_ON_PHOTO,
    SOURCE_KIND_ISOLATED_GARMENT_PLATE,
    analyze_lower_garment_geometry,
    classify_structure_image_role,
    merge_openai_design_hints,
    openai_trouser_design_hints,
    soft_try_on_structure_review,
)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _transparent(w: int = 256, h: int = 512) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _narrow_jumpsuit_png() -> bytes:
    """Existing green-jumpsuit source geometry (#170/#171)."""
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    green = (22, 101, 52, 255)
    draw.polygon([(110, 40), (170, 40), (190, 200), (90, 200)], fill=green)
    draw.rectangle([95, 200, 125, 520], fill=green)
    draw.rectangle([155, 200, 185, 520], fill=green)
    return _png(img)


def _top_shorts_png() -> bytes:
    img = _transparent(240, 440)
    draw = ImageDraw.Draw(img)
    draw.rectangle([70, 40, 170, 140], fill=(200, 80, 40, 255))
    draw.rectangle([80, 220, 160, 300], fill=(40, 40, 40, 255))
    return _png(img)


def _merged_isolated_plate_png() -> bytes:
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    draw.rectangle([90, 40, 190, 520], fill=(22, 101, 52, 255))
    return _png(img)


def _white_bg_full_body_png(*, skin: tuple[int, int, int], garment: tuple[int, int, int]) -> bytes:
    """Full-body photograph on mostly white background — pixel heuristics may say plate."""
    img = Image.new("RGB", (384, 640), (252, 252, 252))
    draw = ImageDraw.Draw(img)
    draw.ellipse([170, 40, 220, 95], fill=skin)
    draw.polygon([(145, 95), (245, 95), (265, 330), (125, 330)], fill=garment)
    draw.rectangle([150, 330, 185, 610], fill=garment)
    draw.rectangle([205, 330, 240, 610], fill=garment)
    draw.rectangle([118, 180, 140, 320], fill=skin)
    draw.rectangle([250, 180, 272, 320], fill=skin)
    return _png(img.convert("RGBA"))


def _full_coverage_jumpsuit_minimal_skin_png() -> bytes:
    """Nearly full-coverage jumpsuit, tiny face — looks like isolated plate to heuristics."""
    img = Image.new("RGB", (384, 640), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.ellipse([175, 35, 215, 80], fill=(80, 55, 40))
    # Continuous dark-green panel (merged legs) covering torso+legs.
    draw.rectangle([130, 80, 260, 620], fill=(10, 80, 40))
    return _png(img.convert("RGBA"))


def _dark_clothing_varied_skin_png() -> bytes:
    img = Image.new("RGB", (384, 640), (248, 248, 248))
    draw = ImageDraw.Draw(img)
    # Deep skin tone + near-black clothing.
    draw.ellipse([170, 45, 220, 100], fill=(45, 28, 20))
    draw.polygon([(140, 100), (250, 100), (270, 340), (120, 340)], fill=(12, 12, 16))
    draw.rectangle([145, 340, 185, 610], fill=(12, 12, 16))
    draw.rectangle([205, 340, 245, 610], fill=(12, 12, 16))
    draw.rectangle([115, 200, 138, 280], fill=(45, 28, 20))
    draw.rectangle([252, 200, 275, 280], fill=(45, 28, 20))
    return _png(img.convert("RGBA"))


def test_pixel_heuristics_still_mislabel_white_bg_person_photos():
    """Documents the #172 risk: heuristics alone can call person photos isolated plates."""
    white_bg = _white_bg_full_body_png(skin=(210, 160, 130), garment=(22, 101, 52))
    dark = _dark_clothing_varied_skin_png()
    full = _full_coverage_jumpsuit_minimal_skin_png()
    # At least one of these adversarial fixtures must be mislabeled without provenance.
    roles = {
        classify_structure_image_role(white_bg),
        classify_structure_image_role(dark),
        classify_structure_image_role(full),
    }
    assert "isolated_garment" in roles


def test_openai_photo_provenance_blocks_false_failure_on_white_bg():
    src = _narrow_jumpsuit_png()
    photo = _full_coverage_jumpsuit_minimal_skin_png()
    assert classify_structure_image_role(photo) == "isolated_garment"
    # Without provenance this would false-fail STRUCTURE_LEGS_MERGED_OR_LOST.
    naive = soft_try_on_structure_review(source_png=src, result_png=photo)
    assert naive["state"] == "failed"

    review = soft_try_on_structure_review(
        source_png=src,
        result_png=photo,
        result_kind=RESULT_KIND_OPENAI_TRY_ON_PHOTO,
    )
    assert review["version"] == "try-on-structure-review-v3"
    assert review["state"] == "inconclusive"
    assert review["code"] == "STRUCTURE_INCOMPARABLE_RESULT"
    assert review["faithful"] is None
    assert review["result_kind"] == RESULT_KIND_OPENAI_TRY_ON_PHOTO
    assert review["result_role"] == "full_scene"
    assert review["result"] is None
    assert "pass/fail" in review["message"].lower() or "isolation" in review["message"].lower()


def test_openai_photo_dark_clothing_not_soft_pass_or_fail():
    src = _narrow_jumpsuit_png()
    photo = _dark_clothing_varied_skin_png()
    review = soft_try_on_structure_review(
        source_png=src,
        result_png=photo,
        result_kind=RESULT_KIND_OPENAI_TRY_ON_PHOTO,
    )
    assert review["state"] == "inconclusive"
    assert review["faithful"] is None
    assert review["state"] != "passed_soft"
    assert review["state"] != "failed"


def test_openai_photo_non_trouser_source_not_applicable():
    review = soft_try_on_structure_review(
        source_png=_top_shorts_png(),
        result_png=_white_bg_full_body_png(skin=(180, 120, 90), garment=(40, 40, 40)),
        result_kind=RESULT_KIND_OPENAI_TRY_ON_PHOTO,
    )
    assert review["state"] == "not_applicable"
    assert review["code"] == "STRUCTURE_CHECK_NOT_APPLICABLE"
    assert review["faithful"] is None


def test_trusted_isolated_plate_mismatch_still_fails():
    review = soft_try_on_structure_review(
        source_png=_narrow_jumpsuit_png(),
        result_png=_merged_isolated_plate_png(),
        result_kind=RESULT_KIND_ISOLATED_GARMENT_PLATE,
        source_kind=SOURCE_KIND_ISOLATED_GARMENT_PLATE,
    )
    assert review["state"] == "failed"
    assert review["faithful"] is False
    assert review["code"] == "STRUCTURE_LEGS_MERGED_OR_LOST"


def test_green_jumpsuit_source_geometry_preserved():
    geo = analyze_lower_garment_geometry(_narrow_jumpsuit_png())
    assert geo.looks_like_trousers is True
    hints = openai_trouser_design_hints(geo)
    assert any("jumpsuit" in h.lower() or "trousers" in h.lower() for h in hints)


def test_geometry_hints_win_eight_hint_budget():
    studio = [f"solid fill color #{i:06X}" for i in range(8)]
    geo = [
        "garment type: one-piece jumpsuit with trousers — not a dress, skirt, or swimsuit",
        "keep both leg openings separate; preserve each hem position from image 2",
        "preserve narrow leg width — do not flare, widen, or lengthen the legs",
        "do not connect the legs into a continuous skirt panel",
    ]
    merged = merge_openai_design_hints(studio, geo, max_hints=8)
    assert len(merged) <= 8
    assert all(h in merged for h in geo)
    assert any("jumpsuit" in h.lower() for h in merged)
    # Lower-priority color hints fill remaining slots only.
    assert sum(1 for h in merged if h.startswith("solid fill")) == 4
