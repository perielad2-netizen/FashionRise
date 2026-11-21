"""Owner-only Fitting Room model compare — mocked only, no paid HTTP."""

from __future__ import annotations

import base64
import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from tests.auth_test_helpers import register_with_invite
from tests.look_test_images import floral_blue_look_plate_png, wings_outdoor_person_png

COMPARE = "/api/v1/ai/fitting-room/model-compare"


def _b64(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enable_compare(monkeypatch, *, username: str = "owner_cmp"):
    get_settings.cache_clear()
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "false")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_OWNER_ALLOWLIST", username)
    get_settings.cache_clear()


def test_compare_prompt_is_short_and_identity_first():
    from app.services.fitting_room_model_compare import COMPARE_PROMPT, COMPARE_PROMPT_VERSION

    assert COMPARE_PROMPT_VERSION == "fitting-room-model-compare-v1"
    assert len(COMPARE_PROMPT) < 400
    low = COMPARE_PROMPT.lower()
    assert "image 2" in low and "image 1" in low
    assert "preserve the person's original face" in low
    assert "do not change anything else" in low
    # No enormous instruction dump / footwear essays.
    assert "black sketch outlines" not in low


def test_dry_run_plans_three_arms_without_paid_calls(client, db_session, monkeypatch):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_cmp")
    calls: list[str] = []

    def _no_openai(**_k):
        calls.append("openai")
        raise AssertionError("dry-run must not call OpenAI")

    def _no_fashn(**_k):
        calls.append("fashn")
        raise AssertionError("dry-run must not call FASHN")

    cmp.set_model_compare_runners_for_tests(openai_runner=_no_openai, fashn_runner=_no_fashn)
    tokens = register_with_invite(
        client, db_session, email="owner_cmp@example.com", username="owner_cmp"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": _b64(wings_outdoor_person_png()),
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "authorize_paid": False,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "dry_run"
    assert body["paid_calls"] == 0
    assert body["stars_touched"] is False
    assert body["human_review"]["winner"] is None
    arms = {a["arm"]: a for a in body["arms"]}
    assert set(arms) == {"A", "B", "C"}
    assert arms["A"]["model"] == "chatgpt-image-latest"
    assert arms["B"]["model"] == "gpt-image-2.6-sunburst"
    assert arms["C"]["model"] == "tryon-max"
    assert all(a["preprocessing"] == "none" for a in body["arms"])
    assert all(a["postprocessing"] == "none" for a in body["arms"])
    assert calls == []
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_non_owner_forbidden(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="someone_else")
    tokens = register_with_invite(
        client, db_session, email="norm@example.com", username="norm_user"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": _b64(wings_outdoor_person_png()),
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "authorize_paid": False,
        },
    )
    assert r.status_code == 403
    get_settings.cache_clear()


def test_authorize_paid_without_live_http_forbidden(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_paid")
    # live_http false
    tokens = register_with_invite(
        client, db_session, email="owner_paid@example.com", username="owner_paid"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": _b64(wings_outdoor_person_png()),
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "authorize_paid": True,
            "arms": ["A"],
        },
    )
    assert r.status_code == 403
    get_settings.cache_clear()


def test_authorize_paid_runs_one_call_per_arm_mocked(client, db_session, monkeypatch, tmp_path):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_live")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    get_settings.cache_clear()

    def _png(color) -> bytes:
        im = Image.new("RGB", (64, 96), color)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()

    def _openai(*, person_png, design_png, model):
        assert person_png and design_png
        assert model in {"chatgpt-image-latest", "gpt-image-2.6-sunburst"}
        return _png((40, 120, 220)), {
            "provider": "openai",
            "model": model,
            "path": "openai_images_edit_person_garment",
            "duration_ms": 12,
            "estimate_cents": 6,
            "openai_calls": 1,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    def _fashn(*, person_png, design_png):
        assert person_png and design_png
        return _png((220, 80, 160)), {
            "provider": "fashn",
            "model": "tryon-max",
            "path": "fashn_tryon_max_raw_person_product",
            "duration_ms": 20,
            "estimate_cents": 32,
            "fashn_calls": 1,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_openai, fashn_runner=_fashn)
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    tokens = register_with_invite(
        client, db_session, email="owner_live@example.com", username="owner_live"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": _b64(wings_outdoor_person_png()),
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "authorize_paid": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["paid_calls"] == 3
    assert body["stars_touched"] is False
    assert body["human_review"]["winner"] is None
    for arm in body["arms"]:
        assert arm["status"] == "ok"
        assert arm["result_url"]
        assert arm["meta"]["preprocessing"] == "none"
        assert arm["meta"]["postprocessing"] == "none"
        assert arm["meta"].get("identity_lock") in (False, None)
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_preflight_lists_arms(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_pf")
    tokens = register_with_invite(
        client, db_session, email="owner_pf@example.com", username="owner_pf"
    )
    r = client.get(f"{COMPARE}/preflight", headers=_auth(tokens))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "preflight"
    assert len(body["arms"]) == 3
    assert "Face" in body["human_review"]["instruction"] or "face" in body["human_review"]["instruction"].lower()
    get_settings.cache_clear()
