"""WEB-V4E Magic quality: deterministic prompt + mocked pipeline tests.

Never call the live OpenAI API. No paid images.edit / images.generate.
"""

from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services import sketch_openai

# 1×1 PNG
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
)


def _settings(**env) -> Settings:
    data = {
        "testing": True,
        "environment": "development",
        "openai_api_key": "sk-test-not-a-real-key",
        "openai_model": "gpt-6-luna",
        "openai_reasoning_effort": "none",
        "openai_max_completion_tokens": 1400,
        "openai_image_model": "gpt-image-1",
        "openai_image_size": "1024x1536",
        "openai_timeout_seconds": 180.0,
        "openai_http_timeout_seconds": 60.0,
        "openai_base_url": None,
    }
    data.update(env)
    return Settings.model_construct(**data)


def _job(**input_data) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type="sketch_polish", input_data=input_data)


def _completion(content: str, *, finish_reason: str = "stop"):
    message = SimpleNamespace(content=content, refusal=None)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _operator_sample_structured() -> dict[str, Any]:
    return {
        "summary": "A bold pink jumpsuit with a wide-brim hat",
        "polish_bullets": ["Deepen the V neckline contrast", "Keep sleeve flow"],
        "design_identity": {
            "garment_category": "jumpsuit",
            "silhouette": "flowing full-length jumpsuit",
            "pose": "standing front view",
            "neckline": "deep V neckline",
            "sleeve_type": "flowing",
            "sleeve_length": "long",
            "hemline": "full length",
            "main_colors": "pink",
            "fabric_patterns": "pink patterned textile",
            "accessories": "wide-brimmed hat",
            "asymmetry_notes": "asymmetric leg design",
            "distinctive_details": "wide-brim hat, deep V, flowing sleeves",
        },
        "refine_ok": ["wobbly outlines", "uneven fill"],
        "image_prompt": (
            "Standing figure in a pink patterned jumpsuit with deep V neckline, "
            "flowing long sleeves, asymmetric leg design, and a wide-brimmed hat."
        ),
    }


@pytest.fixture
def settings(monkeypatch):
    s = _settings()
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    return s


def test_polish_system_prompt_separates_design_from_imperfections():
    prompt = sketch_openai._system_prompt("sketch_polish")
    assert "design decisions" in prompt.lower() or "DESIGN CONCEPT" in prompt
    assert "design_identity" in prompt
    assert "refine_ok" in prompt
    assert "image_prompt" in prompt
    assert "amateur line quality" in prompt.lower() or "child sketch look" in prompt.lower()
    # Must not instruct vision to keep the child's rough drawing look.
    assert "still look like the child's sketch" not in prompt.lower()


def test_build_image_prompt_professional_refinement_not_wash():
    structured = _operator_sample_structured()
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"])
    lower = prompt.lower()

    assert "source of truth" in lower
    assert "professionally refine" in lower or "polished fashion-design" in lower
    assert "fabric folds" in lower or "draping" in lower
    assert "tailoring" in lower or "garment construction" in lower
    assert "preserve" in lower
    assert "asymmetry" in lower
    assert "wide-brim" in lower or "hat" in lower
    assert "deep v" in lower
    assert "pink" in lower
    assert "asymmetric" in lower or "asymmetry" in lower

    # Old positive wash/child-sketch instructions must stay gone (negated bans are OK).
    assert "only clean the linework and add a light color wash" not in lower
    assert "result must still look like the child's sketch" not in lower
    assert "do not apply only a faint watercolor or light color wash" in lower


def test_build_image_prompt_includes_design_identity_fields():
    structured = _operator_sample_structured()
    prompt = sketch_openai._build_image_prompt(structured, "summary")
    assert "garment category: jumpsuit" in prompt.lower()
    assert "neckline: deep v neckline" in prompt.lower()
    assert "accessories: wide-brimmed hat" in prompt.lower()
    assert "asymmetry notes: asymmetric leg design" in prompt.lower()


def test_build_image_prompt_preserves_color_and_texture_language():
    structured = {
        "summary": "Checked coat",
        "image_prompt": "Red-and-black check coat, stand collar, knee hem",
        "design_identity": {
            "main_colors": "red and black",
            "fabric_patterns": "large check plaid",
        },
    }
    prompt = sketch_openai._build_image_prompt(structured, "Checked coat")
    lower = prompt.lower()
    assert "red and black" in lower
    assert "check" in lower or "plaid" in lower
    assert "faithful colors" in lower or "richer but faithful" in lower
    assert "textile patterns" in lower or "fabric patterns" in lower


def test_build_image_prompt_avoids_generic_outfit_homogenization():
    prompt = sketch_openai._build_image_prompt(
        {"summary": "Unique look", "image_prompt": "Asymmetric cape dress"},
        "Unique look",
    )
    assert "generic fashion outfit" in prompt.lower()
    assert "invent a different garment" in prompt.lower() or "do not invent" in prompt.lower()


