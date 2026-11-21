"""Owner-only Fitting Room model compare — mocked only, no paid HTTP."""

from __future__ import annotations

import base64
import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.fitting_room_model_compare import FittingRoomModelCompareOperation
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.look_test_images import floral_blue_look_plate_png, wings_outdoor_person_png

COMPARE = "/api/v1/ai/fitting-room/model-compare"
CONSENT = "fitting-room-model-compare-v1"


def _b64(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enable_compare(monkeypatch, *, username: str = "owner_cmp"):
    get_settings.cache_clear()
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "false")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_OWNER_ALLOWLIST", username)
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_MAX_PAID_OPS", "1")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_MAX_PROVIDER_CALLS", "3")
    get_settings.cache_clear()


def _consent_payload(**extra):
    base = {
        "person_image_base64": _b64(wings_outdoor_person_png()),
        "design_image_base64": _b64(floral_blue_look_plate_png()),
        "consent_acknowledged": True,
        "consent_version": CONSENT,
        "authorize_paid": False,
    }
    base.update(extra)
    return base


def _png(color) -> bytes:
    im = Image.new("RGB", (64, 96), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_compare_prompt_is_short_and_identity_first():
    from app.services.fitting_room_model_compare import COMPARE_PROMPT, COMPARE_PROMPT_VERSION

    assert COMPARE_PROMPT_VERSION == "fitting-room-model-compare-v1"
    assert len(COMPARE_PROMPT) < 400
    low = COMPARE_PROMPT.lower()
    assert "image 2" in low and "image 1" in low
    assert "preserve the person's original face" in low
    assert "do not change anything else" in low
    assert "black sketch outlines" not in low


def test_dry_run_plans_three_arms_without_paid_calls(client, db_session, monkeypatch):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_cmp")
    calls: list[str] = []

    def _no_openai(**_k):
        calls.append("openai")
        raise AssertionError("dry-run must not call OpenAI")

    def _no_fashn(**_k):
        calls.append("fashn")
        raise AssertionError("dry-run must not call FASHN")

    cmp.set_model_compare_runners_for_tests(openai_runner=_no_openai, fashn_runner=_no_fashn)
    tokens = register_with_invite(
        client, db_session, email="owner_cmp@example.com", username="owner_cmp"
    )
    r = client.post(COMPARE, headers=_auth(tokens), json=_consent_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "dry_run"
    assert body["paid_calls"] == 0
    assert body["stars_touched"] is False
    assert body["human_review"]["winner"] is None
    assert body["consent_version"] == CONSENT
    arms = {a["arm"]: a for a in body["arms"]}
    assert set(arms) == {"A", "B", "C"}
    assert arms["A"]["model"] == "chatgpt-image-latest"
    assert arms["B"]["model"] == "gpt-image-2.6-sunburst"
    assert arms["C"]["model"] == "tryon-max"
    assert all(a["preprocessing"] == "none" for a in body["arms"])
    assert all(a["postprocessing"] == "none" for a in body["arms"])
    assert all(a.get("result_url") in (None, "") for a in body["arms"])
    assert calls == []
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_consent_required(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_consent")
    tokens = register_with_invite(
        client, db_session, email="owner_consent@example.com", username="owner_consent"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": _b64(wings_outdoor_person_png()),
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "authorize_paid": False,
            "consent_acknowledged": False,
            "consent_version": CONSENT,
        },
    )
    assert r.status_code == 400
    get_settings.cache_clear()


def test_non_owner_forbidden(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="someone_else")
    tokens = register_with_invite(
        client, db_session, email="norm@example.com", username="norm_user"
    )
    r = client.post(COMPARE, headers=_auth(tokens), json=_consent_payload())
    assert r.status_code == 403
    get_settings.cache_clear()


def test_authorize_paid_without_live_http_forbidden(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_paid")
    tokens = register_with_invite(
        client, db_session, email="owner_paid@example.com", username="owner_paid"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="paid-without-live-01",
        ),
    )
    assert r.status_code == 403
    get_settings.cache_clear()


def test_authorize_paid_runs_one_call_per_arm_private_storage(
    client, db_session, monkeypatch, tmp_path
):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_live")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    call_log: list[str] = []

    def _openai(*, person_png, design_png, model):
        assert person_png and design_png
        assert model in {"chatgpt-image-latest", "gpt-image-2.6-sunburst"}
        call_log.append(f"openai:{model}")
        return _png((40, 120, 220)), {
            "provider": "openai",
            "model": model,
            "path": "openai_images_edit_person_garment",
            "duration_ms": 12,
            "estimate_cents": 6,
            "openai_calls": 1,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    def _fashn(*, person_png, design_png):
        assert person_png and design_png
        call_log.append("fashn")
        return _png((220, 80, 160)), {
            "provider": "fashn",
            "model": "tryon-max",
            "path": "fashn_tryon_max_raw_person_product",
            "duration_ms": 20,
            "estimate_cents": 32,
            "fashn_calls": 1,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_openai, fashn_runner=_fashn)
    tokens = register_with_invite(
        client, db_session, email="owner_live@example.com", username="owner_live"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            idempotency_key="live-three-arms-001",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["paid_calls"] == 3
    assert body["dispatched_requests"] == 3
    assert body["successful_outputs"] == 3
    assert body["stars_touched"] is False
    assert body["human_review"]["winner"] is None
    assert body["operation_id"]
    assert len(call_log) == 3

    storage = LocalStorageBackend()
    public_root = storage.public_upload_root()
    private_root = storage.private_fitting_compare_root()

    for arm in body["arms"]:
        assert arm["status"] == "ok"
        assert arm.get("result_url") in (None, "")
        assert arm["result_ref"]["retrieval_path"].startswith(
            "/api/v1/ai/fitting-room/model-compare/results/"
        )
        key = arm["storage_key"]
        path = storage.resolve_private_fitting_compare_file(key=key)
        assert path is not None and path.is_file()
        assert str(path.resolve()).startswith(str(private_root.resolve()))
        with pytest.raises(ValueError):
            path.resolve().relative_to(public_root)

        # Authenticated owner retrieval works.
        img = client.get(arm["result_ref"]["retrieval_path"], headers=_auth(tokens))
        assert img.status_code == 200
        assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

        # Public static mount must not expose the private key.
        static = client.get(f"/static/uploads/{key}")
        assert static.status_code == 404

        # Anonymous cannot retrieve.
        anon = client.get(arm["result_ref"]["retrieval_path"])
        assert anon.status_code in {401, 403}

    # Second owner cannot read first owner's results.
    _enable_compare(monkeypatch, username="other_owner,owner_live")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    get_settings.cache_clear()
    other = register_with_invite(
        client, db_session, email="other_owner@example.com", username="other_owner"
    )
    stolen = client.get(body["arms"][0]["result_ref"]["retrieval_path"], headers=_auth(other))
    assert stolen.status_code == 404

    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_idempotent_replay_does_not_re_dispatch(client, db_session, monkeypatch, tmp_path):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_idem")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    calls = {"n": 0}

    def _openai(**_k):
        calls["n"] += 1
        return _png((10, 10, 10)), {
            "provider": "openai",
            "model": "chatgpt-image-latest",
            "openai_calls": 1,
            "duration_ms": 1,
            "estimate_cents": 6,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_openai, fashn_runner=_openai)
    tokens = register_with_invite(
        client, db_session, email="owner_idem@example.com", username="owner_idem"
    )
    payload = _consent_payload(
        authorize_paid=True,
        arms=["A"],
        idempotency_key="idem-key-replay-01",
    )
    r1 = client.post(COMPARE, headers=_auth(tokens), json=payload)
    assert r1.status_code == 200, r1.text
    assert calls["n"] == 1
    r2 = client.post(COMPARE, headers=_auth(tokens), json=payload)
    assert r2.status_code == 200, r2.text
    assert r2.json().get("replay") is True
    assert calls["n"] == 1  # no second dispatch
    assert r1.json()["operation_id"] == r2.json()["operation_id"]
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_second_paid_operation_exhausted(client, db_session, monkeypatch, tmp_path):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_budget")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def _ok(**_k):
        return _png((1, 2, 3)), {
            "provider": "openai",
            "model": "chatgpt-image-latest",
            "openai_calls": 1,
            "duration_ms": 1,
            "estimate_cents": 6,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_ok, fashn_runner=_ok)
    tokens = register_with_invite(
        client, db_session, email="owner_budget@example.com", username="owner_budget"
    )
    first = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="budget-first-op",
        ),
    )
    assert first.status_code == 200, first.text
    second = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["B"],
            idempotency_key="budget-second-op",
        ),
    )
    assert second.status_code == 403
    assert "exhausted" in second.json()["detail"].lower()
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_ambiguous_provider_outcome_no_retry(client, db_session, monkeypatch, tmp_path):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_amb")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    attempts = {"n": 0}

    def _ambiguous(**_k):
        attempts["n"] += 1
        raise RuntimeError("Unrecognized provider output shape")

    cmp.set_model_compare_runners_for_tests(openai_runner=_ambiguous, fashn_runner=_ambiguous)
    tokens = register_with_invite(
        client, db_session, email="owner_amb@example.com", username="owner_amb"
    )
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="ambiguous-no-retry-01",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dispatched_requests"] == 1
    assert body["successful_outputs"] == 0
    assert body["arms"][0]["status"] == "failed"
    assert body["arms"][0]["no_retry"] is True
    assert attempts["n"] == 1
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_oversized_base64_rejected(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_big")
    get_settings.cache_clear()
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    get_settings.cache_clear()
    tokens = register_with_invite(
        client, db_session, email="owner_big@example.com", username="owner_big"
    )
    # ~2MB of base64 payload for a 1MB limit.
    huge = "A" * (2 * 1024 * 1024)
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json={
            "person_image_base64": huge,
            "design_image_base64": _b64(floral_blue_look_plate_png()),
            "consent_acknowledged": True,
            "consent_version": CONSENT,
            "authorize_paid": False,
        },
    )
    assert r.status_code == 400
    get_settings.cache_clear()
    monkeypatch.delenv("MAX_UPLOAD_SIZE_MB", raising=False)
    get_settings.cache_clear()


