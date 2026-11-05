"""#171 — structure review must not compare person photos as garment masks."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from app.services.garment_leg_geometry import (
    analyze_lower_garment_geometry,
    classify_structure_image_role,
    openai_trouser_design_hints,
    soft_try_on_structure_review,
)
from app.services.looks_service import _structural_fidelity_rejected
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


def _full_person_try_on_png(*, flared_lower: bool = False) -> bytes:
    """Opaque photoreal-like person scene with skin, hair, background — not a garment plate."""
    img = Image.new("RGB", (384, 640), (235, 232, 226))  # studio bg
    draw = ImageDraw.Draw(img)
    # Hair
    draw.ellipse([150, 30, 240, 120], fill=(40, 28, 22))
    # Face / skin
    draw.ellipse([165, 70, 225, 145], fill=(210, 160, 130))
    # Torso skin
    draw.rectangle([170, 145, 220, 210], fill=(210, 160, 130))
    # Green garment torso
    draw.polygon([(155, 160), (235, 160), (250, 320), (140, 320)], fill=(22, 101, 52))
    if flared_lower:
        draw.polygon([(140, 320), (250, 320), (300, 600), (90, 600)], fill=(22, 101, 52))
    else:
        draw.rectangle([150, 320, 185, 600], fill=(22, 101, 52))
        draw.rectangle([205, 320, 240, 600], fill=(22, 101, 52))
        # Skin between legs (gap) — would poison a naive mask compare
        draw.rectangle([186, 340, 204, 580], fill=(210, 160, 130))
    # Arms
    draw.rectangle([120, 180, 150, 360], fill=(210, 160, 130))
    draw.rectangle([240, 180, 270, 360], fill=(210, 160, 130))
    return _png(img.convert("RGBA"))


def _merged_isolated_plate_png() -> bytes:
    img = _transparent(280, 560)
    draw = ImageDraw.Draw(img)
    draw.rectangle([90, 40, 190, 520], fill=(22, 101, 52, 255))
    return _png(img)


class _FakeJob:
    def __init__(self, result_data: dict):
        self.result_data = result_data
        self.status = "completed"


def test_full_person_photo_is_not_isolated_garment_role():
    role = classify_structure_image_role(_full_person_try_on_png())
    assert role == "full_scene"
    assert classify_structure_image_role(_narrow_jumpsuit_png()) == "isolated_garment"


def test_person_photo_does_not_false_fail_leg_merge():
    """Comparing jumpsuit plate to person photo must be inconclusive — not STRUCTURE_LEGS_MERGED."""
    review = soft_try_on_structure_review(
        source_png=_narrow_jumpsuit_png(),
        result_png=_full_person_try_on_png(flared_lower=True),
    )
    assert review["state"] == "inconclusive"
    assert review["code"] == "STRUCTURE_INCOMPARABLE_RESULT"
    assert review["faithful"] is None
    assert review["result_role"] == "full_scene"
    assert review["result"] is None  # do not publish poisoned person-mask geometry


def test_ordinary_top_shorts_not_downgraded():
    review = soft_try_on_structure_review(
        source_png=_top_shorts_png(),
        result_png=_full_person_try_on_png(),
    )
    assert review["state"] == "not_applicable"
    assert review["code"] == "STRUCTURE_CHECK_NOT_APPLICABLE"
    assert "ordinary" in review["message"].lower() or "does not apply" in review["message"].lower()


def test_narrow_jumpsuit_keeps_additive_hints():
    geo = analyze_lower_garment_geometry(_narrow_jumpsuit_png())
    hints = openai_trouser_design_hints(geo)
    assert geo.looks_like_trousers is True
    assert any("jumpsuit" in h.lower() or "trousers" in h.lower() for h in hints)
    prompt = build_try_on_prompt(hints)
    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.4"
    assert prompt.startswith(build_try_on_prompt(None))
    assert "Studio design evidence" in prompt


def test_isolated_plate_mismatch_still_fails():
    review = soft_try_on_structure_review(
        source_png=_narrow_jumpsuit_png(),
        result_png=_merged_isolated_plate_png(),
    )
    assert review["state"] == "failed"
    assert review["faithful"] is False
    assert review["code"] == "STRUCTURE_LEGS_MERGED_OR_LOST"


def test_my_looks_excludes_verified_structure_failures():
    assert _structural_fidelity_rejected(
        _FakeJob(  # type: ignore[arg-type]
            {
                "status": "completed_unverified",
                "fidelity_ok": False,
                "structure_review": {"state": "failed"},
            }
        )
    )
    assert not _structural_fidelity_rejected(
        _FakeJob(  # type: ignore[arg-type]
            {
                "status": "completed",
                "fidelity_ok": None,
                "structure_review": {"state": "not_applicable"},
            }
        )
    )
    assert not _structural_fidelity_rejected(
        _FakeJob(  # type: ignore[arg-type]
            {
                "status": "completed",
                "structure_review": {"state": "inconclusive"},
            }
        )
    )
