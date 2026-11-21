"""Identity lock: face/hair pixel composite + gate (no live OpenAI)."""

from __future__ import annotations

from tests.look_test_images import (
    FLORAL_BLUE,
    FLORAL_PINK,
    floral_blue_tryon_good_png,
    person_photo_png,
    tryon_result_png,
    wings_outdoor_person_png,
)


def test_composite_restores_face_when_model_rewrote_it():
    from app.services.look_identity_lock import (
        composite_identity_from_person,
        validate_identity_lock,
    )

    person = wings_outdoor_person_png()
    # Simulate identity drift: different face/skin tone on same scene garment.
    drifted = tryon_result_png(
        bodice=FLORAL_BLUE,
        skirt=FLORAL_PINK,
        size=(400, 600),
        textured=True,
    )
    # Paint a fake "new face" blob in the head region.
    from io import BytesIO

    from PIL import Image, ImageDraw

    with Image.open(BytesIO(drifted)) as im:
        rgb = im.convert("RGB")
        draw = ImageDraw.Draw(rgb)
        draw.ellipse((150, 20, 250, 120), fill=(255, 220, 200))  # smoothed AI face
        buf = BytesIO()
        rgb.save(buf, format="PNG")
        drifted = buf.getvalue()

    locked, meta = composite_identity_from_person(drifted, person)
    assert meta["applied"] is True
    assert meta["face_luma_mad_after"] <= meta["face_luma_mad_before"]
    gate = validate_identity_lock(locked, person, composite_meta=meta)
    assert gate["ok"] is True
    assert gate["face_luma_mad"] <= gate["threshold"]


def test_validate_rejects_uncomposited_face_swap():
    from app.services.look_identity_lock import validate_identity_lock

    person = person_photo_png(size=(400, 600))
    # Completely different result frame (wrong person stand-in).
    other = floral_blue_tryon_good_png(size=(400, 600))
    from io import BytesIO

    from PIL import Image, ImageDraw

    with Image.open(BytesIO(other)) as im:
        rgb = im.convert("RGB")
        draw = ImageDraw.Draw(rgb)
        # Obliterate head region with solid color — face MAD will be huge.
        draw.rectangle((120, 10, 280, 180), fill=(10, 10, 10))
        buf = BytesIO()
        rgb.save(buf, format="PNG")
        other = buf.getvalue()

    gate = validate_identity_lock(other, person)
    assert gate["ok"] is False
    assert gate["reason"] in {"face_pixels_differ", "unaligned_high_face_delta"}


def test_protect_mask_covers_upper_face_not_skirt():
    from app.services.look_identity_lock import build_face_hair_protect_mask

    person = wings_outdoor_person_png()
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(person)) as im:
        rgb = im.convert("RGB")
    mask = build_face_hair_protect_mask(rgb)
    w, h = mask.size
    # Strongest protect mass must sit in the upper third (face/hair), not skirt.
    upper = sum(
        1
        for y in range(int(h * 0.05), int(h * 0.30))
        for x in range(int(w * 0.30), int(w * 0.70))
        if mask.getpixel((x, y)) > 180
    )
    lower = sum(
        1
        for y in range(int(h * 0.50), int(h * 0.70))
        for x in range(int(w * 0.30), int(w * 0.70))
        if mask.getpixel((x, y)) > 40
    )
    assert upper > 200
    assert lower < 30
    assert mask.getpixel((w // 2, int(h * 0.55))) < 40
