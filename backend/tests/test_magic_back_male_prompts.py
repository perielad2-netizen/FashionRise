"""Back Magic prompt should keep full garments (incl. male robes), not swimwear bias."""
from app.services.sketch_openai import (
    _smart_back_flag,
    _studio_side_edit_clause,
    _studio_side_vision_clause,
)


def test_back_vision_not_swimwear_biased():
    text = _studio_side_vision_clause("back")
    assert "adult swimwear" not in text.lower()
    assert "SAME garment coverage" in text or "same garment coverage" in text.lower()
    assert "underwear" in text.lower()


def test_smart_back_vision_uses_front_seed():
    text = _studio_side_vision_clause("back", smart_back=True)
    assert "FRONT sketch" in text or "Front sketch" in text or "front sketch" in text.lower()
    assert "underwear" in text.lower()
    assert "male" in text.lower()


def test_smart_back_flag():
    assert _smart_back_flag({"smart_back": True}) is True
    assert _smart_back_flag({"smart_back": "true"}) is True
    assert _smart_back_flag({"smart_back": False}) is False
    assert _smart_back_flag({}) is False


def test_back_edit_keeps_full_coverage():
    text = _studio_side_edit_clause("back")
    assert "robes" in text.lower() or "hoods" in text.lower()
    smart = _studio_side_edit_clause("back", smart_back=True)
    assert "underwear" in smart.lower()