def test_edit_request_uses_high_fidelity_and_sketch_bytes(monkeypatch, settings):
    captured: dict[str, Any] = {}

    class _EditClient:
        def __init__(self):
            self.images = SimpleNamespace(edit=self.edit)

        def edit(self, **kwargs):
            captured.update(kwargs)
            item = SimpleNamespace(url=None, b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"))
            return SimpleNamespace(data=[item])

    saved: list[tuple[str, bytes]] = []

    def fake_save(*, key, data, content_type):
        raw = data.read() if hasattr(data, "read") else data
        saved.append((key, raw if isinstance(raw, (bytes, bytearray)) else bytes(raw)))
        return f"http://127.0.0.1:8001/static/uploads/{key}"

    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(save_file=fake_save),
    )

    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    structured = _operator_sample_structured()
    url = sketch_openai._generate_and_store_look_image(_EditClient(), job, structured, structured["summary"])

    assert url.startswith("http://127.0.0.1:8001/static/uploads/ai/")
    assert captured["model"] == "gpt-image-1"
    assert captured["input_fidelity"] == "high"
    assert captured["n"] == 1
    assert captured["size"] == "1024x1536"
    assert "only clean the linework and add a light color wash" not in captured["prompt"].lower()
    assert "professionally refine" in captured["prompt"].lower()
    name, buf, mime = captured["image"]
    assert name.startswith("sketch.")
    assert isinstance(buf, BytesIO)
    assert buf.getvalue() == _TINY_PNG
    assert mime.startswith("image/")
    assert saved and saved[0][1] == b"FAKEPNG"


def test_no_reference_less_generate_fallback_on_edit_failure(monkeypatch, settings):
    calls: list[str] = []

    class _FailEditClient:
        def __init__(self):
            self.images = SimpleNamespace(edit=self.edit, generate=self.generate)

        def edit(self, **kwargs):
            calls.append("edit")
            raise RuntimeError("edit unavailable")

        def generate(self, **kwargs):
            calls.append("generate")
            raise AssertionError("images.generate must not run as Magic fallback")

    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            _FailEditClient(), job, _operator_sample_structured(), "summary"
        )
    assert calls  # edit may retry across gpt-image models
    assert all(c == "edit" for c in calls)
    assert "generate" not in calls


def test_edit_retries_image_models_but_never_generate(monkeypatch, settings):
    edits: list[str] = []

    class _Client:
        def __init__(self):
            self.images = SimpleNamespace(edit=self.edit, generate=self.generate)

        def edit(self, **kwargs):
            edits.append(kwargs["model"])
            raise RuntimeError(f"fail {kwargs['model']}")

        def generate(self, **kwargs):
            raise AssertionError("generate forbidden")

    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            _Client(), job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert "gpt-image-1" in edits
    assert "gpt-image-1-mini" in edits


def test_missing_sketch_fails_without_generate(monkeypatch, settings):
    class _Client:
        def __init__(self):
            self.images = SimpleNamespace(
                edit=lambda **k: (_ for _ in ()).throw(AssertionError("edit")),
                generate=lambda **k: (_ for _ in ()).throw(AssertionError("generate")),
            )

    with pytest.raises(sketch_openai.SketchCompletionError, match="no sketch image for edit"):
        sketch_openai._generate_and_store_look_image(
            _Client(), _job(notes="no image"), {"summary": "x", "image_prompt": "dress"}, "x"
        )


def test_image_model_off_skips_edit_and_generate(monkeypatch):
    s = _settings(openai_image_model="off")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)

    class _Client:
        def __init__(self):
            self.images = SimpleNamespace(
                edit=lambda **k: (_ for _ in ()).throw(AssertionError("edit")),
                generate=lambda **k: (_ for _ in ()).throw(AssertionError("generate")),
            )

    assert (
        sketch_openai._generate_and_store_look_image(
            _Client(),
            _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}"),
            {"summary": "x", "image_prompt": "dress"},
            "x",
        )
        is None
    )


def test_complete_polish_records_images_edit_provenance(monkeypatch, settings):
    payload = _operator_sample_structured()
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kw: _completion(json.dumps(payload)))
        )
    )
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(
        sketch_openai,
        "_generate_and_store_look_image",
        lambda *a, **k: "http://127.0.0.1:8001/static/uploads/ai/look.png",
    )

    result = sketch_openai.complete_sketch_job(
        _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    )
    assert result["image_url"].endswith("look.png")
    assert result["image_provenance"] == "images.edit"
    assert "image_base64" not in json.dumps(result)


def test_complete_polish_propagates_edit_failure(monkeypatch, settings):
    payload = _operator_sample_structured()

    class _Client:
        def __init__(self):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: _completion(json.dumps(payload)))
            )
            self.images = SimpleNamespace(
                edit=lambda **kw: (_ for _ in ()).throw(RuntimeError("edit boom")),
                generate=lambda **kw: (_ for _ in ()).throw(AssertionError("generate")),
            )

    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: _Client())

    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai.complete_sketch_job(
            _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
        )


def test_failure_messages_do_not_leak_base64_or_secrets(monkeypatch, settings, caplog):
    secret_b64 = "SECRET_SKETCH_PAYLOAD_" + ("A" * 80)

    class _Client:
        def __init__(self):
            self.images = SimpleNamespace(
                edit=lambda **kw: (_ for _ in ()).throw(RuntimeError(f"provider saw {secret_b64}")),
                generate=lambda **kw: (_ for _ in ()).throw(AssertionError("generate")),
            )

    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with caplog.at_level(logging.WARNING):
        with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
            sketch_openai._generate_and_store_look_image(
                _Client(), job, {"summary": "x", "image_prompt": "dress"}, "x"
            )
    msg = str(excinfo.value)
    assert secret_b64 not in msg
    assert "sk-test" not in msg
    assert "data:image" not in msg
    # Worker-facing token stays short and sanitized.
    assert msg == "sketch image edit failed"


def test_build_sketch_chat_request_polish_uses_new_system_prompt(settings):
    job = _job(notes="pink jumpsuit")
    req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=1400,
    )
    system = req["messages"][0]["content"]
    assert "design_identity" in system
    assert "light color wash" not in system.lower()
