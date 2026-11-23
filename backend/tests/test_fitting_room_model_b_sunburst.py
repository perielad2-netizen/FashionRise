"""Fitting Room Model B (gpt-image-2.6-sunburst) — owner-only raw path.

Mocked only. Does not prove the model will generate correct shoes — only that
the planned request includes the footwear instruction and is a single edit.
"""

from __future__ import annotations

import base64
import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.user import User
from app.services.ai_worker import run_magic_worker_tick
from app.services.fitting_room import (
    FITTING_ROOM_CONSENT_VERSION,
    FITTING_ROOM_JOB_TYPE,
    MODEL_B_SUNBURST_FOOTWEAR_CLAUSE,
    MODEL_B_SUNBURST_MODEL,
    MODEL_B_SUNBURST_PATH,
    MODEL_B_SUNBURST_PROMPT,
    MODEL_B_SUNBURST_PROMPT_VERSION,
)
from app.services.personal_try_on_provider import set_try_on_provider_override
from tests.auth_test_helpers import register_with_invite

FR = "/api/v1/ai/fitting-room"


def _png_bytes(size: tuple[int, int] = (64, 96), color=(200, 100, 80, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _b64_png(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enable_fitting_room(monkeypatch, *, live: bool = True):
    get_settings.cache_clear()
    monkeypatch.setenv("FITTING_ROOM_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LIVE_HTTP", "true" if live else "false")
    get_settings.cache_clear()


def _grant_stars(db_session, username: str, amount: int = 40) -> None:
    user = db_session.query(User).filter(User.username == username).one()
    user.ai_stars = amount
    db_session.commit()


def _look_body(*, look_png: bytes, person_png: bytes, prefer_model_b: bool = False) -> dict:
    return {
        "person_image_base64": _b64_png(person_png),
        "garment_pieces": [
            {
                "image_base64": _b64_png(look_png),
                "category": "dresses",
                "source": "fashionrise_look",
            }
        ],
        "idempotency_key": f"fitting_room:{uuid.uuid4()}",
        "consent_acknowledged": True,
        "consent_version": FITTING_ROOM_CONSENT_VERSION,
        "prefer_model_b_sunburst": prefer_model_b,
    }


@pytest.fixture(autouse=True)
def _cleanup(monkeypatch, db_session):
    set_try_on_provider_override(None)
    db_session.query(AIJob).filter(AIJob.job_type == FITTING_ROOM_JOB_TYPE).delete()
    db_session.flush()
    yield
    set_try_on_provider_override(None)
    get_settings.cache_clear()
    monkeypatch.delenv("FITTING_ROOM_ENABLED", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LIVE_HTTP", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LOOK_DIRECT_EDIT_V2_ENABLED", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LOOK_IDENTITY_LOCK_ENABLED", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", raising=False)
    get_settings.cache_clear()


def test_model_b_flag_defaults_false():
    get_settings.cache_clear()
    s = get_settings()
    assert s.fitting_room_look_model_b_sunburst_enabled is False
    assert (s.fitting_room_look_model_b_sunburst_owner_allowlist or "") == ""


def test_model_b_prompt_includes_footwear_and_preserve_clause():
    from app.services.sunburst_try_on_prompt import (
        MODEL_B_SUNBURST_MALE_PANTS_CLAUSE,
        MODEL_B_SUNBURST_SEX_CLAUSE,
        MODEL_B_SUNBURST_SHORTS_CLAUSE,
        sex_flag_design_hints,
    )

    low = MODEL_B_SUNBURST_PROMPT.lower()
    assert "gpt-image" not in low  # prompt is garment instructions, not model id
    assert MODEL_B_SUNBURST_FOOTWEAR_CLAUSE in MODEL_B_SUNBURST_PROMPT
    assert MODEL_B_SUNBURST_SEX_CLAUSE in MODEL_B_SUNBURST_PROMPT
    assert MODEL_B_SUNBURST_SHORTS_CLAUSE in MODEL_B_SUNBURST_PROMPT
    assert MODEL_B_SUNBURST_MALE_PANTS_CLAUSE in MODEL_B_SUNBURST_PROMPT
    assert "replace the person's existing footwear" in low
    assert "if no footwear is shown in the design, preserve the original shoes" in low
    assert "preserve the person's original face" in low
    assert "person sex flag" in low
    assert "shorts" in low and "skirt" in low
    assert MODEL_B_SUNBURST_PROMPT_VERSION == "fitting-room-model-b-sunburst-v3"
    male = " ".join(sex_flag_design_hints("male")).lower()
    assert "person sex flag: male" in male
    assert "never a skirt" in male
    female = " ".join(sex_flag_design_hints("female")).lower()
    assert "person sex flag: female" in female


def test_model_b_shared_helper_person_then_design_one_call(monkeypatch):
    """Contract: model B, image order person→design, exactly one edit, no extras."""
    import openai as openai_mod

    from app.services.openai_person_garment_edit import (
        run_openai_person_garment_images_edit,
    )
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        wings_outdoor_person_png,
    )

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_settings.cache_clear()
    captured: dict = {}
    edit_calls = {"n": 0}

    class _FakeImages:
        def edit(self, **kwargs):
            edit_calls["n"] += 1
            captured.update(kwargs)
            out = floral_blue_look_plate_png()
            b64 = base64.b64encode(out).decode("ascii")

            class _Data:
                b64_json = b64
                url = None

            class _Resp:
                def __init__(self) -> None:
                    self.data = [_Data()]

            return _Resp()

    class _FakeClient:
        def __init__(self, *a, **k):
            self.images = _FakeImages()

        def with_options(self, **_k):
            return self

    monkeypatch.setattr(openai_mod, "OpenAI", _FakeClient)

    person = wings_outdoor_person_png()
    design = floral_blue_look_plate_png()
    png, meta = run_openai_person_garment_images_edit(
        person_png=person,
        design_png=design,
        model=MODEL_B_SUNBURST_MODEL,
        prompt=MODEL_B_SUNBURST_PROMPT,
        prompt_version=MODEL_B_SUNBURST_PROMPT_VERSION,
        path=MODEL_B_SUNBURST_PATH,
        quality="high",
    )
    assert png
    assert edit_calls["n"] == 1
    assert captured["model"] == MODEL_B_SUNBURST_MODEL
    assert captured["quality"] == "high"
    assert captured["n"] == 1
    images = captured["image"]
    assert len(images) == 2
    assert images[0][0] == "person.png"
    assert images[1][0] == "garment.png"
    assert images[0][1].getvalue() == person
    assert images[1][1].getvalue() == design
    assert meta["image_order"] == ["person", "garment"]
    assert meta["openai_calls"] == 1
    assert meta["paid_retries"] == 0
    assert meta["materialize"] is False
    assert meta["mask"] is False
    assert meta["face_patch"] is False
    assert meta["color_lock"] is False
    assert meta["identity_lock"] is False
    assert MODEL_B_SUNBURST_FOOTWEAR_CLAUSE in meta["prompt"]
    get_settings.cache_clear()


def test_preflight_model_b_available_when_flag_on_empty_allowlist_means_everyone(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(
        client, db_session, email="mb-pre@example.com", username="mb_pre"
    )
    _enable_fitting_room(monkeypatch)
    get_settings.cache_clear()
    r = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r.status_code == 200
    body = r.json()
    assert body["look_model_b_sunburst_available"] is False
    assert body["look_model_b_sunburst_model"] == MODEL_B_SUNBURST_MODEL

    # Flag on + empty allowlist = GA for everyone.
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "")
    get_settings.cache_clear()
    r2 = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r2.status_code == 200
    assert r2.json()["look_model_b_sunburst_available"] is True

    # Non-empty allowlist still restricts.
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "someone_else")
    get_settings.cache_clear()
    r3 = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r3.status_code == 200
    assert r3.json()["look_model_b_sunburst_available"] is False


def test_model_b_job_path_one_generation_no_materialize_no_fallback(
    client, db_session, monkeypatch
):
    import app.services.look_garment_normalize as lgn
    from app.services import fitting_room as fr
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        floral_blue_tryon_good_png,
        wings_outdoor_person_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "mb_owner")
    monkeypatch.setenv("FITTING_ROOM_LOOK_DIRECT_EDIT_V2_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_IDENTITY_LOCK_ENABLED", "false")
    get_settings.cache_clear()

    calls: list[str] = []

    def _materialize(**_k):
        calls.append("materialize")
        raise AssertionError("materialize must not run on Model B success")

    def _no_v2(*_a, **_k):
        calls.append("direct_edit_v2")
        raise AssertionError("direct-edit-v2 must not run when Model B succeeds")

    def _no_clone(*_a, **_k):
        calls.append("chatgpt_clone")
        raise AssertionError("chatgpt-clone must not run after Model B")

    def _no_lock(*_a, **_k):
        calls.append("color_lock")
        raise AssertionError("color lock must not run on Model B path")

    def _no_recover(*_a, **_k):
        calls.append("recover")
        raise AssertionError("paid recovery must not run on Model B path")

    def _model_b_edit(*, person_png, design_png, model, prompt, **_k):
        calls.append("model_b_edit")
        assert model == MODEL_B_SUNBURST_MODEL
        assert person_png and design_png
        assert MODEL_B_SUNBURST_FOOTWEAR_CLAUSE in prompt
        assert "preserve the original shoes" in prompt.lower()
        return floral_blue_tryon_good_png(), {
            "provider": "openai",
            "model": MODEL_B_SUNBURST_MODEL,
            "path": MODEL_B_SUNBURST_PATH,
            "prompt_version": MODEL_B_SUNBURST_PROMPT_VERSION,
            "prompt": prompt,
            "image_order": ["person", "garment"],
            "quality": "high",
            "size": "1024x1536",
            "openai_calls": 1,
            "paid_retries": 0,
            "preprocessing": "none",
            "postprocessing": "none",
            "identity_lock": False,
            "materialize": False,
            "color_lock": False,
            "mask": False,
            "face_patch": False,
        }

    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _materialize)
    monkeypatch.setattr(fr, "_run_direct_edit_v2_images_edit", _no_v2)
    monkeypatch.setattr(fr, "_run_chatgpt_clone_images_edit", _no_clone)
    monkeypatch.setattr(fr, "lock_result_to_palette", _no_lock)
    monkeypatch.setattr(fr, "_recover_illustrated_look_tryon", _no_recover)
    monkeypatch.setattr(
        "app.services.openai_person_garment_edit.run_openai_person_garment_images_edit",
        _model_b_edit,
    )
    set_try_on_provider_override(None)

    tokens = register_with_invite(
        client, db_session, email="mb-owner@example.com", username="mb_owner"
    )
    _grant_stars(db_session, "mb_owner", amount=40)
    body = _look_body(
        look_png=floral_blue_look_plate_png(),
        person_png=wings_outdoor_person_png(),
        prefer_model_b=True,
    )
    r = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r.status_code == 201, r.text
    job_id = uuid.UUID(r.json()["id"])
    job = db_session.get(AIJob, job_id)
    assert job is not None
    assert job.input_data.get("prefer_model_b_sunburst") is True

    before = db_session.query(User).filter(User.username == "mb_owner").one().ai_stars
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job_id)
    assert job.status == "completed", job.error_message
    result = job.result_data or {}
    assert result.get("fitting_room_look_path") == MODEL_B_SUNBURST_PATH
    assert result.get("model") == MODEL_B_SUNBURST_MODEL
    assert result.get("model_b_sunburst") is True
    assert result.get("image_order") == ["person", "garment"]
    assert result.get("openai_calls") == 1
    assert result.get("paid_retries") == 0
    assert result.get("materialize") is False
    assert result.get("mask") is False
    assert result.get("face_patch") is False
    assert result.get("color_lock") is False
    assert result.get("look_color_lock_final", {}).get("reason") == "skipped_model_b_sunburst"
    assert calls == ["model_b_edit"]
    after = db_session.query(User).filter(User.username == "mb_owner").one().ai_stars
    assert after == before - 20


