"""Issue #128 / PR #130 — garment identity + PDF-bind CAS + independent sessions.

Mocked provider only. Extends concurrent-write safety beyond measurement-only edits.
"""

from __future__ import annotations

import copy
import io
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.ai_job import AIJob
from app.models.techpack_ai_artifact import TechpackAIArtifact
from app.models.techpack_ai_run import TechpackAIRun
from app.models.techpack_draft import TechpackDraft, TechpackExport
from app.models.user import User
from app.schemas.auth import UserRegister
from app.services import auth_service, invitation_service, techpack_service
from app.services.techpack_ai import (
    ensure_professional_pdf_for_run,
    set_professional_provider_override,
)
from app.services.techpack_ai_professional import MockProfessionalProvider
from app.services.techpack_ai_worker import run_techpack_worker_tick
from app.services.techpack_garments import FINISHED_POM, default_piece
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.test_techpack_meas_concurrent import (
    ConcurrentEditProvider,
    _auth,
    _designer_cell,
    _enable_ai,
    _find_shorts_piece,
    _seed_shorts_draft,
)


def _png_bytes() -> bytes:
    img = Image.new("RGB", (128, 192), (200, 80, 40))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _store_image() -> str:
    storage = LocalStorageBackend()
    key = f"ai/{uuid.uuid4().hex}_look.png"
    return storage.save_file(key=key, data=io.BytesIO(_png_bytes()), content_type="image/png")


def _piece_by_id(spec: dict[str, Any], piece_id: str) -> dict[str, Any]:
    outfit = spec.get("outfit") if isinstance(spec.get("outfit"), dict) else {}
    for piece in outfit.get("pieces") or []:
        if isinstance(piece, dict) and str(piece.get("id")) == piece_id:
            return piece
    raise AssertionError(f"piece {piece_id} missing")


def _mutate_piece_identity(
    db_session,
    draft_id: uuid.UUID,
    piece_id: str,
    *,
    category: str | None = None,
    label: str | None = None,
    closures: dict[str, Any] | None = None,
    color_hint: str | None = None,
) -> None:
    live = db_session.get(TechpackDraft, draft_id)
    assert live is not None
    spec = copy.deepcopy(live.spec if isinstance(live.spec, dict) else {})
    p = _piece_by_id(spec, piece_id)
    if category is not None:
        p["category"] = category
    if label is not None:
        p["label"] = label
    if closures is not None:
        p["closures"] = closures
    if color_hint is not None:
        p["color_hint"] = color_hint
    for i, x in enumerate(spec["outfit"]["pieces"]):
        if str(x.get("id")) == piece_id:
            spec["outfit"]["pieces"][i] = p
    live.spec = spec
    flag_modified(live, "spec")
    live.revision = int(live.revision or 1) + 1
    live.updated_at = datetime.now(UTC)
    db_session.add(live)
    db_session.commit()


@pytest.fixture(autouse=True)
def _clear_provider():
    set_professional_provider_override(None)
    yield
    set_professional_provider_override(None)


def test_same_piece_id_shirt_to_shorts_does_not_bind_stale_artwork(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "id128a@example.com", "id128a")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    piece = _find_shorts_piece(draft["spec"])
    piece_id = str(piece["id"])

    # Start as shirt with same piece id — generation authorizes shirt identity.
    _mutate_piece_identity(
        db_session,
        draft_id,
        piece_id,
        category="shirt",
        label="Shirt",
        closures={"type": "buttons", "notes": "centre front"},
        color_hint="white",
    )

    set_professional_provider_override(
        ConcurrentEditProvider(
            lambda: _mutate_piece_identity(
                db_session,
                draft_id,
                piece_id,
                category="shorts",
                label="Shorts",
                closures={"type": "zipper", "notes": "fly"},
                color_hint="navy",
            )
        )
    )
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"id-shirt-shorts-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"
    assert status.get("pdf_ready") is not True
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    result = run_row.result if isinstance(run_row.result, dict) else {}
    assert result.get("skipped_stale_spec_write") is True
    assert result.get("skipped_identity_drift") is True
    assert int(run_row.cost_usd_cents or 0) > 0
    arts = list(
        db_session.scalars(
            select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run_row.id)
        ).all()
    )
    assert arts, "paid artifacts must be retained even when artwork is not bound"

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    live_piece = _piece_by_id(reopened["spec"], piece_id)
    assert live_piece["category"] == "shorts"
    assert live_piece["closures"]["type"] == "zipper"
    assert live_piece["color_hint"] == "navy"
    # Stale shirt artwork must not be bound onto the shorts piece.
    illust = live_piece.get("illustrations") if isinstance(live_piece.get("illustrations"), dict) else {}
    assert illust.get("mode") != "professional"
    ai = reopened["spec"].get("ai") if isinstance(reopened["spec"].get("ai"), dict) else {}
    assert str(ai.get("last_run_id") or "") != run_id


