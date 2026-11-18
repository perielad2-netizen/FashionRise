"""Design palette extraction and deterministic color lock for Social look try-ons."""

from __future__ import annotations

import colorsys

from app.services.look_color_lock import (
    describe_color,
    extract_design_palette,
    lock_plate_to_palette,
    lock_result_to_palette,
    palette_prompt_clause,
    palette_summary,
)
from tests.look_test_images import (
    FOREST,
    GARMENT_BOTTOM,
    GARMENT_TOP,
    OLIVE,
    SHEER_LEG,
    SHEER_LEG_BOX,
    SKIN,
    SKY,
    look_plate_png,
    person_photo_png,
    pixel,
    product_photo_png,
    reframe_png,
    split_row,
    tryon_result_png,
)

# What generators typically hand back: bodice pushed toward green, skirt toward teal.
DRIFT_BODICE = (95, 150, 60)
DRIFT_SKIRT = (40, 110, 95)


def _hue(rgb: tuple[int, int, int]) -> float:
    return colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)[0] * 360.0


def _hue_gap(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    gap = abs(_hue(a) - _hue(b)) % 360.0
    return min(gap, 360.0 - gap)


def _garment_row(fraction: float) -> float:
    return GARMENT_TOP + (GARMENT_BOTTOM - GARMENT_TOP) * fraction


def test_drift_fixtures_are_visibly_off_design():
    assert _hue_gap(DRIFT_BODICE, OLIVE) > 25
    assert _hue_gap(DRIFT_SKIRT, FOREST) > 25
    assert _hue_gap(OLIVE, FOREST) > 50


def test_palette_measures_both_panels_of_a_two_tone_look():
    palette = extract_design_palette(look_plate_png())
    assert palette is not None
    assert palette["multi_tone"] is True
    top, bottom = palette["panels"][0], palette["panels"][-1]
    assert _hue_gap(tuple(top["rgb"]), OLIVE) < 6
    assert _hue_gap(tuple(bottom["rgb"]), FOREST) < 6
    assert "olive" in top["name"]
    assert "forest" in bottom["name"]
    clause = palette_prompt_clause(palette)
    assert "COLOR LOCK" in clause
    assert top["hex"] in clause and bottom["hex"] in clause
    assert len(clause) < 260


def test_palette_single_tone_look_has_one_panel():
    palette = extract_design_palette(look_plate_png(bodice=FOREST, skirt=FOREST))
    assert palette is not None
    assert palette["multi_tone"] is False
    assert len(palette["panels"]) == 1
    assert "garment color is" in palette_prompt_clause(palette)


def test_palette_is_none_for_achromatic_or_nude_garments():
    # Honest scope: white / grey / skin-toned dresses cannot be told from paper or skin.
    assert extract_design_palette(look_plate_png(bodice=(250, 250, 250), skirt=(238, 238, 238))) is None
    assert extract_design_palette(look_plate_png(bodice=SKIN, skirt=SKIN)) is None
    assert palette_prompt_clause(None) == ""
    assert palette_summary(None) is None


def test_describe_color_names_are_plain_language():
    assert "olive" in describe_color(OLIVE)
    assert "forest green" in describe_color(FOREST)
    assert describe_color((250, 250, 250)) == "white"
    assert "navy" in describe_color((30, 40, 90))


def test_product_lock_pulls_drifted_plate_back_to_design():
    palette = extract_design_palette(look_plate_png())
    drifted = product_photo_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT)
    locked, meta = lock_plate_to_palette(drifted, palette)
    assert meta["applied"] is True
    assert meta["chroma_drift_after"] < meta["chroma_drift_before"] * 0.35
    bodice_px = pixel(locked, 0.5, _garment_row(0.1))
    skirt_px = pixel(locked, 0.5, _garment_row(0.7))
    assert _hue_gap(bodice_px, OLIVE) < 8
    assert _hue_gap(skirt_px, FOREST) < 8
    # Backdrop and mannequin are neutral — never tinted.
    assert pixel(locked, 0.05, 0.5) == pixel(drifted, 0.05, 0.5)
    assert pixel(locked, 0.5, 0.07) == pixel(drifted, 0.5, 0.07)


def test_product_lock_leaves_faithful_plate_untouched():
    palette = extract_design_palette(look_plate_png())
    faithful = product_photo_png()
    locked, meta = lock_plate_to_palette(faithful, palette)
    assert meta["applied"] is False
    assert meta["reason"] == "within_tolerance"
    assert locked is faithful


def test_result_lock_recolors_only_the_fitted_garment():
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png()
    result = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT)
    locked, meta = lock_result_to_palette(result, person, palette)
    assert meta["applied"] is True
    assert meta["alignment"] == "boundary"
    assert meta["chroma_drift_after"] < meta["chroma_drift_before"] * 0.5
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.1)), OLIVE) < 10
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.7)), FOREST) < 10
    # Sky, ground, face and legs are byte-identical.
    for fx, fy in ((0.08, 0.1), (0.9, 0.9), (0.5, 0.07), (0.45, 0.85)):
        assert pixel(locked, fx, fy) == pixel(result, fx, fy)
    assert pixel(locked, 0.08, 0.1) == SKY
    assert pixel(locked, 0.5, 0.07) == SKIN


