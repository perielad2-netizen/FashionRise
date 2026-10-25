"""P1 #59: selected croquis identity for Magic — offline mocks only. No paid OpenAI."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.errors import ValidationAppError
from app.models.ai_job import AIJob
from app.services import sketch_openai
from app.services.reference_croquis import (
    ALLOWED_REFERENCE_MODEL_IDS,
    SELECTABLE_FEMALE_IDS,
    SELECTABLE_MALE_IDS,
    edit_reference_instructions,
    parse_reference_model_id,
    reference_from_job_input,
    vision_reference_instructions,
)
from tests.auth_test_helpers import register_with_invite

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
)


def _job(**input_data: Any) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), job_type="sketch_polish", input_data=input_data)


@pytest.mark.parametrize("model_id", sorted(SELECTABLE_MALE_IDS | {"male"}))
def test_male_library_and_legacy_ids_parse_as_male(model_id: str):
    ref = parse_reference_model_id(model_id)
    assert ref is not None
    assert ref.family == "male"
    assert ref.model_id == model_id
    vision = vision_reference_instructions(ref)
    edit = edit_reference_instructions(ref)
    assert "male" in vision.lower()
    assert "female-presenting" in vision.lower() or "female" in vision.lower()
    assert model_id in edit
    assert "Do NOT replace" in edit or "do NOT replace" in edit.lower()


@pytest.mark.parametrize("model_id", sorted(SELECTABLE_FEMALE_IDS | {"female"}))
def test_female_library_and_legacy_ids_parse_as_female(model_id: str):
    ref = parse_reference_model_id(model_id)
    assert ref is not None
    assert ref.family == "female"
    vision = vision_reference_instructions(ref)
    edit = edit_reference_instructions(ref)
    assert "female" in vision.lower()
    assert model_id in edit
    assert "male-presenting" in vision.lower() or "male" in vision.lower()


@pytest.mark.parametrize("model_id", ["custom", "blank"])
def test_utility_ids_do_not_invent_gender(model_id: str):
    ref = parse_reference_model_id(model_id)
    assert ref is not None
    assert ref.family is None
    assert ref.kind == "utility"
    vision = vision_reference_instructions(ref)
    edit = edit_reference_instructions(ref)
    assert "no explicit" in vision.lower() or "did not select" in vision.lower()
    assert "do not default to a female" in vision.lower()
    assert "do not invent" in edit.lower()


def test_missing_metadata_is_backward_compatible():
    assert parse_reference_model_id(None) is None
    assert parse_reference_model_id("") is None
    assert reference_from_job_input({}) is None
    assert reference_from_job_input({"notes": "polish concept"}) is None
    vision = vision_reference_instructions(None)
    assert "not provided" in vision.lower()
    assert "do not invent" in vision.lower() or "ambiguous" in vision.lower()


def test_invalid_reference_model_id_fails_closed():
    with pytest.raises(ValidationAppError, match="not a recognized"):
        parse_reference_model_id("female-invented")
    with pytest.raises(ValidationAppError, match="not a recognized"):
        parse_reference_model_id("male-extra")
    with pytest.raises(ValidationAppError, match="string"):
        parse_reference_model_id(123)


def test_allowlist_covers_ten_builtins_plus_legacy_and_utility():
    assert len(SELECTABLE_FEMALE_IDS) == 6
    assert len(SELECTABLE_MALE_IDS) == 4
    assert "female" in ALLOWED_REFERENCE_MODEL_IDS
    assert "male" in ALLOWED_REFERENCE_MODEL_IDS
    assert "custom" in ALLOWED_REFERENCE_MODEL_IDS
    assert "blank" in ALLOWED_REFERENCE_MODEL_IDS


def test_user_text_includes_selected_male_reference():
    text = sketch_openai._user_text(_job(notes="polish concept", reference_model_id="male-straight"))
    assert "SELECTED STUDIO REFERENCE" in text
    assert "male-straight" in text
    assert "male fashion-croquis" in text.lower() or "male" in text.lower()
    assert "polish concept" in text


def test_user_text_missing_reference_stays_compatible():
    text = sketch_openai._user_text(_job(notes="polish concept"))
    assert "SELECTED STUDIO REFERENCE" in text
    assert "not provided" in text.lower()


def test_edit_prompt_preserves_male_identity_over_conflicting_vision():
    structured = {
        "summary": "A stylish look",
        "image_prompt": (
            "Preserve the grey top and blue trousers on a female-presenting model "
            "with long wavy hair and feminine styling."
        ),
        "design_identity": {
            "garment_category": "top and trousers",
            "silhouette": "long sleeve top with straight trousers",
            "pose": "standing front view",
            "main_colors": "grey and blue",
            "fabric_patterns": "solid",
            "accessories": None,
            "asymmetry_notes": None,
            "distinctive_details": "grey long sleeves",
        },
    }
    job = _job(reference_model_id="male-contrapposto", notes="polish concept")
    prompt = sketch_openai._build_image_prompt(structured, structured["summary"], job=job)
    assert "male-contrapposto" in prompt
    assert "SELECTED STUDIO REFERENCE" in prompt
    assert "female-presenting fashion figure" in prompt.lower() or "female-presenting" in prompt.lower()
    assert "Avoid photorealism" in prompt
    # Scrubbed vision prose should not keep instructing a woman figure.
    assert "long wavy hair" not in prompt.lower()
    assert "PRESERVE exactly from visible evidence" in prompt


def test_edit_prompt_custom_blank_do_not_force_female():
    for model_id in ("custom", "blank"):
        job = _job(reference_model_id=model_id)
        prompt = sketch_openai._build_image_prompt(
            {"summary": "x", "image_prompt": "preserve garment colors"},
            "x",
            job=job,
        )
        assert model_id in prompt
        assert "do not default to a female" in prompt.lower() or "do not invent" in prompt.lower()


def test_reference_identity_survives_verbose_evidence_pressure():
    huge = ("verbose design note about seams and hems " * 200).strip()
    structured = {
        "summary": "pressure",
        "image_prompt": huge,
        "design_identity": {
            "garment_category": "dress",
            "silhouette": "A-line",
            "pose": "front croquis",
            "main_colors": "red",
            "fabric_patterns": "dots",
        },
    }
    job = _job(reference_model_id="male-walk")
    prompt = sketch_openai._build_image_prompt(structured, "pressure", job=job)
    assert "male-walk" in prompt
    assert "SELECTED STUDIO REFERENCE" in prompt
    assert "PRESERVE exactly from visible evidence" in prompt


class _EditTrackingClient:
    def __init__(self, on_edit):
        self.on_edit = on_edit
        self.option_calls: list[dict[str, Any]] = []
        self.edit_models: list[str] = []
        self.generate_calls = 0
        self.images = self
        self.last_edit_kwargs: dict[str, Any] = {}

    def with_options(self, **kwargs):
        self.option_calls.append(kwargs)
        return self

    def edit(self, **kwargs):
        self.edit_models.append(str(kwargs.get("model") or ""))
        self.last_edit_kwargs = kwargs
        return self.on_edit(**kwargs)

    def generate(self, **kwargs):
        self.generate_calls += 1
        raise AssertionError("images.generate must not be called")


def test_polish_path_sends_identity_into_single_images_edit(monkeypatch):
    captured: dict[str, Any] = {}

    def on_edit(**kwargs):
        captured.update(kwargs)
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
    monkeypatch.setattr(
        sketch_openai,
        "get_settings",
        lambda: SimpleNamespace(
            openai_image_model="gpt-image-2.5-sunburst",
            openai_image_size="1024x1536",
            openai_image_quality="high",
        ),
    )
    job = _job(
        reference_model_id="male-straight",
        image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}",
    )
    structured = {
        "summary": "grey top blue trousers",
        "image_prompt": "female model in grey top",
        "design_identity": {
            "garment_category": "separates",
            "main_colors": "grey and blue",
            "pose": "standing",
        },
    }
    url = sketch_openai._generate_and_store_look_image(client, job, structured, "grey top")
    assert url.endswith("look.png")
    assert client.generate_calls == 0
    assert len(client.edit_models) == 1
    prompt = captured.get("prompt") or ""
    assert "male-straight" in prompt
    assert "SELECTED STUDIO REFERENCE" in prompt
    if client.option_calls:
        assert client.option_calls == [{"max_retries": 0}]


def test_camel_case_reference_model_id_accepted():
    ref = reference_from_job_input({"referenceModelId": "female-hand-hip"})
    assert ref is not None
    assert ref.model_id == "female-hand-hip"
    assert ref.family == "female"


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _polish_payload(*, reference_model_id: str | None = None, include_image: bool = True) -> dict:
    tiny = base64.b64encode(_TINY_PNG).decode("ascii")
    input_data: dict[str, Any] = {"notes": "polish concept"}
    if include_image:
        input_data["image_base64"] = f"data:image/png;base64,{tiny}"
    if reference_model_id is not None:
        input_data["reference_model_id"] = reference_model_id
    return {"input_data": input_data}


@pytest.mark.parametrize("model_id", sorted(ALLOWED_REFERENCE_MODEL_IDS))
def test_api_accepts_every_allowlisted_reference_model_id(client, db_session, model_id: str):
    slug = model_id.replace("-", "_")
    tokens = register_with_invite(client, db_session, f"ref_{slug}@example.com", f"ref_{slug}"[:32])
    created = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json=_polish_payload(reference_model_id=model_id),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["input_data"].get("reference_model_id") == model_id
    # Sketch bytes redacted from API; selected croquis id is not secret and remains.
    assert "image_base64" not in body["input_data"]
    row = db_session.get(AIJob, UUID(body["id"]))
    assert row is not None
    assert row.input_data.get("reference_model_id") == model_id


def test_api_missing_reference_model_id_remains_backward_compatible(client, db_session):
    tokens = register_with_invite(client, db_session, "ref_missing@example.com", "ref_missing")
    created = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json=_polish_payload(),
    )
    assert created.status_code == 201, created.text
    assert "reference_model_id" not in created.json()["input_data"]


def test_api_rejects_invalid_reference_model_id(client, db_session):
    tokens = register_with_invite(client, db_session, "ref_bad@example.com", "ref_bad")
    created = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json=_polish_payload(reference_model_id="male-invented"),
    )
    assert created.status_code == 422, created.text


def test_system_prompt_defers_to_selected_studio_reference():
    prompt = sketch_openai._system_prompt("sketch_polish")
    assert "SELECTED STUDIO REFERENCE" in prompt
    assert "authoritative" in prompt.lower()


def test_build_sketch_chat_request_includes_vision_identity():
    job = _job(
        reference_model_id="male-step",
        image_base64=f"data:image/png;base64,{base64.b64encode(_TINY_PNG).decode('ascii')}",
    )
    req = sketch_openai.build_sketch_chat_request(
        job,
        model="gpt-6-luna",
        reasoning_effort="none",
        max_completion_tokens=800,
    )
    user = req["messages"][1]["content"]
    assert isinstance(user, list)
    text = user[0]["text"]
    assert "male-step" in text
    assert "SELECTED STUDIO REFERENCE" in text
    assert "SELECTED STUDIO REFERENCE" in req["messages"][0]["content"]