def test_buttons_to_zipper_same_piece_skips_artwork_bind(
    client, db_session, monkeypatch
):
    tokens = register_with_invite(client, db_session, "id128b@example.com", "id128b")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    piece_id = str(_find_shorts_piece(draft["spec"])["id"])

    _mutate_piece_identity(
        db_session,
        draft_id,
        piece_id,
        closures={"type": "buttons", "notes": "snap"},
    )

    set_professional_provider_override(
        ConcurrentEditProvider(
            lambda: _mutate_piece_identity(
                db_session,
                draft_id,
                piece_id,
                closures={"type": "zipper", "notes": "invisible zip"},
            )
        )
    )
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"id-closure-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    result = run_row.result if isinstance(run_row.result, dict) else {}
    assert result.get("skipped_identity_drift") is True
    assert result.get("skipped_stale_spec_write") is True
    assert result.get("pdf_ready") is not True

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert _piece_by_id(reopened["spec"], piece_id)["closures"]["type"] == "zipper"
    illust = _piece_by_id(reopened["spec"], piece_id).get("illustrations") or {}
    assert illust.get("mode") != "professional"


def test_buttons_to_zipper_ensure_pdf_does_not_rebind(client, db_session, monkeypatch):
    tokens = register_with_invite(client, db_session, "id128c@example.com", "id128c")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    piece_id = str(_find_shorts_piece(draft["spec"])["id"])
    user = db_session.get(User, uuid.UUID(me["id"]))
    assert user is not None

    _mutate_piece_identity(
        db_session,
        draft_id,
        piece_id,
        closures={"type": "buttons", "notes": "snap"},
    )

    set_professional_provider_override(
        ConcurrentEditProvider(
            lambda: _mutate_piece_identity(
                db_session,
                draft_id,
                piece_id,
                closures={"type": "zipper", "notes": "invisible zip"},
            )
        )
    )
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"id-closure2-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    before_ai = copy.deepcopy(
        (db_session.get(TechpackDraft, draft_id).spec or {}).get("ai")  # type: ignore[union-attr]
    )
    ensure_professional_pdf_for_run(db_session, user, run_row)
    after = db_session.get(TechpackDraft, draft_id)
    assert after is not None
    after_ai = (after.spec or {}).get("ai") if isinstance(after.spec, dict) else {}
    assert after_ai.get("last_run_id") == (before_ai or {}).get("last_run_id")
    assert after_ai.get("export_id") == (before_ai or {}).get("export_id")
    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    assert _piece_by_id(reopened["spec"], piece_id)["closures"]["type"] == "zipper"
    run_after = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_after is not None
    result_after = run_after.result if isinstance(run_after.result, dict) else {}
    assert result_after.get("pdf_ready") is not True


def _cleanup_user_rows(SessionLocal, user_id: uuid.UUID | None) -> None:
    """Delete techpack rows for this user. Leave auth rows for session drop_all."""
    if user_id is None:
        return
    cleanup = SessionLocal()
    try:
        for model in (TechpackAIArtifact, TechpackExport, TechpackAIRun, TechpackDraft, AIJob):
            for row in cleanup.scalars(select(model).where(model.user_id == user_id)).all():
                cleanup.delete(row)
        cleanup.commit()
    finally:
        cleanup.close()


