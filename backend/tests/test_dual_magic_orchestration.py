"""WEB-V4J Stage C: dual-side Magic orchestration (offline; mocked prompts only)."""

from __future__ import annotations

import base64
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models.ai_job import AIJob
from app.models.user import User
from app.schemas.ai import SketchPolishDualBody
from app.services import ai_service, sketch_openai
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
        "magic_operation_id": str(uuid4()),
        "source_revision": 3,
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
    assert front["input_data"].get("source_revision") == 3
    assert back["input_data"].get("source_revision") == 3
    assert front["input_data"].get("image_fingerprint")
    assert front["input_data"]["image_fingerprint"] == back["input_data"]["image_fingerprint"]


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


def test_recovery_get_magic_operation_jobs(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_rec@example.com", "dual_rec")
    body = _dual_payload()
    created = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert created.status_code == 201
    op = created.json()["magic_operation_id"]
    listed = client.get(f"/api/v1/ai/magic-operations/{op}/jobs", headers=_auth(tokens))
    assert listed.status_code == 200
    jobs = listed.json()["jobs"]
    assert len(jobs) == 2
    ids = {j["id"] for j in jobs}
    assert created.json()["front_job"]["id"] in ids
    assert created.json()["back_job"]["id"] in ids


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


def test_single_polish_idempotency_mismatch_image_409(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_d2@example.com", "dual_d2")
    other_png = base64.b64encode(b"\x89PNG diff bytes").decode("ascii")
    other_url = f"data:image/png;base64,{other_png}"
    base = {
        "input_data": {
            "image_base64": _DATA_URL,
            "idempotency_key": "idem-mismatch",
            "magic_operation_id": str(uuid4()),
            "source_revision": 1,
        }
    }
    assert client.post("/api/v1/ai/sketch/polish", headers=_auth(tokens), json=base).status_code == 201
    clash = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={**base, "input_data": {**base["input_data"], "image_base64": other_url}},
    )
    assert clash.status_code == 409


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

    # Identical failed-key replay creates zero new jobs.
    replay = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert replay.status_code == 201
    assert replay.json()["front_job"]["id"] == front_id
    assert replay.json()["back_job"]["id"] == back_id
    assert replay.json()["back_job"]["status"] == "failed"

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


def test_dual_rejects_fresh_keys_while_side_still_active(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_active@example.com", "dual_active")
    op = str(uuid4())
    first = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": "active-front"},
        back={"image_base64": _DATA_URL, "idempotency_key": "active-back"},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=first).status_code == 201
    second = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": "active-front-2"},
        back={"image_base64": _DATA_URL, "idempotency_key": "active-back-2"},
    )
    clash = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=second)
    assert clash.status_code == 409
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 2


def test_dual_prompt_identity_mismatch_409(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_prompt@example.com", "dual_prompt")
    op = str(uuid4())
    body = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": "prompt-front"},
        back={"image_base64": _DATA_URL, "idempotency_key": "prompt-back"},
        shared_garment_spec={"silhouette": "A-line dress"},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 201
    clash = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": "prompt-front"},
        back={"image_base64": _DATA_URL, "idempotency_key": "prompt-back"},
        shared_garment_spec={"silhouette": "column gown"},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=clash).status_code == 409


def test_failed_single_polish_key_replay_creates_zero_jobs(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_fail_replay@example.com", "dual_fail_r")
    payload = {
        "input_data": {
            "image_base64": _DATA_URL,
            "idempotency_key": "fail-single-1",
            "notes": "polish concept",
        }
    }
    first = client.post("/api/v1/ai/sketch/polish", headers=_auth(tokens), json=payload)
    assert first.status_code == 201
    job_id = first.json()["id"]
    row = db_session.get(AIJob, UUID(job_id))
    row.status = "failed"
    row.error_message = "provider failed"
    db_session.commit()

    second = client.post("/api/v1/ai/sketch/polish", headers=_auth(tokens), json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == job_id
    assert second.json()["status"] == "failed"
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 1


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
                "source_revision": 2,
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
                "source_revision": 2,
            }
        },
    )
    assert front.status_code == 201 and back.status_code == 201
    assert front.json()["input_data"]["magic_operation_id"] == op
    assert back.json()["input_data"]["magic_operation_id"] == op


