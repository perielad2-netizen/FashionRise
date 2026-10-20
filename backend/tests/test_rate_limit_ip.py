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
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_trust_flag_defaults_false(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    assert rate_limit.trust_proxy_headers() is False


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not-an-ip",
        "999.999.999.999",
        "198.51.100.20/32",
        "198.51.100.20 198.51.100.21",
        "2001:db8::1,2001:db8::2",
        "localhost",
    ],
)
def test_rejects_malformed_x_real_ip(monkeypatch, raw: str):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(client_host="127.0.0.1", headers={"X-Real-IP": raw})
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_accepts_ipv6_x_real_ip(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(client_host="127.0.0.1", headers={"X-Real-IP": "2001:db8::1"})
    assert rate_limit.client_ip_key(req) == "2001:db8::1"


def test_missing_x_real_ip_falls_back_to_peer(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(client_host="203.0.113.55", headers={})
    assert rate_limit.client_ip_key(req) == "203.0.113.55"


def test_parse_single_ip_helpers():
    assert rate_limit.parse_single_ip("198.51.100.1") == "198.51.100.1"
    assert rate_limit.parse_single_ip("2001:DB8::1") == "2001:db8::1"
    assert rate_limit.parse_single_ip("1.2.3.4,5.6.7.8") is None
    assert rate_limit.parse_single_ip(None) is None
