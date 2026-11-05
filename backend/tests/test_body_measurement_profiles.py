"""Named reusable body measurement profiles for Create Real Design."""

from __future__ import annotations

from app.services.body_measurement_profile_service import apply_profile_to_spec
from app.services.techpack_spec import default_spec
from tests.auth_test_helpers import register_with_invite


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_create_list_apply_body_profile(client, db_session):
    tokens = register_with_invite(client, db_session, "bodyprof@example.com", "bodyprof")
    # Need a look to create a techpack — use Magic look fixture path via invite user.
    # Create profile first (no look required).
    created = client.post(
        "/api/v1/techpacks/measurement-profiles",
        headers=_auth(tokens),
        json={
            "name": "Mom",
            "units": "cm",
            "sample_size": "M",
            "measurements": {
                "height": {"value": 168, "unit": "cm"},
                "bust": {"value": 92, "unit": "cm"},
                "waist": {"value": 74, "unit": "cm"},
                "hip": {"value": 98, "unit": "cm"},
            },
            "is_default": True,
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile["name"] == "Mom"
    assert profile["is_default"] is True
    assert profile["measurements"]["bust"]["value"] == 92
    assert profile["measurements"]["bust"]["source"] == "designer"

    listed = client.get("/api/v1/techpacks/measurement-profiles", headers=_auth(tokens))
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Second person
    second = client.post(
        "/api/v1/techpacks/measurement-profiles",
        headers=_auth(tokens),
        json={
            "name": "Me",
            "measurements": {"height": {"value": 175}, "waist": {"value": 80}},
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["is_default"] is False

    # Reject empty measurements
    empty = client.post(
        "/api/v1/techpacks/measurement-profiles",
        headers=_auth(tokens),
        json={"name": "Empty", "measurements": {}},
    )
    assert empty.status_code in (400, 422)


def test_apply_profile_to_spec_sets_body_and_lineage():
    profile_like = type(
        "P",
        (),
        {
            "id": __import__("uuid").uuid4(),
            "name": "Client Anna",
            "units": "cm",
            "sample_size": "38",
            "measurements": {
                "height": {"value": 170, "unit": "cm", "source": "designer"},
                "bust": {"value": 88, "unit": "cm", "source": "designer"},
                "waist": {"value": 70, "unit": "cm", "source": "designer"},
                "hip": {"value": 94, "unit": "cm", "source": "designer"},
                "inseam": {"value": None, "unit": "cm", "source": "empty"},
            },
        },
    )()
    spec = default_spec(look_summary="ivory evening column dress")
    out = apply_profile_to_spec(spec, profile_like)
    assert out["body"]["bust"]["value"] == 88
    assert out["body"]["bust"]["source"] == "designer"
    assert out["sample_size"] == "38"
    assert out["ai"]["body_profile_name"] == "Client Anna"
    assert out["ai"]["body_profile_id"] == str(profile_like.id)