def test_linked_polish_requires_idempotency_key(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_nokey@example.com", "dual_nokey")
    r = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": str(uuid4()),
                "source_revision": 1,
                "shared_garment_spec": {"silhouette": "dress"},
            }
        },
    )
    assert r.status_code == 422


def test_linked_polish_back_retry_one_new_job_preserves_front(client, db_session):
    """FE-style path: dual enqueue → Back fails → POST /polish retry with new key."""
    tokens = register_with_invite(client, db_session, "dual_retry_polish@example.com", "dual_rp")
    op = str(uuid4())
    front_key = "rp-front"
    back_fail_key = "rp-back-fail"
    body = _dual_payload(
        magic_operation_id=op,
        content_fingerprint="fp-stable-1",
        front={"image_base64": _DATA_URL, "idempotency_key": front_key},
        back={"image_base64": _DATA_URL, "idempotency_key": back_fail_key},
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
    db_session.commit()

    shared = body["shared_garment_spec"]
    # Same failed key via /polish → zero new jobs (identity must match original).
    replay = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": back_fail_key,
                "source_revision": body["source_revision"],
                "content_fingerprint": "fp-stable-1",
                "shared_garment_spec": shared,
                "reference_model_id": body["reference_model_id"],
                "notes": body["notes"],
            }
        },
    )
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == back_id
    assert replay.json()["status"] == "failed"

    retry_key = "rp-back-retry-1"
    retry = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": retry_key,
                "source_revision": body["source_revision"],
                "content_fingerprint": "fp-stable-1",
                "shared_garment_spec": shared,
                "reference_model_id": body["reference_model_id"],
                "notes": "polish concept (back) retry",
            }
        },
    )
    assert retry.status_code == 201
    assert retry.json()["id"] != back_id
    assert retry.json()["status"] == "queued"
    assert retry.json()["input_data"]["studio_side"] == "back"

    # Replay retry key → same job (must match attempt identity incl. notes).
    retry_again = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": retry_key,
                "source_revision": body["source_revision"],
                "content_fingerprint": "fp-stable-1",
                "shared_garment_spec": shared,
                "reference_model_id": body["reference_model_id"],
                "notes": "polish concept (back) retry",
            }
        },
    )
    assert retry_again.status_code == 201, retry_again.text
    assert retry_again.json()["id"] == retry.json()["id"]

    # Changed design fingerprint → reject new attempt key.
    drift = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": "rp-back-retry-2",
                "source_revision": body["source_revision"],
                "content_fingerprint": "fp-CHANGED",
                "shared_garment_spec": shared,
                "reference_model_id": body["reference_model_id"],
            }
        },
    )
    # Latest back is queued (active) — blocked before identity, OR if we mark failed first...
    assert drift.status_code == 409

    # Mark retry failed, then drift fingerprint must 409 for operation identity.
    retry_row = db_session.get(AIJob, UUID(retry.json()["id"]))
    retry_row.status = "failed"
    db_session.commit()
    drift2 = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": "rp-back-retry-2",
                "source_revision": body["source_revision"],
                "content_fingerprint": "fp-CHANGED",
                "shared_garment_spec": shared,
                "reference_model_id": body["reference_model_id"],
            }
        },
    )
    assert drift2.status_code == 409
    assert drift2.json()["detail"]["payload"]["reason"] == "operation_identity_mismatch"

    # Front remains the original completed job — never regenerated.
    listed = client.get(f"/api/v1/ai/magic-operations/{op}/jobs", headers=_auth(tokens))
    assert listed.status_code == 200
    fronts = [j for j in listed.json()["jobs"] if j["input_data"].get("studio_side") == "front"]
    assert len(fronts) == 1
    assert fronts[0]["id"] == front_id
    assert fronts[0]["status"] == "completed"

    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 3  # front + failed back + one retry back


def test_linked_polish_rejects_new_key_while_side_active(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_link_active@example.com", "dual_la")
    op = str(uuid4())
    first = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "front",
                "magic_operation_id": op,
                "idempotency_key": "la-front-1",
                "source_revision": 1,
                "shared_garment_spec": {"silhouette": "coat"},
            }
        },
    )
    assert first.status_code == 201
    clash = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "front",
                "magic_operation_id": op,
                "idempotency_key": "la-front-2",
                "source_revision": 1,
                "shared_garment_spec": {"silhouette": "coat"},
            }
        },
    )
    assert clash.status_code == 409
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 1


