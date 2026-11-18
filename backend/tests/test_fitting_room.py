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
        self.last_prompt_override: str | None = None

    def generate(
        self,
        *,
        photo_png: bytes,
        garment_png: bytes,
        design_hints=None,
        prompt_override: str | None = None,
        **kwargs,
    ):
        self.calls += 1
        self.last_hints = list(design_hints) if design_hints else []
        self.last_prompt_override = prompt_override
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
        return out, {
            "provider": "fashn_tryon_max",
            "actual_cost_cents": 8,
            "prediction_ids": ["pred_test"],
            "generation_mode": kwargs.get("generation_mode") or "quality",
            "resolution": kwargs.get("resolution") or "2k",
        }


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
    # Second call is Try-On Max quality · 2k (better swimwear/lingerie path).
    second = mock.kwargs[1]
    assert second.get("generation_mode") == "quality"
    assert second.get("resolution") == "2k"
    assert "skin tone" in (second.get("prompt") or "").lower()
    assert "bottle" in (second.get("prompt") or "").lower()
    result = job.result_data or {}
    assert result.get("provider") == "fashn_tryon_max"
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


def _jpeg_with_exif_orientation(orientation: int = 6) -> bytes:
    """Landscape 40×20 JPEG tagged Orientation=6 (display as 20×40 portrait)."""
    img = Image.new("RGB", (40, 20), (200, 50, 50))
    exif = img.getexif()
    exif[274] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif, quality=90)
    return buf.getvalue()


def test_decode_applies_exif_orientation_before_provider(client, db_session, monkeypatch):
    """Phone portrait JPEGs must be upright PNG before try-on (no 90° result flip)."""
    from app.services import fitting_room as fr

    _enable_fitting_room(monkeypatch, live=True)
    raw = _jpeg_with_exif_orientation(6)
    before = Image.open(io.BytesIO(raw))
    assert before.size == (40, 20)
    assert before.getexif().get(274) == 6

    data_url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    oriented = fr._decode_png(data_url, field="person_image_base64")
    assert oriented[:8] == b"\x89PNG\r\n\x1a\n"
    out = Image.open(io.BytesIO(oriented))
    assert out.size == (20, 40)
    assert out.getexif().get(274) in (None, 1)


def _two_tone_look_png(
    *,
    bodice=(90, 120, 70),
    skirt=(40, 70, 45),
    size=(200, 400),
) -> bytes:
    """Synthetic FashionRise look plate: light olive bodice over darker forest skirt."""
    im = Image.new("RGB", size, (245, 245, 245))
    w, h = size
    for y in range(int(h * 0.28), int(h * 0.46)):
        for x in range(int(w * 0.30), int(w * 0.70)):
            im.putpixel((x, y), bodice)
    for y in range(int(h * 0.52), int(h * 0.74)):
        for x in range(int(w * 0.25), int(w * 0.75)):
            im.putpixel((x, y), skirt)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_sample_look_garment_panel_colors_detects_lighter_bodice():
    from app.services.fitting_room import sample_look_garment_panel_colors

    lock = sample_look_garment_panel_colors(_two_tone_look_png())
    assert lock is not None
    assert lock["relation"] == "lighter_bodice"
    assert lock["bodice_hex"].startswith("#")
    assert lock["skirt_hex"].startswith("#")
    assert lock["luma_delta"] > 6


def test_look_plate_max_prompt_includes_color_lock():
    from app.services.fitting_room import (
        _fitting_room_max_prompt,
        sample_look_garment_panel_colors,
    )

    lock = sample_look_garment_panel_colors(_two_tone_look_png())
    prompt = _fitting_room_max_prompt(
        {"garment_source": "fashionrise_look", "look_color_lock": lock}
    )
    assert "COLOR LOCK" in prompt
    assert lock["bodice_hex"] in prompt
    assert lock["skirt_hex"] in prompt
    assert "lighter than the skirt" in prompt
    assert len(prompt) <= 1000


def test_look_plate_skips_max_first_flag_helper():
    from app.services.fitting_room import _is_fashionrise_look_plate

    assert _is_fashionrise_look_plate({"garment_source": "fashionrise_look"})
    assert _is_fashionrise_look_plate({"garment_sources": ["fashionrise_look"]})
    assert not _is_fashionrise_look_plate({"garment_source": "upload"})
    assert not _is_fashionrise_look_plate({})


def test_look_plate_openai_prompt_demands_photoreal_not_sketch():
    from app.services.fitting_room import (
        _fitting_room_openai_prompt,
        sample_look_garment_panel_colors,
    )

    lock = sample_look_garment_panel_colors(_two_tone_look_png())
    prompt = _fitting_room_openai_prompt(
        {"garment_source": "fashionrise_look", "look_color_lock": lock},
        [
            "Render real fabric photo matching image-1 lighting; no sketch overlay.",
            "1:1 look design; photoreal cloth not illustration paste.",
        ],
    )
    assert prompt is not None
    assert "photorealistic" in prompt.lower()
    assert "sketch" in prompt.lower()
    assert "one-to-one" in prompt.lower() or "1:1" in prompt
    assert lock["bodice_hex"] in prompt
    assert "COLOR LOCK" in prompt


def test_look_plate_max_prompt_asks_real_fabric_not_overlay():
    from app.services.fitting_room import _fitting_room_max_prompt

    prompt = _fitting_room_max_prompt({"garment_source": "fashionrise_look"})
    assert "REAL photographed clothing" in prompt or "real photographed" in prompt.lower()
    assert "sketch overlay" in prompt.lower()
    assert len(prompt) <= 1000
