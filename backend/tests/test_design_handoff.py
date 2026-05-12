import uuid

from app.auth.dependencies import get_current_user
from app.core.errors import ForbiddenError
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services import design_service


def _fake_user() -> User:
    u = User(email="maker@example.com", username="maker", hashed_password="x")
    u.id = uuid.uuid4()
    u.is_active = True
    return u


def _override_db():
    yield object()


def test_design_handoff_manifest_shape(client, monkeypatch):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _override_db

    def fake_manifest(_db, _design_id, _user):
        return {
            "schema_version": "1.0",
            "export_kind": "fashionrise.handoff.manifest_v1",
            "design": {"id": str(_design_id), "title": "Test look"},
            "revision_summary": {
                "count": 2,
                "latest_revision_number": 2,
                "recent": [
                    {"revision_number": 2, "notes": None, "created_at": "2026-05-11T10:00:00+00:00"},
                    {"revision_number": 1, "notes": "first", "created_at": "2026-05-11T09:00:00+00:00"},
                ],
            },
            "export_hints": {
                "intended_consumers": ["maker", "atelier", "classroom"],
                "next_exports": ["spec_sheet_pdf", "cut_plan_pdf"],
                "notes": "JSON-first",
            },
        }

    monkeypatch.setattr(design_service, "build_handoff_manifest", fake_manifest)

    design_id = uuid.uuid4()
    resp = client.get(f"/api/v1/designs/{design_id}/handoff")
    assert resp.status_code == 200
    body = resp.json()
    assert body["export_kind"] == "fashionrise.handoff.manifest_v1"
    assert body["revision_summary"]["latest_revision_number"] == 2
    assert body["export_hints"]["next_exports"] == ["spec_sheet_pdf", "cut_plan_pdf"]

    app.dependency_overrides.clear()


def test_design_handoff_forbidden_maps_to_403(client, monkeypatch):
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _override_db

    def fake_forbidden(_db, _design_id, _user):
        raise ForbiddenError("Not allowed to view this design handoff")

    monkeypatch.setattr(design_service, "build_handoff_manifest", fake_forbidden)

    resp = client.get(f"/api/v1/designs/{uuid.uuid4()}/handoff")
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["code"] == "forbidden"

    app.dependency_overrides.clear()
