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
        self.last_garment_png: bytes | None = None

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
        self.last_garment_png = garment_png
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
    note = (body.get("stars_cost_note") or "").lower()
    assert "20" in note or "stars" in note
    assert body.get("max_outfit_pieces") == 1


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
    assert any("outfit_piece_count:1" in h for h in mock.last_hints)
    result = job.result_data or {}
    assert result.get("image_url")
    assert result.get("mode") == "fitting_room"
    assert result.get("stars_cost") == 20
    assert result.get("stars_debited") is True
    assert "preview" in (result.get("summary") or "").lower()
    after = db_session.query(User).filter(User.username == "fr_ok").one().ai_stars
    assert after == before - 20


def test_fitting_room_rejects_multi_piece_outfit(client, db_session, monkeypatch):
    """Collage multi-item (dress+boot+gloves) is not reliable — enforce one piece."""
    from app.services.fitting_room import MAX_OUTFIT_PIECES

    assert MAX_OUTFIT_PIECES == 1
    _enable_fitting_room(monkeypatch)
    set_try_on_provider_override(MockTryOnProvider())
    tokens = register_with_invite(
        client, db_session, email="fr-multi@example.com", username="fr_multi"
    )
    _grant_stars(db_session, "fr_multi", amount=40)
    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {"image_base64": _data_url((40, 80, 200, 255)), "category": "dresses"},
                {"image_base64": _data_url((20, 20, 20, 255)), "category": "shoes"},
            ],
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 400, r.text
    assert "at most 1" in (r.json().get("detail") or "").lower()


def test_preflight_reports_max_one_outfit_piece(client, db_session, monkeypatch):
    _enable_fitting_room(monkeypatch)
    tokens = register_with_invite(
        client, db_session, email="fr-max1@example.com", username="fr_max1"
    )
    r = client.get(f"{FR}/preflight", headers=_auth(tokens))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["max_outfit_pieces"] == 1
    assert "one clothing or shoes" in (body.get("stars_cost_note") or "").lower()


def test_fitting_room_social_tryon_credits_other_designer_two_stars(
    client, db_session, monkeypatch
):
    """Successful Social Fitting Room try-on credits the look owner +2 (not self)."""
    from app.models.competition import StarPayout
    from app.models.gallery_item import GalleryItem
    from app.models.user import User
    from app.services.fitting_room import FITTING_ROOM_DESIGNER_TRYON_STARS

    _enable_fitting_room(monkeypatch)
    set_try_on_provider_override(MockTryOnProvider())

    designer_tokens = register_with_invite(
        client, db_session, email="fr-des@example.com", username="fr_des"
    )
    viewer_tokens = register_with_invite(
        client, db_session, email="fr-viewer@example.com", username="fr_viewer"
    )
    designer = db_session.query(User).filter(User.username == "fr_des").one()
    viewer = db_session.query(User).filter(User.username == "fr_viewer").one()
    designer.ai_stars = 10
    viewer.ai_stars = 40
    item = GalleryItem(
        look_id=uuid.uuid4(),
        user_id=designer.id,
        title="Designer look",
        image_url="https://example.com/look.png",
        visibility="public",
        moderation_status="ok",
    )
    db_session.add(item)
    db_session.commit()
    gallery_id = item.id
    designer_before = designer.ai_stars
    viewer_before = viewer.ai_stars

    r = client.post(
        f"{FR}/try-on",
        headers=_auth(viewer_tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {
                    "image_base64": _data_url((40, 80, 200, 255)),
                    "category": "dresses",
                    "source": "fashionrise_look",
                }
            ],
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
            "source_gallery_item_id": str(gallery_id),
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    assert run_magic_worker_tick(db_session, limit=4) >= 1
    db_session.expire_all()

    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None and job.status == "completed"
    assert (job.input_data or {}).get("source_gallery_item_id") == str(gallery_id)

    designer_after = db_session.query(User).filter(User.username == "fr_des").one().ai_stars
    viewer_after = db_session.query(User).filter(User.username == "fr_viewer").one().ai_stars
    assert designer_after == designer_before + FITTING_ROOM_DESIGNER_TRYON_STARS
    assert viewer_after == viewer_before - 20

    payout = (
        db_session.query(StarPayout)
        .filter(StarPayout.payout_key == f"fitting_room_designer_tryon:{job_id}")
        .one()
    )
    assert payout.user_id == designer.id
    assert payout.amount == FITTING_ROOM_DESIGNER_TRYON_STARS
    assert payout.reason == "fitting_room_designer_tryon"

    # Own-design try-on: same designer tries their look — no extra designer credit.
    _grant_stars(db_session, "fr_des", amount=40)
    designer_before_own = (
        db_session.query(User).filter(User.username == "fr_des").one().ai_stars
    )
    own = client.post(
        f"{FR}/try-on",
        headers=_auth(designer_tokens),
        json={
            "person_image_base64": _data_url((10, 20, 30, 255)),
            "garment_pieces": [
                {
                    "image_base64": _data_url((90, 40, 10, 255)),
                    "category": "dresses",
                    "source": "fashionrise_look",
                }
            ],
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
            "source_gallery_item_id": str(gallery_id),
        },
    )
    assert own.status_code == 201, own.text
    own_job_id = own.json()["id"]
    assert run_magic_worker_tick(db_session, limit=4) >= 1
    db_session.expire_all()
    designer_after_own = (
        db_session.query(User).filter(User.username == "fr_des").one().ai_stars
    )
    # Spent 20 for own try-on; no +2 designer reward.
    assert designer_after_own == designer_before_own - 20
    assert (
        db_session.query(StarPayout)
        .filter(StarPayout.payout_key == f"fitting_room_designer_tryon:{own_job_id}")
        .count()
        == 0
    )


def test_fitting_room_upload_tryon_does_not_credit_designer(
    client, db_session, monkeypatch
):
    """Uploaded garments (no Social gallery source) never mint designer Stars."""
    from app.models.competition import StarPayout
    from app.models.user import User

    _enable_fitting_room(monkeypatch)
    set_try_on_provider_override(MockTryOnProvider())
    tokens = register_with_invite(
        client, db_session, email="fr-up@example.com", username="fr_up"
    )
    _grant_stars(db_session, "fr_up", amount=40)

    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {"image_base64": _data_url((40, 80, 200, 255)), "category": "tops"}
            ],
            "idempotency_key": f"fitting_room:{uuid.uuid4()}",
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    assert run_magic_worker_tick(db_session, limit=4) >= 1
    db_session.expire_all()
    assert (
        db_session.query(StarPayout)
        .filter(StarPayout.reason == "fitting_room_designer_tryon")
        .count()
        == 0
    )
    assert db_session.query(User).filter(User.username == "fr_up").one().ai_stars == 20


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
    assert "footwear" in prompt.lower() or "shoes" in prompt.lower()


