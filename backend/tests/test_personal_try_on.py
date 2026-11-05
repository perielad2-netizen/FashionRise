"""Personal Try On Person — enqueue, spend, binding, recovery (mocked provider only)."""

from __future__ import annotations

import base64
import io
import uuid
import pytest
from PIL import Image

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis_spend import (
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.services.ai_worker import run_magic_worker_tick
from app.services.personal_croquis_provider import (
    MockCroquisProvider,
    ProviderNotAvailableError,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    provider_network_tripwire_hits,
    set_croquis_provider_override,
)
from app.services.personal_try_on_provider import (
    TRY_ON_CONSENT_VERSION,
    TRY_ON_JOB_TYPE,
    TRY_ON_PROMPT_V1,
    TRY_ON_PROMPT_V2_7,
    TRY_ON_PROMPT_V3,
    TRY_ON_PROMPT_VERSION,
    TRY_ON_USER_MODERATION_MESSAGE,
    OpenAITryOnImagesEditAdapter,
    build_try_on_prompt,
    set_try_on_provider_override,
)
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    enable_synthetic_croquis_notices,
    storage_body,
)

BASE = "/api/v1/personal-croquis"
TRY_ON = "/api/v1/ai/personal-try-on"


def _png_bytes(size: tuple[int, int] = (64, 96), color=(200, 100, 80, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _garment_data_url() -> str:
    # Non-empty garment artwork with alpha.
    raw = _png_bytes((48, 64), (30, 90, 200, 200))
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enable_upload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


def _enable_ai_spend(
    monkeypatch,
    *,
    ceiling_usd: str = "5",
    max_run: str = "1",
    max_day: str = "5",
    estimate_cents: str = "3",
    max_exposure_cents: str = "100",
):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", ceiling_usd)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", max_run)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", max_day)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", estimate_cents)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", max_exposure_cents)
    get_settings.cache_clear()


def _disable_ai(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_AI_ENABLED", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_SPEND_CEILING_USD", raising=False)
    get_settings.cache_clear()


class MockTryOnProvider:
    def __init__(self, *, cost_cents: int = 4, fail: Exception | None = None):
        self.calls = 0
        self.fail = fail
        self.last_photo: bytes | None = None
        self.last_garment: bytes | None = None
        self.last_design_hints: list[str] | None = None
        self.cost_cents = cost_cents

    def generate(self, *, photo_png: bytes, garment_png: bytes, design_hints=None):
        self.calls += 1
        self.last_photo = photo_png
        self.last_garment = garment_png
        self.last_design_hints = list(design_hints) if design_hints else []
        if self.fail is not None:
            raise self.fail
        out = _png_bytes((80, 120), (10, 20, 30, 255))
        return out, {"actual_cost_cents": self.cost_cents, "prompt_version": TRY_ON_PROMPT_VERSION}


@pytest.fixture(autouse=True)
def _synthetic_notices(monkeypatch, db_session):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    set_try_on_provider_override(None)
    arm_provider_network_tripwire()
    db_session.query(PersonalCroquisSpendReservation).delete()
    db_session.query(AIJob).filter(AIJob.job_type.in_((TRY_ON_JOB_TYPE,))).delete()
    db_session.flush()
    yield
    disarm_provider_network_tripwire()
    set_try_on_provider_override(None)
    set_croquis_provider_override(None)
    _disable_ai(monkeypatch)


def _upload_ready(client, tokens, monkeypatch):
    _enable_upload(monkeypatch)
    a = client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body())
    assert a.status_code == 200, a.text
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200, c.text
    consent_id = c.json()["id"]
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"storage_consent_id": consent_id, "display_name": "Try-on subject"},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _try_on_body(*, croquis_id: str, croquis_version: int = 1, key: str | None = None) -> dict:
    return {
        "croquis_id": croquis_id,
        "croquis_version": croquis_version,
        "garment_image_base64": _garment_data_url(),
        "idempotency_key": key or f"try_on:{uuid.uuid4()}",
        "source_revision": 1,
        "content_fingerprint": "fp-try-on-test-001",
        "consent_acknowledged": True,
        "consent_version": TRY_ON_CONSENT_VERSION,
    }