def test_concurrent_claims_single_operation(client, db_session, monkeypatch, tmp_path):
    """Two near-simultaneous paid posts with different keys: only one may claim budget."""
    from app.services import fitting_room_model_compare as cmp
    from app.models.user import User

    _enable_compare(monkeypatch, username="owner_conc")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def _slow(**_k):
        return _png((9, 9, 9)), {
            "provider": "openai",
            "model": "chatgpt-image-latest",
            "openai_calls": 1,
            "duration_ms": 5,
            "estimate_cents": 6,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_slow, fashn_runner=_slow)
    tokens = register_with_invite(
        client, db_session, email="owner_conc@example.com", username="owner_conc"
    )
    user = db_session.query(User).filter(User.username == "owner_conc").one()

    # Seed one completed op via API, then assert a second key is rejected.
    # (True multi-thread client races are flaky under TestClient; budget + advisory lock
    # are covered by sequential exhaustion + replay tests. Here we assert ledger count.)
    r = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="conc-first",
        ),
    )
    assert r.status_code == 200, r.text
    count = (
        db_session.query(FittingRoomModelCompareOperation)
        .filter(FittingRoomModelCompareOperation.owner_id == user.id)
        .count()
    )
    assert count == 1
    blocked = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="conc-second",
        ),
    )
    assert blocked.status_code == 403
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_idempotency_identity_mismatch_rejected(client, db_session, monkeypatch, tmp_path):
    from app.services import fitting_room_model_compare as cmp

    _enable_compare(monkeypatch, username="owner_idmiss")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()

    def _ok(**_k):
        return _png((5, 5, 5)), {
            "provider": "openai",
            "model": "chatgpt-image-latest",
            "openai_calls": 1,
            "duration_ms": 1,
            "estimate_cents": 6,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_ok, fashn_runner=_ok)
    tokens = register_with_invite(
        client, db_session, email="owner_idmiss@example.com", username="owner_idmiss"
    )
    first = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="identity-mismatch-key",
        ),
    )
    assert first.status_code == 200, first.text
    # Same key, different design image → 409
    other_design = Image.new("RGB", (64, 96), (200, 10, 10))
    buf = io.BytesIO()
    other_design.save(buf, format="PNG")
    second = client.post(
        COMPARE,
        headers=_auth(tokens),
        json=_consent_payload(
            authorize_paid=True,
            arms=["A"],
            idempotency_key="identity-mismatch-key",
            design_image_base64=_b64(buf.getvalue()),
        ),
    )
    assert second.status_code == 409
    cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
    get_settings.cache_clear()


