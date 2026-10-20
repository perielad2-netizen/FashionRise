"""Unit tests for trustworthy rate-limit client IP selection. No network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import rate_limit


class _Headers(dict):
    def get(self, key, default=None):  # noqa: ANN001
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


def _request(*, client_host: str = "203.0.113.10", headers: dict | None = None):
    return SimpleNamespace(
        client=SimpleNamespace(host=client_host, port=443),
        headers=_Headers(headers or {}),
    )


def test_ignores_forged_x_forwarded_for_by_default(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    # Force re-read
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    req = _request(
        client_host="203.0.113.10",
        headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8", "X-Real-IP": "9.9.9.9"},
    )
    assert rate_limit.client_ip_key(req) == "203.0.113.10"


def test_trusts_single_x_real_ip_when_enabled(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        headers={"X-Real-IP": "198.51.100.20", "X-Forwarded-For": "1.2.3.4"},
    )
    assert rate_limit.client_ip_key(req) == "198.51.100.20"


def test_rejects_multi_value_x_real_ip_when_enabled(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        headers={"X-Real-IP": "198.51.100.20, 1.2.3.4"},
    )
    # Fall back to direct peer — do not honor a forged chain.
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_trust_flag_defaults_false(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    assert rate_limit.trust_proxy_headers() is False