def test_pdf_assembly_edit_preserves_dirty_and_skips_stale_bind(engine, monkeypatch):
    """Independent-session edit between PDF render and final bind (real PG tx)."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    email = f"pdf128_{uuid.uuid4().hex[:8]}@example.com"
    username = f"pdf128_{uuid.uuid4().hex[:8]}"
    user_id: uuid.UUID | None = None

    bootstrap = SessionLocal()
    try:
        inv = invitation_service.create_invitation(bootstrap, email=email, expires_in_hours=24)
        token = inv.plaintext_token
        bootstrap.commit()
    finally:
        bootstrap.close()

    worker = SessionLocal()
    try:
        user = auth_service.register_user(
            worker,
            UserRegister(
                email=email,
                username=username,
                password="StrongPass123!",
                invitation_code=token,
                display_name=username,
            ),
        )
        worker.commit()
        user_id = user.id

        image_url = _store_image()
        job = AIJob(
            user_id=user_id,
            design_id=None,
            job_type="sketch_polish",
            status="completed",
            input_data={"studio_side": "front"},
            result_data={
                "summary": "golden-yellow mid-thigh shorts",
                "pipeline": "sketch_polish",
                "image_url": image_url,
            },
            error_message=None,
        )
        worker.add(job)
        worker.commit()
        worker.refresh(job)

        def _override_get_db():
            yield worker

        app.dependency_overrides[get_db] = _override_get_db
        _enable_ai(monkeypatch, email)
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "StrongPass123!"},
            )
            if login.status_code == 200:
                headers = _auth(login.json())

            created = client.post(
                "/api/v1/techpacks",
                headers=headers,
                json={"look_id": str(job.id), "title": "PDF CAS"},
            )
            assert created.status_code == 201, created.text
            draft = created.json()
            draft_id = uuid.UUID(draft["id"])

            live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=headers).json()
            pieces = live["spec"]["outfit"]["pieces"]
            target = pieces[0]
            target["category"] = "shorts"
            target["label"] = "Shorts"
            finished = {}
            values = {
                "waist": 75.0,
                "hip": 110.0,
                "inseam": 18.0,
                "outseam": 42.0,
                "front_rise": 30.0,
                "back_rise": 40.0,
                "thigh": 58.0,
                "leg_opening": 40.0,
                "waistband": 4.0,
            }
            for key in FINISHED_POM["shorts"]:
                finished[key] = _designer_cell(values[key], definition=key)
            target["finished_measurements"] = finished
            patched = client.patch(
                f"/api/v1/techpacks/{draft['id']}",
                headers=headers,
                json={"spec": {"outfit": {"piece_count": len(pieces), "pieces": pieces}}},
            )
            assert patched.status_code == 200, patched.text
            worker.commit()

            real_export = techpack_service.export_pdf

            def _export_then_owner_edit(*args, **kwargs):
                exported = real_export(*args, **kwargs)
                # Separate SQLAlchemy session + PostgreSQL transaction.
                s = SessionLocal()
                try:
                    row = s.get(TechpackDraft, draft_id)
                    assert row is not None
                    spec = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
                    piece = _find_shorts_piece(spec)
                    fm = dict(piece.get("finished_measurements") or {})
                    fm["waist"] = _designer_cell(
                        79.0, definition="Waist", note="during pdf assemble"
                    )
                    piece["finished_measurements"] = fm
                    for i, p in enumerate(spec["outfit"]["pieces"]):
                        if str(p.get("id")) == str(piece.get("id")):
                            spec["outfit"]["pieces"][i] = piece
                    ai = dict(spec.get("ai") if isinstance(spec.get("ai"), dict) else {})
                    ai["dirty_since_generation"] = True
                    spec["ai"] = ai
                    row.spec = spec
                    flag_modified(row, "spec")
                    row.revision = int(row.revision or 1) + 1
                    row.updated_at = datetime.now(UTC)
                    s.add(row)
                    s.commit()
                finally:
                    s.close()
                return exported

            set_professional_provider_override(MockProfessionalProvider())
            with patch.object(techpack_service, "export_pdf", side_effect=_export_then_owner_edit):
                gen = client.post(
                    f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
                    headers=headers,
                    json={"idempotency_key": f"pdf-cas-{uuid.uuid4().hex}"},
                )
                assert gen.status_code == 202, gen.text
                run_id = gen.json()["run_id"]
                worker.commit()
                assert run_techpack_worker_tick(worker, limit=2) >= 1
                worker.commit()

            status = client.get(
                f"/api/v1/techpacks/ai/runs/{run_id}", headers=headers
            ).json()
            assert status["status"] == "completed"
            assert status.get("pdf_ready") is not True

            verify = SessionLocal()
            try:
                run_row = verify.get(TechpackAIRun, uuid.UUID(run_id))
                assert run_row is not None
                result = run_row.result if isinstance(run_row.result, dict) else {}
                assert result.get("skipped_stale_pdf_bind") is True
                assert result.get("orphaned_export_id")
                orphan = str(result.get("orphaned_export_id"))

                row = verify.get(TechpackDraft, draft_id)
                assert row is not None
                waist = _find_shorts_piece(row.spec)["finished_measurements"]["waist"]
                assert waist["value"] == 79.0
                assert waist["note"] == "during pdf assemble"
                ai = (row.spec or {}).get("ai") if isinstance(row.spec, dict) else {}
                assert ai.get("dirty_since_generation") is True
                assert str(ai.get("export_id") or "") != orphan
            finally:
                verify.close()
    finally:
        set_professional_provider_override(None)
        app.dependency_overrides.pop(get_db, None)
        worker.close()
        _cleanup_user_rows(SessionLocal, user_id)


def test_owner_waist_edit_independent_sqlalchemy_session(engine, monkeypatch):
    """Real second PostgreSQL session + FOR UPDATE refresh (not shared test connection)."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    email = f"indep128_{uuid.uuid4().hex[:8]}@example.com"
    username = f"indep128_{uuid.uuid4().hex[:8]}"
    user_id: uuid.UUID | None = None

    bootstrap = SessionLocal()
    try:
        inv = invitation_service.create_invitation(bootstrap, email=email, expires_in_hours=24)
        token = inv.plaintext_token
        bootstrap.commit()
    finally:
        bootstrap.close()

    worker = SessionLocal()
    try:
        user = auth_service.register_user(
            worker,
            UserRegister(
                email=email,
                username=username,
                password="StrongPass123!",
                invitation_code=token,
                display_name=username,
            ),
        )
        worker.commit()
        user_id = user.id

        image_url = _store_image()
        job = AIJob(
            user_id=user_id,
            design_id=None,
            job_type="sketch_polish",
            status="completed",
            input_data={"studio_side": "front"},
            result_data={
                "summary": "golden-yellow mid-thigh shorts",
                "pipeline": "sketch_polish",
                "image_url": image_url,
            },
            error_message=None,
        )
        worker.add(job)
        worker.commit()
        worker.refresh(job)

        def _override_get_db():
            yield worker

        app.dependency_overrides[get_db] = _override_get_db
        _enable_ai(monkeypatch, email)
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "StrongPass123!"},
            )
            if login.status_code == 200:
                headers = _auth(login.json())

            created = client.post(
                "/api/v1/techpacks",
                headers=headers,
                json={"look_id": str(job.id), "title": "Indep session"},
            )
            assert created.status_code == 201, created.text
            draft = created.json()
            draft_id = uuid.UUID(draft["id"])

            live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=headers).json()
            pieces = live["spec"]["outfit"]["pieces"]
            target = pieces[0]
            target["category"] = "shorts"
            target["label"] = "Shorts"
            finished = {}
            values = {
                "waist": 75.0,
                "hip": 110.0,
                "inseam": 18.0,
                "outseam": 42.0,
                "front_rise": 30.0,
                "back_rise": 40.0,
                "thigh": 58.0,
                "leg_opening": 40.0,
                "waistband": 4.0,
            }
            for key in FINISHED_POM["shorts"]:
                finished[key] = _designer_cell(values[key], definition=key)
            target["finished_measurements"] = finished
            patched = client.patch(
                f"/api/v1/techpacks/{draft['id']}",
                headers=headers,
                json={"spec": {"outfit": {"piece_count": len(pieces), "pieces": pieces}}},
            )
            assert patched.status_code == 200, patched.text
            worker.commit()
            pre_revision = int(patched.json().get("revision") or 1)

            ConcurrentEditProvider.provider_calls = 0

            def _owner_edit_other_session() -> None:
                s = SessionLocal()
                try:
                    row = s.get(TechpackDraft, draft_id)
                    assert row is not None
                    spec = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
                    piece = _find_shorts_piece(spec)
                    fm = dict(piece.get("finished_measurements") or {})
                    fm["waist"] = _designer_cell(
                        76.5, definition="Waist", note="independent session"
                    )
                    piece["finished_measurements"] = fm
                    for i, p in enumerate(spec["outfit"]["pieces"]):
                        if str(p.get("id")) == str(piece.get("id")):
                            spec["outfit"]["pieces"][i] = piece
                    row.spec = spec
                    flag_modified(row, "spec")
                    row.revision = int(row.revision or 1) + 1
                    row.updated_at = datetime.now(UTC)
                    s.add(row)
                    s.commit()
                finally:
                    s.close()

            set_professional_provider_override(ConcurrentEditProvider(_owner_edit_other_session))
            gen = client.post(
                f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
                headers=headers,
                json={"idempotency_key": f"indep-{uuid.uuid4().hex}"},
            )
            assert gen.status_code == 202, gen.text
            run_id = gen.json()["run_id"]
            worker.commit()
            assert run_techpack_worker_tick(worker, limit=2) >= 1
            worker.commit()

            status = client.get(
                f"/api/v1/techpacks/ai/runs/{run_id}", headers=headers
            ).json()
            assert status["status"] == "completed"

            verify = SessionLocal()
            try:
                row = verify.get(TechpackDraft, draft_id)
                assert row is not None
                waist = _find_shorts_piece(row.spec)["finished_measurements"]["waist"]
                assert waist["value"] == 76.5
                assert waist["note"] == "independent session"
                assert int(row.revision or 1) > pre_revision
                # Authoritative revision after FOR UPDATE refresh must reflect owner edit.
                run_row = verify.get(TechpackAIRun, uuid.UUID(run_id))
                assert run_row is not None
                result = run_row.result if isinstance(run_row.result, dict) else {}
                assert result.get("reconciled_concurrent_designer_edits") is True
            finally:
                verify.close()
    finally:
        set_professional_provider_override(None)
        app.dependency_overrides.pop(get_db, None)
        worker.close()
        _cleanup_user_rows(SessionLocal, user_id)