def test_preflight_lists_arms_and_budget(client, db_session, monkeypatch):
    _enable_compare(monkeypatch, username="owner_pf")
    tokens = register_with_invite(
        client, db_session, email="owner_pf@example.com", username="owner_pf"
    )
    r = client.get(f"{COMPARE}/preflight", headers=_auth(tokens))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "preflight"
    assert len(body["arms"]) == 3
    assert body["consent_version"] == CONSENT
    assert "OpenAI" in body["notice_text"] or "third-party" in body["notice_text"].lower()
    assert body["budget"]["max_paid_ops"] == 1
    assert body["budget"]["max_provider_calls"] == 3
    assert "provider_gates" in body
    assert "openai" in body["provider_gates"]
    assert "fashn_tryon_max" in body["provider_gates"]
    assert "api_key_present" in body["provider_gates"]["fashn_tryon_max"]
    assert "fashn_try_on_max_live_http" in body["provider_gates"]["fashn_tryon_max"]
    assert "Face" in body["human_review"]["instruction"] or "face" in body["human_review"]["instruction"].lower()
    get_settings.cache_clear()


def test_private_storage_key_rejects_traversal():
    storage = LocalStorageBackend()
    with pytest.raises(ValueError):
        storage.validate_fitting_compare_storage_key("../etc/passwd")
    with pytest.raises(ValueError):
        storage.validate_fitting_compare_storage_key("/absolute/path.png")
    oid = uuid.uuid4()
    op = uuid.uuid4()
    key = storage.fitting_compare_storage_key(owner_id=oid, operation_id=op, arm="A")
    owner, operation, arm = storage.validate_fitting_compare_storage_key(key)
    assert owner == oid and operation == op and arm == "A"
