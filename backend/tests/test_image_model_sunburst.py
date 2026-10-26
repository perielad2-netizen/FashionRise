"""P1 #54 image-model migration: gpt-image-2.5-sunburst mocks only. No live OpenAI."""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import sketch_openai

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
)

_SWIMWEAR_NOTES = (
    "bikini two-piece swimsuit",
    "one-piece swimsuit",
    "swim shorts beachwear",
    "orange long-sleeve top with blue shorts",
)


def _settings(**env) -> Settings:
    data = {
        "testing": True,
        "environment": "development",
        "openai_api_key": "sk-test-not-a-real-key",
        "openai_model": "gpt-6-luna",
        "openai_reasoning_effort": "none",
        "openai_max_completion_tokens": 1400,
        "openai_image_model": "gpt-image-2.5-sunburst",
        "openai_image_size": "1024x1536",
        "openai_image_quality": "high",
        "openai_timeout_seconds": 180.0,
        "openai_http_timeout_seconds": 60.0,
        "openai_base_url": None,
    }
    data.update(env)
    return Settings.model_construct(**data)


def _job(**input_data) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type="sketch_polish", input_data=input_data)


class _EditTrackingClient:
    def __init__(self, on_edit):
        self.on_edit = on_edit
        self.option_calls: list[dict[str, Any]] = []
        self.edit_models: list[str] = []
        self.generate_calls = 0
        self.images = self

    def with_options(self, **kwargs):
        self.option_calls.append(kwargs)
        return self

    def edit(self, **kwargs):
        self.edit_models.append(kwargs.get("model", ""))
        return self.on_edit(**kwargs)

    def generate(self, **kwargs):
        self.generate_calls += 1
        raise AssertionError("images.generate must not be called")


@pytest.fixture
def settings(monkeypatch):
    s = _settings()
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    return s


def test_retired_gpt_image_1_fails_closed_without_paid_edit(monkeypatch, caplog):
    s = _settings(openai_image_model="gpt-image-1")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    client = _EditTrackingClient(on_edit=lambda **kw: (_ for _ in ()).throw(AssertionError("no edit")))
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(sketch_openai.SketchCompletionError, match="image model configuration"),
    ):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == []
    assert client.option_calls == []
    assert client.generate_calls == 0


def test_unknown_image_model_fails_closed_without_paid_edit(monkeypatch):
    s = _settings(openai_image_model="gpt-image-99-unknown")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    client = _EditTrackingClient(on_edit=lambda **kw: (_ for _ in ()).throw(AssertionError("no edit")))
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="image model configuration"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == []


def test_sunburst_edit_request_shape_and_storage(monkeypatch, settings):
    captured: dict[str, Any] = {}

    def on_edit(**kwargs):
        captured.update(kwargs)
        item = SimpleNamespace(url=None, b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"))
        return SimpleNamespace(data=[item])

    client = _EditTrackingClient(on_edit=on_edit)
    saved: list[bytes] = []

    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(
            save_file=lambda **kw: (
                saved.append(kw["data"].read() if hasattr(kw["data"], "read") else kw["data"])
                or "http://127.0.0.1:8001/static/uploads/ai/look.png"
            )
        ),
    )
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    url = sketch_openai._generate_and_store_look_image(
        client, job, {"summary": "look", "image_prompt": "refined fashion illustration"}, "look"
    )
    assert url.endswith("look.png")
    assert saved and saved[0] == b"FAKEPNG"
    assert client.option_calls == [{"max_retries": 0}]
    assert captured["model"] == "gpt-image-2.5-sunburst"
    assert captured["size"] == "1024x1536"
    assert captured["quality"] == "high"
    assert captured["output_format"] == "png"
    assert captured["n"] == 1
    assert "input_fidelity" not in captured
    assert client.generate_calls == 0


def test_quality_legacy_standard_maps_to_high_xhigh_max_fail_closed():
    caps = sketch_openai.image_edit_capabilities("gpt-image-2.5-sunburst")
    assert caps is not None
    assert sketch_openai.resolve_image_edit_quality(caps, "standard") == "high"
    assert sketch_openai.resolve_image_edit_quality(caps, "high") == "high"
    assert sketch_openai.resolve_image_edit_quality(caps, "medium") == "medium"
    with pytest.raises(sketch_openai.SketchCompletionError, match="image quality configuration"):
        sketch_openai.resolve_image_edit_quality(caps, "xhigh")
    with pytest.raises(sketch_openai.SketchCompletionError, match="image quality configuration"):
        sketch_openai.resolve_image_edit_quality(caps, "max")
    with pytest.raises(sketch_openai.SketchCompletionError, match="image quality configuration"):
        sketch_openai.resolve_image_edit_quality(caps, "not-a-quality")


def test_unknown_snapshot_suffix_fails_closed_without_paid_edit(monkeypatch):
    """Arbitrary gpt-image-2.5-sunburst-* suffixes must not be accepted."""
    s = _settings(openai_image_model="gpt-image-2.5-sunburst-unverified-future")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    client = _EditTrackingClient(on_edit=lambda **kw: (_ for _ in ()).throw(AssertionError("no edit")))
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="image model configuration"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == []
    assert client.option_calls == []
    assert client.generate_calls == 0
    assert sketch_openai.image_edit_capabilities("gpt-image-2.5-sunburst-unverified-future") is None
    assert sketch_openai.image_edit_capabilities("gpt-image-2.5-flare-unverified") is None
    assert sketch_openai.image_edit_capabilities("gpt-image-2-unverified") is None


