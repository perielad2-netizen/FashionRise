"""Mocked gpt-6-luna Chat Completions migration tests. Never call the live OpenAI API."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import Settings, get_settings
from app.services import ai_worker, sketch_openai


def _settings(**env) -> Settings:
    data = {
        "testing": True,
        "environment": "development",
        "openai_api_key": "sk-test-not-a-real-key",
        "openai_model": "gpt-6-luna",
        "openai_reasoning_effort": "none",
        "openai_max_completion_tokens": 1400,
        "openai_image_model": "gpt-image-2.5-sunburst",
        "openai_timeout_seconds": 180.0,
        "openai_http_timeout_seconds": 60.0,
        "openai_base_url": None,
    }
    data.update(env)
    # model_construct avoids picking up a developer's real OPENAI_* env vars.
    return Settings.model_construct(**data)


def _job(job_type: str = "sketch_clean", **input_data) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type=job_type, input_data=input_data)


def _completion(content: str, *, finish_reason: str = "stop", refusal: str | None = None):
    message = SimpleNamespace(content=content, refusal=refusal)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


class _CapturingClient:
    def __init__(self, result, *, error: Exception | None = None):
        self.result = result
        self.error = error
        self.kwargs: dict = {}
        self.image_calls: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.images = SimpleNamespace(edit=self._image_edit, generate=self._image_generate)

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.result

    def _image_edit(self, **kwargs):
        self.image_calls.append("edit")
        raise AssertionError("images.edit must not run for an incomplete or invalid completion")

    def _image_generate(self, **kwargs):
        self.image_calls.append("generate")
        raise AssertionError("images.generate must not run for an incomplete or invalid completion")


@pytest.fixture
def settings(monkeypatch):
    s = _settings()
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    return s


def test_default_chat_model_is_gpt_6_luna(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OPENAI_MAX_COMPLETION_TOKENS", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_QUALITY", raising=False)
    # Ignore backend/.env so this asserts code defaults, not a local developer pin.
    s = Settings(
        _env_file=None,
        testing=True,
        environment="development",
        openai_api_key=None,
    )
    assert s.openai_model == "gpt-6-luna"
    assert s.openai_reasoning_effort == "none"
    assert s.openai_max_completion_tokens == 1400
    assert s.openai_image_model == "gpt-image-2.5-sunburst"
    assert s.openai_image_quality == "high"


def test_environment_override_still_selects_the_model(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()
    try:
        s = Settings()
        assert s.openai_model == "gpt-4o-mini"
        assert s.openai_reasoning_effort == "low"
    finally:
        get_settings.cache_clear()


def test_reasoning_families_are_model_specific():
    assert sketch_openai.reasoning_family("gpt-6-luna") == "including_none"
    assert sketch_openai.reasoning_family("gpt-6-luna-2026-09-01") == "including_none"
    assert sketch_openai.reasoning_family("gpt-6-sol") == "including_none"
    assert sketch_openai.reasoning_family("gpt-6-astra") == "no_none"
    assert sketch_openai.reasoning_family("gpt-6-astra-2026-09-01") == "no_none"
    assert sketch_openai.reasoning_family("gpt-6.1-sol") == "no_none"
    assert sketch_openai.reasoning_family("gpt-6.1-sol-2026-09-15") == "no_none"
    assert sketch_openai.reasoning_family("gpt-4o-mini") == "omit"
    assert sketch_openai.reasoning_family("gpt-4o-mini-2024-07-18") == "omit"
    assert sketch_openai.reasoning_family("gpt-5.6-sol") == "unknown"
    assert sketch_openai.uses_chat_reasoning_effort("gpt-6-luna") is True
    assert sketch_openai.uses_chat_reasoning_effort("gpt-6-astra") is True
    assert sketch_openai.uses_chat_reasoning_effort("gpt-4o-mini") is False


def test_luna_none_is_sent_and_gpt4o_omits():
    luna = sketch_openai.chat_completion_kwargs(
        model="gpt-6-luna",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=1400,
        reasoning_effort="none",
    )
    assert luna["reasoning_effort"] == "none"
    assert luna["response_format"] == {"type": "json_object"}
    assert "temperature" not in luna

    rollback = sketch_openai.chat_completion_kwargs(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=1400,
        reasoning_effort="none",
    )
    assert "reasoning_effort" not in rollback


@pytest.mark.parametrize(
    "model",
    ["gpt-6-astra", "gpt-6-astra-2026-09-01", "gpt-6.1-sol", "gpt-6.1-sol-2026-09-15"],
)
def test_models_that_reject_none_fail_closed(model):
    with pytest.raises(sketch_openai.SketchConfigError, match="none is not supported"):
        sketch_openai.chat_completion_kwargs(
            model=model,
            messages=[{"role": "user", "content": "x"}],
            max_completion_tokens=1400,
            reasoning_effort="none",
        )


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-6.1-sol"])
def test_astra_and_61_sol_accept_low(model):
    kwargs = sketch_openai.chat_completion_kwargs(
        model=model,
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=1400,
        reasoning_effort="low",
    )
    assert kwargs["reasoning_effort"] == "low"


def test_astra_default_none_never_opens_a_client(monkeypatch):
    s = _settings(openai_model="gpt-6-astra", openai_reasoning_effort="none")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    opened: list[str] = []

    def boom(**kw):
        opened.append("client")
        raise AssertionError("OpenAI client must not be constructed for an invalid combo")

    monkeypatch.setattr(sketch_openai, "OpenAI", boom)
    with pytest.raises(sketch_openai.SketchConfigError, match="none is not supported"):
        sketch_openai.complete_sketch_job(_job("sketch_clean"))
    assert opened == []


@pytest.mark.parametrize("model", ["gpt-5.6-sol", "gpt-5-mini", "gpt-5", "gpt-6", "gpt-6-pro"])
def test_unknown_model_does_not_send_reasoning_effort(model):
    with pytest.raises(sketch_openai.SketchConfigError, match="known Chat Completions reasoning table"):
        sketch_openai.chat_completion_kwargs(
            model=model,
            messages=[{"role": "user", "content": "x"}],
            max_completion_tokens=1400,
            reasoning_effort="none",
        )


def test_sdk_floor_and_create_accepts_reasoning_effort():
    import inspect
    from pathlib import Path

    import openai
    from openai.resources.chat.completions import Completions

    parts = tuple(int(p) for p in openai.__version__.split(".")[:3])
    assert parts >= (1, 109, 1)
    params = inspect.signature(Completions.create).parameters
    for name in ("model", "messages", "response_format", "max_completion_tokens", "reasoning_effort"):
        assert name in params
    req = Path(__file__).resolve().parents[1] / "requirements.txt"
    text = req.read_text(encoding="utf-8")
    assert "openai>=1.109.1,<2.0.0" in text
    assert "openai>=1.40.0" not in text


@pytest.mark.parametrize(
    ("job_type", "payload", "required"),
    [
        (
            "sketch_clean",
            {"summary": "Clean lines", "cleanup_bullets": ["trace", "simplify", "hem"]},
            "cleanup_bullets",
        ),
        (
            "sketch_polish",
            {
                "summary": "Bright dress",
                "polish_bullets": ["color wash", "neckline"],
                "image_prompt": "A-line dress",
            },
            "polish_bullets",
        ),
        (
            "style_suggest",
            {
                "summary": "Five looks",
                "suggestions": [
                    {"title": "A", "description": "one"},
                    {"title": "B", "description": "two"},
                    {"title": "C", "description": "three"},
                    {"title": "D", "description": "four"},
                    {"title": "E", "description": "five"},
                ],
            },
            "suggestions",
        ),
    ],
)
def test_job_types_preserve_structured_keys(monkeypatch, settings, job_type, payload, required):
    client = _CapturingClient(_completion(json.dumps(payload)))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(sketch_openai, "_generate_and_store_look_image", lambda *a, **k: None)

    result = sketch_openai.complete_sketch_job(_job(job_type, notes="kid sketch"))

    assert result["message"] == "openai"
    assert result["pipeline"] == job_type
    assert result["model"] == "gpt-6-luna"
    assert result["summary"] == payload["summary"]
    assert required in result["structured"]
    assert result["structured"][required] == payload[required]
    assert client.kwargs["model"] == "gpt-6-luna"
    assert client.kwargs["response_format"] == {"type": "json_object"}
    assert client.kwargs["reasoning_effort"] == "none"
    assert client.kwargs["max_completion_tokens"] == 1400
    roles = [m["role"] for m in client.kwargs["messages"]]
    assert roles == ["system", "user"]


def test_image_base64_is_attached_as_vision_part(monkeypatch, settings):
    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
    client = _CapturingClient(_completion('{"summary":"seen","cleanup_bullets":["ok"]}'))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    sketch_openai.complete_sketch_job(
        _job("sketch_clean", image_base64=f"data:image/png;base64,{png_b64}")
    )

    user = client.kwargs["messages"][1]["content"]
    assert user[0]["type"] == "text"
    assert user[1]["type"] == "image_url"
    assert user[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_image_url_is_fetched_and_inlined(monkeypatch, settings):
    client = _CapturingClient(_completion('{"summary":"seen","cleanup_bullets":["ok"]}'))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(
        sketch_openai,
        "_fetch_image",
        lambda url: (b"\x89PNG", "image/png") if url.startswith("https://") else (_ for _ in ()).throw(AssertionError(url)),
    )

    sketch_openai.complete_sketch_job(
        _job("sketch_clean", image_url="https://example.test/sketch.png")
    )

    user = client.kwargs["messages"][1]["content"]
    assert user[1]["type"] == "image_url"
    assert "base64," in user[1]["image_url"]["url"]


def test_failed_model_request_propagates(monkeypatch, settings):
    client = _CapturingClient(None, error=RuntimeError("429 rate limited"))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(RuntimeError, match="429"):
        sketch_openai.complete_sketch_job(_job("sketch_clean"))


def test_empty_and_refused_completions_fail_safely():
    with pytest.raises(sketch_openai.SketchCompletionError, match="empty"):
        sketch_openai._parse_chat_completion(_completion(""))
    with pytest.raises(sketch_openai.SketchCompletionError, match="refused"):
        sketch_openai._parse_chat_completion(_completion("{}", refusal="I can't help with that"))
    with pytest.raises(sketch_openai.SketchCompletionError, match="no choices"):
        sketch_openai._parse_chat_completion(SimpleNamespace(choices=[]))


def test_truncated_and_invalid_json_fail_the_job():
    with pytest.raises(sketch_openai.SketchCompletionError, match="truncated"):
        sketch_openai._parse_chat_completion(
            _completion('{"summary": "cut off"', finish_reason="length")
        )
    with pytest.raises(sketch_openai.SketchCompletionError, match="invalid JSON"):
        sketch_openai._parse_chat_completion(_completion('{"summary": '))
    with pytest.raises(sketch_openai.SketchCompletionError, match="not an object"):
        sketch_openai._parse_chat_completion(_completion('["not", "an", "object"]'))


def test_truncated_polish_never_calls_image_generation(monkeypatch, settings):
    client = _CapturingClient(_completion('{"summary":"cut","polish_bullets":["x"]', finish_reason="length"))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="truncated"):
        sketch_openai.complete_sketch_job(_job("sketch_polish", notes="dress"))
    assert client.image_calls == []


def test_invalid_json_polish_never_calls_image_generation(monkeypatch, settings):
    client = _CapturingClient(_completion("not-json"))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="invalid JSON"):
        sketch_openai.complete_sketch_job(_job("sketch_polish"))
    assert client.image_calls == []


def test_refused_polish_never_calls_image_generation(monkeypatch, settings):
    client = _CapturingClient(_completion("{}", refusal="no"))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="refused"):
        sketch_openai.complete_sketch_job(_job("sketch_polish"))
    assert client.image_calls == []


def test_empty_polish_never_calls_image_generation(monkeypatch, settings):
    client = _CapturingClient(_completion(""))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="empty"):
        sketch_openai.complete_sketch_job(_job("sketch_polish"))
    assert client.image_calls == []


def test_length_finish_reason_fails_even_if_json_parses(monkeypatch, settings):
    payload = {
        "summary": "looks complete",
        "polish_bullets": ["color wash"],
        "image_prompt": "A-line dress",
    }
    client = _CapturingClient(_completion(json.dumps(payload), finish_reason="length"))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="truncated"):
        sketch_openai.complete_sketch_job(_job("sketch_polish"))
    assert client.image_calls == []


def test_successful_polish_uses_image_prompt(monkeypatch, settings):
    payload = {
        "summary": "Bright dress",
        "polish_bullets": ["color wash"],
        "image_prompt": "A-line dress, short sleeves",
    }
    client = _CapturingClient(_completion(json.dumps(payload)))
    seen: list[tuple[Any, str]] = []

    def fake_image(_client, _job, structured, summary):
        seen.append((structured, summary))
        return "http://127.0.0.1:8001/static/uploads/ai/look.png"

    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(sketch_openai, "_generate_and_store_look_image", fake_image)

    result = sketch_openai.complete_sketch_job(_job("sketch_polish"))
    assert result["image_url"].endswith("look.png")
    assert result["structured"]["image_prompt"] == payload["image_prompt"]
    assert seen == [(payload, "Bright dress")]


def test_worker_marks_failed_when_completion_is_truncated(monkeypatch, settings):
    job = SimpleNamespace(
        id=uuid4(),
        job_type="sketch_polish",
        input_data={},
        result_data=None,
        error_message=None,
        status="queued",
    )
    client = _CapturingClient(_completion('{"summary":"', finish_reason="length"))
    monkeypatch.setattr(sketch_openai, "is_configured", lambda: True)
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: settings)

    class _Db:
        def scalar(self, _stmt):
            return job if job.status == "queued" else None

        def commit(self):
            pass

    processed = ai_worker.run_worker_tick(_Db(), limit=1)
    assert processed == 1
    assert job.status == "failed"
    assert "truncated" in (job.error_message or "")
    assert job.result_data is None
    assert client.image_calls == []
    assert "sk-test" not in (job.error_message or "")


def test_no_api_key_uses_stub_and_completes(monkeypatch):
    job = SimpleNamespace(
        id=uuid4(),
        job_type="sketch_clean",
        input_data={"notes": "x"},
        result_data=None,
        error_message="old",
        status="queued",
    )
    monkeypatch.setattr(sketch_openai, "is_configured", lambda: False)
    monkeypatch.setattr(sketch_openai, "complete_sketch_job", lambda *a, **k: (_ for _ in ()).throw(AssertionError("live path")))

    class _Db:
        def __init__(self):
            self.committed = False

        def scalar(self, _stmt):
            return job if job.status == "queued" else None

        def commit(self):
            self.committed = True
            job.status = "completed"

    db = _Db()
    # First tick consumes the job; second sees None.
    processed = ai_worker.run_worker_tick(db, limit=1)
    assert processed == 1
    assert job.status == "completed"
    assert job.error_message is None
    assert job.result_data["message"].startswith("stub worker")
    assert job.result_data["pipeline"] == "sketch_clean"


def test_worker_marks_failed_when_openai_raises(monkeypatch):
    job = SimpleNamespace(
        id=uuid4(),
        job_type="style_suggest",
        input_data={},
        result_data={"keep": False},
        error_message=None,
        status="queued",
    )
    monkeypatch.setattr(sketch_openai, "is_configured", lambda: True)
    monkeypatch.setattr(
        sketch_openai,
        "complete_sketch_job",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("model timeout")),
    )

    class _Db:
        def scalar(self, _stmt):
            return job if job.status == "queued" else None

        def commit(self):
            pass

    processed = ai_worker.run_worker_tick(_Db(), limit=1)
    assert processed == 1
    assert job.status == "failed"
    assert "model timeout" in (job.error_message or "")
    assert job.result_data is None


def test_worker_persists_allowlisted_failure_meta_only(monkeypatch):
    job = SimpleNamespace(
        id=uuid4(),
        job_type="sketch_polish",
        input_data={},
        result_data=None,
        error_message=None,
        status="queued",
    )

    def _boom(*_a, **_k):
        raise sketch_openai.SketchCompletionError(
            "sketch image edit failed",
            safe_meta={
                "error_category": "provider_bad_request",
                "error_type": "BadRequestError",
                "http_status": 400,
                "provider_code": "invalid_image",
                "request_id": "req_worker_meta_001",
                "stage": "images.edit",
                "image_edit_attempted": True,
                "image_bytes_returned": False,
                "raw_body": "SECRET_MUST_NOT_PERSIST",
                "prompt": "SECRET_PROMPT",
            },
        )

    monkeypatch.setattr(sketch_openai, "is_configured", lambda: True)
    monkeypatch.setattr(sketch_openai, "complete_sketch_job", _boom)

    class _Db:
        def scalar(self, _stmt):
            return job if job.status == "queued" else None

        def commit(self):
            pass

    processed = ai_worker.run_worker_tick(_Db(), limit=1)
    assert processed == 1
    assert job.status == "failed"
    assert job.error_message == "sketch image edit failed"
    assert job.result_data == {
        "error": {
            "error_category": "provider_bad_request",
            "error_type": "BadRequestError",
            "http_status": 400,
            "provider_code": "invalid_image",
            "request_id": "req_worker_meta_001",
            "stage": "images.edit",
            "image_edit_attempted": True,
            "image_bytes_returned": False,
        }
    }
    dumped = json.dumps(job.result_data)
    assert "SECRET" not in dumped
    assert "prompt" not in dumped



def test_api_key_is_not_logged(monkeypatch, settings, caplog):
    client = _CapturingClient(_completion('{"summary":"ok","cleanup_bullets":["a"]}'))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with caplog.at_level(logging.DEBUG):
        sketch_openai.complete_sketch_job(_job("sketch_clean", notes="secret-looking notes"))

    blob = "\n".join(f"{r.name} {r.message}" for r in caplog.records)
    assert "sk-test-not-a-real-key" not in blob
    assert "sk-test" not in blob