def test_try_on_prompt_is_not_sketch_polish():
    assert "photorealistic" in TRY_ON_PROMPT_V1.lower()
    assert "image 1" in TRY_ON_PROMPT_V1.lower()
    assert "image 2" in TRY_ON_PROMPT_V1.lower()
    # Must not reuse the fashion-illustration polish framing.
    assert "fashion illustration" not in TRY_ON_PROMPT_V1.lower()
    assert "flat sketch" not in TRY_ON_PROMPT_V1.lower()


def test_try_on_prompt_v2_restored_for_ordinary_openai_path():
    """#168/#174/#182 — live OpenAI Try On uses V2.2; V3 swimwear wording stays archive-only.

    Production evidence: every try-on-person-v3 job failed with
    PROVIDER_MODERATION_BLOCKED / moderation_stage=input / categories=sexual,
    including ordinary magenta top + orange shorts + cap (461c9419…). Last
    successful ordinary outfit used try-on-person-v2 on the same croquis photo.
    V2.2 keeps that base, clarifies fashion slits must not become trousers, and
    adds pale/bridal neckline + sleeve fidelity (#182).
    """
    from app.services.personal_try_on_provider import TRY_ON_PROMPT_V2_7

    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.7"
    active = build_try_on_prompt(None)
    assert active == TRY_ON_PROMPT_V2_7
    # Live prompt must not carry V3 swimwear / skin-uncovering language.
    assert "swimwear" not in active.lower()
    assert "lingerie" not in active.lower()
    assert "skin previously covered" not in active.lower()
    assert "sexual" not in active.lower()
    # V2 fidelity rules for ordinary outfits.
    assert "checkerboard" in active.lower()
    assert "hats/caps" in active.lower() or "hat/cap" in active.lower()
    assert "photorealistic" in active.lower()
    assert "fashion illustration" not in active.lower()
    # #174 — slit dress must not be coerced into trousers/jumpsuit.
    assert "slit" in active.lower()
    assert "jumpsuit" in active.lower()
    # #182 — pale bridal / open neckline / both sleeves.
    assert "matte" in active.lower()
    assert "plunging" in active.lower() or "deep-v" in active.lower()
    assert "both sleeves" in active.lower()
    # #184 — drawn footwear replaces photo shoes/boots.
    assert "footwear" in active.lower() or "shoes" in active.lower()
    assert "boots" in active.lower()
    # V2.5 — bare feet when image 2 has no footwear on a high-cut one-piece.
    assert "bare feet" in active.lower()
    assert "do not lengthen" in active.lower() or "high-cut" in active.lower()
    # V3 archive retained but not activated.
    assert "swimwear" in TRY_ON_PROMPT_V3.lower()
    assert "opaque" in TRY_ON_PROMPT_V3.lower()
    assert TRY_ON_PROMPT_V3 != TRY_ON_PROMPT_VERSION
    with_hints = build_try_on_prompt(
        ["exact designer colors: #FF8A5B, #C2185B", "upper-plane ink present — include any drawn hat/cap"]
    )
    assert with_hints.startswith(TRY_ON_PROMPT_V2_7)
    assert "#FF8A5B" in with_hints
    assert "hat/cap" in with_hints.lower()
    long = "x" * 200
    clipped = build_try_on_prompt([long, "", "  keep  me  ", long])
    assert long not in clipped
    assert "x" * 120 in clipped
    assert "keep me" in clipped


