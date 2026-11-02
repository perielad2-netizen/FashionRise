"""#176 — FASHN v1.6 experiment knobs, approved-garment reuse, Max visibility, OpenAI refusal copy.

Offline only — no paid provider calls.
"""

from __future__ import annotations

import base64
import io
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.services.fashn_try_on_provider import (
    FASHN_MODEL_NAME,
    V16_DEFAULT_GARMENT_PHOTO_TYPE,
    V16_DEFAULT_MODE,
    V16_DEFAULT_MODERATION_LEVEL,
    V16_DEFAULT_SEED,
    V16_DEFAULT_SEGMENTATION_FREE,
    build_tryon_v16_run_payload,
    normalize_v16_category,
    normalize_v16_mode,
    normalize_v16_seed,
    normalize_v16_segmentation_free,
)
from app.services.fashn_try_on_max_provider import user_on_fashn_max_allowlist
from app.services.personal_try_on_provider import (
    TRY_ON_USER_MODERATION_MESSAGE,
    TRY_ON_USER_OUTPUT_MODERATION_MESSAGE,
)


def _png_bytes(color=(20, 120, 40, 255), size=(64, 96)) -> bytes:
    img = Image.new("RGBA", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_v16_payload_maps_documented_fields_only():
    payload = build_tryon_v16_run_payload(
        model_image="data:image/png;base64,aaa",
        garment_image="data:image/png;base64,bbb",
        category="one-pieces",
        segmentation_free=True,
        mode="balanced",
        seed=42,
        num_samples=1,
    )
    assert payload["model_name"] == FASHN_MODEL_NAME == "tryon-v1.6"
    inputs = payload["inputs"]
    assert set(inputs.keys()) == {
        "model_image",
        "garment_image",
        "category",
        "garment_photo_type",
        "moderation_level",
        "segmentation_free",
        "mode",
        "seed",
        "num_samples",
        "output_format",
        "return_base64",
    }
    assert "prompt" not in inputs
    assert inputs["category"] == "one-pieces"
    assert inputs["garment_photo_type"] == V16_DEFAULT_GARMENT_PHOTO_TYPE == "flat-lay"
    assert inputs["moderation_level"] == V16_DEFAULT_MODERATION_LEVEL == "permissive"
    assert inputs["segmentation_free"] is True
    assert inputs["mode"] == "balanced"
    assert inputs["seed"] == 42
    assert inputs["num_samples"] == 1
    assert inputs["return_base64"] is True


def test_v16_category_and_segmentation_owner_options():
    assert normalize_v16_category("one-pieces") == "one-pieces"
    assert normalize_v16_category("auto") == "auto"
    # Owner knobs only accept one-pieces|auto; other raw values fall back to piece category.
    assert normalize_v16_category("tops", piece_category="bottoms") == "bottoms"
    assert normalize_v16_category(None, piece_category="bottoms") == "bottoms"
    assert normalize_v16_category("nope") == "one-pieces"
    assert normalize_v16_segmentation_free(True) is True
    assert normalize_v16_segmentation_free(False) is False
    assert normalize_v16_segmentation_free(None) is V16_DEFAULT_SEGMENTATION_FREE
    assert normalize_v16_mode("quality") == "quality"
    assert normalize_v16_mode("balanced") == V16_DEFAULT_MODE
    assert normalize_v16_mode("bogus") == V16_DEFAULT_MODE
    assert normalize_v16_seed(99) == 99
    assert normalize_v16_seed(-1) == V16_DEFAULT_SEED
    assert normalize_v16_seed(None) == V16_DEFAULT_SEED


def test_v16_quality_mode_and_seg_false_in_payload():
    payload = build_tryon_v16_run_payload(
        model_image="m",
        garment_image="g",
        category="auto",
        segmentation_free=False,
        mode="quality",
        seed=7,
    )
    assert payload["inputs"]["category"] == "auto"
    assert payload["inputs"]["segmentation_free"] is False
    assert payload["inputs"]["mode"] == "quality"
    assert payload["inputs"]["seed"] == 7


def test_output_moderation_message_differs_from_generic():
    assert "output safety" in TRY_ON_USER_OUTPUT_MODERATION_MESSAGE.lower()
    assert TRY_ON_USER_OUTPUT_MODERATION_MESSAGE != TRY_ON_USER_MODERATION_MESSAGE


def test_fail_path_preserves_output_moderation_diagnostics():
    from app.services import personal_try_on as pts

    exc = Exception("moderation_blocked")
    exc.safe_meta = {  # type: ignore[attr-defined]
        "error_code": "PROVIDER_MODERATION_BLOCKED",
        "provider_code": "moderation_blocked",
        "moderation_stage": "output",
        "categories": ["sexual"],
        "http_status": 400,
        "request_id": "req_test_176",
        "operator_summary": "output blocked",
    }
    user_msg, rd = pts._try_on_user_failure_payload(exc)
    assert user_msg == TRY_ON_USER_OUTPUT_MODERATION_MESSAGE
    assert rd["error_code"] == "PROVIDER_MODERATION_BLOCKED"
    assert rd["summary"] == TRY_ON_USER_OUTPUT_MODERATION_MESSAGE
    assert rd["provider_rejection"]["moderation_stage"] == "output"
    assert rd["provider_rejection"]["categories"] == ["sexual"]
    assert rd["provider_rejection"]["request_id"] == "req_test_176"


def test_list_accepted_garment_realism_owner_only(monkeypatch):
    from app.core.config import get_settings
    from app.services import personal_try_on as pts
    from fastapi import HTTPException

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "")
    get_settings.cache_clear()

    stranger = SimpleNamespace(id=uuid.uuid4(), email="x@example.com", username="x")
    with pytest.raises(HTTPException) as ei:
        pts.list_accepted_garment_realism_jobs(db=MagicMock(), user=stranger)
    assert ei.value.status_code == 403
    get_settings.cache_clear()


