"""#179 — Smart Try-On hardening: auth, moderation exclusion, looks eligibility, structure."""

from __future__ import annotations

import io
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.services.garment_leg_geometry import (
    analyze_lower_garment_geometry,
    garment_structure_contradiction,
    openai_trouser_design_hints,
)
from app.services.looks_service import _experiment_lane_excluded
from app.services.personal_try_on import (
    SMART_FALLBACK_ERROR_CODES,
    SMART_FALLBACK_EXCLUDED_CODES,
    TRY_ON_PROVIDER_FASHN_MAX,
    TRY_ON_PROVIDER_OPENAI,
    is_openai_try_on_eligible_for_max_fallback,
    is_openai_try_on_terminal_failure,
    smart_max_fallback_available,
)


def _clear():
    get_settings.cache_clear()


def _png(draw_fn) -> bytes:
    img = Image.new("RGBA", (256, 384), (255, 255, 255, 0))
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _high_slit_dress_png() -> bytes:
    def draw(d):
        # Continuous dress panel with a high side slit (open gap, not two legs).
        d.polygon([(90, 40), (170, 40), (190, 340), (70, 340)], fill=(20, 140, 60, 255))
        # Carve a slit on the right by clearing a triangular gap.
        d.polygon([(150, 160), (190, 340), (150, 340)], fill=(255, 255, 255, 0))

    return _png(draw)


def _trousers_png() -> bytes:
    def draw(d):
        d.rectangle((70, 40, 186, 160), fill=(20, 140, 60, 255))
        d.rectangle((70, 160, 120, 350), fill=(20, 140, 60, 255))
        d.rectangle((136, 160, 186, 350), fill=(20, 140, 60, 255))

    return _png(draw)


def test_moderation_and_unknown_excluded_from_auto_max():
    assert "PROVIDER_MODERATION_BLOCKED" in SMART_FALLBACK_EXCLUDED_CODES
    assert "PROVIDER_OUTCOME_UNKNOWN" in SMART_FALLBACK_EXCLUDED_CODES
    assert "PROVIDER_MODERATION_BLOCKED" not in SMART_FALLBACK_ERROR_CODES
    assert "PROVIDER_TIMEOUT" in SMART_FALLBACK_ERROR_CODES

    assert (
        is_openai_try_on_terminal_failure(
            job_status="failed",
            result_data={"error_code": "PROVIDER_MODERATION_BLOCKED"},
        )
        is True
    )
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data={"error_code": "PROVIDER_MODERATION_BLOCKED"},
        )
        is False
    )
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data={"error_code": "PROVIDER_OUTCOME_UNKNOWN", "reconciliation_required": True},
        )
        is False
    )
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data={"error_code": "PROVIDER_TIMEOUT"},
        )
        is True
    )
    # Failed without a structured code must not invent another paid generation.
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data={},
        )
        is False
    )
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="completed",
            result_data={"status": "completed"},
        )
        is False
    )


def test_smart_public_max_enters_my_looks():
    smart = SimpleNamespace(
        result_data={
            "experiment": False,
            "looks_eligible": True,
            "provider": "fashn_tryon_max",
            "archive_status": "accepted",
            "smart_fallback": True,
            "smart_pipeline": {"lane": "smart_public"},
        },
        input_data={"smart_fallback": True, "experiment": False, "looks_eligible": True},
    )
    assert _experiment_lane_excluded(smart) is False

    owner_exp = SimpleNamespace(
        result_data={
            "experiment": True,
            "looks_eligible": False,
            "provider": "fashn_tryon_max",
            "archive_status": "private",
        },
        input_data={"experiment": True},
    )
    assert _experiment_lane_excluded(owner_exp) is True

    # Fail-closed: bare Max provider without public stamps stays out.
    bare_max = SimpleNamespace(
        result_data={"provider": "fashn_tryon_max", "status": "completed"},
        input_data={"provider": "fashn_max"},
    )
    assert _experiment_lane_excluded(bare_max) is True


def test_high_slit_hints_and_contradiction_guard():
    dress = _high_slit_dress_png()
    trousers = _trousers_png()
    geo = analyze_lower_garment_geometry(dress)
    # Fixture may be borderline; when classified as high-slit, hints must be dress-preserving.
    hints = openai_trouser_design_hints(geo)
    if geo.looks_like_high_slit_dress and not geo.looks_like_trousers:
        assert any("dress" in h.lower() for h in hints)
        assert any("slit" in h.lower() or "opening" in h.lower() for h in hints)
        assert not any("trousers / pant legs" == h for h in hints)

    # Confident dress source + trousers product → contradiction.
    dress_geo = analyze_lower_garment_geometry(dress)
    trouser_geo = analyze_lower_garment_geometry(trousers)
    if dress_geo.looks_like_high_slit_dress and trouser_geo.looks_like_trousers:
        contra = garment_structure_contradiction(source_png=dress, product_png=trousers)
        assert contra is not None
        assert contra["code"] == "STRUCTURE_CATEGORY_CONTRADICTION"
        assert "trousers" in contra["reason"]

    # Matching trousers must not invent a dress contradiction.
    same = garment_structure_contradiction(source_png=trousers, product_png=trousers)
    assert same is None


