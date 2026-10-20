"""Shared SlowAPI limiter with trustworthy client IP determination.

By default only the direct peer address is used. Client-supplied
``X-Forwarded-For`` is ignored so attackers cannot bypass per-IP limits.

When FashionRise sits behind Nginx that **overwrites** forwarding headers
with the real peer (``proxy_set_header X-Real-IP $remote_addr``), set
``TRUST_PROXY_HEADERS=true`` so the limiter keys on ``X-Real-IP``.
"""

from __future__ import annotations

import os
import re

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

_SINGLE_IP_RE = re.compile(
    r"^(?:"
    r"(?:\d{1,3}\.){3}\d{1,3}"  # IPv4
    r"|"
    r"[0-9a-fA-F:]+"  # coarse IPv6
    r")$"
)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def trust_proxy_headers() -> bool:
    return _env_flag("TRUST_PROXY_HEADERS", default=False)


def client_ip_key(request: Request) -> str:
    """Return the IP used for rate-limit buckets.

    - Default: direct ASGI client host (ignores forged X-Forwarded-For).
    - With TRUST_PROXY_HEADERS: only a single ``X-Real-IP`` value written by a
      trusted reverse proxy. Multi-value / forged XFF chains are ignored.
    """
    if trust_proxy_headers():
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip and _SINGLE_IP_RE.match(real_ip) and "," not in real_ip:
            return real_ip
    return get_remote_address(request)


# headers_enabled=False: SlowAPI otherwise requires a Starlette Response in the handler
# to inject X-RateLimit-* headers; FastAPI + Pydantic JSON responses do not satisfy that.
# Disable in automated tests so suites that register many users are not flaky.
_testing = _env_flag("TESTING", default=False)
limiter = Limiter(key_func=client_ip_key, headers_enabled=False, enabled=not _testing)