def test_model_b_restricted_allowlist_blocks_non_listed_user(
    client, db_session, monkeypatch
):
    """When an allowlist is set, non-listed users cannot activate Model B."""
    from app.services import fitting_room as fr
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        floral_blue_tryon_good_png,
        wings_outdoor_person_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "real_owner_only")
    monkeypatch.setenv("FITTING_ROOM_LOOK_DIRECT_EDIT_V2_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", "false")
    get_settings.cache_clear()

    model_b_calls = {"n": 0}

    def _spy_model_b(*_a, **_k):
        model_b_calls["n"] += 1
        raise AssertionError("Model B must not run for non-allowlisted users")

    def _direct_v2(*, person_png, look_png, prompt, identity_lock=False):
        return floral_blue_tryon_good_png(), {
            "provider": "openai_images_edit",
            "model": "chatgpt-image-latest",
            "direct_edit_v2": True,
            "chatgpt_clone": True,
            "image_order": ["person", "garment"],
            "fitting_room_look_path": "chatgpt_direct_edit_v2",
        }

    monkeypatch.setattr(fr, "_try_model_b_sunburst_look_fit", _spy_model_b)
    monkeypatch.setattr(fr, "_run_direct_edit_v2_images_edit", _direct_v2)
    set_try_on_provider_override(None)

    tokens = register_with_invite(
        client, db_session, email="mb-stranger@example.com", username="mb_stranger"
    )
    _grant_stars(db_session, "mb_stranger", amount=40)

    r_pf = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r_pf.status_code == 200
    assert r_pf.json()["look_model_b_sunburst_available"] is False

    body = _look_body(
        look_png=floral_blue_look_plate_png(),
        person_png=wings_outdoor_person_png(),
        prefer_model_b=True,
    )
    r = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r.status_code == 201, r.text
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(r.json()["id"]))
    assert job.status == "completed", job.error_message
    assert (job.result_data or {}).get("fitting_room_look_path") == "chatgpt_direct_edit_v2"
    assert model_b_calls["n"] == 0


