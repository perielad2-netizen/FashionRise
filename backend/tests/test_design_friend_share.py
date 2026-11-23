"""Share saved design with accepted friend — pending approval then copy + grants."""

from __future__ import annotations

import base64
import io
import uuid

from PIL import Image

from app.core.config import get_settings
from app.services.ai_worker import run_magic_worker_tick
from app.services.friendship_service import ensure_accepted_friends
from app.services.personal_croquis_provider import (
    MockCroquisProvider,
    set_croquis_provider_override,
)
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_PROMPT_VERSION,
    set_try_on_provider_override,
)
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    enable_synthetic_croquis_notices,
    storage_body,
)


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(size: tuple[int, int] = (64, 96), color=(200, 100, 80, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _save_design(
    client,
    tokens,
    *,
    title: str = "Shared look",
    personal_croquis_id: str | None = None,
    personal_croquis_version: int | None = None,
) -> dict:
    save_id = str(uuid.uuid4())
    body = {
        "title": title,
        "garment_category": "dress",
        "visibility": "private",
        "status": "draft",
        "metadata": {
            "designKind": "saved_design",
            "envelope": "fashionrise.saved_design.v2",
            "saveRequestId": save_id,
        },
        "design_data": {
            "schema": "fashionrise.saved_design.v2",
            "saveRequestId": save_id,
            "savedAt": "2026-11-22T00:00:00Z",
            "sourceRevision": 1,
            "snapshot": {
                "strokes": [],
                "fills": [],
                "model": "personal" if personal_croquis_id else "female",
                "brush": {"size": 8, "opacity": 1, "color": "#111111"},
                "dimmed": False,
                "activeSide": "front",
                "back": {"strokes": [], "fills": []},
                "personalCroquisId": personal_croquis_id,
                "personalCroquisVersion": personal_croquis_version,
            },
        },
    }
    res = client.post("/api/v1/designs", headers=_auth(tokens), json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_share_requires_accept_before_my_designs(client, db_session):
    peri = register_with_invite(client, db_session, "peri_share@example.com", "PeriShare")
    yaniv = register_with_invite(client, db_session, "yaniv_share@example.com", "YanivShare")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriShare").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivShare").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(200, 40, 120)).save(buf, format="PNG")
    buf.seek(0)
    up = client.post(
        "/api/v1/fabrics",
        headers=_auth(peri),
        files={"file": ("tile.png", buf.getvalue(), "image/png")},
        data={"name": "Share Denim"},
    )
    assert up.status_code == 201, up.text
    fabric_id = up.json()["id"]

    design = _save_design(client, peri, title="Collab dress")
    share = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id), "note": "Your turn"},
    )
    assert share.status_code == 201, share.text
    payload = share.json()
    assert payload["received_design"] is None
    assert payload["transfer"]["status"] == "pending"
    transfer_id = payload["transfer"]["id"]

    # Not in My Designs until accepted.
    mine_before = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    assert mine_before.status_code == 200
    assert all("Collab dress" not in (row.get("title") or "") for row in mine_before.json())

    # Fabric not granted yet.
    fabrics_before = client.get("/api/v1/fabrics", headers=_auth(yaniv))
    assert fabric_id not in {row["id"] for row in fabrics_before.json()}

    inbox = client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv))
    assert inbox.status_code == 200, inbox.text
    assert len(inbox.json()) == 1
    assert inbox.json()[0]["id"] == transfer_id
    assert inbox.json()[0]["from_username"] == "PeriShare"

    accepted = client.post(
        f"/api/v1/designs/shares/{transfer_id}/accept",
        headers=_auth(yaniv),
    )
    assert accepted.status_code == 200, accepted.text
    accepted_body = accepted.json()
    assert accepted_body["transfer"]["status"] == "accepted"
    assert accepted_body["received_design"]["user_id"] == str(yaniv_user.id)
    assert "From PeriShare:" in accepted_body["received_design"]["title"]
    assert accepted_body["transfer"]["fabrics_granted"] >= 1

    mine = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    ids = {row["id"] for row in mine.json()}
    assert accepted_body["received_design"]["id"] in ids

    fabrics = client.get("/api/v1/fabrics", headers=_auth(yaniv))
    assert fabric_id in {row["id"] for row in fabrics.json()}
    img = client.get(f"/api/v1/fabrics/{fabric_id}/image", headers=_auth(yaniv))
    assert img.status_code == 200, img.text

    empty = client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv))
    assert empty.json() == []