def test_look_plate_max_prompt_asks_real_fabric_not_overlay():
    from app.services.fitting_room import _fitting_room_max_prompt

    prompt = _fitting_room_max_prompt({"garment_source": "fashionrise_look"})
    assert "REAL photographed clothing" in prompt or "real photographed" in prompt.lower()
    assert "sketch overlay" in prompt.lower()
    assert len(prompt) <= 1000


def test_look_tryon_prompts_replace_photo_footwear_with_look_shoes():
    """Social looks that draw shoes must not keep the person's photo boots."""
    from app.services.fitting_room import (
        FITTING_ROOM_LOOK_FOOTWEAR_CLAUSE,
        FITTING_ROOM_LOOK_MATERIALIZED_MAX_PROMPT,
        _fitting_room_max_prompt,
        _fitting_room_openai_prompt,
        _look_materialized_max_prompt,
    )
    from app.services.look_garment_normalize import LOOK_MATERIALIZE_PROMPT

    max_prompts = (
        _fitting_room_max_prompt({"garment_source": "fashionrise_look"}),
        _fitting_room_max_prompt(
            {"garment_source": "fashionrise_look", "look_productized": True}
        ),
        FITTING_ROOM_LOOK_MATERIALIZED_MAX_PROMPT,
        _look_materialized_max_prompt(None),
    )
    openai_prompts = (
        _fitting_room_openai_prompt({"garment_source": "fashionrise_look"}, []),
        _fitting_room_openai_prompt(
            {"garment_source": "fashionrise_look", "look_normalized": True}, []
        ),
    )
    for prompt in (*max_prompts, *openai_prompts, FITTING_ROOM_LOOK_FOOTWEAR_CLAUSE):
        assert prompt is not None
        low = prompt.lower()
        assert "shoe" in low or "footwear" in low
        assert "replace" in low
        assert "keep the person's existing footwear" not in low
    for prompt in max_prompts:
        assert len(prompt) <= 1000
    assert "shoes" in LOOK_MATERIALIZE_PROMPT.lower()
    assert "footwear" in LOOK_MATERIALIZE_PROMPT.lower() or "sneakers" in LOOK_MATERIALIZE_PROMPT.lower()


def test_look_productized_max_prompt_is_product_fit_not_illustration():
    from app.services.fitting_room import (
        FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT,
        _fitting_room_max_prompt,
        sample_look_garment_panel_colors,
    )

    lock = sample_look_garment_panel_colors(_two_tone_look_png())
    prompt = _fitting_room_max_prompt(
        {
            "garment_source": "fashionrise_look",
            "look_productized": True,
            "look_color_lock": lock,
        }
    )
    assert prompt.startswith(FITTING_ROOM_LOOK_PRODUCT_MAX_PROMPT[:40])
    assert "COLOR LOCK" in prompt
    assert "drawn model" not in prompt.lower()
    assert len(prompt) <= 1000


def _sheer_look_png(*, size=(200, 400)) -> bytes:
    """Synthetic sheer look: two-tone dress with skin-visible lower legs / high-low hem."""
    im = Image.new("RGB", size, (245, 245, 245))
    w, h = size
    skin = (210, 160, 130)
    bodice = (90, 120, 70)
    skirt = (40, 70, 45)
    for y in range(int(h * 0.28), int(h * 0.46)):
        for x in range(int(w * 0.30), int(w * 0.70)):
            im.putpixel((x, y), bodice)
    for y in range(int(h * 0.52), int(h * 0.70)):
        for x in range(int(w * 0.25), int(w * 0.55)):
            t = 0.30
            im.putpixel(
                (x, y),
                (
                    int(skirt[0] * t + skin[0] * (1 - t)),
                    int(skirt[1] * t + skin[1] * (1 - t)),
                    int(skirt[2] * t + skin[2] * (1 - t)),
                ),
            )
    # High-low: right side opens to skin; ankle band mostly exposed.
    for y in range(int(h * 0.55), int(h * 0.95)):
        for x in range(int(w * 0.55), int(w * 0.75)):
            im.putpixel((x, y), skin)
    for y in range(int(h * 0.72), int(h * 0.95)):
        for x in range(int(w * 0.32), int(w * 0.55)):
            im.putpixel((x, y), skin)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_sample_look_garment_panel_colors_works_for_non_green():
    from app.services.fitting_room import sample_look_garment_panel_colors

    lock = sample_look_garment_panel_colors(
        _two_tone_look_png(bodice=(180, 60, 70), skirt=(40, 50, 140))
    )
    assert lock is not None
    assert lock["relation"] == "lighter_bodice"
    assert lock["bodice_hex"].startswith("#")


