"""Create Real Design — techpack draft + PDF API (0 paid AI)."""

from __future__ import annotations

import base64
import io
import uuid

from pypdf import PdfReader

from app.models.ai_job import AIJob
from app.models.magic_look_meta import MagicLookMeta
from app.models.techpack_draft import TechpackDraft
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def _store_image() -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")


def _add_job(
    db_session,
    *,
    user_id: uuid.UUID,
    image_url: str,
    studio_side: str | None = "front",
    magic_operation_id: str | None = None,
    summary: str = "cream dress look",
) -> AIJob:
    input_data: dict = {"notes": "polish concept"}
    if studio_side:
        input_data["studio_side"] = studio_side
    if magic_operation_id:
        input_data["magic_operation_id"] = magic_operation_id
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data=input_data,
        result_data={"summary": summary, "pipeline": "sketch_polish", "image_url": image_url},
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_techpack_requires_auth(client):
    assert client.get("/api/v1/techpacks").status_code in (401, 403)
    assert client.post("/api/v1/techpacks", json={"look_id": str(uuid.uuid4())}).status_code in (
        401,
        403,
    )


def test_create_update_export_pdf_and_owner_isolation(client, db_session):
    tokens = register_with_invite(client, db_session, "tp_a@example.com", "tp_a")
    other = register_with_invite(client, db_session, "tp_b@example.com", "tp_b")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url = _store_image()
    job = _add_job(db_session, user_id=uid, image_url=url, studio_side=None)

    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Cream day dress"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["title"] == "Cream day dress"
    assert draft["status"] == "DRAFT"
    assert draft["verification"] == "UNVERIFIED"
    assert draft["look_id"] == str(job.id)
    assert draft["front_job_id"] == str(job.id)
    assert draft["back_job_id"] is None
    assert draft["spec"]["body"]["height"]["source"] == "empty"
    assert "Estimate" in (draft["spec"]["garment"]["garment_length"].get("note") or "")

    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={
            "spec": {
                "body": {"height": {"value": 170, "unit": "cm", "source": "designer"}},
                "materials": {"shell": {"name": "Cotton sateen", "composition": "100% cotton"}},
            },
            "bump_revision": True,
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["revision"] == 2
    assert body["spec"]["body"]["height"]["value"] == 170
    assert body["spec"]["body"]["height"]["source"] == "designer"
    assert body["status"] == "DRAFT"
    assert body["verification"] == "UNVERIFIED"

    exported = client.post(f"/api/v1/techpacks/{draft['id']}/export", headers=_auth(tokens))
    assert exported.status_code == 201, exported.text
    export = exported.json()
    assert export["status"] == "DRAFT"
    assert export["verification"] == "UNVERIFIED"
    assert export["page_count"] >= 5
    assert export["byte_size"] > 500
    assert export["metadata"]["height_rows"] == 1
    assert export["metadata"]["cutting_reuses_magic_looks"] is True

    pdf = client.get(f"/api/v1/techpacks/exports/{export['id']}/pdf", headers=_auth(tokens))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages) == export["page_count"]
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "DRAFT" in text and "UNVERIFIED" in text
    assert "Body measurements" in text
    # Height appears as a measurement label once in the body table (not duplicated).
    assert text.count("Height") == 1
    assert "same Magic job" in text or "same authenticated Magic" in text
    assert "not fabricated" in text.lower() or "not invented" in text.lower()

    denied = client.get(f"/api/v1/techpacks/exports/{export['id']}/pdf", headers=_auth(other))
    assert denied.status_code == 404

    listed = client.get(f"/api/v1/techpacks?look_id={job.id}", headers=_auth(tokens))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_look_delete_does_not_cascade_techpack_draft(client, db_session):
    tokens = register_with_invite(client, db_session, "tp_del@example.com", "tp_del")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url = _store_image()
    job = _add_job(db_session, user_id=uid, image_url=url, studio_side=None)

    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id)},
    )
    assert created.status_code == 201, created.text
    draft_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/looks/{job.id}", headers=_auth(tokens))
    assert deleted.status_code == 204

    # Look gone from gallery…
    assert client.get(f"/api/v1/looks/{job.id}", headers=_auth(tokens)).status_code == 404
    # …but techpack draft remains owner-accessible.
    still = client.get(f"/api/v1/techpacks/{draft_id}", headers=_auth(tokens))
    assert still.status_code == 200, still.text
    assert still.json()["id"] == draft_id
    row = db_session.get(TechpackDraft, uuid.UUID(draft_id))
    assert row is not None
    meta = db_session.get(MagicLookMeta, job.id)
    assert meta is not None and meta.is_deleted is True


def test_ai_draft_assist_disabled(client, db_session):
    tokens = register_with_invite(client, db_session, "tp_ai@example.com", "tp_ai")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url = _store_image()
    job = _add_job(db_session, user_id=uid, image_url=url, studio_side=None)
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id)},
    )
    assert created.status_code == 201
    resp = client.post(
        f"/api/v1/techpacks/{created.json()['id']}/ai-draft",
        headers=_auth(tokens),
    )
    assert resp.status_code == 403


def test_missing_opposite_side_not_invented(client, db_session):
    tokens = register_with_invite(client, db_session, "tp_side@example.com", "tp_side")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url = _store_image()
    job = _add_job(db_session, user_id=uid, image_url=url, studio_side="front")
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id)},
    ).json()
    assert created["front_job_id"] == str(job.id)
    assert created["back_job_id"] is None
    exported = client.post(f"/api/v1/techpacks/{created['id']}/export", headers=_auth(tokens))
    assert exported.status_code == 201
    assert exported.json()["metadata"]["back_image_present"] is False