def _add_job_for_user(db_session, *, user_id: uuid.UUID) -> AIJob:
    job = AIJob(
        user_id=user_id,
        design_id=None,
        job_type="sketch_polish",
        status="completed",
        input_data={"studio_side": "front"},
        result_data={
            "summary": "red shirt with navy shorts",
            "pipeline": "sketch_polish",
            "image_url": _store_image(),
        },
        error_message=None,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _seed_two_piece_draft(client, db_session, tokens, me) -> dict[str, Any]:
    """Shirt + shorts outfit for structural drift regressions."""
    job = _add_job_for_user(db_session, user_id=uuid.UUID(me["id"]))
    created = client.post(
        "/api/v1/techpacks",
        headers=_auth(tokens),
        json={"look_id": str(job.id), "title": "FR-130 two garment"},
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    shirt_id = f"shirt-{uuid.uuid4().hex[:8]}"
    shorts_id = f"shorts-{uuid.uuid4().hex[:8]}"
    shirt = default_piece(piece_id=shirt_id, category="shirt", label="Shirt", color_hint="red")
    shorts = default_piece(piece_id=shorts_id, category="shorts", label="Shorts", color_hint="navy")
    finished = {}
    values = {
        "waist": 75.0,
        "hip": 110.0,
        "inseam": 18.0,
        "outseam": 42.0,
        "front_rise": 30.0,
        "back_rise": 40.0,
        "thigh": 58.0,
        "leg_opening": 40.0,
        "waistband": 4.0,
    }
    for key in FINISHED_POM["shorts"]:
        finished[key] = _designer_cell(values[key], definition=key)
    shorts["finished_measurements"] = finished
    patched = client.patch(
        f"/api/v1/techpacks/{draft['id']}",
        headers=_auth(tokens),
        json={"spec": {"outfit": {"piece_count": 2, "pieces": [shirt, shorts]}}},
    )
    assert patched.status_code == 200, patched.text
    return patched.json()


def test_piece_removed_mid_run_retains_authorized_artifacts(client, db_session, monkeypatch):
    """Structural drift: remove one garment mid-provider — keep paid bytes, no bind."""
    tokens = register_with_invite(client, db_session, "struct130a@example.com", "struct130a")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_two_piece_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    pieces0 = draft["spec"]["outfit"]["pieces"]
    assert len(pieces0) == 2
    removed_id = str(pieces0[0]["id"])
    kept_id = str(pieces0[1]["id"])

    def _remove_first_piece() -> None:
        live = db_session.get(TechpackDraft, draft_id)
        assert live is not None
        spec = copy.deepcopy(live.spec if isinstance(live.spec, dict) else {})
        remaining = [
            p
            for p in (spec.get("outfit") or {}).get("pieces") or []
            if isinstance(p, dict) and str(p.get("id")) != removed_id
        ]
        assert len(remaining) == 1
        spec["outfit"] = {"piece_count": 1, "pieces": remaining}
        live.spec = spec
        flag_modified(live, "spec")
        live.revision = int(live.revision or 1) + 1
        live.updated_at = datetime.now(UTC)
        db_session.add(live)
        db_session.commit()

    set_professional_provider_override(ConcurrentEditProvider(_remove_first_piece))
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"struct-rm-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1

    status = client.get(f"/api/v1/techpacks/ai/runs/{run_id}", headers=_auth(tokens)).json()
    assert status["status"] == "completed"
    assert status.get("pdf_ready") is not True
    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    result = run_row.result if isinstance(run_row.result, dict) else {}
    assert result.get("skipped_identity_drift") is True
    assert result.get("skipped_stale_spec_write") is True
    assert int(run_row.cost_usd_cents or 0) > 0

    arts = list(
        db_session.scalars(
            select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run_row.id)
        ).all()
    )
    assert arts, "paid artwork must be retained against authorized piece snapshot"
    art_piece_ids = {str(a.piece_id) for a in arts}
    assert removed_id in art_piece_ids
    storage = LocalStorageBackend()
    for art in arts:
        assert art.user_id == uuid.UUID(me["id"])
        assert art.draft_id == draft_id
        assert art.run_id == run_row.id
        assert art.byte_size and art.byte_size > 0
        path = storage._private_techpack_path(art.storage_key)
        assert path.is_file()
        assert path.stat().st_size == art.byte_size

    # Authoritative DB state — current outfit must keep the designer remove.
    db_session.expire_all()
    live_row = db_session.get(TechpackDraft, draft_id)
    assert live_row is not None
    live_spec = live_row.spec if isinstance(live_row.spec, dict) else {}
    live_pieces = (live_spec.get("outfit") or {}).get("pieces") or []
    assert len(live_pieces) == 1, f"expected designer remove to stick, got {len(live_pieces)}"
    assert str(live_pieces[0].get("id")) == kept_id
    for piece in live_pieces:
        illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        assert illust.get("mode") != "professional"
    ai = live_spec.get("ai") if isinstance(live_spec.get("ai"), dict) else {}
    assert str(ai.get("last_run_id") or "") != run_id
    assert not ai.get("export_id")

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    # GET must not rebind stale professional artwork onto the current outfit.
    for piece in reopened["spec"]["outfit"]["pieces"]:
        illust = piece.get("illustrations") if isinstance(piece.get("illustrations"), dict) else {}
        assert illust.get("mode") != "professional"
    ai2 = reopened["spec"].get("ai") if isinstance(reopened["spec"].get("ai"), dict) else {}
    assert str(ai2.get("export_id") or "") == ""


def test_color_treatment_change_same_hint_skips_artwork_bind(client, db_session, monkeypatch):
    """Visual drift: same piece_id + color_hint, gradient→solid mid-run."""
    tokens = register_with_invite(client, db_session, "visual130a@example.com", "visual130a")
    me = client.get("/api/v1/auth/me", headers=_auth(tokens)).json()
    _enable_ai(monkeypatch, me["email"])
    draft = _seed_shorts_draft(client, db_session, tokens, me)
    draft_id = uuid.UUID(draft["id"])
    piece_id = str(_find_shorts_piece(draft["spec"])["id"])

    row = db_session.get(TechpackDraft, draft_id)
    assert row is not None
    spec0 = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
    p0 = _piece_by_id(spec0, piece_id)
    p0["color_hint"] = "red"
    p0["color_treatment"] = {
        "mode": "gradient",
        "stops": ["#FF0000", "#FFFFFF"],
        "direction": "top-to-bottom",
        "placement": "body",
        "designer_confirmed": True,
        "angle": 90,
    }
    p0["visible_details"] = {"pocket_style": "patch", "hem_finish": "clean"}
    for i, p in enumerate(spec0["outfit"]["pieces"]):
        if str(p.get("id")) == piece_id:
            spec0["outfit"]["pieces"][i] = p0
    row.spec = spec0
    flag_modified(row, "spec")
    db_session.add(row)
    db_session.commit()

    def _flatten_to_solid() -> None:
        live = db_session.get(TechpackDraft, draft_id)
        assert live is not None
        spec = copy.deepcopy(live.spec if isinstance(live.spec, dict) else {})
        p = _piece_by_id(spec, piece_id)
        assert p["color_hint"] == "red"
        p["color_treatment"] = {
            "mode": "solid",
            "stops": ["#FF0000"],
            "direction": "",
            "placement": "body",
            "designer_confirmed": True,
        }
        p["visible_details"] = {"pocket_style": "none", "hem_finish": "clean"}
        for i, x in enumerate(spec["outfit"]["pieces"]):
            if str(x.get("id")) == piece_id:
                spec["outfit"]["pieces"][i] = p
        live.spec = spec
        flag_modified(live, "spec")
        live.revision = int(live.revision or 1) + 1
        live.updated_at = datetime.now(UTC)
        db_session.add(live)
        db_session.commit()

    set_professional_provider_override(ConcurrentEditProvider(_flatten_to_solid))
    gen = client.post(
        f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
        headers=_auth(tokens),
        json={"idempotency_key": f"visual-ct-{uuid.uuid4().hex}"},
    )
    assert gen.status_code == 202, gen.text
    run_id = gen.json()["run_id"]
    assert run_techpack_worker_tick(db_session, limit=2) >= 1

    run_row = db_session.get(TechpackAIRun, uuid.UUID(run_id))
    assert run_row is not None
    result = run_row.result if isinstance(run_row.result, dict) else {}
    assert result.get("skipped_identity_drift") is True
    assert result.get("pdf_ready") is not True
    arts = list(
        db_session.scalars(
            select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run_row.id)
        ).all()
    )
    assert arts

    reopened = client.get(f"/api/v1/techpacks/{draft['id']}", headers=_auth(tokens)).json()
    live_piece = _piece_by_id(reopened["spec"], piece_id)
    assert live_piece["color_hint"] == "red"
    assert live_piece["color_treatment"]["mode"] == "solid"
    assert live_piece["visible_details"]["pocket_style"] == "none"
    illust = live_piece.get("illustrations") if isinstance(live_piece.get("illustrations"), dict) else {}
    assert illust.get("mode") != "professional"