def test_analyze_look_plate_detects_sheer_legs():
    from app.services.fitting_room import analyze_fashionrise_look_plate

    solid = analyze_fashionrise_look_plate(_two_tone_look_png())
    sheer = analyze_fashionrise_look_plate(_sheer_look_png())
    assert solid["preferred_path"] == "chatgpt_clone_direct"
    assert sheer["sheer_legs"] is True
    assert sheer["preferred_path"] == "chatgpt_clone_direct"


def test_sketch_texture_score_runs_on_synthetic():
    from app.services.look_garment_normalize import estimate_sketch_texture_score

    score = estimate_sketch_texture_score(_two_tone_look_png())
    assert "edge_density" in score
    assert "illustrated_texture_suspected" in score


def test_soft_check_flags_opaque_skirt_when_sheer_expected():
    from app.services.fitting_room import (
        analyze_fashionrise_look_plate,
        soft_check_look_tryon_result,
    )

    analysis = analyze_fashionrise_look_plate(_sheer_look_png())
    opaque = _two_tone_look_png()  # no legs visible
    quality = soft_check_look_tryon_result(opaque, look_analysis=analysis)
    assert quality["sheer_expected"] is True
    assert "sheer_legs_likely_covered" in quality["warnings"]


# --- Social look pipeline: detect → materialize → Max → color lock -----------------

DRIFT_BODICE = (95, 150, 60)
DRIFT_SKIRT = (40, 110, 95)


def _b64_png(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _look_try_on_body(*, look_png: bytes, person_png: bytes, tagged: bool) -> dict:
    piece: dict = {"image_base64": _b64_png(look_png), "category": "dresses" if tagged else "auto"}
    if tagged:
        piece["source"] = "fashionrise_look"
    return {
        "person_image_base64": _b64_png(person_png),
        "garment_pieces": [piece],
        "idempotency_key": f"fitting_room:{uuid.uuid4()}",
        "consent_acknowledged": True,
        "consent_version": FITTING_ROOM_CONSENT_VERSION,
    }


def _enqueue_look_job(client, db_session, *, username: str, body: dict) -> AIJob:
    tokens = register_with_invite(
        client, db_session, email=f"{username}@example.com", username=username
    )
    _grant_stars(db_session, username, amount=40)
    r = client.post(f"{FR}/try-on", json=body, headers=_auth(tokens))
    assert r.status_code == 201, r.text
    job = db_session.get(AIJob, uuid.UUID(r.json()["id"]))
    assert job is not None
    return job


class _CapturingStorage:
    saved: list[bytes] = []

    def save_file(self, *, key: str, data, content_type: str) -> str:
        _CapturingStorage.saved.append(data.read())
        return f"/uploads/{key}"


def test_untagged_look_plate_is_detected_at_enqueue(client, db_session, monkeypatch):
    """Older app bundles never send source=fashionrise_look — the server must not need it."""
    from tests.look_test_images import look_plate_png, person_photo_png

    _enable_fitting_room(monkeypatch)
    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_untagged",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=False
        ),
    )
    data = job.input_data
    assert data["garment_sources"] == [""]
    assert data["garment_category"] == "auto"
    assert data["garment_source"] == "fashionrise_look"
    assert data["look_detected_by"] == "content"
    assert data["look_detection"]["reason"] == "layout_match"
    assert "fashionrise_look_plate" in data["design_hints"]


def test_tagged_look_plate_skips_content_detection(client, db_session, monkeypatch):
    from tests.look_test_images import look_plate_png, person_photo_png

    _enable_fitting_room(monkeypatch)
    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_tagged",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=True
        ),
    )
    assert job.input_data["garment_source"] == "fashionrise_look"
    assert job.input_data["look_detected_by"] == "client_tag"
    assert job.input_data["look_detection"] is None


def test_product_photo_upload_is_not_treated_as_look(client, db_session, monkeypatch):
    from tests.look_test_images import person_photo_png, product_photo_png

    _enable_fitting_room(monkeypatch)
    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_product_upload",
        body=_look_try_on_body(
            look_png=product_photo_png(size=(600, 800)),
            person_png=person_photo_png(),
            tagged=False,
        ),
    )
    assert job.input_data["garment_source"] is None
    assert job.input_data["look_detected_by"] is None
    assert job.input_data["look_detection"]["reason"] == "size"


def test_look_detection_kill_switch(client, db_session, monkeypatch):
    from tests.look_test_images import look_plate_png, person_photo_png

    _enable_fitting_room(monkeypatch)
    monkeypatch.setenv("FITTING_ROOM_LOOK_DETECT_ENABLED", "false")
    get_settings.cache_clear()
    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_detect_off",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=False
        ),
    )
    assert job.input_data["garment_source"] is None
    assert job.input_data["look_detection"] is None


