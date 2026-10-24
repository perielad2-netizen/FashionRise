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
            "pose": (
                "asymmetric fashion stance with one bent leg angled away from the "
                "supporting leg and one hand on the hip"
            ),
            "neckline": "deep V neckline",
            "sleeve_type": "flowing",
            "sleeve_length": "long",
            "hemline": "full length",
            "main_colors": "pink",
            "fabric_patterns": "pink patterned textile",
            "accessories": "wide-brimmed hat",
            "asymmetry_notes": "asymmetric leg design",
            "distinctive_details": "wide-brim hat, deep V, flowing sleeves",
            "pose_lock": {
                "torso_orientation": "slight three-quarter fashion tilt following the hip line",
                "shoulder_alignment": "shoulders angled with the body, not square-to-camera runway",
                "hip_alignment": "hips shifted with weight on the supporting leg",
                "supporting_leg": "one leg planted as the standing support",
                "bent_or_lifted_leg": (
                    "opposite leg bent at the knee and angled away/back from the supporting leg"
                ),
                "knee_positions": "free-leg knee bent and outward; supporting knee straighter",
                "foot_placement": (
                    "supporting boot planted; free boot not both-feet-flat runway; "
                    "lifted or angled heel/toe relationship preserved"
                ),
                "arm_and_hand_positions": "one hand resting at the waist/hip; other arm follows the sketch",
                "body_asymmetry_and_perspective": (
                    "clear left/right asymmetry in legs and hips; keep original perspective"
                ),
            },
        },
        "refine_ok": ["wobbly outlines", "uneven fill"],
        "image_prompt": (
            "Figure in a pink patterned jumpsuit with deep V neckline, flowing long sleeves, "
            "asymmetric bent-leg stance with one hand on the hip, and a wide-brimmed hat."
        ),
    }


@pytest.fixture
def settings(monkeypatch):
    s = _settings()
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)
    return s


class _EditTrackingClient:
    """Fake OpenAI client: records with_options(max_retries=0) then one images.edit."""

    def __init__(self, *, on_edit):
        self._on_edit = on_edit
        self.option_calls: list[dict[str, Any]] = []
        self.edit_models: list[str] = []
        self.generate_calls = 0
        self.images = SimpleNamespace(edit=self.edit, generate=self.generate)

    def with_options(self, **kwargs):
        self.option_calls.append(kwargs)
        return self

    def edit(self, **kwargs):
        self.edit_models.append(kwargs["model"])
        return self._on_edit(**kwargs)

    def generate(self, **kwargs):
        self.generate_calls += 1
        raise AssertionError("images.generate must not run")


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


def test_edit_request_uses_high_fidelity_and_exactly_one_edit(monkeypatch, settings):
    captured: dict[str, Any] = {}

    def on_edit(**kwargs):
        captured.update(kwargs)
        item = SimpleNamespace(url=None, b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"))
        return SimpleNamespace(data=[item])

    client = _EditTrackingClient(on_edit=on_edit)
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
    url = sketch_openai._generate_and_store_look_image(client, job, structured, structured["summary"])

    assert url.startswith("http://127.0.0.1:8001/static/uploads/ai/")
    assert client.option_calls == [{"max_retries": 0}]
    assert client.edit_models == ["gpt-image-1"]
    assert client.generate_calls == 0
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


def test_edit_failure_exactly_one_edit_no_generate_or_mini(monkeypatch, settings):
    def on_edit(**kwargs):
        raise RuntimeError("edit unavailable SECRET_SHOULD_NOT_LEAK")

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            client, job, _operator_sample_structured(), "summary"
        )
    assert client.option_calls == [{"max_retries": 0}]
    assert client.edit_models == ["gpt-image-1"]
    assert client.generate_calls == 0


def test_empty_edit_response_exactly_one_edit_no_generate(monkeypatch, settings):
    def on_edit(**kwargs):
        return SimpleNamespace(data=[SimpleNamespace(url=None, b64_json=None)])

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.option_calls == [{"max_retries": 0}]
    assert client.edit_models == ["gpt-image-1"]
    assert client.generate_calls == 0


def test_configured_image_model_used_once_never_downgraded(monkeypatch):
    s = _settings(openai_image_model="gpt-image-1")
    monkeypatch.setattr(sketch_openai, "get_settings", lambda: s)

    def on_edit(**kwargs):
        raise RuntimeError("fail configured model")

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert client.option_calls == [{"max_retries": 0}]
    assert client.edit_models == ["gpt-image-1"]
    assert "gpt-image-1-mini" not in client.edit_models
    assert client.generate_calls == 0