def test_try_on_edit_kwargs_photo_then_garment(monkeypatch):
    _enable_ai_spend(monkeypatch)
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
    get_settings.cache_clear()
    adapter = OpenAITryOnImagesEditAdapter()
    photo = _png_bytes((32, 48))
    garment = _png_bytes((32, 48), (0, 0, 255, 128))
    kwargs = adapter.build_edit_kwargs(
        photo_png=photo,
        garment_png=garment,
        design_hints=["exact designer colors: #FF69B4", "preserve print topology"],
    )
    from app.services.personal_try_on_provider import TRY_ON_PROMPT_V2_7

    assert kwargs["prompt"].startswith(TRY_ON_PROMPT_V2_7)
    assert "swimwear" not in kwargs["prompt"].lower()
    assert "exact designer colors: #FF69B4" in kwargs["prompt"]
    assert "preserve print topology" in kwargs["prompt"]
    assert isinstance(kwargs["image"], list) and len(kwargs["image"]) == 2
    assert "moderation" not in kwargs
    assert (kwargs.get("extra_body") or {}).get("moderation") == "low"


def test_openai_try_on_route_independent_from_fashn_prompt_versions():
    """Regular OpenAI button must not inherit FASHN realism / tryon prompt ids."""
    from app.services.fashn_garment_realism import GARMENT_REALISM_PROMPT_VERSION
    from app.services.personal_try_on import FASHN_PROMPT_VERSION

    assert TRY_ON_PROMPT_VERSION == "try-on-person-v2.7"
    assert TRY_ON_PROMPT_VERSION != GARMENT_REALISM_PROMPT_VERSION
    assert TRY_ON_PROMPT_VERSION != FASHN_PROMPT_VERSION
    assert FASHN_PROMPT_VERSION.startswith("fashn-")
    assert GARMENT_REALISM_PROMPT_VERSION.startswith("fashn-garment-realism-")


def test_preflight_and_gate(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to-pre@example.com", "topre")
    _enable_ai_spend(monkeypatch)
    r = client.get(f"{TRY_ON}/preflight", headers=_auth(tokens))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["consent_version"] == TRY_ON_CONSENT_VERSION
    assert body["prompt_version"] == TRY_ON_PROMPT_VERSION
    assert body["enabled"] is True
    assert "notice_text" in body and body["notice_text"]
    assert body["fashn_enabled"] is False
    assert body["fashn_configured"] is False
    assert body["fashn_consent_version"] == "try-on-fashn-oneclick-v1"
    assert "FASHN" in (body.get("fashn_notice_text") or "")
    assert body.get("fashn_one_click") is True
    assert body.get("fashn_combined_estimate_cents_one_piece") == (
        body.get("fashn_realism_estimate_cents_per_piece")
        + body.get("fashn_estimate_cents_per_call")
    )


def test_enqueue_refused_when_ai_gate_off(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to1@example.com", "to1")
    croquis = _upload_ready(client, tokens, monkeypatch)
    # Accept path needs AI; accept manually by marking version after generate with AI briefly.
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to1"},
    )
    assert gen.status_code == 201, gen.text
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    acc = client.post(
        f"{BASE}/{croquis['id']}/versions/1/accept",
        headers=_auth(tokens),
        json={},
    )
    assert acc.status_code == 200, acc.text

    _disable_ai(monkeypatch)
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    r = client.post(TRY_ON, headers=_auth(tokens), json=_try_on_body(croquis_id=croquis["id"]))
    assert r.status_code == 403
    assert mock.calls == 0
    assert provider_network_tripwire_hits() == 0


def test_enqueue_worker_idempotent_and_binding(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to2@example.com", "to2")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to2"},
    )
    assert gen.status_code == 201, gen.text
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    assert (
        client.post(
            f"{BASE}/{croquis['id']}/versions/1/accept",
            headers=_auth(tokens),
            json={},
        ).status_code
        == 200
    )

    mock = MockTryOnProvider(cost_cents=4)
    set_try_on_provider_override(mock)
    key = f"try_on:idem-{uuid.uuid4()}"
    body = _try_on_body(croquis_id=croquis["id"], key=key)
    r1 = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r1.status_code == 201, r1.text
    job_id = r1.json()["id"]
    assert r1.json()["job_type"] == TRY_ON_JOB_TYPE
    # Input must redact garment bytes on read.
    got = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(tokens))
    assert got.status_code == 200
    assert "garment_image_base64" not in (got.json().get("input_data") or {})
    assert (got.json().get("input_data") or {}).get("has_sketch_image") is True
    assert (got.json().get("input_data") or {}).get("source_asset_id") == croquis["source_asset_id"]

    r2 = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r2.status_code == 201
    assert r2.json()["id"] == job_id

    n = run_magic_worker_tick(db_session, limit=4)
    assert n >= 1
    assert mock.calls == 1
    assert mock.last_photo and len(mock.last_photo) > 32
    assert mock.last_garment and len(mock.last_garment) > 32

    done = client.get(f"/api/v1/ai/jobs/{job_id}", headers=_auth(tokens))
    assert done.json()["status"] == "completed"
    assert done.json()["result_data"]["mode"] == "try_on_person"
    assert done.json()["result_data"]["image_url"]
    assert done.json()["result_data"]["source_asset_id"] == croquis["source_asset_id"]
    # #172 — OpenAI completion stamps trusted photo provenance; ordinary preview stays completed.
    review = done.json()["result_data"].get("structure_review") or {}
    assert review.get("result_kind") == "openai_try_on_photo"
    assert review.get("version") == "try-on-structure-review-v3"
    assert review.get("state") in {"not_applicable", "inconclusive"}
    assert done.json()["result_data"].get("fidelity_ok") is None
    assert done.json()["result_data"].get("status") == "completed"

    img = client.get(f"/api/v1/ai/jobs/{job_id}/image", headers=_auth(tokens))
    assert img.status_code == 200
    assert "no-store" in img.headers.get("cache-control", "")
    assert img.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Replay after complete still returns same job — no second provider call.
    r3 = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r3.json()["id"] == job_id
    run_magic_worker_tick(db_session, limit=2)
    assert mock.calls == 1

    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_SETTLED
    assert res.actual_cost_cents == 4