def test_result_lock_aligns_panel_boundary_on_different_proportions():
    """A longer torso must not get the skirt color smeared into the bodice."""
    palette = extract_design_palette(look_plate_png(split=0.26))
    person = person_photo_png()
    result = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, split=0.5)
    locked, meta = lock_result_to_palette(result, person, palette)
    assert meta["applied"] is True
    assert meta["alignment"] == "boundary"
    # 40% down the garment is bodice on this person but skirt on the design figure.
    low_bodice = pixel(locked, 0.5, _garment_row(0.4))
    assert _hue_gap(low_bodice, OLIVE) < 12
    assert _hue_gap(low_bodice, FOREST) > 30
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.8)), FOREST) < 12
    assert split_row(0.5) > split_row(0.26)


def test_result_lock_skips_inventing_panel_when_max_collapsed_two_tone():
    """When Max merges panels, do not invent a painted seam — leave the one real color."""
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png()
    collapsed = tryon_result_png(bodice=FOREST, skirt=FOREST)
    locked, meta = lock_result_to_palette(collapsed, person, palette)
    assert meta.get("applied") is False
    # Either within tolerance or explicitly refused to invent a panel boundary.
    assert meta.get("reason") in {"within_tolerance", "panel_boundary_missing"}
    assert locked == collapsed


def test_result_lock_keeps_upper_panel_when_only_bodice_is_visible():
    """Waist-up photo (garment cut off by the frame): do not invent the skirt color."""
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png(keep_height=0.24)
    bodice_only = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, keep_height=0.24)
    locked, meta = lock_result_to_palette(bodice_only, person, palette)
    assert meta["applied"] is True
    assert meta["alignment"] == "upper_panel"
    for fy in (0.7, 0.95):
        visible = pixel(locked, 0.5, fy)
        assert _hue_gap(visible, OLIVE) < 12
        assert _hue_gap(visible, FOREST) > 30


def test_result_lock_registers_a_reframed_result():
    """FASHN Max answers in its own aspect bucket with the scene a few percent off.

    Production case: 1616x2512 person photo -> 1696x2528 result. A plain per-pixel
    comparison against a busy background then reads as "different scene" and the
    lock used to skip itself on every real photo.
    """
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png(textured=True)
    fitted = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, textured=True)
    result = reframe_png(fitted, size=(416, 600), scale=(1.03, 1.0), shift=(0.015, -0.0075))

    locked, meta = lock_result_to_palette(result, person, palette)

    assert meta["aspect_gap"] > 0.03
    registration = meta["registration"]
    assert registration["registered"] is True
    assert registration["mismatch_after"] < registration["mismatch_before"] * 0.5
    sx, sy, tx, ty = registration["frame"]
    assert abs(sx - 1.03) <= 0.011 and abs(sy - 1.0) <= 0.011
    assert abs(tx - 0.015) <= 0.008 and abs(ty + 0.0075) <= 0.008
    assert meta["median_diff"] <= 4
    assert meta["applied"] is True
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.1)), OLIVE) < 10
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.7)), FOREST) < 10
    # The busy background is never recolored.
    for fx, fy in ((0.06, 0.08), (0.92, 0.3), (0.1, 0.9), (0.9, 0.95)):
        assert pixel(locked, fx, fy) == pixel(result, fx, fy)


def test_result_lock_spares_skin_showing_through_sheer_fabric():
    """A leg behind sheer tulle is not fabric: grading it turned legs mustard-green."""
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png()
    result = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, sheer_leg=SHEER_LEG)
    leg_x = (SHEER_LEG_BOX[0] + SHEER_LEG_BOX[2]) / 2.0
    leg_y = (SHEER_LEG_BOX[1] + SHEER_LEG_BOX[3]) / 2.0
    assert pixel(result, leg_x, leg_y) == SHEER_LEG

    locked, meta = lock_result_to_palette(result, person, palette)

    assert meta["applied"] is True
    assert pixel(locked, leg_x, leg_y) == SHEER_LEG
    # Fabric right beside the leg is still pulled to the design color.
    assert _hue_gap(pixel(locked, 0.34, leg_y), FOREST) < 10
    assert _hue_gap(pixel(locked, 0.66, leg_y), FOREST) < 10
    assert _hue_gap(pixel(locked, 0.5, _garment_row(0.1)), OLIVE) < 10


def test_result_lock_is_fail_safe():
    palette = extract_design_palette(look_plate_png())
    person = person_photo_png()
    result = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT)

    same, meta = lock_result_to_palette(result, person, None)
    assert same is result and meta["reason"] == "no_palette"

    wide = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, size=(600, 600))
    same, meta = lock_result_to_palette(wide, person, palette)
    assert same is wide and meta["reason"] == "aspect_mismatch"

    # A different scene does not overlay the person photo — nothing to localize.
    other_scene = product_photo_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT, size=(400, 600))
    same, meta = lock_result_to_palette(other_scene, person, palette)
    assert same is other_scene and meta["reason"] == "misaligned"

    same, meta = lock_result_to_palette(person, person, palette)
    assert same is person and meta["applied"] is False

    same, meta = lock_result_to_palette(b"not a png", person, palette)
    assert same == b"not a png" and meta["reason"] == "undecodable"