def test_untagged_look_runs_materialize_then_openai_v28_with_color_lock(
    client, db_session, monkeypatch
):
    """Social look path matches model Try On Person: materialize → OpenAI V2.8."""
    import json

    import app.services.look_garment_normalize as lgn
    from app.models.user import User
    from app.services import fitting_room as fr
    from app.services.personal_try_on_provider import TRY_ON_PROMPT_V2_8
    from tests.look_test_images import (
        look_plate_png,
        person_photo_png,
        product_photo_png,
        tryon_result_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)
    monkeypatch.setattr(fr, "_fashn_fallback_armed", lambda: True)
    _CapturingStorage.saved = []
    monkeypatch.setattr(fr, "LocalStorageBackend", _CapturingStorage)

    look_png = look_plate_png()
    person_png = person_photo_png()
    product_png = product_photo_png()
    raw_openai_png = tryon_result_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT)
    calls: list[str] = []

    def _fake_materialize(*, look_png: bytes, palette, color_lock: bool):
        calls.append("materialize")
        assert palette is not None and palette["multi_tone"] is True
        assert color_lock is True
        return product_png, {
            "provider": "openai_look_materialize",
            "prompt_kind": lgn.LOOK_MATERIALIZE_PROMPT_KIND,
            "quality": "high",
            "openai_calls": 1,
            "check": {"ok": True},
            "color_lock": {"stage": "product", "applied": False, "reason": "within_tolerance"},
        }

    def _no_max(**_kwargs):
        raise AssertionError("Max must not run when OpenAI V2.8 succeeds first")

    class _V28Provider(MockTryOnProvider):
        def generate(self, *, photo_png, garment_png, design_hints=None, prompt_override=None, **kwargs):
            calls.append("openai")
            assert garment_png == product_png
            self.calls += 1
            self.last_garment_png = garment_png
            self.last_prompt_override = prompt_override
            prompt = prompt_override or ""
            assert TRY_ON_PROMPT_V2_8[:80] in prompt
            assert "mannequin" in prompt.lower()
            assert "replace the person's original clothes" in prompt.lower()
            return raw_openai_png, {"actual_cost_cents": 4, "provider": "openai"}

    openai_mock = _V28Provider()
    monkeypatch.setattr(fr, "_try_chatgpt_style_look_fit", lambda **_k: None)
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _fake_materialize)
    monkeypatch.setattr(fr, "_generate_look_try_on_via_max", _no_max)
    monkeypatch.setattr(fr, "get_try_on_provider", lambda _name=None: openai_mock)
    set_try_on_provider_override(None)

    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_pipeline",
        body=_look_try_on_body(look_png=look_png, person_png=person_png, tagged=False),
    )
    before = db_session.query(User).filter(User.username == "fr_look_pipeline").one().ai_stars
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    assert calls == ["materialize", "openai"]

    result = job.result_data or {}
    assert result["fitting_room_look_path"] == "materialize_then_openai"
    assert result.get("provider") == "openai"
    assert result["look_detected_by"] == "content"
    assert result["look_palette"]["multi_tone"] is True
    assert result["look_materialize"]["provider"] == "openai_look_materialize"
    assert result["look_materialize"]["openai_calls"] == 1
    final_lock = result["look_color_lock_final"]
    assert final_lock["applied"] is True
    assert final_lock["chroma_drift_after"] < final_lock["chroma_drift_before"]
    assert "look_quality" in result
    assert len(_CapturingStorage.saved) == 1
    assert _CapturingStorage.saved[0] != raw_openai_png

    assert result["stars_cost"] == 20
    after = db_session.query(User).filter(User.username == "fr_look_pipeline").one().ai_stars
    assert after == before - 20
    slim = job.input_data
    assert slim["images_stripped"] is True
    assert "garment_image_base64" not in slim
    json.dumps(slim)
    json.dumps(result)


def test_look_materialize_failure_falls_back_to_direct(client, db_session, monkeypatch):
    """If materialize fails, still deliver a ChatGPT-style direct fit — never empty cancel."""
    import app.services.look_garment_normalize as lgn
    from app.models.user import User
    from app.services import fitting_room as fr
    from app.services.personal_try_on_provider import ProviderNotAvailableError
    from tests.look_test_images import look_plate_png, person_photo_png

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)

    def _fail_materialize(**_kwargs):
        raise ProviderNotAvailableError("look materialize rejected: moderation_blocked")

    def _no_max(**_kwargs):
        raise AssertionError("Max must not run without a materialized product")

    openai_mock = MockTryOnProvider()
    # First ChatGPT-style attempt soft-fails (returns None); force path after materialize uses provider.
    monkeypatch.setattr(fr, "_try_chatgpt_style_look_fit", lambda **_k: None)
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _fail_materialize)
    monkeypatch.setattr(fr, "_generate_look_try_on_via_max", _no_max)
    monkeypatch.setattr(fr, "get_try_on_provider", lambda _name=None: openai_mock)
    # Soft-check on forced direct: accept so we complete.
    monkeypatch.setattr(
        fr,
        "soft_check_look_tryon_result",
        lambda *_a, **_k: {
            "ok": True,
            "warnings": [],
            "result_skin_ratio_lower": 0.1,
            "sheer_expected": False,
            "texture": {},
        },
    )
    set_try_on_provider_override(None)

    look_png = look_plate_png()
    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_fallback",
        body=_look_try_on_body(look_png=look_png, person_png=person_photo_png(), tagged=True),
    )
    before = db_session.query(User).filter(User.username == "fr_look_fallback").one().ai_stars
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    result = job.result_data or {}
    assert result.get("fitting_room_look_path") == "direct_openai_after_materialize_fail"
    assert result.get("image_url")
    assert openai_mock.calls >= 1
    after = db_session.query(User).filter(User.username == "fr_look_fallback").one().ai_stars
    assert after == before - 20