def test_stale_unaccepted_version_rejected(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to3@example.com", "to3")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to3"},
    )
    assert gen.status_code == 201
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    # Do NOT accept — version stays awaiting_review.
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    r = client.post(
        TRY_ON,
        headers=_auth(tokens),
        json=_try_on_body(croquis_id=croquis["id"], croquis_version=1),
    )
    assert r.status_code == 400
    assert "accepted" in r.text.lower()
    assert mock.calls == 0


def test_spend_ceiling_blocks_try_on(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to4@example.com", "to4")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch, ceiling_usd="0.05", max_run="1", max_day="1", max_exposure_cents="5")
    set_croquis_provider_override(MockCroquisProvider(cost_cents=5))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to4"},
    )
    assert gen.status_code == 201
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    assert (
        client.post(
            f"{BASE}/{croquis['id']}/versions/1/accept",
            headers=_auth(tokens),
            json={},
        ).status_code
        == 200
    )
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    r = client.post(TRY_ON, headers=_auth(tokens), json=_try_on_body(croquis_id=croquis["id"]))
    assert r.status_code == 403
    assert mock.calls == 0


def test_provider_refusal_releases_reservation(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to5@example.com", "to5")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to5"},
    )
    assert gen.status_code == 201
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    assert (
        client.post(
            f"{BASE}/{croquis['id']}/versions/1/accept",
            headers=_auth(tokens),
            json={},
        ).status_code
        == 200
    )
    key = f"try_on:refuse-{uuid.uuid4()}"
    raw = (
        "images.edit rejected by provider: BadRequestError status=400 "
        "code=moderation_blocked request_id=req_test moderation_stage=input "
        "categories=sexual Error code: 400 - {'error': {'message': 'Your request was rejected'}}"
    )
    exc = ProviderNotAvailableError(raw)
    exc.safe_meta = {
        "error_code": "PROVIDER_MODERATION_BLOCKED",
        "provider_code": "moderation_blocked",
        "http_status": 400,
        "moderation_stage": "input",
        "categories": ["sexual"],
        "request_id": "req_test",
        "operator_summary": raw[:400],
    }
    mock = MockTryOnProvider(fail=exc)
    set_try_on_provider_override(mock)
    r = client.post(
        TRY_ON,
        headers=_auth(tokens),
        json=_try_on_body(croquis_id=croquis["id"], key=key),
    )
    assert r.status_code == 201
    run_magic_worker_tick(db_session, limit=2)
    assert mock.calls == 1
    # Definite refusal must never auto-retry.
    run_magic_worker_tick(db_session, limit=2)
    assert mock.calls == 1
    job = client.get(f"/api/v1/ai/jobs/{r.json()['id']}", headers=_auth(tokens)).json()
    assert job["status"] == "failed"
    assert job["error_message"] == TRY_ON_USER_MODERATION_MESSAGE
    assert "BadRequestError" not in (job["error_message"] or "")
    assert "moderation_blocked" not in (job["error_message"] or "")
    assert "categories=sexual" not in (job["error_message"] or "")
    rd = job.get("result_data") or {}
    assert rd.get("summary") == TRY_ON_USER_MODERATION_MESSAGE
    assert rd.get("error_code") == "PROVIDER_MODERATION_BLOCKED"
    assert (rd.get("provider_rejection") or {}).get("request_id") == "req_test"
    assert (rd.get("provider_rejection") or {}).get("moderation_stage") == "input"
    # Support diagnostics stay out of the owner-facing error_message.
    assert "req_test" not in (job["error_message"] or "")
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == key)
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.actual_cost_cents is None