def test_model_b_default_path_without_prefer_when_enabled(
    client, db_session, monkeypatch
):
    """Flag on + empty allowlist uses Model B by default (prefer not required)."""
    from app.services import fitting_room as fr
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        floral_blue_tryon_good_png,
        wings_outdoor_person_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "")
    monkeypatch.setenv("FITTING_ROOM_LOOK_DIRECT_EDIT_V2_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", "false")
    monkeypatch.setenv("FITTING_ROOM_LOOK_IDENTITY_LOCK_ENABLED", "false")
    get_settings.cache_clear()

    calls: list[str] = []

    def _model_b_ok(*_a, **_k):
        calls.append("model_b")
        return (
            floral_blue_tryon_good_png(),
            {
                "provider": "openai_images_edit",
                "model": MODEL_B_SUNBURST_MODEL,
                "fitting_room_look_path": MODEL_B_SUNBURST_PATH,
                "openai_calls": 1,
            },
            "openai",
            None,
        )

    def _no_v2(*_a, **_k):
        calls.append("direct_edit_v2")
        raise AssertionError("direct-edit-v2 must not run when Model B is default")

    monkeypatch.setattr(fr, "_try_model_b_sunburst_look_fit", _model_b_ok)
    monkeypatch.setattr(fr, "_try_direct_edit_v2_look_fit", _no_v2)
    set_try_on_provider_override(None)

    tokens = register_with_invite(
        client, db_session, email="mb-ga@example.com", username="mb_ga"
    )
    _grant_stars(db_session, "mb_ga", amount=40)
    body = _look_body(
        look_png=floral_blue_look_plate_png(),
        person_png=wings_outdoor_person_png(),
        prefer_model_b=False,
    )
    r = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r.status_code == 201, r.text
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(r.json()["id"]))
    assert job.status == "completed", job.error_message
    assert (job.result_data or {}).get("fitting_room_look_path") == MODEL_B_SUNBURST_PATH
    assert calls == ["model_b"]