def test_share_reject_keeps_out_of_my_designs(client, db_session):
    peri = register_with_invite(client, db_session, "peri_reject@example.com", "PeriReject")
    yaniv = register_with_invite(client, db_session, "yaniv_reject@example.com", "YanivReject")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriReject").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivReject").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="No thanks")
    share = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    transfer_id = share.json()["transfer"]["id"]
    rejected = client.post(
        f"/api/v1/designs/shares/{transfer_id}/reject",
        headers=_auth(yaniv),
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"

    mine = client.get("/api/v1/designs/my", headers=_auth(yaniv))
    assert all("No thanks" not in (row.get("title") or "") for row in mine.json())
    assert client.get("/api/v1/designs/shares/incoming", headers=_auth(yaniv)).json() == []


def test_share_requires_accepted_friend(client, db_session):
    peri = register_with_invite(client, db_session, "peri_nofriend@example.com", "PeriNoFriend")
    stranger = register_with_invite(client, db_session, "stranger_share@example.com", "StrangerShare")
    from app.models.user import User

    stranger_user = db_session.query(User).filter(User.username == "StrangerShare").one()
    design = _save_design(client, peri)
    res = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(stranger_user.id)},
    )
    assert res.status_code == 403


def test_share_back_and_forth_with_approval(client, db_session):
    peri = register_with_invite(client, db_session, "peri_ping@example.com", "PeriPing")
    yaniv = register_with_invite(client, db_session, "yaniv_pong@example.com", "YanivPong")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriPing").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivPong").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="Ping")
    first = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    assert first.status_code == 201, first.text
    tid = first.json()["transfer"]["id"]
    accepted = client.post(f"/api/v1/designs/shares/{tid}/accept", headers=_auth(yaniv))
    assert accepted.status_code == 200, accepted.text
    received_id = accepted.json()["received_design"]["id"]

    back = client.post(
        f"/api/v1/designs/{received_id}/share",
        headers=_auth(yaniv),
        json={"friend_user_id": str(peri_user.id), "note": "Back to you"},
    )
    assert back.status_code == 201, back.text
    assert back.json()["transfer"]["status"] == "pending"
    back_id = back.json()["transfer"]["id"]
    peri_accept = client.post(f"/api/v1/designs/shares/{back_id}/accept", headers=_auth(peri))
    assert peri_accept.status_code == 200, peri_accept.text
    assert peri_accept.json()["received_design"]["user_id"] == str(peri_user.id)
    assert "From YanivPong:" in peri_accept.json()["received_design"]["title"]


def test_recipient_can_delete_copy_without_touching_source(client, db_session):
    """Recipient deletes their copy only; sender's original stays."""
    peri = register_with_invite(client, db_session, "peri_delcopy@example.com", "PeriDelCopy")
    yaniv = register_with_invite(client, db_session, "yaniv_delcopy@example.com", "YanivDelCopy")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriDelCopy").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivDelCopy").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    design = _save_design(client, peri, title="Keep mine")
    source_id = design["id"]
    share = client.post(
        f"/api/v1/designs/{source_id}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id)},
    )
    assert share.status_code == 201, share.text
    tid = share.json()["transfer"]["id"]
    accepted = client.post(f"/api/v1/designs/shares/{tid}/accept", headers=_auth(yaniv))
    assert accepted.status_code == 200, accepted.text
    copy_id = accepted.json()["received_design"]["id"]
    assert accepted.json()["received_design"]["metadata"]["envelope"] == "fashionrise.saved_design.v2"
    assert accepted.json()["received_design"]["metadata"]["receivedViaShare"] is True

    deleted = client.delete(f"/api/v1/designs/saved/{copy_id}", headers=_auth(yaniv))
    assert deleted.status_code == 204, deleted.text

    assert client.get(f"/api/v1/designs/{copy_id}", headers=_auth(yaniv)).status_code == 404
    still = client.get(f"/api/v1/designs/{source_id}", headers=_auth(peri))
    assert still.status_code == 200, still.text
    assert still.json()["title"] == "Keep mine"


