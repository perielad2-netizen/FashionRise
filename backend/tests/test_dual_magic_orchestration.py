"""WEB-V4J Stage C: dual-side Magic orchestration (offline; mocked prompts only)."""

from __future__ import annotations

import base64
from uuid import UUID, uuid4

import pytest

from app.models.ai_job import AIJob
from app.services import sketch_openai
from tests.auth_test_helpers import register_with_invite

_TINY_PNG = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
).decode("ascii")
_DATA_URL = f"data:image/png;base64,{_TINY_PNG}"


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _dual_payload(**overrides):
    body = {
        "front": {"image_base64": _DATA_URL, "idempotency_key": f"front-{uuid4().hex[:8]}"},
        "back": {"image_base64": _DATA_URL, "idempotency_key": f"back-{uuid4().hex[:8]}"},
        "shared_garment_spec": {"silhouette": "A-line dress", "main_colors": ["coral", "ivory"]},
        "reference_model_id": "female",
        "notes": "dual magic test",
    }
    body.update(overrides)
    return body


def test_dual_enqueue_creates_two_jobs_same_operation(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_a@example.com", "dual_a")
    body = _dual_payload()
    r = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    op = data["magic_operation_id"]
    front = data["front_job"]
    back = data["back_job"]
    assert front["id"] != back["id"]
    assert front["job_type"] == "sketch_polish"
    assert back["job_type"] == "sketch_polish"
    assert front["input_data"]["studio_side"] == "front"
    assert back["input_data"]["studio_side"] == "back"
    assert front["input_data"]["magic_operation_id"] == op
    assert back["input_data"]["magic_operation_id"] == op
    assert front["input_data"].get("shared_garment_spec") == body["shared_garment_spec"]


def test_dual_idempotent_retry_does_not_duplicate(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_b@example.com", "dual_b")
    body = _dual_payload()
    first = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert first.status_code == 201
    second = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert second.status_code == 201
    assert first.json()["front_job"]["id"] == second.json()["front_job"]["id"]
    assert first.json()["back_job"]["id"] == second.json()["back_job"]["id"]
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 2


def test_one_sided_polish_unchanged(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_c@example.com", "dual_c")
    r = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={"input_data": {"notes": "polish concept", "image_base64": _DATA_URL}},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["job_type"] == "sketch_polish"
    assert "studio_side" not in job["input_data"]


def test_single_polish_idempotency_key(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_d@example.com", "dual_d")
    payload = {
        "input_data": {
            "notes": "polish concept",
            "image_base64": _DATA_URL,
            "idempotency_key": "idem-single-1",
        }
    }
    a = client.post("/api/v1/ai/sketch/polish", headers=_auth(tokens), json=payload)
    b = client.post("/api/v1/ai/sketch/polish", headers=_auth(tokens), json=payload)
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["id"] == b.json()["id"]


def test_invalid_studio_side_rejected(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_e@example.com", "dual_e")
    r = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "left",
            }
        },
    )
    assert r.status_code == 422


def test_partial_failure_retry_back_with_new_key(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_f@example.com", "dual_f")
    op = str(uuid4())
    front_key = "partial-front"
    back_key_fail = "partial-back-fail"
    body = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": front_key},
        back={"image_base64": _DATA_URL, "idempotency_key": back_key_fail},
    )
    created = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert created.status_code == 201
    front_id = created.json()["front_job"]["id"]
    back_id = created.json()["back_job"]["id"]

    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    front_row = db_session.get(AIJob, UUID(front_id))
    back_row = db_session.get(AIJob, UUID(back_id))
    front_row.status = "completed"
    back_row.status = "failed"
    back_row.error_message = "sketch image edit failed"
    db_session.commit()

    retry_body = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": front_key},
        back={"image_base64": _DATA_URL, "idempotency_key": "partial-back-retry"},
    )
    retried = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=retry_body)
    assert retried.status_code == 201
    assert retried.json()["front_job"]["id"] == front_id
    assert retried.json()["back_job"]["id"] != back_id
    assert retried.json()["back_job"]["status"] == "queued"

    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 3


def test_sequential_enqueue_linked_by_operation_id(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_g@example.com", "dual_g")
    op = str(uuid4())
    shared = {"silhouette": "wrap skirt", "hem": "midi"}
    front = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "front",
                "magic_operation_id": op,
                "shared_garment_spec": shared,
                "idempotency_key": "seq-front",
            }
        },
    )
    back = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "shared_garment_spec": shared,
                "idempotency_key": "seq-back",
            }
        },
    )
    assert front.status_code == 201 and back.status_code == 201
    assert front.json()["input_data"]["magic_operation_id"] == op
    assert back.json()["input_data"]["magic_operation_id"] == op


def test_back_side_prompt_language():
    from types import SimpleNamespace

    job = SimpleNamespace(
        id=uuid4(),
        job_type="sketch_polish",
        input_data={
            "studio_side": "back",
            "shared_garment_spec": {"garment_category": "evening gown"},
            "notes": "polish back",
        },
    )
    user_text = sketch_openai._user_text(job)
    assert "REAR" in user_text or "rear" in user_text
    assert "back" in user_text.lower()
    assert "SHARED GARMENT SPEC" in user_text
    assert "evening gown" in user_text or "garment_category" in user_text

    prompt = sketch_openai._build_image_prompt({"image_prompt": "back straps"}, "summary", job)
    assert "rear" in prompt.lower() or "back" in prompt.lower()
    assert "front-facing sketch" in prompt.lower() or "not a front" in prompt.lower()
    assert "SHARED GARMENT SPEC" in prompt or "evening gown" in prompt


def test_front_side_prompt_does_not_claim_rear():
    from types import SimpleNamespace

    job = SimpleNamespace(
        id=uuid4(),
        job_type="sketch_polish",
        input_data={"studio_side": "front", "notes": "polish front"},
    )
    user_text = sketch_openai._user_text(job)
    assert "front" in user_text.lower()
    assert "not" in user_text.lower() and "rear" in user_text.lower()


def test_sketch_openai_has_no_pose_lock_packing():
    import inspect

    source = inspect.getsource(sketch_openai)
    assert "pose_lock" not in source.replace("PR #41 pose_lock", "")


@pytest.mark.parametrize("path", ["front", "back"])
def test_dual_side_payload_requires_image(path: str, client, db_session):
    tokens = register_with_invite(client, db_session, f"dual_bad_{path}@example.com", "dual_bad")
    body = {"front": {"notes": "x"}, "back": {"notes": "y"}}
    body[path] = {"notes": "no image"}
    r = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert r.status_code == 422
