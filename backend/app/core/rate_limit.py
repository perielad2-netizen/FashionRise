"""Shared SlowAPI limiter (per-client IP; respects X-Forwarded-For when present)."""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_ip_key(request: Request) -> str:
    """Prefer first hop in X-Forwarded-For (typical behind Nginx); fall back to direct client."""
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip() or get_remote_address(request)
    return get_remote_address(request)


# headers_enabled=False: SlowAPI otherwise requires a Starlette Response in the handler
# to inject X-RateLimit-* headers; FastAPI + Pydantic JSON responses do not satisfy that.
# Disable in automated tests so suites that register many users are not flaky.
_testing = (os.environ.get("TESTING") or "").strip().lower() in {"1", "true", "yes"}
limiter = Limiter(key_func=client_ip_key, headers_enabled=False, enabled=not _testing)