def test_image_edit_disables_sdk_retries_without_touching_chat(monkeypatch, settings):
    """Chat Completions must not inherit max_retries=0 from the image-edit path."""
    chat_kwargs: dict[str, Any] = {}
    payload = _operator_sample_structured()

    class _Client:
        def __init__(self):
            self.chat_option_calls: list[dict[str, Any]] = []
            self.edit_option_calls: list[dict[str, Any]] = []
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            self.images = SimpleNamespace(edit=self.edit, generate=self.generate)

        def with_options(self, **kwargs):
            # Only the edit path should call this; chat uses the bare client.
            self.edit_option_calls.append(kwargs)
            return self

        def create(self, **kwargs):
            chat_kwargs.update(kwargs)
            return _completion(json.dumps(payload))

        def edit(self, **kwargs):
            item = SimpleNamespace(url=None, b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"))
            return SimpleNamespace(data=[item])

        def generate(self, **kwargs):
            raise AssertionError("generate")

    client = _Client()
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)
    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(
            save_file=lambda **kw: "http://127.0.0.1:8001/static/uploads/ai/look.png"
        ),
    )

    result = sketch_openai.complete_sketch_job(
        _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    )
    assert result["image_provenance"] == "images.edit"
    assert client.edit_option_calls == [{"max_retries": 0}]
    assert client.chat_option_calls == []
    assert "max_retries" not in chat_kwargs


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

    class _Client(_EditTrackingClient):
        def __init__(self):
            super().__init__(on_edit=self._boom)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: _completion(json.dumps(payload)))
            )

        def _boom(self, **kwargs):
            raise RuntimeError("edit boom")

    client = _Client()
    monkeypatch.setattr(sketch_openai, "OpenAI", lambda **kw: client)

    with pytest.raises(sketch_openai.SketchCompletionError, match="sketch image edit failed"):
        sketch_openai.complete_sketch_job(
            _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
        )
    assert client.option_calls == [{"max_retries": 0}]
    assert client.edit_models == ["gpt-image-1"]
    assert client.generate_calls == 0


def test_failure_messages_and_logs_do_not_leak_base64_or_secrets(monkeypatch, settings, caplog):
    secret_b64 = "SECRET_SKETCH_PAYLOAD_" + ("A" * 80)

    def on_edit(**kwargs):
        raise RuntimeError(f"provider saw {secret_b64}")

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(sketch_openai.SketchCompletionError) as excinfo,
    ):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    msg = str(excinfo.value)
    assert secret_b64 not in msg
    assert "sk-test" not in msg
    assert "data:image" not in msg
    assert msg == "sketch image edit failed"
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_b64 not in joined
    assert "provider saw" not in joined
    assert "sk-test" not in joined
    assert "data:image" not in joined
    assert "image edit failed type=RuntimeError" in joined
    assert client.option_calls == [{"max_retries": 0}]


def test_edit_path_decodes_sketch_once(monkeypatch, settings):
    decode_calls = {"n": 0}
    real_decode = sketch_openai._decode_inline_base64

    def counting_decode(data: str):
        decode_calls["n"] += 1
        return real_decode(data)

    monkeypatch.setattr(sketch_openai, "_decode_inline_base64", counting_decode)

    def on_edit(**kwargs):
        item = SimpleNamespace(url=None, b64_json=base64.b64encode(b"FAKEPNG").decode("ascii"))
        return SimpleNamespace(data=[item])

    client = _EditTrackingClient(on_edit=on_edit)
    monkeypatch.setattr(
        sketch_openai,
        "LocalStorageBackend",
        lambda: SimpleNamespace(
            save_file=lambda **kw: "http://127.0.0.1:8001/static/uploads/ai/look.png"
        ),
    )

    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    sketch_openai._generate_and_store_look_image(
        client, job, {"summary": "x", "image_prompt": "dress"}, "x"
    )
    assert decode_calls["n"] == 1
    assert client.option_calls == [{"max_retries": 0}]


def test_edit_bad_request_safe_meta_no_body_leak(monkeypatch, settings, caplog):
    """Issue #54 observability: persist allowlisted fields only; never raw provider bodies."""

    class _FakeBadRequest(Exception):
        def __init__(self):
            super().__init__('{"error":{"message":"SECRET_BODY_SHOULD_NOT_LEAK","code":"invalid_image"}}')
            self.status_code = 400
            self.code = "invalid_image"
            self.request_id = "req_test_observability_001"
            self.body = {"error": {"message": "SECRET_BODY_SHOULD_NOT_LEAK", "code": "invalid_image"}}

    def on_edit(**kwargs):
        raise _FakeBadRequest()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(sketch_openai.SketchCompletionError) as excinfo,
    ):
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    err = excinfo.value
    assert str(err) == "sketch image edit failed"
    assert err.safe_meta["error_category"] == "provider_bad_request"
    assert err.safe_meta["http_status"] == 400
    assert err.safe_meta["provider_code"] == "invalid_image"
    assert err.safe_meta["request_id"] == "req_test_observability_001"
    assert err.safe_meta["stage"] == "images.edit"
    assert err.safe_meta["image_edit_attempted"] is True
    assert err.safe_meta["image_bytes_returned"] is False
    assert "SECRET_BODY" not in str(err)
    assert "SECRET_BODY" not in json.dumps(err.safe_meta)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "SECRET_BODY" not in joined
    assert "status=400" in joined
    assert "code=invalid_image" in joined
    assert "request_id=req_test_observability_001" in joined


