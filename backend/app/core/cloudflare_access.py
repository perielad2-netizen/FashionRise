"""Cloudflare Access JWT verification for FashionRise API origin protection.

Default **disabled**. When enabled, validates ``Cf-Access-Jwt-Assertion`` using
RS256 + remote JWKS (``python-jose[cryptography]``). Does **not** replace
FashionRise application JWTs or auto-provision users.

Coverage: FastAPI ``/api/**`` only — Nginx static HTML remains edge Access + AOP.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from jose import JWTError, jwk, jwt
from jose.exceptions import JOSEError

_log = logging.getLogger(__name__)

_HEADER_NAME = "cf-access-jwt-assertion"
_ALLOWED_ALG = "RS256"
_CLOCK_SKEW_SECONDS = 60
_JWKS_TTL_SECONDS = 300.0
_JWKS_TIMEOUT_SECONDS = 5.0
_JWKS_MAX_BYTES = 65_536
_JWKS_MAX_KEYS = 32
_UNKNOWN_KID_REFRESH_MIN_INTERVAL = 10.0
_UNKNOWN_KID_NEGATIVE_TTL = 30.0

# Compact JWS: three base64url segments (Access JWTs never contain commas/spaces).
_JWT_SHAPE_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

# https://<team>.cloudflareaccess.com  (no path/query/fragment, no trailing slash)
_TEAM_DOMAIN_RE = re.compile(
    r"^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?\.cloudflareaccess\.com$",
    re.IGNORECASE,
)


class CloudflareAccessError(Exception):
    """Validation failed. ``code`` is safe for logs; never attach raw tokens."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def normalize_request_path(path: str) -> str:
    """Normalize ASGI path to close simple ``/api//v1`` bypass gaps."""
    raw = unquote(path or "")
    if not raw.startswith("/"):
        raw = "/" + raw
    while "//" in raw:
        raw = raw.replace("//", "/")
    if len(raw) > 1 and raw.endswith("/"):
        raw = raw.rstrip("/")
    return raw or "/"


def path_requires_access_jwt(path: str) -> bool:
    """True for API routes only (not ``/health``, not static mounts)."""
    p = normalize_request_path(path)
    if p == "/health":
        return False
    return p == "/api" or p.startswith("/api/")


def validate_team_domain(team_domain: str) -> str:
    """Return canonical team domain or raise CloudflareAccessError."""
    raw = (team_domain or "").strip().rstrip("/")
    if not raw or not _TEAM_DOMAIN_RE.match(raw):
        raise CloudflareAccessError("bad_team_domain")
    parsed = urlparse(raw)
    host = parsed.hostname
    if not host:
        raise CloudflareAccessError("bad_team_domain")
    return f"https://{host.lower()}"


def jwks_url_for_team(team_domain: str) -> str:
    return f"{validate_team_domain(team_domain)}/cdn-cgi/access/certs"


def raw_assertion_header_values(headers: Any) -> list[str]:
    """Return every Cf-Access-Jwt-Assertion field value, including empties.

    Empty duplicates must be visible to callers so they can reject ambiguity.
    """
    getlist = getattr(headers, "getlist", None)
    if callable(getlist):
        return [str(v) for v in getlist(_HEADER_NAME)]
    if hasattr(headers, "get"):
        raw = headers.get(_HEADER_NAME)
        if raw is None:
            raw = headers.get("Cf-Access-Jwt-Assertion")
        if raw is None:
            return []
        return [str(raw)]
    return []


def extract_assertion_token(headers: Any) -> str:
    """Return exactly one well-formed assertion token or raise.

    Rejects: missing, any duplicate field (including empty), any comma (including
    leading/trailing), whitespace padding, and non-JWS shapes.
    """
    values = raw_assertion_header_values(headers)
    if not values:
        raise CloudflareAccessError("missing")
    if len(values) != 1:
        raise CloudflareAccessError("ambiguous_header")

    token = values[0]
    if token == "" or token.strip() == "":
        raise CloudflareAccessError("missing")
    if token != token.strip():
        raise CloudflareAccessError("malformed")
    if "," in token:
        raise CloudflareAccessError("ambiguous_header")
    if not _JWT_SHAPE_RE.match(token):
        raise CloudflareAccessError("malformed")
    return token


