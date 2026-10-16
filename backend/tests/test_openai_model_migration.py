"""Mocked gpt-6-luna Chat Completions migration tests. Never call the live OpenAI API."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
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
        "openai_image_model": "gpt-image-1",
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
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.result


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
    s = Settings(
        testing=True,
        environment="development",
        openai_api_key=None,
    )
    assert s.openai_model == "gpt-6-luna"
    assert s.openai_reasoning_effort == "none"
    assert s.openai_max_completion_tokens == 1400
    assert s.openai_image_model == "gpt-image-1"


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


def test_reasoning_effort_only_for_gpt6_family():
    assert sketch_openai.uses_chat_reasoning_effort("gpt-6-luna") is True
    assert sketch_openai.uses_chat_reasoning_effort("gpt-6-luna-2026-09-01") is True
    assert sketch_openai.uses_chat_reasoning_effort("gpt-4o-mini") is False
    assert sketch_openai.uses_chat_reasoning_effort("gpt-4o-mini-2024-07-18") is False


def test_chat_kwargs_include_json_object_and_none_effort():
    kwargs = sketch_openai.chat_completion_kwargs(
        model="gpt-6-luna",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=1400,
        reasoning_effort="none",
    )
    assert kwargs["model"] == "gpt-6-luna"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["max_completion_tokens"] == 1400
    assert kwargs["reasoning_effort"] == "none"
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs


def test_chat_kwargs_omit_reasoning_effort_for_gpt4o_override():
    kwargs = sketch_openai.chat_completion_kwargs(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "x"}],
        max_completion_tokens=1400,
        reasoning_effort="none",
    )
    assert "reasoning_effort" not in kwargs
    assert kwargs["response_format"]["type"] == "json_object"


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
    with pytest.raises(RuntimeError, match="empty"):
        sketch_openai._parse_chat_completion(_completion(""))
    with pytest.raises(RuntimeError, match="refused"):
        sketch_openai._parse_chat_completion(_completion("{}", refusal="I can't help with that"))
    with pytest.raises(RuntimeError, match="no choices"):
        sketch_openai._parse_chat_completion(SimpleNamespace(choices=[]))


def test_truncated_json_keeps_parse_error_fallback():
    structured, summary, finish, truncated = sketch_openai._parse_chat_completion(
        _completion('{"summary": "cut off"', finish_reason="length")
    )
    assert truncated is True
    assert finish == "length"
    assert structured["parse_error"] is True
    assert structured["truncated"] is True
    assert summary.startswith('{"summary"')


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


def test_api_key_is_not_logged(monkeypatch, settings, caplog):
    client = _CapturingClient(_completion('{"summary":"ok","cleanup_bullets":["a"]}'))
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with caplog.at_level(logging.DEBUG):
        sketch_openai.complete_sketch_job(_job("sketch_clean", notes="secret-looking notes"))

    blob = "\n".join(f"{r.name} {r.message}" for r in caplog.records)
    assert "sk-test-not-a-real-key" not in blob
    assert "sk-test" not in blob
