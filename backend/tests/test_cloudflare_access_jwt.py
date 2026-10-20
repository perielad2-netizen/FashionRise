"""Cloudflare Access JWT origin gate — synthetic RSA keys + mocked JWKS. No network."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from starlette.datastructures import Headers

from app.core import cloudflare_access as cf
from app.core.cloudflare_access_middleware import CloudflareAccessJWTMiddleware
from app.core.config import get_settings
from app.main import create_app

TEAM = "https://test-team.cloudflareaccess.com"
AUD = "fashionrise-test-aud-tag"


def _b64u_int(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


@pytest.fixture()
def rsa_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    numbers = private_key.public_key().public_numbers()
    jwk_dict = {
        "kty": "RSA",
        "kid": "kid-primary",
        "use": "sig",
        "alg": "RS256",
        "n": _b64u_int(numbers.n),
        "e": _b64u_int(numbers.e),
    }
    return {"priv_pem": priv_pem, "jwk": jwk_dict, "private_key": private_key}


def _mint(
    rsa_material: dict[str, Any],
    *,
    kid: str = "kid-primary",
    aud: str = AUD,
    iss: str = TEAM,
    exp_delta: int = 3600,
    nbf_delta: int | None = None,
    alg: str = "RS256",
    extra: dict[str, Any] | None = None,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "cf-user-1",
        "email": "access-user@example.test",
        "iss": iss,
        "aud": aud,
        "exp": now + exp_delta,
        "iat": now - 5,
    }
    if nbf_delta is not None:
        claims["nbf"] = now + nbf_delta
    if extra:
        claims.update(extra)
    return jwt.encode(
        claims,
        rsa_material["priv_pem"],
        algorithm=alg,
        headers={"kid": kid, "alg": alg},
    )


def _mock_transport(jwks_payload: Any, *, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(jwks_payload, (bytes, str)):
            content = jwks_payload if isinstance(jwks_payload, bytes) else jwks_payload.encode()
            return httpx.Response(status, content=content)
        return httpx.Response(status, json=jwks_payload)

    return httpx.MockTransport(handler)


def _jwks_client(rsa_material: dict[str, Any], **kwargs: Any) -> cf.JwksClient:
    payload = {"keys": [rsa_material["jwk"]]}
    return cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=_mock_transport(payload),
        **kwargs,
    )


def _api_app(jwks_client: cf.JwksClient | None, *, enabled: bool = True) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/auth/login")
    def login() -> dict[str, str]:
        return {"ok": "login"}

    @app.get("/api/v1/designs")
    def designs() -> dict[str, str]:
        return {"ok": "designs"}

    @app.get("/api/v1")
    def api_root() -> dict[str, str]:
        return {"ok": "api"}

    app.add_middleware(
        CloudflareAccessJWTMiddleware,
        enabled=enabled,
        team_domain=TEAM,
        audience=AUD,
        jwks_client=jwks_client,
    )
    return app


# --- path / config helpers ---


def test_normalize_and_path_gate():
    assert cf.normalize_request_path("/api//v1/auth/login") == "/api/v1/auth/login"
    assert cf.normalize_request_path("/api/v1/auth/login/") == "/api/v1/auth/login"
    assert cf.normalize_request_path("/api%2Fv1/auth/login") == "/api/v1/auth/login"
    assert cf.path_requires_access_jwt("/api/v1/auth/login") is True
    assert cf.path_requires_access_jwt("/api") is True
    assert cf.path_requires_access_jwt("/api/v1") is True
    assert cf.path_requires_access_jwt("/api//v1/designs") is True
    assert cf.path_requires_access_jwt("/health") is False
    assert cf.path_requires_access_jwt("/ready") is False
    assert cf.path_requires_access_jwt("/index.html") is False
    assert cf.path_requires_access_jwt("/sw.js") is False
    assert cf.path_requires_access_jwt("/assets/index.js") is False


def test_team_domain_validation():
    assert cf.validate_team_domain("https://Black-Flower-30bb.cloudflareaccess.com/") == (
        "https://black-flower-30bb.cloudflareaccess.com"
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.validate_team_domain("https://evil.example.com")
    assert exc.value.code == "bad_team_domain"


# --- Task A: assertion header hardening (real Starlette Headers) ---


def test_missing_assertion_header():
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(Headers({}))
    assert exc.value.code == "missing"


def test_duplicate_identical_headers_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers(
        raw=[
            (b"cf-access-jwt-assertion", token.encode()),
            (b"cf-access-jwt-assertion", token.encode()),
        ]
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_empty_duplicate_before_valid_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers(
        raw=[
            (b"cf-access-jwt-assertion", b""),
            (b"cf-access-jwt-assertion", token.encode()),
        ]
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_valid_then_empty_duplicate_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers(
        raw=[
            (b"cf-access-jwt-assertion", token.encode()),
            (b"cf-access-jwt-assertion", b""),
        ]
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_trailing_comma_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers({"cf-access-jwt-assertion": f"{token},"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_leading_comma_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers({"cf-access-jwt-assertion": f",{token}"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_empty_comma_sequence_rejected():
    headers = Headers({"cf-access-jwt-assertion": ","})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_comma_joined_two_tokens_rejected(rsa_material):
    token_a = _mint(rsa_material)
    token_b = _mint(rsa_material, extra={"sub": "other"})
    headers = Headers({"cf-access-jwt-assertion": f"{token_a},{token_b}"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "ambiguous_header"


def test_whitespace_padded_token_rejected(rsa_material):
    token = _mint(rsa_material)
    headers = Headers({"cf-access-jwt-assertion": f" {token} "})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "malformed"


def test_malformed_jwt_shape_rejected():
    headers = Headers({"cf-access-jwt-assertion": "not-a-jwt"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "malformed"


def test_cookie_not_accepted_as_assertion(rsa_material):
    token = _mint(rsa_material)
    headers = Headers({"cookie": f"CF_Authorization={token}"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_assertion_token(headers)
    assert exc.value.code == "missing"


# --- token verification ---


@pytest.mark.asyncio
async def test_valid_assertion(rsa_material):
    token = _mint(rsa_material)
    claims = await cf.verify_access_token(
        token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
    )
    assert claims.subject == "cf-user-1"
    assert claims.email == "access-user@example.test"


@pytest.mark.asyncio
async def test_wrong_audience(rsa_material):
    token = _mint(rsa_material, aud="other-app")
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_wrong_issuer(rsa_material):
    token = _mint(rsa_material, iss="https://other-team.cloudflareaccess.com")
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_expired_token(rsa_material):
    token = _mint(rsa_material, exp_delta=-120)
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_nbf_in_future_rejected(rsa_material):
    token = _mint(rsa_material, nbf_delta=3600)
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_forged_signature_rejected(rsa_material):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    token = jwt.encode(
        {"sub": "x", "iss": TEAM, "aud": AUD, "exp": now + 3600},
        other_pem,
        algorithm="RS256",
        headers={"kid": "kid-primary"},
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_alg_confusion_rejected(rsa_material):
    token = jwt.encode(
        {"sub": "x", "iss": TEAM, "aud": AUD, "exp": int(time.time()) + 3600},
        "not-a-real-hmac-secret-for-tests",
        algorithm="HS256",
        headers={"kid": "kid-primary", "alg": "HS256"},
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "bad_alg"


# --- Task B: JWKS reliability ---


@pytest.mark.asyncio
async def test_unknown_kid_refresh_then_ok(rsa_material):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_numbers = other.public_key().public_numbers()
    stale_jwk = {
        "kty": "RSA",
        "kid": "kid-stale",
        "use": "sig",
        "alg": "RS256",
        "n": _b64u_int(other_numbers.n),
        "e": _b64u_int(other_numbers.e),
    }
    rotated = dict(rsa_material["jwk"])
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"keys": [stale_jwk]})
        return httpx.Response(200, json={"keys": [stale_jwk, rotated]})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        ttl_seconds=300,
        unknown_kid_refresh_min_interval=0.0,
    )
    token = _mint(rsa_material)
    claims = await cf.verify_access_token(
        token, team_domain=TEAM, audience=AUD, jwks_client=client
    )
    assert claims.subject == "cf-user-1"
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_unknown_kid_throttled_no_fetch_storm(rsa_material):
    """Repeated unknown kids must not trigger unbounded JWKS fetches."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"keys": [rsa_material["jwk"]]})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        ttl_seconds=300,
        unknown_kid_refresh_min_interval=60.0,
        unknown_kid_negative_ttl=60.0,
    )
    # Warm cache with a valid token first.
    await cf.verify_access_token(
        _mint(rsa_material),
        team_domain=TEAM,
        audience=AUD,
        jwks_client=client,
    )
    warm_fetches = calls["n"]
    assert warm_fetches == 1

    bad = _mint(rsa_material, kid="kid-never-exists")
    for _ in range(20):
        with pytest.raises(cf.CloudflareAccessError) as exc:
            await cf.verify_access_token(
                bad, team_domain=TEAM, audience=AUD, jwks_client=client
            )
        assert exc.value.code == "unknown_kid"
    # One force refresh after warm, then negative cache / throttle — not 20+.
    assert calls["n"] <= warm_fetches + 1


