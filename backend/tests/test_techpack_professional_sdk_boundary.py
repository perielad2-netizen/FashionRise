"""SDK-boundary tests for OpenAIProfessionalProvider.analyze_garment (no live paid calls)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services.sketch_openai import SketchConfigError
from app.services.techpack_ai_professional import OpenAIProfessionalProvider


class _FakeCompletions:
    def __init__(self, capture: dict):
        self.capture = capture

    def create(self, **kwargs):
        self.capture["kwargs"] = kwargs
        content = (
            '{"schema_version":"techpack.analysis.v1","category":"dress",'
            '"silhouette":"fitted bodycon mini","neckline":"deep plunging V-neckline",'
            '"sleeves":"long sleeves","fabric_pattern":"bright pink and white diagonal stripes",'
            '"stripe_direction":"diagonal","confidence":"high","assumptions":[]}'
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=1200, completion_tokens=200),
        )


class _FakeChat:
    def __init__(self, capture: dict):
        self.completions = _FakeCompletions(capture)


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.capture = kwargs.setdefault("_capture", {})
        self.chat = _FakeChat(self.capture)


def test_analyze_garment_passes_reasoning_effort_and_image_bytes(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "none")
    monkeypatch.setenv("OPENAI_MAX_COMPLETION_TOKENS", "1400")
    get_settings.cache_clear()

    capture: dict = {}

    def _factory(*args, **kwargs):
        kwargs["_capture"] = capture
        return _FakeOpenAI(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.techpack_ai_professional.OpenAI",
        _factory,
        raising=False,
    )
    # Provider imports OpenAI inside the method — patch openai.OpenAI
    import openai

    monkeypatch.setattr(openai, "OpenAI", _factory)

    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    provider = OpenAIProfessionalProvider()
    parsed, usage = provider.analyze_garment(
        image_bytes=png,
        mime="image/png",
        piece={"id": "p1", "category": "dress", "label": "Pink dress"},
        look_notes="bright pink white diagonal striped fitted mini",
    )

    kwargs = capture["kwargs"]
    assert kwargs["model"] == "gpt-6-luna"
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["max_completion_tokens"] <= 1800
    assert "temperature" not in kwargs
    messages = kwargs["messages"]
    user = messages[1]["content"]
    assert isinstance(user, list)
    image_part = next(p for p in user if p.get("type") == "image_url")
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    # actual image bytes must be present in the data URL payload
    import base64

    b64 = url.split(",", 1)[1]
    assert base64.b64decode(b64) == png
    assert parsed["neckline"]
    assert usage.vision_calls == 1
    assert usage.vision_model == "gpt-6-luna"


def test_analyze_garment_rejects_incompatible_reasoning_before_paid_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    # Astra family rejects reasoning_effort=none
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-astra")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "none")
    get_settings.cache_clear()

    called = {"create": 0}

    class _Boom:
        def __init__(self, *a, **k):
            pass

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            called["create"] += 1
            raise AssertionError("must not call provider")

    import openai

    monkeypatch.setattr(openai, "OpenAI", _Boom)

    provider = OpenAIProfessionalProvider()
    with pytest.raises(SketchConfigError):
        provider.analyze_garment(
            image_bytes=b"\x89PNG\r\n\x1a\n",
            mime="image/png",
            piece={"category": "dress"},
            look_notes="",
        )
    assert called["create"] == 0


def test_analyze_garment_empty_effort_fails_closed_for_luna(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "none")
    get_settings.cache_clear()

    # Simulate a runtime empty effort (Settings Literal rejects "" at load).
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_reasoning_effort", "", raising=False)

    called = {"create": 0}

    class _Boom:
        def __init__(self, *a, **k):
            pass

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            called["create"] += 1
            raise AssertionError("must not call provider")

    import openai

    monkeypatch.setattr(openai, "OpenAI", _Boom)
    monkeypatch.setattr(
        "app.services.techpack_ai_professional.get_settings", lambda: settings
    )

    provider = OpenAIProfessionalProvider()
    with pytest.raises(SketchConfigError, match="OPENAI_REASONING_EFFORT is empty"):
        provider.analyze_garment(
            image_bytes=b"\x89PNG\r\n\x1a\n",
            mime="image/png",
            piece={"category": "dress"},
            look_notes="",
        )
    assert called["create"] == 0
