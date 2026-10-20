"""Cloudflare Access JWT verification for FashionRise API origin protection.

Default **disabled**. When enabled, validates ``Cf-Access-Jwt-Assertion`` using
RS256 + remote JWKS (``python-jose[cryptography]``). Does **not** replace
FashionRise application JWTs or auto-provision users.

Coverage: FastAPI ``/api/**`` only — Nginx static HTML remains edge Access + AOP.
"""

from __future__ import annotations

import logging
import re
import threading
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
    # Canonicalize host case for issuer matching.
    parsed = urlparse(raw)
    return f"https://{parsed.hostname.lower()}"


def jwks_url_for_team(team_domain: str) -> str:
    return f"{validate_team_domain(team_domain)}/cdn-cgi/access/certs"


def assertion_header_values(headers: Any) -> list[str]:
    """Return every Cf-Access-Jwt-Assertion field (Starlette getlist-aware).

    Comma-joined single fields are expanded so callers can reject ambiguity.
    Access JWTs are base64url (no commas); a comma always means multiple values.
    """
    values: list[str] = []
    getlist = getattr(headers, "getlist", None)
    if callable(getlist):
        values = [str(v).strip() for v in getlist(_HEADER_NAME) if str(v).strip()]
    else:
        raw = None
        if hasattr(headers, "get"):
            raw = headers.get(_HEADER_NAME)
            if raw is None:
                raw = headers.get("Cf-Access-Jwt-Assertion")
        if raw is not None and str(raw).strip():
            values = [str(raw).strip()]

    expanded: list[str] = []
    for item in values:
        if "," in item:
            expanded.extend(p.strip() for p in item.split(",") if p.strip())
        else:
            expanded.append(item)
    return expanded


@dataclass
class AccessClaims:
    """Minimal verified claims — never log email/sub in INFO."""

    subject: str | None
    email: str | None
    audience: str
    issuer: str


class JwksClient:
    """Thread-safe JWKS fetch with TTL cache and unknown-kid refresh."""

    def __init__(
        self,
        *,
        jwks_url: str,
        ttl_seconds: float = _JWKS_TTL_SECONDS,
        timeout_seconds: float = _JWKS_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._timeout = timeout_seconds
        self._transport = transport
        self._lock = threading.Lock()
        self._fetched_at = 0.0
        self._keys: dict[str, Any] = {}

    def clear(self) -> None:
        with self._lock:
            self._keys.clear()
            self._fetched_at = 0.0

    def get_key(self, kid: str | None) -> Any:
        if not kid:
            raise CloudflareAccessError("missing_kid")
        with self._lock:
            self._ensure_fresh_unlocked(force=False)
            key = self._keys.get(kid)
            if key is not None:
                return key
            # Unknown kid — force refresh once (rotation window).
            self._ensure_fresh_unlocked(force=True)
            key = self._keys.get(kid)
            if key is None:
                raise CloudflareAccessError("unknown_kid")
            return key

    def _ensure_fresh_unlocked(self, *, force: bool) -> None:
        now = time.monotonic()
        if not force and self._keys and (now - self._fetched_at) < self._ttl:
            return
        self._fetch_unlocked()

    def _fetch_unlocked(self) -> None:
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                resp = client.get(self._jwks_url)
                resp.raise_for_status()
                payload = resp.json()
        except Exception:
            _log.warning("cf_access_jwks_fetch_failed code=jwks_http")
            raise CloudflareAccessError("jwks_http") from None

        keys_out: dict[str, Any] = {}
        for item in payload.get("keys") or []:
            if not isinstance(item, dict):
                continue
            kid = item.get("kid")
            if not kid or item.get("kty") != "RSA":
                continue
            try:
                keys_out[str(kid)] = jwk.construct(item, algorithm=_ALLOWED_ALG)
            except (JOSEError, ValueError, TypeError):
                continue
        if not keys_out:
            raise CloudflareAccessError("jwks_empty")
        self._keys = keys_out
        self._fetched_at = time.monotonic()


def _unverified_header(token: str) -> dict[str, Any]:
    try:
        return jwt.get_unverified_header(token)
    except JWTError as exc:
        raise CloudflareAccessError("malformed") from exc


def verify_access_token(
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
    key = jwks_client.get_key(header.get("kid"))

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


def extract_and_verify_assertion(
    headers: Any,
    *,
    team_domain: str,
    audience: str,
    jwks_client: JwksClient,
) -> AccessClaims:
    """Fail closed on missing/duplicate assertion headers (header-only; no cookie)."""
    values = assertion_header_values(headers)
    if not values:
        raise CloudflareAccessError("missing")
    if len(values) != 1:
        raise CloudflareAccessError("ambiguous_header")
    return verify_access_token(
        values[0],
        team_domain=team_domain,
        audience=audience,
        jwks_client=jwks_client,
    )
