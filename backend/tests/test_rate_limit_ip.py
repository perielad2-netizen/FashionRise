"""Unit tests for trustworthy rate-limit client IP selection. No network."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers

from app.core import rate_limit


def _request(*, client_host: str = "203.0.113.10", header_list: list[tuple[str, str]] | None = None):
    """Build a minimal request using real Starlette Headers (supports duplicates)."""
    raw = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (header_list or [])]
    return SimpleNamespace(
        client=SimpleNamespace(host=client_host, port=443),
        headers=Headers(raw=raw),
    )


def test_default_off_ignores_forged_x_real_ip_and_xff(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    req = _request(
        client_host="203.0.113.10",
        header_list=[
            ("x-forwarded-for", "1.2.3.4, 5.6.7.8"),
            ("x-real-ip", "9.9.9.9"),
        ],
    )
    assert rate_limit.client_ip_key(req) == "203.0.113.10"


def test_default_off_when_env_unset(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    assert rate_limit.trust_proxy_headers() is False
    req = _request(
        client_host="203.0.113.10",
        header_list=[("x-real-ip", "198.51.100.20")],
    )
    assert rate_limit.client_ip_key(req) == "203.0.113.10"


def test_trusts_single_x_real_ip_when_enabled(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        header_list=[
            ("x-real-ip", "198.51.100.20"),
            ("x-forwarded-for", "1.2.3.4"),
        ],
    )
    assert rate_limit.client_ip_key(req) == "198.51.100.20"


def test_rejects_duplicate_x_real_ip_headers_starlette(monkeypatch):
    """Duplicate fields must fail closed — Headers.getlist exposes both values."""
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        header_list=[
            ("x-real-ip", "198.51.100.20"),
            ("x-real-ip", "203.0.113.50"),
        ],
    )
    assert req.headers.getlist("x-real-ip") == ["198.51.100.20", "203.0.113.50"]
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_rejects_duplicate_identical_x_real_ip_headers(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        header_list=[
            ("x-real-ip", "198.51.100.20"),
            ("x-real-ip", "198.51.100.20"),
        ],
    )
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_rejects_comma_joined_x_real_ip(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        header_list=[("x-real-ip", "198.51.100.20, 1.2.3.4")],
    )
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not-an-ip",
        "999.999.999.999",
        "198.51.100.20/32",
        "198.51.100.20 198.51.100.21",
        "198.51.100.20:443",
        "[2001:db8::1]",
        "[2001:db8::1]:443",
        "2001:db8::1%eth0",
        "fe80::1%lo0",
        "localhost",
    ],
)
def test_rejects_malformed_x_real_ip(monkeypatch, raw: str):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(client_host="127.0.0.1", header_list=[("x-real-ip", raw)])
    assert rate_limit.client_ip_key(req) == "127.0.0.1"


def test_accepts_ipv6_and_normalizes(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(
        client_host="127.0.0.1",
        header_list=[("x-real-ip", "2001:DB8::1")],
    )
    assert rate_limit.client_ip_key(req) == "2001:db8::1"


def test_missing_x_real_ip_falls_back_to_peer(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    req = _request(client_host="203.0.113.55", header_list=[])
    assert rate_limit.client_ip_key(req) == "203.0.113.55"


def test_parse_single_ip_helpers():
    assert rate_limit.parse_single_ip("198.51.100.1") == "198.51.100.1"
    assert rate_limit.parse_single_ip("2001:DB8::1") == "2001:db8::1"
    assert rate_limit.parse_single_ip("1.2.3.4,5.6.7.8") is None
    assert rate_limit.parse_single_ip("1.2.3.4:80") is None
    assert rate_limit.parse_single_ip("[2001:db8::1]") is None
    assert rate_limit.parse_single_ip("fe80::1%eth0") is None
    assert rate_limit.parse_single_ip(None) is None


def test_x_real_ip_header_values_from_starlette_headers():
    h = Headers(
        raw=[
            (b"x-real-ip", b"1.1.1.1"),
            (b"x-real-ip", b"2.2.2.2"),
        ]
    )
    assert rate_limit.x_real_ip_header_values(h) == ["1.1.1.1", "2.2.2.2"]