def test_list_accepted_filters_incomplete_and_maps_provenance(monkeypatch):
    from app.core.config import get_settings
    from app.services import personal_try_on as pts

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv(
        "FASHN_TRY_ON_MAX_OWNER_ALLOWLIST",
        "owner@example.com",
    )
    get_settings.cache_clear()

    owner = SimpleNamespace(id=uuid.uuid4(), email="owner@example.com", username="owner")
    croquis_id = uuid.uuid4()
    good_id = uuid.uuid4()
    good = SimpleNamespace(
        id=good_id,
        user_id=owner.id,
        job_type=pts.GARMENT_REALISM_JOB_TYPE,
        status="completed",
        created_at="2026-11-02",
        result_data={
            "owner_accepted": True,
            "provider": pts.GARMENT_REALISM_PROVIDER_ID,
            "fidelity_ok": True,
            "prompt_version": "garment-realism-v1",
            "pieces": [
                {
                    "category": "one-pieces",
                    "sha256": "abc123",
                    "image_base64": "data:image/png;base64,xx",
                }
            ],
            "owner_accepted_at": "2026-11-02T16:00:00Z",
        },
        input_data={
            "croquis_id": str(croquis_id),
            "croquis_version": 3,
            "garment_fingerprint": "fp-garment",
            "source_revision": 9,
            "content_fingerprint": "fp-content",
        },
    )
    incomplete = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner.id,
        job_type=pts.GARMENT_REALISM_JOB_TYPE,
        status="completed",
        created_at="2026-11-01",
        result_data={
            "owner_accepted": False,
            "provider": pts.GARMENT_REALISM_PROVIDER_ID,
            "pieces": [{"category": "one-pieces", "sha256": "nope"}],
        },
        input_data={},
    )
    blocked = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner.id,
        job_type=pts.GARMENT_REALISM_JOB_TYPE,
        status="completed",
        created_at="2026-11-01",
        result_data={
            "owner_accepted": True,
            "provider": pts.GARMENT_REALISM_PROVIDER_ID,
            "fidelity_ok": False,
            "block_fashn": True,
            "pieces": [{"category": "one-pieces", "sha256": "bad"}],
        },
        input_data={},
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def all(self):
            return [good, incomplete, blocked]

    db = MagicMock()
    db.query.return_value = _Q()
    rows = pts.list_accepted_garment_realism_jobs(db, owner)
    assert len(rows) == 1
    assert rows[0]["job_id"] == good_id
    assert rows[0]["piece_shas"] == ["abc123"]
    assert rows[0]["garment_fingerprint"] == "fp-garment"
    assert rows[0]["croquis_id"] == croquis_id
    get_settings.cache_clear()


