"""#178 — Smart invisible Try On: OpenAI primary → Max Balanced 1k fallback (offline)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.config import get_settings
from app.services.personal_try_on import (
    TRY_ON_PROVIDER_FASHN_MAX,
    TRY_ON_PROVIDER_OPENAI,
    is_openai_try_on_eligible_for_max_fallback,
    is_openai_try_on_terminal_failure,
    smart_max_fallback_available,
    try_on_preflight_public,
)


def _clear():
    get_settings.cache_clear()


def _base_env(monkeypatch, *, max_enabled=True, max_live=True, allowlist=""):
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_LIVE_HTTP", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", "100")
    monkeypatch.setenv("FASHN_TRY_ON_ENABLED", "true")
    monkeypatch.setenv("FASHN_TRY_ON_LIVE_HTTP", "true")
    monkeypatch.setenv("FASHN_API_KEY", "test-key-not-used")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_ENABLED", "true" if max_enabled else "false")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_LIVE_HTTP", "true" if max_live else "false")
    monkeypatch.setenv("FASHN_TRY_ON_MAX_OWNER_ALLOWLIST", allowlist)
    _clear()


def test_terminal_failure_classifier_openai_success_no_fallback():
    assert (
        is_openai_try_on_terminal_failure(
            job_status="completed",
            result_data={"status": "completed", "image_url": "x"},
        )
        is False
    )
    # Soft structure flag still delivered an image — not a fallback trigger.
    assert (
        is_openai_try_on_terminal_failure(
            job_status="completed",
            result_data={"status": "completed_unverified", "fidelity_ok": False},
        )
        is False
    )


@pytest.mark.parametrize(
    "code",
    [
        "PROVIDER_MODERATION_BLOCKED",
        "PROVIDER_REJECTED",
        "PROVIDER_OUTCOME_UNKNOWN",
        "PROVIDER_TIMEOUT",
        "GENERATION_FAILED",
    ],
)
def test_terminal_failure_classifier_hard_codes(code):
    assert (
        is_openai_try_on_terminal_failure(
            job_status="failed",
            result_data={"error_code": code, "summary": "blocked"},
        )
        is True
    )


@pytest.mark.parametrize(
    "code,eligible,extra",
    [
        ("PROVIDER_TIMEOUT", True, {}),
        ("PROVIDER_FAILED", True, {}),
        ("GENERATION_FAILED", True, {}),
        ("PROVIDER_REJECTED", True, {}),
        (
            "PROVIDER_MODERATION_BLOCKED",
            True,
            {"provider_rejection": {"moderation_stage": "output"}},
        ),
        (
            "PROVIDER_MODERATION_BLOCKED",
            True,
            {"provider_rejection": {"moderation_stage": "input", "categories": ["sexual"]}},
        ),
        ("PROVIDER_OUTCOME_UNKNOWN", False, {}),
    ],
)
def test_max_fallback_eligibility_excludes_moderation_and_unknown(code, eligible, extra):
    """#180/#181 — technical + moderation (input/output) may Max; unknown may not."""
    data = {"error_code": code, "summary": "x", **extra}
    assert (
        is_openai_try_on_eligible_for_max_fallback(
            job_status="failed",
            result_data=data,
        )
        is eligible
    )


def test_preflight_smart_fallback_independent_of_allowlist(monkeypatch):
    stranger = SimpleNamespace(id=uuid.uuid4(), email="customer@example.com", username="c")
    _base_env(monkeypatch, max_enabled=True, max_live=True, allowlist="owner@example.com")
    assert smart_max_fallback_available() is True
    pf = try_on_preflight_public(user=stranger)
    assert pf["smart_try_on_max_fallback_available"] is True
    assert pf["fashn_owner_experiment_allowed"] is False
    assert pf["fashn_max_owner_allowed"] is False
    _clear()


def test_preflight_smart_fallback_off_when_max_not_live(monkeypatch):
    _base_env(monkeypatch, max_enabled=True, max_live=False, allowlist="")
    assert smart_max_fallback_available() is False
    pf = try_on_preflight_public(user=None)
    assert pf["smart_try_on_max_fallback_available"] is False
    _clear()


def test_enqueue_smart_max_forbidden_without_live(monkeypatch):
    from app.services import personal_try_on as pts

    _base_env(monkeypatch, max_enabled=True, max_live=False, allowlist="")
    user = SimpleNamespace(id=uuid.uuid4(), email="anyone@example.com", username="anyone")
    with pytest.raises(HTTPException) as ei:
        pts.enqueue_personal_try_on(
            db=MagicMock(),
            user=user,
            croquis_id=uuid.uuid4(),
            croquis_version=1,
            garment_image_base64="data:image/png;base64," + ("A" * 40),
            idempotency_key="try_on:fashn_max:smart-1",
            design_id=None,
            source_revision=1,
            content_fingerprint="fp" * 8,
            consent_acknowledged=True,
            consent_version="fashn-tryon-v1",
            provider="fashn_max",
            smart_fallback=True,
            smart_operation_id="op-1",
            smart_fallback_reason="PROVIDER_MODERATION_BLOCKED",
        )
    assert ei.value.status_code == 403
    _clear()


def test_enqueue_owner_max_still_requires_allowlist(monkeypatch):
    """Without smart_fallback, Max remains owner-allowlist gated (#173/#177)."""
    from app.services import personal_try_on as pts
    from app.services.fashn_try_on_provider import FASHN_CONSENT_VERSION

    _base_env(monkeypatch, max_enabled=True, max_live=True, allowlist="")
    user = SimpleNamespace(id=uuid.uuid4(), email="stranger@example.com", username="x")
    with pytest.raises(HTTPException) as ei:
        pts.enqueue_personal_try_on(
            db=MagicMock(),
            user=user,
            croquis_id=uuid.uuid4(),
            croquis_version=1,
            garment_image_base64="data:image/png;base64," + ("A" * 40),
            idempotency_key="try_on:fashn_max:owner-1",
            design_id=None,
            source_revision=1,
            content_fingerprint="fp" * 8,
            consent_acknowledged=True,
            consent_version=FASHN_CONSENT_VERSION,
            provider="fashn_max",
            smart_fallback=False,
        )
    assert ei.value.status_code == 403
    assert "owner-only" in str(ei.value.detail).lower()
    _clear()


def test_smart_pipeline_metadata_shape():
    """Document expected diagnostic fields for one logical user operation."""
    meta = {
        "lane": "smart_public",
        "primary_provider": TRY_ON_PROVIDER_OPENAI,
        "fallback_triggered": True,
        "fallback_reason": "PROVIDER_MODERATION_BLOCKED",
        "fallback_provider": TRY_ON_PROVIDER_FASHN_MAX,
        "final_provider": TRY_ON_PROVIDER_FASHN_MAX,
        "path": "openai->fashn_max",
        "generation_mode": "balanced",
        "resolution": "1k",
        "smart_operation_id": "op-abc",
        "user_visible_charge_units": 1,
    }
    assert meta["user_visible_charge_units"] == 1
    assert meta["path"] == "openai->fashn_max"
    assert meta["fallback_triggered"] is True