def test_look_openai_moderation_falls_back_to_max_with_product(client, db_session, monkeypatch):
    """When OpenAI V2.8 is moderation-blocked, Max may run only on the product photo."""
    import app.services.look_garment_normalize as lgn
    from app.services import fitting_room as fr
    from app.services.personal_try_on_provider import ProviderNotAvailableError
    from tests.look_test_images import (
        look_plate_png,
        person_photo_png,
        product_photo_png,
        tryon_result_png,
    )

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)
    monkeypatch.setattr(fr, "_fashn_fallback_armed", lambda: True)
    product_png = product_photo_png()
    calls: list[str] = []

    def _fake_materialize(**_kwargs):
        calls.append("materialize")
        return product_png, {"provider": "openai_look_materialize", "openai_calls": 1}

    def _fake_max(*, person_png, product_png, palette, data):
        calls.append("max")
        assert product_png == _fake_max.expected
        assert data.get("look_materialized") is True
        return tryon_result_png(), {"provider": "fashn_tryon_max", "credits_used": 4}

    _fake_max.expected = product_png

    class _ModerationOpenAI(MockTryOnProvider):
        def generate(self, **kwargs):
            calls.append("openai")
            raise ProviderNotAvailableError(
                "OpenAI images.edit rejected: moderation_blocked"
            )

    monkeypatch.setattr(fr, "_try_chatgpt_style_look_fit", lambda **_k: None)
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _fake_materialize)
    monkeypatch.setattr(fr, "_generate_look_try_on_via_max", _fake_max)
    monkeypatch.setattr(fr, "get_try_on_provider", lambda _name=None: _ModerationOpenAI())
    set_try_on_provider_override(None)

    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_mod_max",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=True
        ),
    )
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    assert calls == ["materialize", "openai", "max"]
    result = job.result_data or {}
    assert result["fitting_room_look_path"] == "materialize_then_openai"
    assert result.get("fallback_from") == "openai"
    assert "fashn" in str(result.get("provider") or "")


def test_look_final_illustrated_quality_recovers_via_openai(client, db_session, monkeypatch):
    """Soft illustrated check must escalate OpenAI recovery — never cancel the try-on."""
    import app.services.look_garment_normalize as lgn
    from app.models.user import User
    from app.services import fitting_room as fr
    from tests.look_test_images import look_plate_png, person_photo_png, product_photo_png

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)
    product_png = product_photo_png()
    soft_calls = {"n": 0}

    def _fake_materialize(**_kwargs):
        return product_png, {"provider": "openai_look_materialize", "openai_calls": 1}

    def _soft(png, *, look_analysis=None):
        soft_calls["n"] += 1
        # First result looks illustrated; recovery retry clears.
        if soft_calls["n"] == 1:
            return {
                "ok": False,
                "warnings": ["illustrated_texture_suspected"],
                "result_skin_ratio_lower": 0.1,
                "sheer_expected": False,
                "texture": {"illustrated_texture_suspected": True},
            }
        return {
            "ok": True,
            "warnings": [],
            "result_skin_ratio_lower": 0.1,
            "sheer_expected": False,
            "texture": {"illustrated_texture_suspected": False},
        }

    openai_mock = MockTryOnProvider()
    monkeypatch.setattr(fr, "_try_chatgpt_style_look_fit", lambda **_k: None)
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _fake_materialize)
    monkeypatch.setattr(fr, "soft_check_look_tryon_result", _soft)
    monkeypatch.setattr(fr, "get_try_on_provider", lambda _name=None: openai_mock)
    monkeypatch.setattr(
        fr,
        "_generate_look_try_on_via_max",
        lambda **_k: (_ for _ in ()).throw(AssertionError("Max unused when OpenAI recovers")),
    )
    set_try_on_provider_override(None)

    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_quality_recover",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=True
        ),
    )
    before = (
        db_session.query(User).filter(User.username == "fr_look_quality_recover").one().ai_stars
    )
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    result = job.result_data or {}
    assert result.get("error_code") is None
    assert result.get("fitting_room_look_path") == "materialize_then_openai_recovery"
    assert result.get("image_url")
    recovery = result.get("look_quality_recovery") or []
    assert any(step.get("step") == "openai_photoreal_recovery" for step in recovery)
    after = (
        db_session.query(User).filter(User.username == "fr_look_quality_recover").one().ai_stars
    )
    assert after == before - 20
    assert openai_mock.calls == 2  # initial + recovery
    assert soft_calls["n"] == 2