def test_dual_missing_shared_garment_spec_422(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_miss@example.com", "dual_miss")
    body = _dual_payload()
    body.pop("shared_garment_spec")
    r = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert r.status_code == 422


def test_dual_missing_keys_422(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_keys@example.com", "dual_keys")
    body = _dual_payload()
    body.pop("magic_operation_id")
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 422
    body = _dual_payload()
    body.pop("source_revision")
    body.pop("content_fingerprint", None)
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 422
    body = _dual_payload()
    body["front"] = {"image_base64": _DATA_URL}
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 422


def test_dual_idempotency_identity_mismatch_409(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_409@example.com", "dual_409")
    op = str(uuid4())
    body = _dual_payload(
        magic_operation_id=op,
        front={"image_base64": _DATA_URL, "idempotency_key": "idem-front-x"},
        back={"image_base64": _DATA_URL, "idempotency_key": "idem-back-x"},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 201
    clash = _dual_payload(
        magic_operation_id=op,
        source_revision=99,
        front={"image_base64": _DATA_URL, "idempotency_key": "idem-front-x"},
        back={"image_base64": _DATA_URL, "idempotency_key": "idem-back-x"},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=clash).status_code == 409


def test_dual_cross_side_key_reuse_422(client, db_session):
    tokens = register_with_invite(client, db_session, "dual_xside@example.com", "dual_xside")
    key = "same-key-both-sides"
    body = _dual_payload(
        front={"image_base64": _DATA_URL, "idempotency_key": key},
        back={"image_base64": _DATA_URL, "idempotency_key": key},
    )
    assert client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body).status_code == 422


def test_concurrent_dual_enqueue_two_jobs_total(engine):
    """Postgres advisory-lock coverage: parallel polish-dual cannot insert duplicate jobs."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    email = f"dual_conc_{uuid.uuid4().hex[:8]}@example.com"
    username = f"dconc_{uuid.uuid4().hex[:8]}"

    bootstrap = SessionLocal()
    try:
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            is_admin=False,
        )
        bootstrap.add(user)
        bootstrap.commit()
        bootstrap.refresh(user)
        user_id = user.id
    finally:
        bootstrap.close()

    op = uuid4()
    front_key = "conc-front"
    back_key = "conc-back"
    body = SketchPolishDualBody.model_validate(
        {
            "magic_operation_id": str(op),
            "source_revision": 1,
            "front": {"image_base64": _DATA_URL, "idempotency_key": front_key},
            "back": {"image_base64": _DATA_URL, "idempotency_key": back_key},
            "shared_garment_spec": {"silhouette": "gown", "notes": "concurrent"},
        }
    )

    def worker(_: int) -> tuple[str, str]:
        session = SessionLocal()
        try:
            u = session.get(User, user_id)
            assert u is not None
            front_job, back_job, _ = ai_service.enqueue_dual_sketch_polish(session, u, body)
            return str(front_job.id), str(back_job.id)
        finally:
            session.close()

    pairs: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(8)]
        for fut in as_completed(futures):
            pairs.append(fut.result())

    front_ids = {p[0] for p in pairs}
    back_ids = {p[1] for p in pairs}
    assert len(front_ids) == 1
    assert len(back_ids) == 1

    verify = SessionLocal()
    try:
        count = (
            verify.query(AIJob)
            .filter(AIJob.user_id == user_id, AIJob.job_type == "sketch_polish")
            .count()
        )
        assert count == 2
        for row in verify.query(AIJob).filter(AIJob.user_id == user_id).all():
            verify.delete(row)
        u = verify.get(User, user_id)
        if u:
            verify.delete(u)
        verify.commit()
    finally:
        verify.close()


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
    body = _dual_payload()
    body[path] = {"idempotency_key": f"missing-img-{path}", "notes": "no image"}
    r = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert r.status_code == 422


def test_dual_magic_mocked_e2e_complete_retry_recover(client, db_session, monkeypatch):
    """Integrated Dual Magic path with mocked OpenAI: 2 jobs → Back fail → 1 Back retry."""
    tokens = register_with_invite(client, db_session, "dual_e2e@example.com", "dual_e2e")
    op = str(uuid4())
    body = _dual_payload(
        magic_operation_id=op,
        content_fingerprint="e2e-fp-1",
        front={"image_base64": _DATA_URL, "idempotency_key": f"{op}:front"},
        back={"image_base64": _DATA_URL, "idempotency_key": f"{op}:back"},
    )
    created = client.post("/api/v1/ai/sketch/polish-dual", headers=_auth(tokens), json=body)
    assert created.status_code == 201
    front_id = created.json()["front_job"]["id"]
    back_id = created.json()["back_job"]["id"]

    def _fake_complete(job: AIJob) -> dict:
        side = (job.input_data or {}).get("studio_side")
        if side == "back" and str(job.id) == back_id:
            raise sketch_openai.SketchCompletionError("mock back failure")
        return {
            "summary": f"{side} look",
            "image_url": f"http://127.0.0.1:8001/static/uploads/ai/{job.id}.png",
            "image_provenance": "images.edit",
        }

    monkeypatch.setattr(sketch_openai, "complete_sketch_job", _fake_complete)

    # Simulate worker completing Front and failing Back.
    front_row = db_session.get(AIJob, UUID(front_id))
    back_row = db_session.get(AIJob, UUID(back_id))
    try:
        front_row.result_data = sketch_openai.complete_sketch_job(front_row)
        front_row.status = "completed"
    except sketch_openai.SketchCompletionError as exc:
        front_row.status = "failed"
        front_row.error_message = str(exc)
    try:
        back_row.result_data = sketch_openai.complete_sketch_job(back_row)
        back_row.status = "completed"
    except sketch_openai.SketchCompletionError as exc:
        back_row.status = "failed"
        back_row.error_message = str(exc)
    db_session.commit()

    assert db_session.get(AIJob, UUID(front_id)).status == "completed"
    assert db_session.get(AIJob, UUID(back_id)).status == "failed"

    retry_key = f"{op}:back:retry:e2e1"
    retry = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": retry_key,
                "source_revision": body["source_revision"],
                "content_fingerprint": "e2e-fp-1",
                "shared_garment_spec": body["shared_garment_spec"],
                "reference_model_id": body["reference_model_id"],
            }
        },
    )
    assert retry.status_code == 201
    retry_id = retry.json()["id"]
    assert retry_id != back_id

    # Replay / lost-response: zero duplicates.
    replay = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "image_base64": _DATA_URL,
                "studio_side": "back",
                "magic_operation_id": op,
                "idempotency_key": retry_key,
                "source_revision": body["source_revision"],
                "content_fingerprint": "e2e-fp-1",
                "shared_garment_spec": body["shared_garment_spec"],
                "reference_model_id": body["reference_model_id"],
            }
        },
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == retry_id

    retry_row = db_session.get(AIJob, UUID(retry_id))
    retry_row.result_data = {
        "summary": "back look retry",
        "image_url": f"http://127.0.0.1:8001/static/uploads/ai/{retry_id}.png",
        "image_provenance": "images.edit",
    }
    retry_row.status = "completed"
    db_session.commit()

    listed = client.get(f"/api/v1/ai/magic-operations/{op}/jobs", headers=_auth(tokens))
    assert listed.status_code == 200
    jobs = listed.json()["jobs"]
    assert len(jobs) == 3
    by_side: dict[str, list] = {"front": [], "back": []}
    for j in jobs:
        by_side[j["input_data"]["studio_side"]].append(j)
    assert len(by_side["front"]) == 1
    assert by_side["front"][0]["id"] == front_id
    assert by_side["front"][0]["status"] == "completed"
    assert len(by_side["back"]) == 2
    back_ids = {j["id"] for j in by_side["back"]}
    assert back_ids == {back_id, retry_id}
    assert next(j for j in by_side["back"] if j["id"] == retry_id)["status"] == "completed"
    assert next(j for j in by_side["back"] if j["id"] == back_id)["status"] == "failed"

    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    count = (
        db_session.query(AIJob)
        .filter(AIJob.user_id == UUID(me["id"]), AIJob.job_type == "sketch_polish")
        .count()
    )
    assert count == 3
