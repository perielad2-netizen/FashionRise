"""Authenticated AI job image retrieval — no OpenAI, no public upload dependency."""

from __future__ import annotations

import base64
import io
import uuid

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    # Minimal valid 1×1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def test_job_image_requires_owner(client, db_session):
    a = register_with_invite(client, db_session, "img_a@example.com", "img_a")
    b = register_with_invite(client, db_session, "img_b@example.com", "img_b")
    me = client.get("/api/v1/auth/me", headers=_auth(a)).json()

    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    url = storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")

    job = AIJob(
        user_id=uuid.UUID(me["id"]),
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"notes": "polish concept"},
        result_data={"summary": "ok", "image_url": url, "pipeline": "sketch_polish"},
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    ok = client.get(f"/api/v1/ai/jobs/{job.id}/image", headers=_auth(a))
    assert ok.status_code == 200, ok.text
    assert ok.headers.get("content-type", "").startswith("image/")
    assert ok.content[:8] == b"\x89PNG\r\n\x1a\n"

    denied = client.get(f"/api/v1/ai/jobs/{job.id}/image", headers=_auth(b))
    assert denied.status_code == 404

    anon = client.get(f"/api/v1/ai/jobs/{job.id}/image")
    assert anon.status_code in (401, 403)


def test_job_image_missing_when_incomplete(client, db_session):
    tokens = register_with_invite(client, db_session, "img_q@example.com", "img_q")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = AIJob(
        user_id=uuid.UUID(me["id"]),
        design_id=None,
        job_type="sketch_polish",
        status="queued",
        input_data={},
        result_data=None,
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    r = client.get(f"/api/v1/ai/jobs/{job.id}/image", headers=_auth(tokens))
    assert r.status_code == 404


def test_polish_rejects_oversized_image_base64(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "img_big@example.com", "img_big")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    get_settings.cache_clear()
    try:
        huge = "A" * (2 * 1024 * 1024)
        r = client.post(
            "/api/v1/ai/sketch/polish",
            headers=_auth(tokens),
            json={
                "input_data": {
                    "notes": "polish concept",
                    "image_base64": f"data:image/png;base64,{huge}",
                }
            },
        )
        assert r.status_code == 422, r.text
    finally:
        monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
        get_settings.cache_clear()


def test_storage_key_from_public_url_roundtrip():
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_x.png"
    url = storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")
    assert storage.key_from_public_url(url) == key
    assert storage.resolve_existing_file(key=key) is not None


def test_polish_and_status_omit_image_base64_but_preserve_db_input(client, db_session):
    tokens = register_with_invite(client, db_session, "redact@example.com", "redact_user")
    tiny = base64.b64encode(_png_bytes()).decode("ascii")
    data_url = f"data:image/png;base64,{tiny}"
    created = client.post(
        "/api/v1/ai/sketch/polish",
        headers=_auth(tokens),
        json={
            "input_data": {
                "notes": "polish concept",
                "local_path_placeholder": "file:/tmp/sketch.png",
                "image_base64": data_url,
            }
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert "image_base64" not in body["input_data"]
    assert "imageBase64" not in body["input_data"]
    assert body["input_data"].get("has_sketch_image") is True
    assert body["input_data"].get("notes") == "polish concept"
    assert body["input_data"].get("local_path_placeholder") == "file:/tmp/sketch.png"
    job_id = body["id"]

    # Stored worker input still contains the sketch bytes.
    row = db_session.get(AIJob, uuid.UUID(job_id))
    assert row is not None
    assert isinstance(row.input_data, dict)
    assert row.input_data.get("image_base64") == data_url

    status = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(tokens))
    assert status.status_code == 200, status.text
    polled = status.json()
    assert "image_base64" not in polled["input_data"]
    assert polled["input_data"].get("has_sketch_image") is True
    assert polled["job_type"] == "sketch_polish"
    assert polled["status"] in {"queued", "running", "completed", "failed"}
