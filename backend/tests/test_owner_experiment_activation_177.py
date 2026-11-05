"""#177 — Owner experiment allowlist vs Max live readiness (offline, no paid calls)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.core.config import get_settings
from app.services.personal_try_on import try_on_preflight_public


def _clear_settings():
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
    _clear_settings()


def test_preflight_owner_experiment_independent_of_max_live(monkeypatch):
    """Allowlisted owner sees experiment panel even when Max is not live-armed."""
    owner = SimpleNamespace(
        id=uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
        email="owner@example.com",
        username="owner",
    )
    _base_env(
        monkeypatch,
        max_enabled=True,
        max_live=False,
        allowlist="owner@example.com",
    )
    pf = try_on_preflight_public(user=owner)
    assert pf["fashn_owner_experiment_allowed"] is True
    assert pf["fashn_max_owner_allowed"] is False
    assert pf["fashn_max_live_http"] is False
    _clear_settings()


def test_preflight_max_selectable_only_when_configured_and_live(monkeypatch):
    owner = SimpleNamespace(
        id=uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
        email="owner@example.com",
        username="owner",
    )
    _base_env(
        monkeypatch,
        max_enabled=True,
        max_live=True,
        allowlist="owner@example.com",
    )
    pf = try_on_preflight_public(user=owner)
    assert pf["fashn_owner_experiment_allowed"] is True
    assert pf["fashn_max_configured"] is True
    assert pf["fashn_max_live_http"] is True
    assert pf["fashn_max_owner_allowed"] is True
    _clear_settings()


def test_preflight_non_owner_never_sees_experiment_or_max(monkeypatch):
    stranger = SimpleNamespace(
        id=uuid.uuid4(),
        email="customer@example.com",
        username="customer",
    )
    _base_env(
        monkeypatch,
        max_enabled=True,
        max_live=True,
        allowlist="owner@example.com,aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    )
    pf = try_on_preflight_public(user=stranger)
    assert pf["fashn_owner_experiment_allowed"] is False
    assert pf["fashn_max_owner_allowed"] is False
    # Max flags may still report server readiness — authorization stays false.
    assert pf["fashn_max_enabled"] is True
    _clear_settings()


def test_preflight_anonymous_user_denied(monkeypatch):
    _base_env(
        monkeypatch,
        max_enabled=True,
        max_live=True,
        allowlist="owner@example.com",
    )
    pf = try_on_preflight_public(user=None)
    assert pf["fashn_owner_experiment_allowed"] is False
    assert pf["fashn_max_owner_allowed"] is False
    _clear_settings()


def test_preflight_max_disabled_keeps_owner_experiment(monkeypatch):
    owner = SimpleNamespace(
        id=uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
        email="owner@example.com",
        username="owner",
    )
    _base_env(
        monkeypatch,
        max_enabled=False,
        max_live=False,
        allowlist="owner@example.com",
    )
    pf = try_on_preflight_public(user=owner)
    assert pf["fashn_owner_experiment_allowed"] is True
    assert pf["fashn_max_enabled"] is False
    assert pf["fashn_max_owner_allowed"] is False
    _clear_settings()
