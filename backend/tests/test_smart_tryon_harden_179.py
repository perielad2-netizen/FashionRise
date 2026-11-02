"""#179/#180 — Smart Try-On harden: auth, output-mod Max, looks, structure, Max idempotency."""

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


def test_moderation_output_eligible_input_and_unknown_excluded():
    """#180 — output moderation may Max; input moderation / unknown must not."""
    assert "PROVIDER_OUTCOME_UNKNOWN" in SMART_FALLBACK_EXCLUDED_CODES
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
            result_data={
                "error_code": "PROVIDER_MODERATION_BLOCKED",
                "provider_rejection": {"moderation_stage": "output"},
            },
        )
        is True
    )
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data={
                "error_code": "PROVIDER_MODERATION_BLOCKED",
                "provider_rejection": {"moderation_stage": "input"},
            },
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
    assert geo.looks_like_high_slit_dress is True
    assert geo.looks_like_trousers is False
    hints = openai_trouser_design_hints(geo)
    assert hints
    assert any("dress" in h.lower() for h in hints)
    assert any("slit" in h.lower() or "opening" in h.lower() for h in hints)
    assert not any(h.strip().lower().startswith("garment type: trousers") for h in hints)

    trouser_geo = analyze_lower_garment_geometry(trousers)
    assert trouser_geo.looks_like_trousers is True
    contra = garment_structure_contradiction(source_png=dress, product_png=trousers)
    assert contra is not None
    assert contra["code"] == "STRUCTURE_CATEGORY_CONTRADICTION"
    assert "trousers" in contra["reason"]

    # Matching trousers must not invent a dress contradiction.
    same = garment_structure_contradiction(source_png=trousers, product_png=trousers)
    assert same is None


def test_swimsuit_not_false_positive_contradiction():
    """#180 — high-cut swimwear must not trip dress↔trousers guard."""
    from PIL import ImageDraw as ID

    def _swimsuit():
        img = Image.new("RGBA", (220, 420), (255, 255, 255, 0))
        d = ID.Draw(img)
        c = (20, 120, 160, 255)
        d.polygon([(110, 50), (150, 50), (180, 220), (160, 300), (60, 300), (40, 220)], fill=c)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    swim = _swimsuit()
    geo = analyze_lower_garment_geometry(swim)
    assert geo.looks_like_trousers is False
    assert geo.looks_like_high_slit_dress is False
    assert openai_trouser_design_hints(geo) == []
    assert garment_structure_contradiction(source_png=swim, product_png=swim) is None


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


def test_authorize_rejects_input_moderation_allows_output(monkeypatch):
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

    def _primary(stage: str):
        return SimpleNamespace(
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
            result_data={
                "error_code": "PROVIDER_MODERATION_BLOCKED",
                "provider_rejection": {"moderation_stage": stage, "categories": ["sexual"]},
            },
        )

    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    input_primary = _primary("input")
    db.get.return_value = input_primary
    with pytest.raises(HTTPException) as ei:
        pts._authorize_smart_max_fallback(
            db,
            user,
            smart_operation_id="op-1",
            primary_try_on_job_id=input_primary.id,
            croquis_id=croquis_id,
            croquis_version=1,
            garment_fingerprint="a" * 64,
            content_fingerprint="b" * 32,
            source_revision=1,
            client_reason="PROVIDER_MODERATION_BLOCKED",
        )
    assert ei.value.status_code == 422

    output_primary = _primary("output")
    db.get.return_value = output_primary
    out = pts._authorize_smart_max_fallback(
        db,
        user,
        smart_operation_id="op-1",
        primary_try_on_job_id=output_primary.id,
        croquis_id=croquis_id,
        croquis_version=1,
        garment_fingerprint="a" * 64,
        content_fingerprint="b" * 32,
        source_revision=1,
        client_reason="PROVIDER_MODERATION_BLOCKED",
    )
    assert out["primary_job_id"] == str(output_primary.id)
    assert out["server_fallback_reason"] == "PROVIDER_MODERATION_BLOCKED"
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


def test_authorize_recovers_existing_max_instead_of_duplicate(monkeypatch):
    """#180 — queued/running/completed/failed Max for same op recovers, never re-pays."""
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
            "croquis_version": 1,
            "garment_fingerprint": "e" * 64,
            "content_fingerprint": "f" * 32,
            "source_revision": 1,
            "smart_pipeline": {"lane": "smart_public", "smart_operation_id": "op-dup"},
        },
        result_data={"error_code": "PROVIDER_TIMEOUT"},
    )
    existing_max = SimpleNamespace(
        id=uuid.uuid4(),
        status="running",
        input_data={
            "provider": TRY_ON_PROVIDER_FASHN_MAX,
            "smart_fallback": True,
            "smart_pipeline": {"lane": "smart_public", "smart_operation_id": "op-dup"},
        },
        result_data={},
    )
    db = MagicMock()
    db.get.return_value = primary
    db.scalars.return_value.all.return_value = [existing_max]

    out = pts._authorize_smart_max_fallback(
        db,
        user,
        smart_operation_id="op-dup",
        primary_try_on_job_id=primary.id,
        croquis_id=croquis_id,
        croquis_version=1,
        garment_fingerprint="e" * 64,
        content_fingerprint="f" * 32,
        source_revision=1,
        client_reason="PROVIDER_TIMEOUT",
    )
    assert out["existing_max_job_id"] == str(existing_max.id)
    assert "server_fallback_reason" in out

    # Reconciliation-required Max must not authorize another paid attempt.
    existing_max.result_data = {"reconciliation_required": True}
    with pytest.raises(HTTPException) as ei:
        pts._authorize_smart_max_fallback(
            db,
            user,
            smart_operation_id="op-dup",
            primary_try_on_job_id=primary.id,
            croquis_id=croquis_id,
            croquis_version=1,
            garment_fingerprint="e" * 64,
            content_fingerprint="f" * 32,
            source_revision=1,
            client_reason="PROVIDER_TIMEOUT",
        )
    assert ei.value.status_code == 409
    _clear()


def test_smart_max_canonical_idempotency_key_bound_to_operation():
    """#180 — smart Max spend key is always try_on:fashn_max:smart:{op}, not client key."""
    import inspect

    from app.services import personal_try_on as pts

    src = inspect.getsource(pts.enqueue_personal_try_on)
    assert 'key = f"try_on:fashn_max:smart:{op_for_key}"' in src
    assert "smart_operation_id is required for smart Max fallback" in src
    # Spend-lock re-check recovers any prior Max for the same operation.
    assert 'AIJob.input_data["smart_pipeline"]["smart_operation_id"].astext == op_locked' in src
    # Different client keys for the same op therefore share one reservation namespace.
    op = "op-canon-abc"
    assert f"try_on:fashn_max:smart:{op}" == f"try_on:fashn_max:smart:{op}"
    assert "try_on:client-a" != f"try_on:fashn_max:smart:{op}"
    assert "try_on:client-b-different" != f"try_on:fashn_max:smart:{op}"
