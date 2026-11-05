"""#173 — Owner-only FASHN Try-On Max experimental lane (mocked provider, no paid calls)."""

from __future__ import annotations

import base64
import io
import uuid
from types import SimpleNamespace

import pytest
from PIL import Image

from app.services.fashn_try_on_max_provider import (
    DEFAULT_MAX_PROMPT,
    FASHN_MAX_MODEL_NAME,
    FASHN_MAX_PROVIDER_ID,
    build_tryon_max_run_payload,
    estimate_fashn_max_cost_cents,
    fashn_max_credits_per_image,
    normalize_max_generation_mode,
    normalize_max_prompt,
    normalize_max_resolution,
    user_on_fashn_max_allowlist,
)
from app.services.personal_try_on import (
    TRY_ON_PROVIDER_FASHN,
    TRY_ON_PROVIDER_FASHN_MAX,
    _normalize_provider,
)
from app.services.personal_try_on_provider import get_try_on_provider, set_try_on_provider_override
from app.services.looks_service import _experiment_lane_excluded


def _png_bytes(color=(20, 120, 40, 255), size=(64, 96)) -> bytes:
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_max_request_schema_uses_documented_fields_only():
    payload = build_tryon_max_run_payload(
        model_image="data:image/png;base64,aaa",
        product_image="data:image/png;base64,bbb",
        prompt=DEFAULT_MAX_PROMPT,
        generation_mode="balanced",
        resolution="1k",
        seed=42,
        num_images=1,
    )
    assert payload["model_name"] == "tryon-max"
    inputs = payload["inputs"]
    assert set(inputs.keys()) == {
        "model_image",
        "product_image",
        "prompt",
        "resolution",
        "generation_mode",
        "seed",
        "num_images",
        "output_format",
        "return_base64",
    }
    # v1.6-only fields must not appear
    for banned in (
        "garment_image",
        "category",
        "garment_photo_type",
        "moderation_level",
        "segmentation_free",
        "mode",
        "num_samples",
    ):
        assert banned not in inputs
    assert inputs["return_base64"] is True
    assert inputs["generation_mode"] == "balanced"
    assert inputs["resolution"] == "1k"
    assert inputs["seed"] == 42


def test_max_credit_table_and_defaults():
    assert fashn_max_credits_per_image(generation_mode="balanced", resolution="1k") == 2
    assert fashn_max_credits_per_image(generation_mode="quality", resolution="1k") == 3
    assert normalize_max_generation_mode(None) == "balanced"
    assert normalize_max_resolution("nope") == "1k"
    assert normalize_max_prompt("") == DEFAULT_MAX_PROMPT
    assert estimate_fashn_max_cost_cents(generation_mode="balanced", resolution="1k") >= 16


def test_provider_normalize_and_factory(monkeypatch):
    assert _normalize_provider("fashn_max") == TRY_ON_PROVIDER_FASHN_MAX
    assert _normalize_provider("tryon-max") == TRY_ON_PROVIDER_FASHN_MAX
    assert _normalize_provider("fashn") == TRY_ON_PROVIDER_FASHN

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key")
    from app.core.config import get_settings

    get_settings.cache_clear()
    set_try_on_provider_override(None)
    adapter = get_try_on_provider("fashn_max")
    assert adapter.__class__.__name__ == "FashnTryOnMaxAdapter"
    v16 = get_try_on_provider("fashn")
    assert v16.__class__.__name__ == "FashnTryOnV16Adapter"
    get_settings.cache_clear()