def test_edit_unknown_provider_code_not_persisted(monkeypatch, settings):
    class _FakeBadRequest(Exception):
        def __init__(self):
            super().__init__("bad")
            self.status_code = 400
            self.code = "totally_unknown_internal_detail"
            self.request_id = "req_ok_12345678"

    def on_edit(**kwargs):
        raise _FakeBadRequest()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    meta = excinfo.value.safe_meta
    assert "provider_code" not in meta
    assert meta["http_status"] == 400
    assert meta["request_id"] == "req_ok_12345678"
    assert meta["error_category"] == "provider_bad_request"


def test_content_policy_code_maps_to_user_safe_message(monkeypatch, settings):
    class _FakePolicy(Exception):
        def __init__(self):
            super().__init__("policy")
            self.status_code = 400
            self.code = "content_policy_violation"
            self.request_id = "req_policy_abcdef12"

    def on_edit(**kwargs):
        raise _FakePolicy()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "bikini"}, "x"
        )
    assert excinfo.value.safe_meta["error_category"] == "provider_content_policy"
    assert "safety rules" in str(excinfo.value).lower()
    assert "bikini" not in str(excinfo.value).lower()


def test_moderation_blocked_maps_to_content_policy_not_bad_request(monkeypatch, settings):
    class _FakeModeration(Exception):
        def __init__(self):
            super().__init__(
                '{"error":{"code":"moderation_blocked","moderation_details":{"SECRET":true}}}'
            )
            self.status_code = 400
            self.code = "moderation_blocked"
            self.request_id = "req_moderation_abc123"
            self.body = {"error": {"code": "moderation_blocked", "moderation_details": {"SECRET": True}}}

    def on_edit(**kwargs):
        raise _FakeModeration()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "two-piece swimsuit"}, "x"
        )
    meta = excinfo.value.safe_meta
    assert meta["error_category"] == "provider_content_policy"
    assert meta["provider_code"] == "moderation_blocked"
    assert meta["http_status"] == 400
    assert "SECRET" not in json.dumps(meta)
    assert "moderation_details" not in meta
    assert "safety rules" in str(excinfo.value).lower()


def test_http_400_without_safety_code_is_not_content_policy(monkeypatch, settings):
    class _FakeBadRequest(Exception):
        def __init__(self):
            super().__init__("bad")
            self.status_code = 400
            self.code = None
            self.request_id = "req_plain400_zzzz99"

    def on_edit(**kwargs):
        raise _FakeBadRequest()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert excinfo.value.safe_meta["error_category"] == "provider_bad_request"
    assert str(excinfo.value) == "sketch image edit failed"


def test_model_not_found_code_is_model_unavailable(monkeypatch, settings):
    class _FakeMissing(Exception):
        def __init__(self):
            super().__init__("missing")
            self.status_code = 404
            self.code = "model_not_found"
            self.request_id = "req_model_missing01"

    def on_edit(**kwargs):
        raise _FakeMissing()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert excinfo.value.safe_meta["error_category"] == "provider_model_unavailable"


def test_quota_error_category(monkeypatch, settings):
    class _FakeQuota(Exception):
        def __init__(self):
            super().__init__("quota")
            self.status_code = 429
            self.code = "insufficient_quota"
            self.request_id = "req_quota_abcd1234"

    def on_edit(**kwargs):
        raise _FakeQuota()

    client = _EditTrackingClient(on_edit=on_edit)
    job = _job(image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}")
    with pytest.raises(sketch_openai.SketchCompletionError) as excinfo:
        sketch_openai._generate_and_store_look_image(
            client, job, {"summary": "x", "image_prompt": "dress"}, "x"
        )
    assert excinfo.value.safe_meta["error_category"] == "provider_quota"


def test_normalize_failure_meta_drops_unknown_fields():
    kept = sketch_openai.normalize_failure_meta(
        {
            "error_category": "provider_bad_request",
            "error_type": "BadRequestError",
            "http_status": 400,
            "provider_code": "invalid_image",
            "request_id": "req_ok_normalize01",
            "stage": "images.edit",
            "image_edit_attempted": True,
            "image_bytes_returned": False,
            "raw_body": "SECRET",
            "prompt": "SECRET",
        }
    )
    assert kept == {
        "error_category": "provider_bad_request",
        "error_type": "BadRequestError",
        "http_status": 400,
        "provider_code": "invalid_image",
        "request_id": "req_ok_normalize01",
        "stage": "images.edit",
        "image_edit_attempted": True,
        "image_bytes_returned": False,
    }
    dropped = sketch_openai.normalize_failure_meta(
        {
            "error_category": "not_a_real_category",
            "error_type": "EvilClassName",
            "http_status": 400,
            "provider_code": "not_allowlisted_code",
            "request_id": "bad id with spaces!",
            "stage": "images.hack",
            "raw_body": "SECRET",
        }
    )
    assert dropped == {"http_status": 400}


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