def test_set_experiment_verdict_owner_and_fashn_only(monkeypatch):
    from app.core.config import get_settings
    from app.services import personal_try_on as pts
    from fastapi import HTTPException

    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "owner@example.com")
    get_settings.cache_clear()
    monkeypatch.setattr(pts, "flag_modified", lambda *_a, **_k: None)

    owner = SimpleNamespace(id=uuid.uuid4(), email="owner@example.com", username="owner")
    job_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        user_id=owner.id,
        job_type=pts.TRY_ON_JOB_TYPE,
        status="completed",
        input_data={"provider": pts.TRY_ON_PROVIDER_FASHN, "experiment": True},
        result_data={"experiment": True, "looks_eligible": False, "status": "completed"},
    )
    db = MagicMock()
    db.get.return_value = job

    out = pts.set_try_on_experiment_verdict(db, owner, job_id, verdict="rejected")
    assert out.result_data["experiment_verdict"] == "rejected"
    assert out.result_data["looks_eligible"] is False

    openai_job = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner.id,
        job_type=pts.TRY_ON_JOB_TYPE,
        status="completed",
        input_data={"provider": "openai"},
        result_data={"status": "completed"},
    )
    db.get.return_value = openai_job
    with pytest.raises(HTTPException) as ei:
        pts.set_try_on_experiment_verdict(db, owner, openai_job.id, verdict="accepted")
    assert ei.value.status_code == 400

    stranger = SimpleNamespace(id=uuid.uuid4(), email="nope@example.com", username="n")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "owner@example.com")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as ei2:
        pts.set_try_on_experiment_verdict(db, stranger, job_id, verdict="accepted")
    assert ei2.value.status_code == 403
    get_settings.cache_clear()


def test_v16_enqueue_knobs_ignored_for_non_owner(monkeypatch):
    """Non-owner cannot force experiment knobs; allowlist fail-closed."""
    from app.core.config import get_settings

    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", "owner@example.com")
    get_settings.cache_clear()
    stranger = SimpleNamespace(id=uuid.uuid4(), email="x@example.com", username="x")
    assert user_on_fashn_max_allowlist(stranger) is False
    get_settings.cache_clear()


def test_high_slit_dress_classification_still_intact():
    """Regression: #174 high-slit dress must not become jumpsuit hints."""
    from PIL import ImageDraw

    from app.services.garment_leg_geometry import (
        analyze_lower_garment_geometry,
        openai_trouser_design_hints,
    )

    img = Image.new("RGBA", (280, 560), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    green = (22, 101, 52, 255)
    draw.polygon([(120, 50), (160, 50), (190, 180), (90, 180)], fill=green)
    for y in range(180, 520):
        if y < 250:
            draw.rectangle([70, y, 210, y], fill=green)
        else:
            draw.rectangle([70, y, 155, y], fill=green)
            draw.rectangle([175, y, 205, y], fill=green)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    geo = analyze_lower_garment_geometry(buf.getvalue())
    assert geo.looks_like_high_slit_dress is True
    assert geo.looks_like_jumpsuit is False
    hints = openai_trouser_design_hints(geo)
    assert any("slit" in h.lower() for h in hints)
    assert not any("jumpsuit with trousers" in h.lower() for h in hints)


def test_nginx_allowlist_includes_176_routes():
    from pathlib import Path
    import runpy

    script = Path(__file__).resolve().parents[1] / "scripts" / "verify_nginx_ai_allowlist.py"
    ns = runpy.run_path(str(script))
    assert ns["main"]() == 0
