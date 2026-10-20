"""Shared SlowAPI limiter with trustworthy client IP determination.

By default ``TRUST_PROXY_HEADERS`` is off and this module does **not** read
``X-Real-IP`` / ``X-Forwarded-For`` for rate-limit keys.

When FashionRise sits behind Nginx that has already:

1. Applied ``real_ip`` with explicit Cloudflare CIDRs, and
2. **Overwritten** a single ``X-Real-IP`` with the normalized visitor
   ``$remote_addr`` (and overwritten ``X-Forwarded-For`` the same way),

set ``TRUST_PROXY_HEADERS=true`` so the limiter keys on that header.

Validation rules (fail closed → fall back to ASGI peer via
``get_remote_address``):

- Exactly one ``X-Real-IP`` header field (Starlette ``Headers.getlist``).
- No commas / whitespace inside the value (rejects joined chains).
- No ports, brackets, or IPv6 zone identifiers.
- Must parse as a single address via :mod:`ipaddress`.

Syntax validation is **not** provenance. Activation still requires approved
Nginx Option B overwrites and Access/mTLS controls.

Uvicorn note: with default ``--proxy-headers`` and trusted host ``127.0.0.1``,
``Request.client.host`` / ``get_remote_address`` may already reflect
``X-Forwarded-For`` rewritten by ``ProxyHeadersMiddleware`` when Nginx on
localhost forwards that header. The SlowAPI fallback is therefore the
ASGI peer *after* that middleware — not necessarily literal ``127.0.0.1``.
"""

from __future__ import annotations

import ipaddress
import os
from typing import Any

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

    Rejects empty values, comma-separated chains, internal whitespace, ports,
    bracketed host:port forms, IPv6 zone IDs, and anything ``ipaddress`` rejects.
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw or "," in raw or any(ch.isspace() for ch in raw):
        return None
    # Reject host:port and bracketed forms explicitly (ipaddress would too for most).
    if raw.startswith("["):
        return None
    if "%" in raw:  # zone identifier e.g. fe80::1%eth0
        return None
    if raw.count(":") == 1 and "." in raw:
        # IPv4 with port (e.g. 198.51.100.20:443) — not a bare address.
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


def x_real_ip_header_values(headers: Any) -> list[str]:
    """Return every ``X-Real-IP`` field value from a Starlette-like Headers object.

    Duplicate header names must be visible. Prefer ``getlist`` so a mock ``dict``
    cannot hide conflicts. If only ``get`` exists, treat a comma-joined string as
    multiple values.
    """
    getlist = getattr(headers, "getlist", None)
    if callable(getlist):
        return [str(v) for v in getlist("x-real-ip")]
    raw = headers.get("x-real-ip") if hasattr(headers, "get") else None
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    if "," in text:
        return [part.strip() for part in text.split(",")]
    return [text]


def client_ip_key(request: Request) -> str:
    """Return the IP used for rate-limit buckets.

    - Default: ASGI client host via ``get_remote_address`` (does not read
      ``X-Real-IP``). Note Uvicorn may already have rewritten the peer from
      ``X-Forwarded-For`` when proxy headers are enabled for 127.0.0.1.
    - With TRUST_PROXY_HEADERS: require exactly one ``X-Real-IP`` header that
      ``parse_single_ip`` accepts. Zero, duplicate/conflicting, or malformed
      values fail closed to the ASGI peer.
    """
    if trust_proxy_headers():
        values = x_real_ip_header_values(request.headers)
        if len(values) == 1:
            parsed = parse_single_ip(values[0])
            if parsed is not None:
                return parsed
    return get_remote_address(request)


# headers_enabled=False: SlowAPI otherwise requires a Starlette Response in the handler
# to inject X-RateLimit-* headers; FastAPI + Pydantic JSON responses do not satisfy that.
# Disable in automated tests so suites that register many users are not flaky.
_testing = _env_flag("TESTING", default=False)
limiter = Limiter(key_func=client_ip_key, headers_enabled=False, enabled=not _testing)