@pytest.mark.asyncio
async def test_jwks_http_failure(rsa_material):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "nope"})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            _mint(rsa_material), team_domain=TEAM, audience=AUD, jwks_client=client
        )
    assert exc.value.code == "jwks_http"


@pytest.mark.asyncio
async def test_jwks_malformed_json_array(rsa_material):
    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=_mock_transport(["not", "a", "dict"]),
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            _mint(rsa_material), team_domain=TEAM, audience=AUD, jwks_client=client
        )
    assert exc.value.code in {"jwks_malformed", "jwks_http"}


@pytest.mark.asyncio
async def test_jwks_keys_wrong_type(rsa_material):
    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=_mock_transport({"keys": "nope"}),
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            _mint(rsa_material), team_domain=TEAM, audience=AUD, jwks_client=client
        )
    assert exc.value.code in {"jwks_malformed", "jwks_http"}


@pytest.mark.asyncio
async def test_jwks_too_large(rsa_material):
    huge = b'{"keys":[]}' + (b" " * 70_000)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=huge)

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        max_bytes=1024,
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            _mint(rsa_material), team_domain=TEAM, audience=AUD, jwks_client=client
        )
    assert exc.value.code in {"jwks_too_large", "jwks_http"}


@pytest.mark.asyncio
async def test_jwks_too_many_keys(rsa_material):
    keys = []
    for i in range(40):
        item = dict(rsa_material["jwk"])
        item["kid"] = f"k{i}"
        keys.append(item)
    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=_mock_transport({"keys": keys}),
        max_keys=8,
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        await cf.verify_access_token(
            _mint(rsa_material), team_domain=TEAM, audience=AUD, jwks_client=client
        )
    assert exc.value.code in {"jwks_too_many_keys", "jwks_http"}