def test_legacy_boolean_envelope_share_copy_can_be_deleted(client, db_session):
    """Early share copies wrote metadata.envelope=True; delete must still work."""
    from app.models.garment_design import GarmentDesign
    from app.services.design_service import SAVED_DESIGN_V2

    peri = register_with_invite(client, db_session, "peri_legacy@example.com", "PeriLegacy")
    headers = _auth(peri)
    me = client.get("/api/v1/auth/me", headers=headers).json()
    save_id = str(uuid.uuid4())
    row = GarmentDesign(
        user_id=uuid.UUID(me["id"]),
        title="Legacy share copy",
        garment_category="dress",
        visibility="private",
        status="draft",
        metadata_={
            "designKind": "saved_design",
            "envelope": True,
            "receivedViaShare": True,
            "saveRequestId": save_id,
        },
        design_data={
            "schema": SAVED_DESIGN_V2,
            "saveRequestId": save_id,
            "savedAt": "2026-11-22T00:00:00Z",
            "sourceRevision": 1,
            "snapshot": {
                "strokes": [],
                "fills": [],
                "model": "female",
                "brush": {"size": 8, "opacity": 1, "color": "#111111"},
                "dimmed": False,
                "activeSide": "front",
                "back": {"strokes": [], "fills": []},
                "personalCroquisId": None,
                "personalCroquisVersion": None,
            },
        },
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    deleted = client.delete(f"/api/v1/designs/saved/{row.id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/designs/{row.id}", headers=headers).status_code == 404


class _MockTryOnProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.last_photo: bytes | None = None

    def generate(self, *, photo_png: bytes, garment_png: bytes, design_hints=None):
        self.calls += 1
        self.last_photo = photo_png
        out = _png_bytes((80, 120), (10, 20, 30, 255))
        return out, {"actual_cost_cents": 4, "prompt_version": TRY_ON_PROMPT_VERSION}


def test_share_grants_croquis_and_friend_can_try_on_person(client, db_session, monkeypatch):
    """Accept grants My Model + fabrics; friend Try On Person must use the shared photo."""
    enable_synthetic_croquis_notices(monkeypatch)
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", "1")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "3")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    get_settings.cache_clear()
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    mock_try = _MockTryOnProvider()
    set_try_on_provider_override(mock_try)

    peri = register_with_invite(client, db_session, "peri_tryon_share@example.com", "PeriTryShare")
    yaniv = register_with_invite(client, db_session, "yaniv_tryon_share@example.com", "YanivTryShare")
    from app.models.user import User

    peri_user = db_session.query(User).filter(User.username == "PeriTryShare").one()
    yaniv_user = db_session.query(User).filter(User.username == "YanivTryShare").one()
    ensure_accepted_friends(db_session, peri_user, yaniv_user)

    croquis_base = "/api/v1/personal-croquis"
    assert (
        client.post(
            f"{croquis_base}/attestations/adults",
            headers=_auth(peri),
            json=adults_body(),
        ).status_code
        == 200
    )
    storage = client.post(
        f"{croquis_base}/consent/storage",
        headers=_auth(peri),
        json=storage_body(),
    )
    assert storage.status_code == 200, storage.text
    up = client.post(
        f"{croquis_base}/photos",
        headers=_auth(peri),
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"sex": "female", "storage_consent_id": storage.json()["id"], "display_name": "Shared model"},
    )
    assert up.status_code == 201, up.text
    croquis = up.json()
    croquis_id = croquis["id"]
    ai = client.post(
        f"{croquis_base}/consent/ai",
        headers=_auth(peri),
        json=ai_body(croquis_id=croquis_id),
    )
    assert ai.status_code == 200, ai.text
    gen = client.post(
        f"{croquis_base}/{croquis_id}/versions/generate",
        headers=_auth(peri),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-share-tryon"},
    )
    assert gen.status_code == 201, gen.text
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    acc = client.post(
        f"{croquis_base}/{croquis_id}/versions/1/accept",
        headers=_auth(peri),
        json={},
    )
    assert acc.status_code == 200, acc.text

    # Friend cannot read the croquis before Accept.
    assert client.get(f"{croquis_base}/{croquis_id}", headers=_auth(yaniv)).status_code == 404

    design = _save_design(
        client,
        peri,
        title="Pinned My Model look",
        personal_croquis_id=croquis_id,
        personal_croquis_version=1,
    )
    share = client.post(
        f"/api/v1/designs/{design['id']}/share",
        headers=_auth(peri),
        json={"friend_user_id": str(yaniv_user.id), "note": "design with my model"},
    )
    assert share.status_code == 201, share.text
    transfer_id = share.json()["transfer"]["id"]
    accepted = client.post(
        f"/api/v1/designs/shares/{transfer_id}/accept",
        headers=_auth(yaniv),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["transfer"]["croquis_granted"] >= 1
    received = accepted.json()["received_design"]
    snap = (received.get("design_data") or {}).get("snapshot") or {}
    assert snap.get("personalCroquisId") == croquis_id
    assert snap.get("personalCroquisVersion") == 1

    # Underlay path: friend can read croquis + version after grant.
    got = client.get(f"{croquis_base}/{croquis_id}", headers=_auth(yaniv))
    assert got.status_code == 200, got.text
    assert got.json()["id"] == croquis_id

    garment = "data:image/png;base64," + base64.b64encode(
        _png_bytes((48, 64), (30, 90, 200, 200))
    ).decode("ascii")
    try_on = client.post(
        "/api/v1/ai/personal-try-on",
        headers=_auth(yaniv),
        json={
            "croquis_id": croquis_id,
            "croquis_version": 1,
            "garment_image_base64": garment,
            "idempotency_key": f"try_on:share-{uuid.uuid4()}",
            "source_revision": 1,
            "content_fingerprint": "fp-share-try-on",
            "consent_acknowledged": True,
            "consent_version": TRY_ON_CONSENT_VERSION,
        },
    )
    assert try_on.status_code == 201, try_on.text
    job_id = try_on.json()["id"]
    assert try_on.json()["user_id"] == str(yaniv_user.id)

    n = run_magic_worker_tick(db_session, limit=4)
    assert n >= 1
    assert mock_try.calls == 1
    assert mock_try.last_photo and len(mock_try.last_photo) > 32

    done = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(yaniv))
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["result_data"]["mode"] == "try_on_person"
    assert done.json()["result_data"]["image_url"]

    set_try_on_provider_override(None)
    set_croquis_provider_override(None)
    get_settings.cache_clear()
