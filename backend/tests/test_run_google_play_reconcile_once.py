"""Operator entrypoint for automated reconcile — order-scoped safeguards."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings


def _load_once_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_google_play_reconcile_once.py"
    spec = importlib.util.spec_from_file_location("run_google_play_reconcile_once", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_once_refuses_apply_when_persistent_gate_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "true")
    get_settings.cache_clear()
    mod = _load_once_module()
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_google_play_reconcile_once.py",
            "--order-id",
            "GPA.3329-8879-2128-29183",
            "--authorize-apply-stars",
            "50",
            "--apply",
        ],
    )
    assert mod.main() == 3
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "false")
    get_settings.cache_clear()


def test_once_apply_requires_order_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IAP_GOOGLE_FINANCIAL_RECONCILE_APPLY", "false")
    get_settings.cache_clear()
    mod = _load_once_module()
    monkeypatch.setattr("sys.argv", ["run_google_play_reconcile_once.py", "--apply"])
    # Patch worker so we never hit DB if code path wrong.
    monkeypatch.setattr(mod, "run_google_play_reconcile_tick", MagicMock())
    assert mod.main() == 2