def test_look_final_illustrated_quality_keeps_best_after_max(client, db_session, monkeypatch):
    """If soft-check stays red after OpenAI+Max, still deliver the best preview (charge Stars)."""
    import app.services.look_garment_normalize as lgn
    from app.models.user import User
    from app.services import fitting_room as fr
    from tests.look_test_images import look_plate_png, person_photo_png, product_photo_png

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)
    product_png = product_photo_png()
    max_calls = {"n": 0}

    def _fake_materialize(**_kwargs):
        return product_png, {"provider": "openai_look_materialize", "openai_calls": 1}

    def _soft(png, *, look_analysis=None):
        return {
            "ok": False,
            "warnings": ["illustrated_texture_suspected"],
            "result_skin_ratio_lower": 0.1,
            "sheer_expected": False,
            "texture": {"illustrated_texture_suspected": True},
        }

    def _fake_max(**_kwargs):
        max_calls["n"] += 1
        out = _png_bytes((90, 130), (40, 50, 60, 255))
        return out, {"provider": "fashn_tryon_max", "generation_mode": "quality", "resolution": "2k"}

    openai_mock = MockTryOnProvider()
    monkeypatch.setattr(fr, "_try_chatgpt_style_look_fit", lambda **_k: None)
    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _fake_materialize)
    monkeypatch.setattr(fr, "soft_check_look_tryon_result", _soft)
    monkeypatch.setattr(fr, "get_try_on_provider", lambda _name=None: openai_mock)
    monkeypatch.setattr(fr, "_generate_look_try_on_via_max", _fake_max)
    set_try_on_provider_override(None)

    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_quality_keep",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=True
        ),
    )
    before = (
        db_session.query(User).filter(User.username == "fr_look_quality_keep").one().ai_stars
    )
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    result = job.result_data or {}
    assert result.get("error_code") != "LOOK_QUALITY_REJECTED"
    assert result.get("look_quality_kept_despite_soft_check") is True
    assert "max_recovery" in str(result.get("fitting_room_look_path") or "")
    assert result.get("image_url")
    assert max_calls["n"] == 1
    assert openai_mock.calls == 2
    after = (
        db_session.query(User).filter(User.username == "fr_look_quality_keep").one().ai_stars
    )
    assert after == before - 20


