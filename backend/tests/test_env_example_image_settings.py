"""Parser check: backend/.env.example has single effective image-edit defaults."""

from __future__ import annotations

from pathlib import Path

import pytest

_ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

_REQUIRED = {
    "OPENAI_IMAGE_MODEL": "gpt-image-2.5-sunburst",
    "OPENAI_IMAGE_SIZE": "1024x1536",
    "OPENAI_IMAGE_QUALITY": "high",
}


def _parse_dotenv_effective(text: str) -> dict[str, str]:
    """Last assignment wins (dotenv-style). Ignores comments and blank lines."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            out[key] = value.strip()
    return out


def _assignment_counts(text: str, key: str) -> int:
    n = 0
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, _, _ = line.partition("=")
        if k.strip() == key:
            n += 1
    return n


@pytest.mark.parametrize("key,expected", list(_REQUIRED.items()))
def test_env_example_image_keys_appear_once_with_expected_value(key: str, expected: str):
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert _ENV_EXAMPLE.is_file()
    assert _assignment_counts(text, key) == 1, f"{key} must appear exactly once in .env.example"
    effective = _parse_dotenv_effective(text)
    assert effective.get(key) == expected


def test_env_example_no_duplicate_size_or_quality_overriding_high():
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    effective = _parse_dotenv_effective(text)
    assert effective["OPENAI_IMAGE_QUALITY"] == "high"
    assert effective["OPENAI_IMAGE_SIZE"] == "1024x1536"
    assert effective["OPENAI_IMAGE_MODEL"] == "gpt-image-2.5-sunburst"
    # Guard against a trailing OPENAI_IMAGE_QUALITY=standard resurfacing.
    assert "OPENAI_IMAGE_QUALITY=standard" not in text
