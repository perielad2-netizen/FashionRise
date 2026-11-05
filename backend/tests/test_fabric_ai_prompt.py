"""AI fabric prompt validation — fabric-only, color required, no paid calls."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.fabric_ai_prompt import validate_ai_fabric_prompt


def test_accepts_gold_glitter_prompt_with_color_word():
    plan = validate_ai_fabric_prompt(prompt="gold shiny with diamonds like glitters fabric")
    assert plan.color_hex == "#D4A017"
    assert "gold" in plan.prompt_short.lower()
    assert "glitter" in plan.generate_prompt.lower() or "diamond" in plan.generate_prompt.lower()
    assert "no person" in plan.generate_prompt.lower()


def test_palette_color_overrides_prompt_color():
    plan = validate_ai_fabric_prompt(
        prompt="shiny metallic sequin fabric with glitter",
        color_hex="#1D4ED8",
    )
    assert plan.color_hex == "#1D4ED8"
    assert "royal" in plan.prompt_short.lower() or "#1D4ED8" in plan.prompt_short


def test_missing_color_returns_structured_detail():
    with pytest.raises(HTTPException) as ei:
        validate_ai_fabric_prompt(prompt="shiny sequin fabric with glitter sparkle")
    assert ei.value.status_code == 400
    detail = ei.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "missing_fields"
    assert "color" in detail["missing"]


def test_unrelated_person_prompt_rejected():
    with pytest.raises(HTTPException) as ei:
        validate_ai_fabric_prompt(prompt="a beautiful woman wearing gold dress")
    assert ei.value.status_code == 400
    assert "Unrelated prompt" in str(ei.value.detail)


def test_non_fabric_prompt_rejected():
    with pytest.raises(HTTPException) as ei:
        validate_ai_fabric_prompt(prompt="make a spaceship blueprint")
    assert ei.value.status_code == 400
    assert "Unrelated prompt" in str(ei.value.detail)
