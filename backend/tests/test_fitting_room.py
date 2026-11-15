"""AI Fitting Room F1–F3 — gate, enqueue, success/fail (mocked provider)."""

from __future__ import annotations

import base64
import io
import uuid

import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.services.ai_worker import run_magic_worker_tick
from app.services.fitting_room import FITTING_ROOM_CONSENT_VERSION, FITTING_ROOM_JOB_TYPE
from app.services.personal_try_on_provider import (
    ProviderNotAvailableError,
    set_try_on_provider_override,
)
from tests.auth_test_helpers import register_with_invite

FR = "/api/v1/ai/fitting-room"


def _png_bytes(size: tuple[int, int] = (64, 96), color=(200, 100, 80, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _data_url(color=(30, 90, 200, 200)) -> str:
    raw = _png_bytes((48, 64), color)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enable_fitting_room(monkeypatch, *, live: bool = True):
    get_settings.cache_clear()
    monkeypatch.setenv("FITTING_ROOM_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LIVE_HTTP", "true" if live else "false")
    get_settings.cache_clear()


def _disable_fitting_room(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("FITTING_ROOM_ENABLED", raising=False)
    monkeypatch.delenv("FITTING_ROOM_LIVE_HTTP", raising=False)
    get_settings.cache_clear()


class MockTryOnProvider:
    def __init__(self, *, fail: Exception | None = None):
        self.calls = 0
        self.fail = fail
        self.last_hints: list[str] = []

    def generate(self, *, photo_png: bytes, garment_png: bytes, design_hints=None):
        self.calls += 1
        self.last_hints = list(design_hints) if design_hints else []
        if self.fail is not None:
            raise self.fail
        out = _png_bytes((80, 120), (10, 20, 30, 255))
        return out, {"actual_cost_cents": 4, "provider": "mock"}


@pytest.fixture(autouse=True)
def _cleanup(monkeypatch, db_session):
    set_try_on_provider_override(None)
    db_session.query(AIJob).filter(AIJob.job_type == FITTING_ROOM_JOB_TYPE).delete()
    db_session.flush()
    yield
    set_try_on_provider_override(None)
    _disable_fitting_room(monkeypatch)


def test_preflight_fail_closed(client, db_session):
    tokens = register_with_invite(
        client, db_session, email="fr-pre@example.com", username="fr_pre"
    )
    r = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["enabled"] is False
    assert body["consent_version"] == FITTING_ROOM_CONSENT_VERSION
    assert "auto" in body["supported_categories"]
    assert body["stars_cost"] == 20
    assert "flat" in (body.get("stars_cost_note") or "").lower()


def test_enqueue_blocked_when_disabled(client, db_session):
    tokens = register_with_invite(
        client, db_session, email="fr-off@example.com", username="fr_off"
    )
    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url(),
            "garment_image_base64": _data_url((200, 40, 40, 255)),
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 403


def _grant_stars(db_session, username: str, amount: int = 20) -> None:
    from app.models.user import User

    u = db_session.query(User).filter(User.username == username).first()
    assert u is not None
    u.ai_stars = amount
    db_session.commit()


def test_fitting_room_success_flat_20_stars(client, db_session, monkeypatch):
    _enable_fitting_room(monkeypatch)
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    tokens = register_with_invite(
        client, db_session, email="fr-ok@example.com", username="fr_ok"
    )
    _grant_stars(db_session, "fr_ok", amount=40)

    from app.models.user import User

    before = db_session.query(User).filter(User.username == "fr_ok").one().ai_stars

    key = f"fitting_room:{uuid.uuid4()}"
    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {"image_base64": _data_url((40, 80, 200, 255)), "category": "tops"},
                {"image_base64": _data_url((20, 160, 80, 255)), "category": "bottoms"},
                {"image_base64": _data_url((180, 40, 40, 255)), "category": "outerwear"},
            ],
            "idempotency_key": key,
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    assert r.json()["job_type"] == FITTING_ROOM_JOB_TYPE
    # Response must not echo person/garment bytes.
    assert "person_image_base64" not in (r.json().get("input_data") or {})
    assert "garment_image_base64" not in (r.json().get("input_data") or {})

    processed = run_magic_worker_tick(db_session, limit=4)
    assert processed >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None
    assert job.status == "completed"
    assert mock.calls == 1
    assert any("outfit_piece_count:3" in h for h in mock.last_hints)
    result = job.result_data or {}
    assert result.get("image_url")
    assert result.get("mode") == "fitting_room"
    assert result.get("stars_cost") == 20
    assert result.get("stars_debited") is True
    assert "preview" in (result.get("summary") or "").lower()
    after = db_session.query(User).filter(User.username == "fr_ok").one().ai_stars
    # Flat 20 even for 3 pieces — not 60.
    assert after == before - 20


def test_fitting_room_failure_no_success_status(client, db_session, monkeypatch):
    _enable_fitting_room(monkeypatch)
    mock = MockTryOnProvider(fail=ProviderNotAvailableError("provider down"))
    set_try_on_provider_override(mock)
    tokens = register_with_invite(
        client, db_session, email="fr-fail@example.com", username="fr_fail"
    )
    _grant_stars(db_session, "fr_fail")

    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url(),
            "garment_image_base64": _data_url((10, 10, 10, 255)),
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    run_magic_worker_tick(db_session, limit=4)
    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None
    assert job.status == "failed"
    result = job.result_data or {}
    assert result.get("status") == "failed"
    assert result.get("stars_debited") is not True
    # Owner-safe copy — never dump raw provider exceptions.
    assert "BadRequestError" not in (job.error_message or "")
    assert "moderation_blocked" not in (job.error_message or "").lower()


class _OpenAiThenFashnMock:
    """First generate = OpenAI moderation; second = FASHN success (same override)."""

    def __init__(self):
        self.calls = 0
        self.kwargs: list[dict] = []

    def generate(self, *, photo_png: bytes, garment_png: bytes, design_hints=None, **kwargs):
        self.calls += 1
        self.kwargs.append({"design_hints": design_hints, **kwargs})
        if self.calls == 1:
            err = ProviderNotAvailableError(
                "images.edit rejected by provider: BadRequestError status=400 "
                "code=moderation_blocked categories=sexual"
            )
            err.safe_meta = {
                "error_code": "PROVIDER_MODERATION_BLOCKED",
                "provider_code": "moderation_blocked",
                "moderation_stage": "input",
                "categories": ["sexual"],
                "http_status": 400,
            }
            raise err
        out = _png_bytes((80, 120), (90, 40, 160, 255))
        return out, {"provider": "fashn", "actual_cost_cents": 8, "prediction_ids": ["pred_test"]}


def test_fitting_room_openai_moderation_falls_back_to_fashn(client, db_session, monkeypatch):
    _enable_fitting_room(monkeypatch)
    mock = _OpenAiThenFashnMock()
    set_try_on_provider_override(mock)
    tokens = register_with_invite(
        client, db_session, email="fr-swim@example.com", username="fr_swim"
    )
    _grant_stars(db_session, "fr_swim", amount=40)

    from app.models.user import User

    before = db_session.query(User).filter(User.username == "fr_swim").one().ai_stars

    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {"image_base64": _data_url((40, 180, 200, 255)), "category": "one-pieces"},
            ],
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    processed = run_magic_worker_tick(db_session, limit=4)
    assert processed >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None
    assert job.status == "completed", (job.error_message, job.result_data)
    assert mock.calls == 2
    result = job.result_data or {}
    assert result.get("provider") == "fashn"
    assert result.get("fallback_from") == "openai"
    assert result.get("image_url")
    assert result.get("stars_cost") == 20
    assert result.get("stars_debited") is True
    assert "moderation_blocked" not in (job.error_message or "").lower()
    after = db_session.query(User).filter(User.username == "fr_swim").one().ai_stars
    assert after == before - 20


def test_fitting_room_moderation_without_fashn_keeps_owner_safe_copy(
    client, db_session, monkeypatch
):
    _enable_fitting_room(monkeypatch)
    # Fail once; override present so _fashn_fallback_armed is True — force fallback
    # itself to fail by raising on second call with a non-recoverable mock.
    class _ModerationOnlyFail(MockTryOnProvider):
        def generate(self, *, photo_png: bytes, garment_png: bytes, design_hints=None, **kwargs):
            self.calls += 1
            err = ProviderNotAvailableError("moderation_blocked sexual")
            err.safe_meta = {
                "error_code": "PROVIDER_MODERATION_BLOCKED",
                "moderation_stage": "input",
                "categories": ["sexual"],
            }
            raise err

    set_try_on_provider_override(_ModerationOnlyFail())
    tokens = register_with_invite(
        client, db_session, email="fr-mod@example.com", username="fr_mod"
    )
    _grant_stars(db_session, "fr_mod")

    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url(),
            "garment_image_base64": _data_url((10, 10, 10, 255)),
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    run_magic_worker_tick(db_session, limit=4)
    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None
    assert job.status == "failed"
    msg = (job.error_message or "").lower()
    assert "badrequesterror" not in msg
    assert "moderation_blocked" not in msg
    assert "request_id" not in msg
    assert "no stars were charged" in msg
    assert (job.result_data or {}).get("error_code") == "PROVIDER_FALLBACK_FAILED"