def test_model_b_fail_closed_no_paid_fallback(client, db_session, monkeypatch):
    import app.services.look_garment_normalize as lgn
    from app.services import fitting_room as fr
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        wings_outdoor_person_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "mb_fail")
    monkeypatch.setenv("FITTING_ROOM_LOOK_DIRECT_EDIT_V2_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", "true")
    get_settings.cache_clear()

    calls: list[str] = []

    def _boom(*_a, **_k):
        calls.append("model_b")
        raise RuntimeError("provider down")

    def _no_materialize(**_k):
        calls.append("materialize")
        raise AssertionError("no materialize after Model B fail")

    def _no_v2(*_a, **_k):
        calls.append("direct_v2")
        raise AssertionError("no direct-edit-v2 after Model B fail")

    monkeypatch.setattr(
        "app.services.openai_person_garment_edit.run_openai_person_garment_images_edit",
        _boom,
    )
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _no_materialize)
    monkeypatch.setattr(fr, "_run_direct_edit_v2_images_edit", _no_v2)
    set_try_on_provider_override(None)

    tokens = register_with_invite(
        client, db_session, email="mb-fail@example.com", username="mb_fail"
    )
    _grant_stars(db_session, "mb_fail", amount=40)
    before = db_session.query(User).filter(User.username == "mb_fail").one().ai_stars
    body = _look_body(
        look_png=floral_blue_look_plate_png(),
        person_png=wings_outdoor_person_png(),
        prefer_model_b=True,
    )
    r = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r.status_code == 201, r.text
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(r.json()["id"]))
    assert job.status == "failed"
    assert (job.result_data or {}).get("error_code") == "MODEL_B_SUNBURST_FAILED"
    assert calls == ["model_b"]
    after = db_session.query(User).filter(User.username == "mb_fail").one().ai_stars
    assert after == before  # no Stars on failure


