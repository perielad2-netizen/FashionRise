"""Shared SlowAPI limiter with trustworthy client IP determination.

By default only the direct peer address is used. Client-supplied
``X-Forwarded-For`` is ignored so attackers cannot bypass per-IP limits.

When FashionRise sits behind Nginx that has already:

1. Applied ``real_ip`` with explicit Cloudflare CIDRs, and
2. **Overwritten** ``X-Real-IP`` with the normalized visitor ``$remote_addr``,

set ``TRUST_PROXY_HEADERS=true`` so the limiter keys on that single header.

Malformed or multi-value ``X-Real-IP`` values are rejected (fall back to the
direct ASGI peer) using :mod:`ipaddress` validation — not a coarse regex.
"""

from __future__ import annotations

import ipaddress
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def trust_proxy_headers() -> bool:
    return _env_flag("TRUST_PROXY_HEADERS", default=False)


def parse_single_ip(value: str | None) -> str | None:
    """Return a canonical single IP string, or None if missing/unsafe/malformed.

    Rejects empty values, comma-separated chains, whitespace-only input, and
    anything ``ipaddress.ip_address`` cannot parse as a single IPv4/IPv6 address.
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw or "," in raw or any(ch.isspace() for ch in raw):
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def client_ip_key(request: Request) -> str:
    """Return the IP used for rate-limit buckets.

    - Default: direct ASGI client host (ignores forged X-Forwarded-For).
    - With TRUST_PROXY_HEADERS: only a single, ``ipaddress``-validated
      ``X-Real-IP`` written by a trusted reverse proxy. Multi-value / forged
      XFF chains and malformed IPs are ignored (fall back to peer).
    """
    if trust_proxy_headers():
        parsed = parse_single_ip(request.headers.get("x-real-ip"))
        if parsed is not None:
            return parsed
    return get_remote_address(request)


# headers_enabled=False: SlowAPI otherwise requires a Starlette Response in the handler
# to inject X-RateLimit-* headers; FastAPI + Pydantic JSON responses do not satisfy that.
# Disable in automated tests so suites that register many users are not flaky.
_testing = _env_flag("TESTING", default=False)
limiter = Limiter(key_func=client_ip_key, headers_enabled=False, enabled=not _testing)