@dataclass
class AccessClaims:
    """Minimal verified claims — never log email/sub in INFO."""

    subject: str | None
    email: str | None
    audience: str
    issuer: str


class JwksClient:
    """Async JWKS fetch with TTL cache, single-flight refresh, and unknown-kid throttle."""

    def __init__(
        self,
        *,
        jwks_url: str,
        ttl_seconds: float = _JWKS_TTL_SECONDS,
        timeout_seconds: float = _JWKS_TIMEOUT_SECONDS,
        max_bytes: int = _JWKS_MAX_BYTES,
        max_keys: int = _JWKS_MAX_KEYS,
        unknown_kid_refresh_min_interval: float = _UNKNOWN_KID_REFRESH_MIN_INTERVAL,
        unknown_kid_negative_ttl: float = _UNKNOWN_KID_NEGATIVE_TTL,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._max_keys = max_keys
        self._force_min_interval = unknown_kid_refresh_min_interval
        self._negative_ttl = unknown_kid_negative_ttl
        self._transport = transport
        self._lock = asyncio.Lock()
        self._fetched_at = 0.0
        self._last_force_refresh_at = 0.0
        self._keys: dict[str, Any] = {}
        self._negative_kids: dict[str, float] = {}
        self._fetch_count = 0  # test/observability aid (not logged with secrets)

    @property
    def fetch_count(self) -> int:
        return self._fetch_count

    def clear(self) -> None:
        self._keys.clear()
        self._fetched_at = 0.0
        self._last_force_refresh_at = 0.0
        self._negative_kids.clear()

    async def get_key(self, kid: str | None) -> Any:
        if not kid or not str(kid).strip():
            raise CloudflareAccessError("missing_kid")
        kid_s = str(kid)

        async with self._lock:
            now = time.monotonic()
            neg_until = self._negative_kids.get(kid_s)
            if neg_until is not None and now < neg_until:
                raise CloudflareAccessError("unknown_kid")

            await self._ensure_fresh_unlocked(force=False)
            key = self._keys.get(kid_s)
            if key is not None:
                return key

            # Unknown kid: allow at most one force refresh per throttle window.
            if (
                self._keys
                and (now - self._last_force_refresh_at) < self._force_min_interval
            ):
                self._negative_kids[kid_s] = now + self._negative_ttl
                raise CloudflareAccessError("unknown_kid")

            await self._ensure_fresh_unlocked(force=True)
            self._last_force_refresh_at = time.monotonic()
            key = self._keys.get(kid_s)
            if key is None:
                self._negative_kids[kid_s] = time.monotonic() + self._negative_ttl
                raise CloudflareAccessError("unknown_kid")
            self._negative_kids.pop(kid_s, None)
            return key

    async def _ensure_fresh_unlocked(self, *, force: bool) -> None:
        now = time.monotonic()
        if not force and self._keys and (now - self._fetched_at) < self._ttl:
            return
        try:
            await self._fetch_unlocked()
        except CloudflareAccessError:
            # Keep serving known kids from a warm cache during JWKS outages.
            if self._keys and not force:
                _log.warning("cf_access_jwks_fetch_failed code=jwks_stale_cache")
                return
            raise

    async def _fetch_unlocked(self) -> None:
        self._fetch_count += 1
        try:
            payload = await self._http_get_jwks()
            keys_out = _parse_jwks_payload(payload, max_keys=self._max_keys)
        except CloudflareAccessError as exc:
            _log.warning("cf_access_jwks_fetch_failed code=%s", exc.code)
            raise
        except (httpx.HTTPError, TimeoutError, OSError, ValueError, TypeError):
            _log.warning("cf_access_jwks_fetch_failed code=jwks_http")
            raise CloudflareAccessError("jwks_http") from None

        if not keys_out:
            raise CloudflareAccessError("jwks_empty")
        self._keys = keys_out
        self._fetched_at = time.monotonic()

    async def _http_get_jwks(self) -> Any:
        timeout = httpx.Timeout(self._timeout)
        transport = _coerce_async_transport(self._transport)
        async with (
            httpx.AsyncClient(timeout=timeout, transport=transport) as client,
            client.stream("GET", self._jwks_url) as resp,
        ):
            if resp.status_code >= 400:
                raise CloudflareAccessError("jwks_http")
            body = await _read_bounded(resp, self._max_bytes)
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudflareAccessError("jwks_malformed") from exc


def _coerce_async_transport(
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None,
) -> httpx.AsyncBaseTransport | None:
    if transport is None:
        return None
    if isinstance(transport, httpx.AsyncBaseTransport):
        return transport
    return _SyncTransportAdapter(transport)


class _SyncTransportAdapter(httpx.AsyncBaseTransport):
    """Allow tests to inject ``httpx.MockTransport`` without blocking the loop forever."""

    def __init__(self, sync_transport: httpx.BaseTransport) -> None:
        self._sync = sync_transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await asyncio.to_thread(self._sync.handle_request, request)


async def _read_bounded(resp: httpx.Response, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise CloudflareAccessError("jwks_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_jwks_payload(payload: Any, *, max_keys: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CloudflareAccessError("jwks_malformed")
    keys = payload.get("keys")
    if keys is None:
        raise CloudflareAccessError("jwks_empty")
    if not isinstance(keys, list):
        raise CloudflareAccessError("jwks_malformed")
    if len(keys) > max_keys:
        raise CloudflareAccessError("jwks_too_many_keys")

    keys_out: dict[str, Any] = {}
    for item in keys:
        if not isinstance(item, dict):
            continue
        kid = item.get("kid")
        if not kid or item.get("kty") != "RSA":
            continue
        try:
            keys_out[str(kid)] = jwk.construct(item, algorithm=_ALLOWED_ALG)
        except (JOSEError, ValueError, TypeError):
            continue
    return keys_out


def _unverified_header(token: str) -> dict[str, Any]:
    try:
        return jwt.get_unverified_header(token)
    except JWTError as exc:
        raise CloudflareAccessError("malformed") from exc


async def verify_access_token(
    token: str,
    *,
    team_domain: str,
    audience: str,
    jwks_client: JwksClient,
) -> AccessClaims:
    """Verify Access JWT. Never log ``token``."""
    issuer = validate_team_domain(team_domain)
    aud = (audience or "").strip()
    if not aud:
        raise CloudflareAccessError("bad_aud_config")

    header = _unverified_header(token)
    alg = header.get("alg")
    if alg != _ALLOWED_ALG:
        raise CloudflareAccessError("bad_alg")
    key = await jwks_client.get_key(header.get("kid"))

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[_ALLOWED_ALG],
            audience=aud,
            issuer=issuer,
            options={
                "require_exp": True,
                "require_aud": True,
                "require_iss": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
                "leeway": _CLOCK_SKEW_SECONDS,
            },
        )
    except JWTError:
        raise CloudflareAccessError("invalid_token") from None

    if not isinstance(claims, dict):
        raise CloudflareAccessError("invalid_token")

    claim_iss = claims.get("iss")
    if claim_iss != issuer:
        raise CloudflareAccessError("bad_iss")

    claim_aud = claims.get("aud")
    if isinstance(claim_aud, list):
        if aud not in claim_aud:
            raise CloudflareAccessError("bad_aud")
    elif claim_aud != aud:
        raise CloudflareAccessError("bad_aud")

    return AccessClaims(
        subject=str(claims["sub"]) if claims.get("sub") is not None else None,
        email=str(claims["email"]) if claims.get("email") is not None else None,
        audience=aud,
        issuer=issuer,
    )


async def extract_and_verify_assertion(
    headers: Any,
    *,
    team_domain: str,
    audience: str,
    jwks_client: JwksClient,
) -> AccessClaims:
    """Fail closed on missing/duplicate/malformed assertion (header-only; no cookie)."""
    token = extract_assertion_token(headers)
    return await verify_access_token(
        token,
        team_domain=team_domain,
        audience=audience,
        jwks_client=jwks_client,
    )