def test_look_chatgpt_clone_skips_materialize_and_color_lock(client, db_session, monkeypatch):
    """ChatGPT clone: one images.edit (person+design) — no materialize, no color lock."""
    import app.services.look_garment_normalize as lgn
    from app.models.user import User
    from app.services import fitting_room as fr
    from tests.look_test_images import look_plate_png, person_photo_png, tryon_result_png

    _enable_fitting_room(monkeypatch, live=True)
    monkeypatch.setattr(fr, "_fashn_max_fallback_armed", lambda: True)
    monkeypatch.setenv("FITTING_ROOM_LOOK_CHATGPT_CLONE_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_LOOK_OPENAI_MODEL", "gpt-image-2")
    get_settings.cache_clear()
    calls: list[str] = []

    def _no_materialize(**_k):
        calls.append("materialize")
        raise AssertionError("materialize must not run when ChatGPT clone is accepted")

    def _clone_edit(*, person_png, look_png, prompt):
        calls.append("chatgpt_clone")
        assert person_png and look_png
        lowered = prompt.lower()
        assert "fit the colourful design" in lowered
        assert "do not change her face" in lowered
        assert "never crush" in lowered or "black" in lowered
        assert "mannequin" not in lowered
        return tryon_result_png(), {
            "provider": "openai_images_edit",
            "model": "gpt-image-2",
            "quality": "high",
            "chatgpt_clone": True,
        }

    def _no_lock(*_a, **_k):
        raise AssertionError("color lock must not run on ChatGPT-clone path")

    monkeypatch.setattr(lgn, "materialize_fashionrise_look", _no_materialize)
    monkeypatch.setattr(fr, "_run_chatgpt_clone_images_edit", _clone_edit)
    monkeypatch.setattr(fr, "lock_result_to_palette", _no_lock)
    set_try_on_provider_override(None)

    job = _enqueue_look_job(
        client,
        db_session,
        username="fr_look_direct",
        body=_look_try_on_body(
            look_png=look_plate_png(), person_png=person_photo_png(), tagged=True
        ),
    )
    before = db_session.query(User).filter(User.username == "fr_look_direct").one().ai_stars
    assert run_magic_worker_tick(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "completed", job.error_message
    result = job.result_data or {}
    assert result.get("fitting_room_look_path") == "chatgpt_clone_direct"
    assert result.get("look_color_lock_final", {}).get("reason") == "skipped_chatgpt_clone"
    assert "materialize" not in calls
    assert calls == ["chatgpt_clone"]
    after = db_session.query(User).filter(User.username == "fr_look_direct").one().ai_stars
    assert after == before - 20


def test_soft_check_look_color_fidelity_detects_black_crush():
    from app.services.fitting_room import (
        soft_check_look_color_fidelity,
        soft_check_look_tryon_result,
    )
    from tests.look_test_images import tryon_result_png

    # Bright blue bodice design → near-black result bodice.
    look_analysis = {
        "look_color_lock": {
            "bodice_rgb": [40, 120, 220],
            "skirt_rgb": [220, 80, 140],
            "bodice_hex": "#2878DC",
            "skirt_hex": "#DC508C",
            "relation": "lighter_bodice",
            "luma_delta": 20.0,
        },
        "sheer_legs": False,
    }
    crushed = tryon_result_png(bodice=(18, 18, 20), skirt=(200, 90, 150))
    warnings = soft_check_look_color_fidelity(crushed, look_analysis=look_analysis)
    assert "color_crush_to_dark" in warnings
    quality = soft_check_look_tryon_result(crushed, look_analysis=look_analysis)
    assert "color_crush_to_dark" in (quality.get("warnings") or [])


def test_look_prompts_keep_contract_and_fit_max_limit():
    from app.services.fashn_try_on_max_provider import normalize_max_prompt
    from app.services.fitting_room import _look_materialized_max_prompt
    from app.services.look_color_lock import extract_design_palette
    from app.services.look_garment_normalize import look_materialize_prompt
    from tests.look_test_images import look_plate_png

    palette = extract_design_palette(look_plate_png())
    top_hex = palette["panels"][0]["hex"]
    bottom_hex = palette["panels"][-1]["hex"]

    for retry in (False, True):
        prompt = look_materialize_prompt(palette, retry=retry)
        lowered = prompt.lower()
        # Measured in production: wording about taking clothing off is moderation-blocked.
        assert "remove" not in lowered and "undress" not in lowered and "naked" not in lowered
        assert "mannequin" in lowered
        assert "no ink or pencil outlines" in lowered
        assert top_hex in prompt and bottom_hex in prompt
    assert "COLOR LOCK" not in look_materialize_prompt(None)

    max_prompt = _look_materialized_max_prompt(palette)
    assert "mannequin" in max_prompt
    assert top_hex in max_prompt and bottom_hex in max_prompt
    assert len(max_prompt) <= 1000
    assert normalize_max_prompt(max_prompt) == " ".join(max_prompt.split())
    assert "COLOR LOCK" not in _look_materialized_max_prompt(None)


def test_check_materialized_product_requires_the_garment():
    from app.services.look_color_lock import extract_design_palette
    from app.services.look_garment_normalize import check_materialized_product
    from tests.look_test_images import look_plate_png, product_photo_png

    palette = extract_design_palette(look_plate_png())
    assert check_materialized_product(product_photo_png(), palette)["ok"] is True
    bare = check_materialized_product(product_photo_png(bodice=None, skirt=None), palette)
    assert bare["ok"] is False and bare["reason"] == "garment_missing"
    assert check_materialized_product(b"nope", palette)["reason"] == "undecodable"
    # No measurable palette (white / nude design): accept any decodable photo.
    assert check_materialized_product(product_photo_png(bodice=None, skirt=None), None)["ok"] is True


def test_materialize_retries_once_then_color_locks(monkeypatch):
    import app.services.look_garment_normalize as lgn
    from app.services.look_color_lock import extract_design_palette
    from tests.look_test_images import look_plate_png, product_photo_png

    palette = extract_design_palette(look_plate_png())
    outputs = [
        product_photo_png(bodice=None, skirt=None),
        product_photo_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT),
    ]
    prompts: list[str] = []

    def _fake_edit(*, look_png: bytes, prompt: str, quality: str):
        prompts.append(prompt)
        return outputs[len(prompts) - 1], {"model": "m", "quality": quality, "size": "1024x1536"}

    monkeypatch.setattr(lgn, "_assert_materialize_armed", lambda: None)
    monkeypatch.setattr(lgn, "_images_edit_product", _fake_edit)

    product, meta = lgn.materialize_fashionrise_look(look_png=look_plate_png(), palette=palette)
    assert len(prompts) == 2
    assert prompts[1].endswith(lgn.LOOK_MATERIALIZE_RETRY_SUFFIX)
    assert meta["openai_calls"] == 2
    assert meta["quality"] == "high"
    assert meta["check"]["ok"] is True
    assert meta["color_lock"]["applied"] is True
    assert product != outputs[1]


def test_materialize_color_lock_can_be_disabled(monkeypatch):
    import app.services.look_garment_normalize as lgn
    from app.services.look_color_lock import extract_design_palette
    from tests.look_test_images import look_plate_png, product_photo_png

    palette = extract_design_palette(look_plate_png())
    drifted = product_photo_png(bodice=DRIFT_BODICE, skirt=DRIFT_SKIRT)
    monkeypatch.setattr(lgn, "_assert_materialize_armed", lambda: None)
    monkeypatch.setattr(
        lgn,
        "_images_edit_product",
        lambda *, look_png, prompt, quality: (drifted, {"model": "m", "quality": quality}),
    )
    product, meta = lgn.materialize_fashionrise_look(
        look_png=look_plate_png(), palette=palette, color_lock=False
    )
    assert product == drifted
    assert meta["openai_calls"] == 1
    assert meta["color_lock"] == {"stage": "product", "applied": False, "reason": "disabled"}


def test_materialize_soft_keeps_product_after_one_retry(monkeypatch):
    """Second soft garment_missing keeps the product photo instead of falling back to the look."""
    import app.services.look_garment_normalize as lgn
    from app.services.look_color_lock import extract_design_palette
    from tests.look_test_images import look_plate_png, product_photo_png

    palette = extract_design_palette(look_plate_png())
    calls: list[str] = []
    soft = product_photo_png(bodice=None, skirt=None)

    def _blank_edit(*, look_png: bytes, prompt: str, quality: str):
        calls.append(prompt)
        return soft, {"model": "m", "quality": quality}

    monkeypatch.setattr(lgn, "_assert_materialize_armed", lambda: None)
    monkeypatch.setattr(lgn, "_images_edit_product", _blank_edit)
    product, meta = lgn.materialize_fashionrise_look(
        look_png=look_plate_png(), palette=palette, color_lock=False
    )
    assert len(calls) == 2
    assert product == soft
    assert meta["check"].get("accepted") == "soft_keep"