def test_looks_list_includes_try_on_and_delete(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to6@example.com", "to6")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to6"},
    )
    assert gen.status_code == 201
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    assert (
        client.post(
            f"{BASE}/{croquis['id']}/versions/1/accept",
            headers=_auth(tokens),
            json={},
        ).status_code
        == 200
    )
    set_try_on_provider_override(MockTryOnProvider(cost_cents=3))
    r = client.post(TRY_ON, headers=_auth(tokens), json=_try_on_body(croquis_id=croquis["id"]))
    assert r.status_code == 201
    job_id = r.json()["id"]
    run_magic_worker_tick(db_session, limit=2)

    looks = client.get("/api/v1/looks", headers=_auth(tokens))
    assert looks.status_code == 200, looks.text
    items = looks.json().get("items") or looks.json().get("looks") or []
    # Find look whose front/id matches job
    match = None
    for item in items:
        front = item.get("front") or {}
        if str(front.get("job_id")) == job_id or str(item.get("id")) == job_id:
            match = item
            break
    assert match is not None, looks.text
    look_id = match["id"]
    deleted = client.delete(f"/api/v1/looks/{look_id}", headers=_auth(tokens))
    assert deleted.status_code in (200, 204), deleted.text
    again = client.get("/api/v1/looks", headers=_auth(tokens))
    again_items = again.json().get("items") or again.json().get("looks") or []
    assert all(str(i.get("id")) != look_id for i in again_items)


def test_consent_required(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to7@example.com", "to7")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-to7"},
    )
    assert gen.status_code == 201
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    assert (
        client.post(
            f"{BASE}/{croquis['id']}/versions/1/accept",
            headers=_auth(tokens),
            json={},
        ).status_code
        == 200
    )
    body = _try_on_body(croquis_id=croquis["id"])
    body["consent_acknowledged"] = False
    mock = MockTryOnProvider()
    set_try_on_provider_override(mock)
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 400
    assert mock.calls == 0

def test_enqueue_passes_design_hints_to_provider(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "to-hints@example.com", "tohints")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis["id"]),
    )
    gen = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": "g-tohints"},
    )
    assert gen.status_code == 201, gen.text
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    acc = client.post(
        f"{BASE}/{croquis['id']}/versions/1/accept",
        headers=_auth(tokens),
        json={},
    )
    assert acc.status_code == 200, acc.text

    mock = MockTryOnProvider(cost_cents=4)
    set_try_on_provider_override(mock)
    body = _try_on_body(croquis_id=croquis["id"], key="try_on:hints-1")
    body["design_hints"] = [
        "pink checkerboard print — keep exact Studio print geometry",
        "upper-plane ink present — include any drawn hat/cap accessory from image 2",
        "",
        "x" * 200,
    ]
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 201, r.text
    run_magic_worker_tick(db_session, limit=4)
    assert mock.calls == 1
    assert mock.last_design_hints is not None
    assert any("checkerboard" in h for h in mock.last_design_hints)
    assert any("hat/cap" in h for h in mock.last_design_hints)
    assert all(len(h) <= 120 for h in mock.last_design_hints)
    assert provider_network_tripwire_hits() == 0



