"""ASGI middleware: Cloudflare Access JWT gate for FashionRise ``/api/**``.

When ``CF_ACCESS_JWT_VALIDATION`` is false, this is a no-op.
When true, missing/invalid configuration must already have failed at app startup.

Protects FastAPI application APIs only — not Nginx-served static HTML.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.cloudflare_access import (
    CloudflareAccessError,
    JwksClient,
    extract_and_verify_assertion,
    normalize_request_path,
    path_requires_access_jwt,
)

_log = logging.getLogger(__name__)


class CloudflareAccessJWTMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        team_domain: str,
        audience: str,
        jwks_client: JwksClient | None = None,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.team_domain = team_domain
        self.audience = audience
        self.jwks_client = jwks_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        # Normalize before the gate so /api//v1/... cannot skip /api/ checks.
        path = normalize_request_path(str(scope.get("path") or "/"))
        scope["path"] = path
        if not path_requires_access_jwt(path):
            await self.app(scope, receive, send)
            return

        if self.jwks_client is None:
            _log.error("cf_access_denied code=misconfigured")
            await JSONResponse({"detail": "Access denied"}, status_code=403)(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        try:
            claims = await extract_and_verify_assertion(
                request.headers,
                team_domain=self.team_domain,
                audience=self.audience,
                jwks_client=self.jwks_client,
            )
        except CloudflareAccessError as exc:
            _log.warning("cf_access_denied code=%s", exc.code)
            await JSONResponse({"detail": "Access denied"}, status_code=403)(scope, receive, send)
            return

        scope.setdefault("state", {})
        # Marker only — never store email/raw token; Access identity ≠ app user.
        scope["state"]["cf_access_ok"] = True
        scope["state"]["cf_access_sub"] = claims.subject
        await self.app(scope, receive, send)


__all__ = ["CloudflareAccessJWTMiddleware"]