def test_owner_allowlist_fail_closed_and_match(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "")
    get_settings.cache_clear()
    user = SimpleNamespace(id=uuid.uuid4(), email="owner@example.com", username="owner")
    assert user_on_fashn_max_allowlist(user) is False

    monkeypatch.setenv(
        "FASHN_TRY_ON_MAX_OWNER_ALLOWLIST",
        "owner@example.com,aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    )
    get_settings.cache_clear()
    assert user_on_fashn_max_allowlist(user) is True
    stranger = SimpleNamespace(id=uuid.uuid4(), email="other@example.com", username="x")
    assert user_on_fashn_max_allowlist(stranger) is False
    get_settings.cache_clear()


def test_experiment_results_excluded_from_my_looks():
    job = SimpleNamespace(
        result_data={
            "experiment": True,
            "looks_eligible": False,
            "provider": FASHN_MAX_PROVIDER_ID,
            "archive_status": "private",
        }
    )
    assert _experiment_lane_excluded(job) is True
    rejected = SimpleNamespace(
        result_data={"experiment": True, "archive_status": "rejected", "looks_eligible": False}
    )
    assert _experiment_lane_excluded(rejected) is True
    ordinary = SimpleNamespace(result_data={"provider": "fashn_tryon_v1_6", "status": "completed"})
    assert _experiment_lane_excluded(ordinary) is False


def test_enqueue_fashn_max_forbidden_without_allowlist(monkeypatch):
    """Empty allowlist / non-owner cannot pass the Max gate even when flags are on."""
    from app.core.config import get_settings
    from app.services import personal_try_on as pts
    from fastapi import HTTPException

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "")
    get_settings.cache_clear()

    user = SimpleNamespace(id=uuid.uuid4(), email="stranger@example.com", username="stranger")
    with pytest.raises(HTTPException) as ei:
        pts.enqueue_personal_try_on(
            db=SimpleNamespace(),  # unused before allowlist gate
            user=user,
            croquis_id=uuid.uuid4(),
            croquis_version=1,
            garment_image_base64="data:image/png;base64," + base64.b64encode(_png_bytes()).decode(),
            idempotency_key=f"try_on:fashn_max:{uuid.uuid4()}",
            design_id=None,
            source_revision=1,
            content_fingerprint="a" * 32,
            consent_acknowledged=True,
            consent_version="try-on-fashn-oneclick-v1",
            provider="fashn_max",
            fashn_max_generation_mode="balanced",
            fashn_max_resolution="1k",
        )
    assert ei.value.status_code == 403
    assert "owner-only" in str(ei.value.detail).lower()
    get_settings.cache_clear()


def test_max_adapter_generate_passes_experiment_kwargs(monkeypatch):
    """Adapter.generate accepts Max knobs and builds product_image payload (mocked HTTP)."""
    from app.core.config import get_settings
    from app.services.fashn_try_on_max_provider import FashnTryOnMaxAdapter
    from app.services.fashn_garment_prep import prep_from_approved_product_pieces

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key")
    get_settings.cache_clear()

    captured: dict = {}

    class FakeResp:
        status_code = 200
        headers = {"x-fashn-credits-used": "2"}

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResp({"id": "pred-max-1", "error": None})

        def get(self, url, headers=None):
            out_png = _png_bytes((10, 10, 10, 255))
            uri = "data:image/png;base64," + base64.b64encode(out_png).decode("ascii")
            return FakeResp(
                {"id": "pred-max-1", "status": "completed", "output": [uri], "error": None}
            )

    monkeypatch.setattr("app.services.fashn_try_on_max_provider.httpx.Client", FakeClient)

    product = _png_bytes((0, 100, 0, 255))
    prep = prep_from_approved_product_pieces(
        pieces=[("one-pieces", product)],
        source_fingerprint="fp",
    )
    adapter = FashnTryOnMaxAdapter()
    photo = _png_bytes((200, 180, 160, 255))
    out, meta = adapter.generate(
        photo_png=photo,
        garment_png=product,
        prep=prep,
        generation_mode="quality",
        resolution="1k",
        prompt="Preserve the deep V and high slit.",
        seed=42,
        num_images=1,
    )
    assert isinstance(out, (bytes, bytearray)) and len(out) > 32
    assert meta["provider"] == FASHN_MAX_PROVIDER_ID
    assert meta["model"] == FASHN_MAX_MODEL_NAME
    assert meta["generation_mode"] == "quality"
    assert meta["experiment"] is True
    assert meta["looks_eligible"] is False
    assert captured["json"]["model_name"] == "tryon-max"
    assert "product_image" in captured["json"]["inputs"]
    assert "garment_image" not in captured["json"]["inputs"]
    assert captured["json"]["inputs"]["generation_mode"] == "quality"
    get_settings.cache_clear()