def test_model_b_idempotency_unchanged(client, db_session, monkeypatch):
    from app.services import fitting_room as fr
    from tests.look_test_images import (
        floral_blue_look_plate_png,
        floral_blue_tryon_good_png,
        wings_outdoor_person_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_MODEL_B_SUNBURST_OWNER_ALLOWLIST", "mb_idem")
    get_settings.cache_clear()

    def _ok(*_a, **_k):
        return floral_blue_tryon_good_png(), {
            "provider": "openai",
            "model": MODEL_B_SUNBURST_MODEL,
            "path": MODEL_B_SUNBURST_PATH,
            "prompt_version": MODEL_B_SUNBURST_PROMPT_VERSION,
            "prompt": MODEL_B_SUNBURST_PROMPT,
            "image_order": ["person", "garment"],
            "openai_calls": 1,
            "paid_retries": 0,
            "materialize": False,
            "mask": False,
            "face_patch": False,
            "color_lock": False,
            "identity_lock": False,
        }

    monkeypatch.setattr(
        "app.services.openai_person_garment_edit.run_openai_person_garment_images_edit",
        _ok,
    )
    set_try_on_provider_override(None)

    tokens = register_with_invite(
        client, db_session, email="mb-idem@example.com", username="mb_idem"
    )
    _grant_stars(db_session, "mb_idem", amount=80)
    key = f"fitting_room:{uuid.uuid4()}"
    body = _look_body(
        look_png=floral_blue_look_plate_png(),
        person_png=wings_outdoor_person_png(),
        prefer_model_b=True,
    )
    body["idempotency_key"] = key
    r1 = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    r2 = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(r1.json()["id"]))
    assert job.status == "completed"
    # Replay enqueue must not create a second job / second charge path.
    count = (
        db_session.query(AIJob)
        .filter(
            AIJob.job_type == FITTING_ROOM_JOB_TYPE,
            AIJob.input_data["idempotency_key"].astext == key,
        )
        .count()
    )
    assert count == 1
    _ = fr  # keep import used for module side-effects / clarity