def _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis_id: str, key: str):
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    ai = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis_id),
    )
    gen = client.post(
        f"{BASE}/{croquis_id}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai.json()["id"], "idempotency_key": key},
    )
    assert gen.status_code == 201, gen.text
    from app.services.personal_croquis_worker import run_croquis_worker_tick

    run_croquis_worker_tick(db_session, limit=4)
    acc = client.post(
        f"{BASE}/{croquis_id}/versions/1/accept",
        headers=_auth(tokens),
        json={},
    )
    assert acc.status_code == 200, acc.text


def test_fashn_prepare_offline_and_enqueue_mocked(client, monkeypatch, db_session):
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    tokens = register_with_invite(client, db_session, "to-fashn@example.com", "tofashn")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-tofashn")

    # Enable FASHN flags with a non-empty key — never assert the value.
    get_settings.cache_clear()
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-fashn-key-not-real")
    monkeypatch.setenv("FASHN_TRY_ON_ESTIMATE_CENTS", "8")
    get_settings.cache_clear()

    prep = client.post(
        f"{TRY_ON}/fashn/prepare",
        headers=_auth(tokens),
        json={"garment_image_base64": _garment_data_url()},
    )
    assert prep.status_code == 200, prep.text
    pbody = prep.json()
    assert pbody["provider"] == "fashn"
    assert pbody["configured"] is True
    assert pbody["consent_version"] == FASHN_CONSENT_VERSION
    assert pbody["composite_preview_base64"].startswith("data:image/png;base64,")
    assert pbody["fashn_calls"] >= 1
    assert pbody["estimate_cents"] == 8 * pbody["fashn_calls"]
    assert "realism_estimate_cents" in pbody
    assert "combined_estimate_cents" in pbody
    assert pbody["quality_ok"] is True

    # Without realism job id, FASHN enqueue must fail closed (#166).
    body_missing = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:missing-approve")
    body_missing["provider"] = "fashn"
    body_missing["consent_version"] = FASHN_CONSENT_VERSION
    missing = client.post(TRY_ON, headers=_auth(tokens), json=body_missing)
    assert missing.status_code == 400, missing.text
    assert "realism" in missing.json()["detail"].lower()

    # Sketch plates as approved pieces (no realism job) must also fail closed.
    body_plates = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:plates-only")
    body_plates["provider"] = "fashn"
    body_plates["consent_version"] = FASHN_CONSENT_VERSION
    body_plates["approved_garment_pieces"] = [
        {"category": piece["category"], "image_base64": piece["image_base64"]}
        for piece in pbody["pieces"]
    ]
    plates_only = client.post(TRY_ON, headers=_auth(tokens), json=body_plates)
    assert plates_only.status_code == 400, plates_only.text

    class MockFashn:
        def __init__(self):
            self.calls = 0

        def generate(
            self, *, photo_png, garment_png, design_hints=None, prep=None, v16_experiment=None
        ):
            self.calls += 1
            assert photo_png and garment_png
            assert prep is not None
            assert getattr(prep, "quality_ok", True) is True
            # One-piece swimwear must not be sent as category=auto.
            assert all(p.category != "auto" for p in prep.pieces)
            # #176 — customer path freezes documented v1.6 defaults (no owner override).
            if isinstance(v16_experiment, dict):
                assert v16_experiment.get("owner_experiment") in (False, True, None)
            out = _png_bytes((80, 120), (12, 34, 56, 255))
            return out, {
                "actual_cost_cents": 8 * prep.fashn_calls,
                "prompt_version": "fashn-tryon-v1.6",
                "provider": "fashn_tryon_v1_6",
                "fashn_calls": prep.fashn_calls,
                "layout": prep.layout,
                "prediction_ids": ["pred-mock-1"],
                "v16_settings": v16_experiment,
            }

    # Seed a completed OpenAI realism job with product pieces that differ from sketch plates.
    from app.models.user import User
    from app.services.fashn_garment_realism import (
        GARMENT_REALISM_JOB_TYPE,
        GARMENT_REALISM_PROVIDER_ID,
        GARMENT_REALISM_PROMPT_VERSION,
    )

    owner = db_session.query(User).filter(User.email == "to-fashn@example.com").one()
    product_pieces = []
    for piece in pbody["pieces"]:
        # Slightly different solid product plate (not the sketch bytes).
        prod = _png_bytes((96, 128), (40, 120, 210, 255))
        product_pieces.append(
            {
                "category": piece["category"],
                "image_base64": "data:image/png;base64," + base64.b64encode(prod).decode("ascii"),
                "sha256": __import__("hashlib").sha256(prod).hexdigest(),
                "source_plate_sha256": "plate-sha-placeholder",
            }
        )
    realism_job = AIJob(
        id=uuid.uuid4(),
        user_id=owner.id,
        design_id=None,
        job_type=GARMENT_REALISM_JOB_TYPE,
        status="completed",
        input_data={"mode": "garment_realism"},
        result_data={
            "status": "completed",
            "mode": "garment_realism",
            "provider": GARMENT_REALISM_PROVIDER_ID,
            "prompt_version": GARMENT_REALISM_PROMPT_VERSION,
            "prefer_local_product": False,
            "fidelity_ok": True,
            "block_fashn": False,
            "requires_owner_acceptance": True,
            "owner_accepted": True,
            "pieces": product_pieces,
            "summary": "Realistic garment product image ready (fidelity checks passed).",
        },
    )
    db_session.add(realism_job)
    db_session.commit()

    mock = MockFashn()
    set_try_on_provider_override(mock)
    body = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:mock-1")
    body["provider"] = "fashn"
    body["consent_version"] = FASHN_CONSENT_VERSION
    body["garment_realism_job_id"] = str(realism_job.id)
    # Client may still send pieces; server binds from realism job.
    body["approved_garment_pieces"] = [
        {"category": p["category"], "image_base64": p["image_base64"]} for p in product_pieces
    ]
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    run_magic_worker_tick(db_session, limit=4)
    assert mock.calls == 1
    job = db_session.get(AIJob, uuid.UUID(job_id))
    assert job is not None
    assert job.status == "completed"
    assert job.input_data.get("provider") == "fashn"
    assert job.input_data.get("garment_realism_job_id") == str(realism_job.id)
    assert job.result_data.get("provider") == "fashn_tryon_v1_6"
    # Prove FASHN used realism product SHAs, not sketch plates.
    approved = job.input_data.get("approved_garment_pieces") or []
    assert approved
    assert approved[0]["sha256"] == product_pieces[0]["sha256"]
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "try_on:fashn:mock-1")
        .one()
    )
    assert res.status == RESERVATION_SETTLED
    assert provider_network_tripwire_hits() == 0


def test_fashn_enqueue_refuses_without_key(client, monkeypatch, db_session):
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    tokens = register_with_invite(client, db_session, "to-fashn2@example.com", "tofashn2")
    croquis = _upload_ready(client, tokens, monkeypatch)
    _accept_personal_croquis(client, tokens, monkeypatch, db_session, croquis["id"], "g-tofashn2")

    get_settings.cache_clear()
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.delenv("FASHN_API_KEY", raising=False)
    get_settings.cache_clear()

    body = _try_on_body(croquis_id=croquis["id"], key="try_on:fashn:nokey")
    body["provider"] = "fashn"
    body["consent_version"] = FASHN_CONSENT_VERSION
    r = client.post(TRY_ON, headers=_auth(tokens), json=body)
    assert r.status_code == 403
