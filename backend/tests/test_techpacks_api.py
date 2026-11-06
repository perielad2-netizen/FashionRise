"""Create Real Design V2 — techpack draft + PDF + heuristic AI (0 paid AI by default)."""

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
    assert draft["spec"]["schema_version"].startswith("2")
    assert draft["spec"]["body"]["height"]["source"] == "empty"
    pieces = draft["spec"]["outfit"]["pieces"]
    assert len(pieces) >= 1
    assert pieces[0]["category"] == "dress"
    assert "chest_bust" in pieces[0]["finished_measurements"]

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
    assert body["spec"]["outfit"]["pieces"][0]["materials"]["shell"]["name"] == "Cotton sateen"
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
    assert export["metadata"]["cutting_uses_schematics"] is True
    assert export["metadata"]["cutting_reuses_magic_looks"] is False

    pdf = client.get(f"/api/v1/techpacks/exports/{export['id']}/pdf", headers=_auth(tokens))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages) == export["page_count"]
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    assert "DRAFT" in text and "UNVERIFIED" in text
    assert "Body measurements" in text
    assert text.count("Height") == 1
    assert "NOT TO SCALE" in text
    assert "Technical flat" in text or "SCHEMATIC" in text
    assert "Pattern piece development" in text
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

    assert client.get(f"/api/v1/looks/{job.id}", headers=_auth(tokens)).status_code == 404
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


def test_heuristic_generate_two_piece_and_ai_status(client, db_session):
    tokens = register_with_invite(client, db_session, "tp_v2@example.com", "tp_v2")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url = _store_image()
    job = _add_job(
        db_session,
        user_id=uid,
        image_url=url,
        studio_side="front",
        summary="black shirt and beige trousers outfit",
    )
    status = client.get("/api/v1/techpacks/ai/status", headers=_auth(tokens))
    assert status.status_code == 200
    assert status.json()["enabled"] is False
    assert status.json()["spend_ceiling_usd"] == 0.0

    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "Black shirt set"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    pieces = draft["spec"]["outfit"]["pieces"]
    assert draft["spec"]["outfit"]["piece_count"] == 2
    cats = {p["category"] for p in pieces}
    assert "shirt" in cats
    assert "trousers" in cats
    shirt = next(p for p in pieces if p["category"] == "shirt")
    trousers = next(p for p in pieces if p["category"] == "trousers")
    assert "chest_bust" in shirt["finished_measurements"]
    assert "inseam" in trousers["finished_measurements"]
    assert "chest_bust" not in trousers["finished_measurements"]
    assert "sleeve_length" not in trousers["finished_measurements"]

    confirm = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(tokens),
        json={"stage": "generate"},
    )
    assert confirm.status_code == 200, confirm.text
    token = confirm.json()["confirm_token"]
    assert len(token) >= 8
    assert confirm.json()["ai_enabled"] is False

    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": token,
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
            "mode": "heuristic",
        },
    )
    assert gen.status_code == 200, gen.text
    assert gen.json()["mode"] == "heuristic"
    assert gen.json()["cost_usd_cents"] == 0

    refreshed = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    for piece in refreshed["spec"]["outfit"]["pieces"]:
        assert piece["pattern_pieces"]
        assert piece["construction_steps"]
        assert piece["bom"]

    # Paid AI fails closed without spend ceiling.
    confirm2 = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/confirm",
        headers=_auth(tokens),
        json={"stage": "generate"},
    ).json()
    paid = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate",
        headers=_auth(tokens),
        json={
            "confirm_token": confirm2["confirm_token"],
            "idempotency_key": f"idem-paid-{uuid.uuid4().hex}",
            "mode": "ai",
        },
    )
    assert paid.status_code == 403

    exported = client.post(f"/api/v1/techpacks/{draft['id']}/export", headers=_auth(tokens))
    assert exported.status_code == 201
    assert exported.json()["metadata"]["piece_count"] == 2
    assert exported.json()["page_count"] >= 8
    pdf = client.get(
        f"/api/v1/techpacks/exports/{exported.json()['id']}/pdf",
        headers=_auth(tokens),
    )
    text = "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "SHIRT" in text.upper() or "shirt" in text.lower()
    assert "TROUSER" in text.upper() or "trouser" in text.lower()
    assert "CUTTING LAYOUT" in text.upper() or "Cutting layout" in text