def test_materialize_kill_switch_fails_closed_before_any_call(monkeypatch):
    import app.services.look_garment_normalize as lgn
    from app.services.personal_try_on_provider import ProviderNotAvailableError
    from tests.look_test_images import look_plate_png

    monkeypatch.setenv("FITTING_ROOM_LOOK_MATERIALIZE_ENABLED", "false")
    get_settings.cache_clear()

    def _no_call(**_kwargs):
        raise AssertionError("no paid call when the stage is switched off")

    monkeypatch.setattr(lgn, "_images_edit_product", _no_call)
    with pytest.raises(ProviderNotAvailableError, match="FITTING_ROOM_LOOK_MATERIALIZE_ENABLED"):
        lgn.materialize_fashionrise_look(look_png=look_plate_png(), palette=None)
    get_settings.cache_clear()


def test_native_product_prep_keeps_full_resolution():
    from app.services.fitting_room import _native_product_prep
    from tests.look_test_images import product_photo_png

    prep = _native_product_prep(product_png=product_photo_png(), source_fingerprint="fp")
    assert prep.layout == "one_piece" and prep.fashn_calls == 1
    with Image.open(io.BytesIO(prep.pieces[0].png_bytes)) as im:
        assert im.size == (1024, 1536)
        assert im.mode == "RGB"


def test_normalize_category_maps_boots_alias_to_shoes():
    from app.services.fitting_room import _normalize_category

    assert _normalize_category("boots") == "shoes"
    assert _normalize_category("Boot") == "shoes"
    assert _normalize_category("footwear") == "shoes"
    assert _normalize_category("heels") == "shoes"
    assert _normalize_category("dresses") == "dresses"


def test_multi_piece_dress_plus_auto_boot_uses_outfit_footwear_max_prompt():
    """QA: dress + boot (often tagged auto) must not use apparel-only Max prompt."""
    from app.services.fitting_room import (
        FITTING_ROOM_MAX_OUTFIT_PROMPT,
        FITTING_ROOM_MAX_PROMPT,
        _fitting_room_max_prompt,
        _fitting_room_openai_prompt,
        _outfit_needs_footwear_contract,
    )

    data = {
        "garment_category": "auto",
        "outfit_categories": ["dresses", "auto"],
        "outfit_piece_count": 2,
    }
    assert _outfit_needs_footwear_contract(data)
    max_prompt = _fitting_room_max_prompt(data)
    assert max_prompt == FITTING_ROOM_MAX_OUTFIT_PROMPT
    assert max_prompt != FITTING_ROOM_MAX_PROMPT
    low = max_prompt.lower()
    assert "boot" in low or "footwear" in low or "shoe" in low
    assert "collage" in low
    openai_prompt = _fitting_room_openai_prompt(data, [])
    assert openai_prompt is not None
    assert "boot" in openai_prompt.lower() or "footwear" in openai_prompt.lower()
    assert len(max_prompt) <= 1000


def test_explicit_shoes_category_uses_outfit_footwear_max_prompt():
    from app.services.fitting_room import (
        FITTING_ROOM_MAX_OUTFIT_PROMPT,
        _fitting_room_max_prompt,
        _outfit_needs_footwear_contract,
    )

    data = {
        "garment_category": "shoes",
        "outfit_categories": ["shoes"],
        "outfit_piece_count": 1,
    }
    assert _outfit_needs_footwear_contract(data)
    assert _fitting_room_max_prompt(data) == FITTING_ROOM_MAX_OUTFIT_PROMPT


def test_single_dress_keeps_apparel_only_max_prompt():
    from app.services.fitting_room import FITTING_ROOM_MAX_PROMPT, _fitting_room_max_prompt

    data = {
        "garment_category": "dresses",
        "outfit_categories": ["dresses"],
        "outfit_piece_count": 1,
    }
    assert _fitting_room_max_prompt(data) == FITTING_ROOM_MAX_PROMPT


def test_enqueue_shoes_only_emits_footwear_hint(client, db_session, monkeypatch):
    """Single shoes piece still gets the footwear contract (one item at a time)."""
    _enable_fitting_room(monkeypatch)
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    tokens = register_with_invite(
        client, db_session, email="fr-boot@example.com", username="fr_boot"
    )
    _grant_stars(db_session, "fr_boot", amount=40)

    key = f"fitting_room:{uuid.uuid4()}"
    r = client.post(
        f"{FR}/try-on",
        headers=_auth(tokens),
        json={
            "person_image_base64": _data_url((180, 120, 90, 255)),
            "garment_pieces": [
                {"image_base64": _data_url((20, 20, 20, 255)), "category": "shoes"},
            ],
            "idempotency_key": key,
            "consent_acknowledged": True,
            "consent_version": FITTING_ROOM_CONSENT_VERSION,
        },
    )
    assert r.status_code == 201, r.text
    processed = run_magic_worker_tick(db_session, limit=4)
    assert processed >= 1
    joined = " | ".join(mock.last_hints)
    assert "outfit_piece_count:1" in joined
    assert "FOOTWEAR" in joined or "shoes" in joined.lower()