def test_documented_sunburst_snapshot_alias_allowed():
    caps = sketch_openai.image_edit_capabilities("gpt-image-2.5-sunburst-2026-09-08")
    assert caps is not None
    assert caps.model_id == "gpt-image-2.5-sunburst"
    kwargs = sketch_openai.build_image_edit_kwargs(
        model="gpt-image-2.5-sunburst-2026-09-08",
        prompt="professionally refine the fashion sketch",
        sketch=(_TINY_PNG, "image/png"),
        size="1024x1536",
        quality="high",
    )
    assert kwargs["model"] == "gpt-image-2.5-sunburst-2026-09-08"
    assert kwargs["quality"] == "high"
    assert "input_fidelity" not in kwargs


def test_xhigh_quality_setting_fails_before_paid_edit(monkeypatch):
    s = _settings(openai_image_quality="xhigh")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    client = _EditTrackingClient(on_edit=lambda **kw: (_ for _ in ()).throw(AssertionError("no edit")))
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="image quality configuration"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == []
    assert client.generate_calls == 0


def test_invalid_parameter_mock_does_not_call_generate(monkeypatch, settings):
    class _BadParam(Exception):
        def __init__(self):
            super().__init__("invalid_value SECRET_BODY")
            self.status_code = 400
            self.code = "invalid_value"

    def on_edit(**kwargs):
        raise _BadParam()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == ["gpt-image-2.5-sunburst"]
    assert client.generate_calls == 0


def test_provider_refusal_mock_safe_message(monkeypatch, settings, caplog):
    class _Moderation(Exception):
        def __init__(self):
            super().__init__('{"code":"moderation_blocked","moderation_details":{"SECRET":1}}')
            self.status_code = 400
            self.code = "moderation_blocked"

    def on_edit(**kwargs):
        raise _Moderation()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(sketch_openai.SketchCompletionError) as excinfo,
    ):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "bikini"}, "x"
        )
    # Migration PR keeps the historical generic edit failure string (observability mapping is PR #55).
    assert "SECRET" not in str(excinfo.value)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "SECRET" not in joined
    assert "moderation_details" not in joined
    assert client.generate_calls == 0


@pytest.mark.parametrize("notes", _SWIMWEAR_NOTES)
def test_app_prompt_path_accepts_legitimate_swimwear_and_apparel(settings, notes):
    """App construction must not reject ordinary swimwear/apparel categories."""
    job = _job(
        notes=notes,
        image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}",
    )
    req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=1400,
    )
    assert req["model"] == "gpt-6-luna"
    blob = json_dumps(req)
    assert notes.split()[0] in blob or notes in blob
    # No application-level garment ban strings.
    assert "not allowed" not in blob.lower()
    assert "forbidden garment" not in blob.lower()


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj)


def test_build_image_edit_kwargs_omits_input_fidelity_for_sunburst():
    kwargs = sketch_openai.build_image_edit_kwargs(
        model="gpt-image-2.5-sunburst",
        prompt="professionally refine the fashion sketch",
        sketch=(_TINY_PNG, "image/png"),
        size="1024x1536",
        quality="high",
    )
    assert kwargs["model"] == "gpt-image-2.5-sunburst"
    assert kwargs["quality"] == "high"
    assert kwargs["output_format"] == "png"
    assert kwargs["n"] == 1
    assert "input_fidelity" not in kwargs
    name, buf, _mime = kwargs["image"]
    assert name.startswith("sketch.")
    assert isinstance(buf, BytesIO)
    assert buf.getvalue() == _TINY_PNG


def test_build_image_edit_kwargs_sends_sketch_then_textile_swatch():
    textile = _TINY_PNG + b"\x01\x02"
    kwargs = sketch_openai.build_image_edit_kwargs(
        model="gpt-image-2.5-sunburst",
        prompt="refine with textile",
        sketch=(_TINY_PNG, "image/png"),
        size="1024x1536",
        quality="high",
        fabric_swatch=(textile, "image/png"),
    )
    assert isinstance(kwargs["image"], list)
    assert len(kwargs["image"]) == 2
    sketch_name, sketch_buf, _ = kwargs["image"][0]
    textile_name, textile_buf, _ = kwargs["image"][1]
    assert sketch_name.startswith("sketch.")
    assert textile_name.startswith("textile.")
    assert sketch_buf.getvalue() == _TINY_PNG
    assert textile_buf.getvalue() == textile


def test_image_prompt_includes_textile_clause_when_swatch_present():
    job = _job(
        image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}",
        fabric_swatch_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}",
        shared_garment_spec={"main_colors": ["#BE185D"], "materials": ["Satin repeating textile"]},
    )
    prompt = sketch_openai._build_image_prompt(
        {"summary": "pink satin swimsuit", "image_prompt": "one-piece pink swimsuit"},
        "pink satin swimsuit",
        job,
    )
    assert "TEXTILE REFERENCE" in prompt
    assert "Image 2" in prompt
    assert "plain glossy satin" in prompt.lower() or "plain glossy" in prompt.lower()


def test_gpt_image_2_also_omits_input_fidelity():
    kwargs = sketch_openai.build_image_edit_kwargs(
        model="gpt-image-2",
        prompt="refine",
        sketch=(_TINY_PNG, "image/png"),
        size="1024x1536",
        quality="high",
    )
    assert "input_fidelity" not in kwargs


def test_no_silent_fallback_to_flare_on_sunburst_failure(monkeypatch, settings):
    def on_edit(**kwargs):
        raise RuntimeError("sunburst edit failed")

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.edit_models == ["gpt-image-2.5-sunburst"]
    assert client.generate_calls == 0
