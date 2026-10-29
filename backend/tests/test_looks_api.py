"""My Looks API — owner-scoped gallery over completed sketch_polish jobs."""

from __future__ import annotations

import base64
import io
import uuid

from app.models.ai_job import AIJob
from app.models.magic_look_meta import MagicLookMeta
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
    status: str = "completed",
    image_url: str | None = None,
    studio_side: str | None = None,
    magic_operation_id: str | None = None,
    summary: str = "look ok",
    design_id: uuid.UUID | None = None,
) -> AIJob:
    input_data: dict = {"notes": "polish concept"}
    if studio_side:
        input_data["studio_side"] = studio_side
    if magic_operation_id:
        input_data["magic_operation_id"] = magic_operation_id
    result = None
    if status == "completed":
        result = {"summary": summary, "pipeline": "sketch_polish"}
        if image_url:
            result["image_url"] = image_url
    job = AIJob(
        user_id=user_id,
        design_id=design_id,
        job_type="sketch_polish",
        status=status,
        input_data=input_data,
        result_data=result,
        error_message=None if status == "completed" else "failed",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_list_looks_requires_auth(client):
    assert client.get("/api/v1/looks").status_code in (401, 403)


def test_historical_single_and_dual_grouping(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_a@example.com", "looks_a")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    url1 = _store_image()
    url2 = _store_image()
    url3 = _store_image()
    single = _add_job(db_session, user_id=uid, image_url=url1, summary="solo look")
    op = str(uuid.uuid4())
    front = _add_job(
        db_session,
        user_id=uid,
        image_url=url2,
        studio_side="front",
        magic_operation_id=op,
        summary="front look",
    )
    back = _add_job(
        db_session,
        user_id=uid,
        image_url=url3,
        studio_side="back",
        magic_operation_id=op,
        summary="back look",
    )

    listed = client.get("/api/v1/looks", headers=_auth(tokens))
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    by_id = {item["id"]: item for item in body["items"]}
    assert str(single.id) in by_id
    assert op in by_id
    solo = by_id[str(single.id)]
    assert solo["kind"] == "single"
    assert solo["front"]["job_id"] == str(single.id)
    assert solo["front"]["has_image"] is True
    assert solo["back"] is None
    dual = by_id[op]
    assert dual["kind"] == "dual"
    assert dual["magic_operation_id"] == op
    assert dual["front"]["job_id"] == str(front.id)
    assert dual["back"]["job_id"] == str(back.id)
    assert dual["front"]["has_image"] is True
    assert dual["back"]["has_image"] is True

    # Stable across refresh / re-list (no duplicates).
    again = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    assert again["total"] == 2
    assert {i["id"] for i in again["items"]} == {str(single.id), op}


def test_failed_retry_keeps_successful_image(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_retry@example.com", "looks_retry")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    op = str(uuid.uuid4())
    good_url = _store_image()
    success = _add_job(
        db_session,
        user_id=uid,
        image_url=good_url,
        studio_side="front",
        magic_operation_id=op,
    )
    _add_job(
        db_session,
        user_id=uid,
        status="failed",
        studio_side="front",
        magic_operation_id=op,
    )
    # Later completed without image must not replace the good side.
    _add_job(
        db_session,
        user_id=uid,
        status="completed",
        image_url=None,
        studio_side="front",
        magic_operation_id=op,
    )

    detail = client.get(f"/api/v1/looks/{op}", headers=_auth(tokens))
    assert detail.status_code == 200, detail.text
    look = detail.json()
    assert look["front"]["job_id"] == str(success.id)
    assert look["front"]["has_image"] is True


def test_partial_dual_and_missing_image_skipped(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_partial@example.com", "looks_partial")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    op = str(uuid.uuid4())
    front_url = _store_image()
    _add_job(
        db_session,
        user_id=uid,
        image_url=front_url,
        studio_side="front",
        magic_operation_id=op,
    )
    _add_job(
        db_session,
        user_id=uid,
        status="failed",
        studio_side="back",
        magic_operation_id=op,
    )
    # Completed job whose file is gone — omitted from gallery eligibility alone.
    missing = _add_job(
        db_session,
        user_id=uid,
        image_url="http://127.0.0.1:9/static/uploads/ai/does-not-exist.png",
    )

    listed = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    assert listed["total"] == 1
    look = listed["items"][0]
    assert look["id"] == op
    assert look["kind"] == "dual"
    assert look["front"]["has_image"] is True
    assert look["back"] is None or look["back"]["has_image"] is False

    assert client.get(f"/api/v1/looks/{missing.id}", headers=_auth(tokens)).status_code == 404


def test_cross_account_isolation(client, db_session):
    a = register_with_invite(client, db_session, "looks_own@example.com", "looks_own")
    b = register_with_invite(client, db_session, "looks_other@example.com", "looks_other")
    me = client.get("/api/v1/auth/me", headers=_auth(a)).json()
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image())

    assert client.get("/api/v1/looks", headers=_auth(b)).json()["total"] == 0
    assert client.get(f"/api/v1/looks/{job.id}", headers=_auth(b)).status_code == 404
    denied = client.patch(
        f"/api/v1/looks/{job.id}",
        headers=_auth(b),
        json={"title": "Stolen"},
    )
    assert denied.status_code == 404
    # Image endpoint remains owner-scoped.
    assert client.get(f"/api/v1/ai/jobs/{job.id}/image", headers=_auth(b)).status_code == 404
    assert client.get(f"/api/v1/ai/jobs/{job.id}/image", headers=_auth(a)).status_code == 200


def test_favorite_rename_archive_restore_and_filters(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_meta@example.com", "looks_meta")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    job = _add_job(db_session, user_id=uuid.UUID(me["id"]), image_url=_store_image())
    look_id = str(job.id)

    renamed = client.patch(
        f"/api/v1/looks/{look_id}",
        headers=_auth(tokens),
        json={"title": "Runway blush"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Runway blush"

    fav = client.patch(
        f"/api/v1/looks/{look_id}",
        headers=_auth(tokens),
        json={"is_favorite": True},
    )
    assert fav.json()["is_favorite"] is True

    favs = client.get("/api/v1/looks?filter=favorites", headers=_auth(tokens)).json()
    assert favs["total"] == 1
    assert favs["items"][0]["title"] == "Runway blush"

    search = client.get("/api/v1/looks?q=blush", headers=_auth(tokens)).json()
    assert search["total"] == 1

    archived = client.patch(
        f"/api/v1/looks/{look_id}",
        headers=_auth(tokens),
        json={"is_archived": True},
    )
    assert archived.json()["is_archived"] is True
    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 0
    assert client.get("/api/v1/looks?filter=archived", headers=_auth(tokens)).json()["total"] == 1
    assert client.get("/api/v1/looks?filter=favorites", headers=_auth(tokens)).json()["total"] == 0

    restored = client.patch(
        f"/api/v1/looks/{look_id}",
        headers=_auth(tokens),
        json={"is_archived": False},
    )
    assert restored.json()["is_archived"] is False
    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 1

    # Underlying AI job untouched.
    assert db_session.get(AIJob, job.id) is not None
    meta = db_session.get(MagicLookMeta, job.id)
    assert meta is not None
    assert meta.title == "Runway blush"


def test_pagination_and_validation(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_page@example.com", "looks_page")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    for _ in range(3):
        _add_job(db_session, user_id=uid, image_url=_store_image())

    page = client.get("/api/v1/looks?limit=2&offset=0", headers=_auth(tokens)).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    page2 = client.get("/api/v1/looks?limit=2&offset=2", headers=_auth(tokens)).json()
    assert len(page2["items"]) == 1
    assert {i["id"] for i in page["items"]}.isdisjoint({i["id"] for i in page2["items"]})

    bad = client.patch(
        f"/api/v1/looks/{page['items'][0]['id']}",
        headers=_auth(tokens),
        json={"title": "x" * 121},
    )
    assert bad.status_code == 422

    empty = client.patch(
        f"/api/v1/looks/{page['items'][0]['id']}",
        headers=_auth(tokens),
        json={},
    )
    assert empty.status_code == 422


def test_delete_single_and_dual_look_tombstone(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_del@example.com", "looks_del")
    other = register_with_invite(client, db_session, "looks_del_o@example.com", "looks_delo")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    single = _add_job(db_session, user_id=uid, image_url=_store_image())
    op = str(uuid.uuid4())
    front = _add_job(
        db_session,
        user_id=uid,
        image_url=_store_image(),
        studio_side="front",
        magic_operation_id=op,
    )
    back = _add_job(
        db_session,
        user_id=uid,
        image_url=_store_image(),
        studio_side="back",
        magic_operation_id=op,
    )
    keep = _add_job(db_session, user_id=uid, image_url=_store_image())

    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 3

    deleted = client.delete(f"/api/v1/looks/{single.id}", headers=_auth(tokens))
    assert deleted.status_code == 204
    # Idempotent
    assert client.delete(f"/api/v1/looks/{single.id}", headers=_auth(tokens)).status_code == 204

    listed = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    assert listed["total"] == 2
    ids = {i["id"] for i in listed["items"]}
    assert str(single.id) not in ids
    assert op in ids
    assert str(keep.id) in ids

    assert client.get(f"/api/v1/looks/{single.id}", headers=_auth(tokens)).status_code == 404
    assert (
        client.patch(
            f"/api/v1/looks/{single.id}",
            headers=_auth(tokens),
            json={"title": "Revive"},
        ).status_code
        == 404
    )
    # Underlying AI job + image remain for operational history / non-gallery use.
    assert db_session.get(AIJob, single.id) is not None
    assert client.get(f"/api/v1/ai/jobs/{single.id}/image", headers=_auth(tokens)).status_code == 200
    meta = db_session.get(MagicLookMeta, single.id)
    assert meta is not None and meta.is_deleted is True and meta.deleted_at is not None

    # Dual look deletes as one entity; AI jobs retained.
    assert client.delete(f"/api/v1/looks/{op}", headers=_auth(tokens)).status_code == 204
    listed2 = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    assert listed2["total"] == 1
    assert listed2["items"][0]["id"] == str(keep.id)
    assert client.get(f"/api/v1/looks/{op}", headers=_auth(tokens)).status_code == 404
    assert db_session.get(AIJob, front.id) is not None
    assert db_session.get(AIJob, back.id) is not None
    assert client.get(f"/api/v1/ai/jobs/{front.id}/image", headers=_auth(tokens)).status_code == 200

    # Cross-account: other user sees 404 (privacy) even with known id.
    assert client.delete(f"/api/v1/looks/{keep.id}", headers=_auth(other)).status_code == 404
    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 1

    # Missing id
    assert client.delete(f"/api/v1/looks/{uuid.uuid4()}", headers=_auth(tokens)).status_code == 404

    # Archive remains reversible for a non-deleted look; delete is not.
    client.patch(
        f"/api/v1/looks/{keep.id}",
        headers=_auth(tokens),
        json={"is_archived": True},
    )
    assert client.get("/api/v1/looks?filter=archived", headers=_auth(tokens)).json()["total"] == 1
    client.patch(
        f"/api/v1/looks/{keep.id}",
        headers=_auth(tokens),
        json={"is_archived": False},
    )
    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 1


def test_deleted_look_does_not_reappear_after_new_side_job(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_ghost@example.com", "looks_ghost")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    uid = uuid.UUID(me["id"])
    op = str(uuid.uuid4())
    _add_job(
        db_session,
        user_id=uid,
        image_url=_store_image(),
        studio_side="front",
        magic_operation_id=op,
    )
    assert client.delete(f"/api/v1/looks/{op}", headers=_auth(tokens)).status_code == 204
    # Later completed back / retry must not resurrect the tombstoned look.
    _add_job(
        db_session,
        user_id=uid,
        image_url=_store_image(),
        studio_side="back",
        magic_operation_id=op,
    )
    _add_job(
        db_session,
        user_id=uid,
        image_url=_store_image(),
        studio_side="front",
        magic_operation_id=op,
    )
    assert client.get("/api/v1/looks", headers=_auth(tokens)).json()["total"] == 0
    assert client.get(f"/api/v1/looks/{op}", headers=_auth(tokens)).status_code == 404


def test_gallery_response_omits_sketch_payloads(client, db_session):
    tokens = register_with_invite(client, db_session, "looks_lean@example.com", "looks_lean")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    url = _store_image()
    job = AIJob(
        user_id=uuid.UUID(me["id"]),
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"image_base64": "data:image/png;base64,AAAA", "notes": "secret sketch"},
        result_data={"summary": "ok", "image_url": url, "pipeline": "sketch_polish"},
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    body = client.get("/api/v1/looks", headers=_auth(tokens)).json()
    raw = str(body)
    assert "image_base64" not in raw
    assert "AAAA" not in raw
    assert "secret sketch" not in raw