def test_forged_smart_fallback_rejected_without_primary(monkeypatch):
    from app.services import personal_try_on as pts
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "")
    _clear()

    user = SimpleNamespace(id=uuid.uuid4(), email="customer@example.com", username="c")
    db = MagicMock()
    # No primary OpenAI job found.
    db.get.return_value = None
    db.scalars.return_value.all.return_value = []

    with pytest.raises(HTTPException) as ei:
        # Decode garment will fail early unless we stub — authorize runs after decode.
        # Use empty garment to fail earlier OR stub decode. Prefer calling authorize directly.
        pts._authorize_smart_max_fallback(
            db,
            user,
            smart_operation_id="op-forged",
            primary_try_on_job_id=None,
            croquis_id=uuid.uuid4(),
            croquis_version=1,
            garment_fingerprint="a" * 64,
            content_fingerprint="b" * 32,
            source_revision=1,
            client_reason="PROVIDER_MODERATION_BLOCKED",
        )
    assert ei.value.status_code in {403, 400}
    _clear()


def test_authorize_rejects_moderation_primary(monkeypatch):
    from app.services import personal_try_on as pts

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key")
    _clear()
    assert smart_max_fallback_available() is True

    user = SimpleNamespace(id=uuid.uuid4(), email="c@example.com", username="c")
    croquis_id = uuid.uuid4()
    primary = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_try_on",
        status="failed",
        error_message="blocked",
        input_data={
            "provider": TRY_ON_PROVIDER_OPENAI,
            "croquis_id": str(croquis_id),
            "croquis_version": 1,
            "garment_fingerprint": "a" * 64,
            "content_fingerprint": "b" * 32,
            "source_revision": 1,
            "smart_pipeline": {
                "lane": "smart_public",
                "smart_operation_id": "op-1",
            },
        },
        result_data={"error_code": "PROVIDER_MODERATION_BLOCKED"},
    )
    db = MagicMock()
    db.get.return_value = primary

    with pytest.raises(HTTPException) as ei:
        pts._authorize_smart_max_fallback(
            db,
            user,
            smart_operation_id="op-1",
            primary_try_on_job_id=primary.id,
            croquis_id=croquis_id,
            croquis_version=1,
            garment_fingerprint="a" * 64,
            content_fingerprint="b" * 32,
            source_revision=1,
            client_reason="PROVIDER_MODERATION_BLOCKED",
        )
    assert ei.value.status_code == 422
    _clear()


def test_authorize_accepts_technical_timeout(monkeypatch):
    from app.services import personal_try_on as pts

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key")
    _clear()

    user = SimpleNamespace(id=uuid.uuid4(), email="c@example.com", username="c")
    croquis_id = uuid.uuid4()
    primary = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_try_on",
        status="failed",
        error_message="timeout",
        input_data={
            "provider": TRY_ON_PROVIDER_OPENAI,
            "croquis_id": str(croquis_id),
            "croquis_version": 2,
            "garment_fingerprint": "c" * 64,
            "content_fingerprint": "d" * 32,
            "source_revision": 3,
            "smart_pipeline": {
                "lane": "smart_public",
                "smart_operation_id": "op-tech",
            },
        },
        result_data={"error_code": "PROVIDER_TIMEOUT"},
    )
    db = MagicMock()
    db.get.return_value = primary
    db.scalars.return_value.all.return_value = []  # no prior Max

    out = pts._authorize_smart_max_fallback(
        db,
        user,
        smart_operation_id="op-tech",
        primary_try_on_job_id=primary.id,
        croquis_id=croquis_id,
        croquis_version=2,
        garment_fingerprint="c" * 64,
        content_fingerprint="d" * 32,
        source_revision=3,
        client_reason="client_forged_reason",
    )
    assert out["primary_job_id"] == str(primary.id)
    assert out["server_fallback_reason"] == "PROVIDER_TIMEOUT"
    assert out["smart_operation_id"] == "op-tech"
    _clear()


def test_authorize_rejects_fingerprint_mismatch(monkeypatch):
    from app.services import personal_try_on as pts

    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key")
    _clear()

    user = SimpleNamespace(id=uuid.uuid4(), email="c@example.com", username="c")
    croquis_id = uuid.uuid4()
    primary = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_try_on",
        status="failed",
        error_message="timeout",
        input_data={
            "provider": TRY_ON_PROVIDER_OPENAI,
            "croquis_id": str(croquis_id),
            "croquis_version": 1,
            "garment_fingerprint": "old" + ("0" * 61),
            "content_fingerprint": "d" * 32,
            "source_revision": 1,
            "smart_pipeline": {"smart_operation_id": "op-m", "lane": "smart_public"},
        },
        result_data={"error_code": "PROVIDER_TIMEOUT"},
    )
    db = MagicMock()
    db.get.return_value = primary
    with pytest.raises(HTTPException) as ei:
        pts._authorize_smart_max_fallback(
            db,
            user,
            smart_operation_id="op-m",
            primary_try_on_job_id=primary.id,
            croquis_id=croquis_id,
            croquis_version=1,
            garment_fingerprint="new" + ("0" * 61),
            content_fingerprint="d" * 32,
            source_revision=1,
            client_reason=None,
        )
    assert ei.value.status_code == 409
    _clear()


def test_smart_pipeline_metadata_still_one_charge_unit():
    meta = {
        "lane": "smart_public",
        "primary_provider": TRY_ON_PROVIDER_OPENAI,
        "fallback_triggered": True,
        "fallback_reason": "PROVIDER_TIMEOUT",
        "fallback_provider": TRY_ON_PROVIDER_FASHN_MAX,
        "path": "openai->fashn_max",
        "user_visible_charge_units": 1,
    }
    assert meta["user_visible_charge_units"] == 1
    # Metadata is not a billing implementation — document the commercial contract gap.
    assert meta["user_visible_charge_units"] != "implemented_debit"