def test_color_treatment_drift_independent_sqlalchemy_session(engine, monkeypatch):
    """Independent PG session: gradient→solid mid-run; keep latest design, no bind."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    email = f"visualindep_{uuid.uuid4().hex[:8]}@example.com"
    username = f"visualindep_{uuid.uuid4().hex[:8]}"
    user_id: uuid.UUID | None = None

    bootstrap = SessionLocal()
    try:
        inv = invitation_service.create_invitation(bootstrap, email=email, expires_in_hours=24)
        token = inv.plaintext_token
        bootstrap.commit()
    finally:
        bootstrap.close()

    worker = SessionLocal()
    try:
        user = auth_service.register_user(
            worker,
            UserRegister(
                email=email,
                username=username,
                password="StrongPass123!",
                invitation_code=token,
                display_name=username,
            ),
        )
        worker.commit()
        user_id = user.id
        job = AIJob(
            user_id=user_id,
            design_id=None,
            job_type="sketch_polish",
            status="completed",
            input_data={"studio_side": "front"},
            result_data={
                "summary": "red gradient shorts",
                "pipeline": "sketch_polish",
                "image_url": _store_image(),
            },
            error_message=None,
        )
        worker.add(job)
        worker.commit()
        worker.refresh(job)

        def _override_get_db():
            yield worker

        app.dependency_overrides[get_db] = _override_get_db
        _enable_ai(monkeypatch, email)
        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}"}
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "StrongPass123!"},
            )
            if login.status_code == 200:
                headers = _auth(login.json())

            created = client.post(
                "/api/v1/techpacks",
                headers=headers,
                json={"look_id": str(job.id), "title": "Visual indep"},
            )
            assert created.status_code == 201, created.text
            draft = created.json()
            draft_id = uuid.UUID(draft["id"])
            live = client.get(f"/api/v1/techpacks/{draft['id']}", headers=headers).json()
            pieces = live["spec"]["outfit"]["pieces"]
            target = pieces[0]
            target["category"] = "shorts"
            target["label"] = "Shorts"
            target["color_hint"] = "red"
            target["color_treatment"] = {
                "mode": "gradient",
                "stops": ["#AA0000", "#FFCCCC"],
                "direction": "left-to-right",
                "placement": "body",
                "designer_confirmed": True,
                "angle": 0,
            }
            finished = {}
            values = {
                "waist": 75.0,
                "hip": 110.0,
                "inseam": 18.0,
                "outseam": 42.0,
                "front_rise": 30.0,
                "back_rise": 40.0,
                "thigh": 58.0,
                "leg_opening": 40.0,
                "waistband": 4.0,
            }
            for key in FINISHED_POM["shorts"]:
                finished[key] = _designer_cell(values[key], definition=key)
            target["finished_measurements"] = finished
            patched = client.patch(
                f"/api/v1/techpacks/{draft['id']}",
                headers=headers,
                json={"spec": {"outfit": {"piece_count": len(pieces), "pieces": pieces}}},
            )
            assert patched.status_code == 200, patched.text
            worker.commit()
            piece_id = str(target["id"])

            def _owner_visual_edit() -> None:
                s = SessionLocal()
                try:
                    row = s.get(TechpackDraft, draft_id)
                    assert row is not None
                    spec = copy.deepcopy(row.spec if isinstance(row.spec, dict) else {})
                    p = _piece_by_id(spec, piece_id)
                    p["color_treatment"] = {
                        "mode": "solid",
                        "stops": ["#AA0000"],
                        "direction": "",
                        "placement": "body",
                        "designer_confirmed": True,
                    }
                    for i, x in enumerate(spec["outfit"]["pieces"]):
                        if str(x.get("id")) == piece_id:
                            spec["outfit"]["pieces"][i] = p
                    row.spec = spec
                    flag_modified(row, "spec")
                    row.revision = int(row.revision or 1) + 1
                    row.updated_at = datetime.now(UTC)
                    s.add(row)
                    s.commit()
                finally:
                    s.close()

            set_professional_provider_override(ConcurrentEditProvider(_owner_visual_edit))
            gen = client.post(
                f"/api/v1/techpacks/{draft['id']}/ai/generate-professional",
                headers=headers,
                json={"idempotency_key": f"vis-indep-{uuid.uuid4().hex}"},
            )
            assert gen.status_code == 202, gen.text
            run_id = gen.json()["run_id"]
            worker.commit()
            assert run_techpack_worker_tick(worker, limit=2) >= 1
            worker.commit()

            verify = SessionLocal()
            try:
                run_row = verify.get(TechpackAIRun, uuid.UUID(run_id))
                assert run_row is not None
                result = run_row.result if isinstance(run_row.result, dict) else {}
                assert result.get("skipped_identity_drift") is True
                arts = list(
                    verify.scalars(
                        select(TechpackAIArtifact).where(TechpackAIArtifact.run_id == run_row.id)
                    ).all()
                )
                assert arts
                row = verify.get(TechpackDraft, draft_id)
                assert row is not None
                live_piece = _piece_by_id(row.spec, piece_id)
                assert live_piece["color_treatment"]["mode"] == "solid"
                illust = (
                    live_piece.get("illustrations")
                    if isinstance(live_piece.get("illustrations"), dict)
                    else {}
                )
                assert illust.get("mode") != "professional"
            finally:
                verify.close()
    finally:
        set_professional_provider_override(None)
        app.dependency_overrides.pop(get_db, None)
        worker.close()
        _cleanup_user_rows(SessionLocal, user_id)