@pytest.mark.asyncio
async def test_jwks_cache_ttl_avoids_refetch(rsa_material):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"keys": [rsa_material["jwk"]]})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        ttl_seconds=300,
    )
    token = _mint(rsa_material)
    await cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    await cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_stale_cache_serves_known_kid_during_outage(rsa_material):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"keys": [rsa_material["jwk"]]})
        return httpx.Response(503, json={"error": "down"})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        ttl_seconds=0.01,
    )
    token = _mint(rsa_material)
    await cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    await asyncio.sleep(0.02)
    claims = await cf.verify_access_token(
        token, team_domain=TEAM, audience=AUD, jwks_client=client
    )
    assert claims.subject == "cf-user-1"
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_concurrent_valid_requests_single_flight(rsa_material):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"keys": [rsa_material["jwk"]]})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
        ttl_seconds=300,
    )
    token = _mint(rsa_material)

    async def one() -> str:
        claims = await cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=client
        )
        return claims.subject or ""

    results = await asyncio.gather(*[one() for _ in range(12)])
    assert results == ["cf-user-1"] * 12
    # Lock serializes refresh; warm cache means one fetch for the burst.
    assert calls["n"] == 1


# --- middleware ASGI ---


def test_middleware_allows_health_without_token(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    r = client.get("/health")
    assert r.status_code == 200


def test_middleware_blocks_api_without_token(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    r = client.get("/api/v1/auth/login")
    assert r.status_code == 403
    assert r.json() == {"detail": "Access denied"}


def test_middleware_allows_valid_api(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    r = client.get(
        "/api/v1/designs",
        headers={"Cf-Access-Jwt-Assertion": _mint(rsa_material)},
    )
    assert r.status_code == 200
    assert r.json()["ok"] == "designs"


def test_middleware_blocks_path_normalization_bypass(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    r = client.get("/api//v1/auth/login")
    assert r.status_code == 403


def test_middleware_blocks_bare_api_prefix(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    assert client.get("/api").status_code == 403
    assert client.get("/api/v1").status_code == 403


def test_middleware_disabled_is_noop(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material), enabled=False))
    r = client.get("/api/v1/auth/login")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_middleware_rejects_duplicate_headers(rsa_material):
    token = _mint(rsa_material)
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    # httpx may coalesce; drive ASGI scope with raw duplicates via Starlette TestClient
    # by using a request that sets headers list through the ASGI interface.
    from starlette.requests import Request

    app = _api_app(_jwks_client(rsa_material))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "headers": [
            (b"cf-access-jwt-assertion", token.encode()),
            (b"cf-access-jwt-assertion", token.encode()),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
    }
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    assert start["status"] == 403
    del Request, client


def test_middleware_does_not_log_raw_token(rsa_material, caplog):
    import logging

    token = _mint(rsa_material)
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    with caplog.at_level(logging.WARNING):
        client.get("/api/v1/auth/login", headers={"Cf-Access-Jwt-Assertion": "aaa.bbb.ccc"})
    joined = " ".join(r.message for r in caplog.records)
    assert "aaa.bbb.ccc" not in joined
    assert token not in joined
    assert "access-user@example.test" not in joined


# --- app factory / settings interaction ---


def test_create_app_default_validation_disabled():
    get_settings.cache_clear()
    app = create_app()
    assert get_settings().cf_access_jwt_validation is False
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        # Default-off: API login reachable without Access JWT (still app-auth gated).
        r2 = client.post("/api/v1/auth/login", json={"email": "x", "password": "y"})
        assert r2.status_code != 403 or "Access denied" not in r2.text


def test_create_app_fails_closed_when_enabled_without_aud(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_JWT_VALIDATION", "true")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="CF_ACCESS_AUD"):
        create_app()
    get_settings.cache_clear()


def test_create_app_fails_closed_when_enabled_with_bad_team(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_JWT_VALIDATION", "true")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "https://evil.example.com")
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="CF_ACCESS_TEAM_DOMAIN"):
        create_app()
    get_settings.cache_clear()


def test_registration_disabled_compatible_with_access_gate(rsa_material, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    get_settings.cache_clear()

    app = FastAPI()

    @app.post("/api/v1/auth/register")
    def register() -> dict[str, str]:
        if not get_settings().registration_enabled:
            raise HTTPException(status_code=403, detail="Registration is disabled")
        return {"ok": "registered"}

    app.add_middleware(
        CloudflareAccessJWTMiddleware,
        enabled=True,
        team_domain=TEAM,
        audience=AUD,
        jwks_client=_jwks_client(rsa_material),
    )
    client = TestClient(app)
    assert client.post("/api/v1/auth/register", json={}).status_code == 403
    r = client.post(
        "/api/v1/auth/register",
        json={},
        headers={"Cf-Access-Jwt-Assertion": _mint(rsa_material)},
    )
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()
    get_settings.cache_clear()


def test_app_jwt_still_required_after_access_ok(rsa_material):
    from app.main import app as full_app

    wrapped = CloudflareAccessJWTMiddleware(
        full_app,
        enabled=True,
        team_domain=TEAM,
        audience=AUD,
        jwks_client=_jwks_client(rsa_material),
    )
    client = TestClient(wrapped)
    r = client.get(
        "/api/v1/auth/me",
        headers={"Cf-Access-Jwt-Assertion": _mint(rsa_material)},
    )
    assert r.status_code == 401
