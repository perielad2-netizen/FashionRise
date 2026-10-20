"""Cloudflare Access JWT origin gate — synthetic RSA keys + mocked JWKS. No network."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
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
    headers = {"kid": kid, "alg": alg}
    return jwt.encode(claims, rsa_material["priv_pem"], algorithm=alg, headers=headers)


def _mock_transport(jwks_payload: dict[str, Any], *, status: int = 200, delay: float = 0.0):
    def handler(request: httpx.Request) -> httpx.Response:
        if delay:
            time.sleep(delay)
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

    @app.get("/api//v1/auth/login")
    def weird() -> dict[str, str]:
        return {"ok": "weird"}

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
    assert cf.path_requires_access_jwt("/api/v1/auth/login") is True
    assert cf.path_requires_access_jwt("/api//v1/designs") is True
    assert cf.path_requires_access_jwt("/health") is False
    assert cf.path_requires_access_jwt("/ready") is False
    assert cf.path_requires_access_jwt("/index.html") is False
    assert cf.path_requires_access_jwt("/sw.js") is False


def test_team_domain_validation():
    assert cf.validate_team_domain("https://Black-Flower-30bb.cloudflareaccess.com/") == (
        "https://black-flower-30bb.cloudflareaccess.com"
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.validate_team_domain("https://evil.example.com")
    assert exc.value.code == "bad_team_domain"
    with pytest.raises(cf.CloudflareAccessError):
        cf.validate_team_domain("https://team.cloudflareaccess.com/cdn-cgi/access/certs")


# --- token verification ---


def test_valid_assertion(rsa_material):
    token = _mint(rsa_material)
    claims = cf.verify_access_token(
        token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
    )
    assert claims.subject == "cf-user-1"
    assert claims.email == "access-user@example.test"


def test_missing_assertion_header(rsa_material):
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_and_verify_assertion(
            Headers({}),
            team_domain=TEAM,
            audience=AUD,
            jwks_client=_jwks_client(rsa_material),
        )
    assert exc.value.code == "missing"


def test_duplicate_assertion_headers_rejected(rsa_material):
    headers = Headers(
        raw=[
            (b"cf-access-jwt-assertion", b"one"),
            (b"cf-access-jwt-assertion", b"two"),
        ]
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_and_verify_assertion(
            headers,
            team_domain=TEAM,
            audience=AUD,
            jwks_client=_jwks_client(rsa_material),
        )
    assert exc.value.code == "ambiguous_header"


def test_comma_joined_assertion_rejected(rsa_material):
    token_a = _mint(rsa_material)
    token_b = _mint(rsa_material, extra={"sub": "other"})
    headers = Headers({"cf-access-jwt-assertion": f"{token_a},{token_b}"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_and_verify_assertion(
            headers,
            team_domain=TEAM,
            audience=AUD,
            jwks_client=_jwks_client(rsa_material),
        )
    assert exc.value.code == "ambiguous_header"


def test_wrong_audience(rsa_material):
    token = _mint(rsa_material, aud="other-app")
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


def test_wrong_issuer(rsa_material):
    token = _mint(rsa_material, iss="https://other-team.cloudflareaccess.com")
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


def test_expired_token(rsa_material):
    token = _mint(rsa_material, exp_delta=-120)
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


def test_nbf_in_future_rejected(rsa_material):
    token = _mint(rsa_material, nbf_delta=3600)
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


def test_forged_signature_rejected(rsa_material):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "x",
            "iss": TEAM,
            "aud": AUD,
            "exp": now + 3600,
        },
        other_pem,
        algorithm="RS256",
        headers={"kid": "kid-primary"},
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "invalid_token"


def test_alg_confusion_rejected(rsa_material):
    # HS256 header with RSA key material must not verify as Access JWT.
    token = jwt.encode(
        {"sub": "x", "iss": TEAM, "aud": AUD, "exp": int(time.time()) + 3600},
        "not-a-real-hmac-secret-for-tests",
        algorithm="HS256",
        headers={"kid": "kid-primary", "alg": "HS256"},
    )
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            token, team_domain=TEAM, audience=AUD, jwks_client=_jwks_client(rsa_material)
        )
    assert exc.value.code == "bad_alg"


def test_malformed_token(rsa_material):
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(
            "not.a.jwt",
            team_domain=TEAM,
            audience=AUD,
            jwks_client=_jwks_client(rsa_material),
        )
    assert exc.value.code == "malformed"


def test_unknown_kid_refresh_then_ok(rsa_material):
    """First JWKS lacks target kid; forced refresh returns rotated key."""
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
    )
    token = _mint(rsa_material)
    claims = cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    assert claims.subject == "cf-user-1"
    assert calls["n"] >= 2


def test_jwks_http_failure(rsa_material):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "nope"})

    client = cf.JwksClient(
        jwks_url=f"{TEAM}/cdn-cgi/access/certs",
        transport=httpx.MockTransport(handler),
    )
    token = _mint(rsa_material)
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    assert exc.value.code == "jwks_http"


def test_jwks_cache_ttl_avoids_refetch(rsa_material):
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
    cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    cf.verify_access_token(token, team_domain=TEAM, audience=AUD, jwks_client=client)
    assert calls["n"] == 1


def test_cookie_not_accepted_as_assertion(rsa_material):
    """Header-only policy: CF_Authorization cookie alone is insufficient."""
    token = _mint(rsa_material)
    headers = Headers({"cookie": f"CF_Authorization={token}"})
    with pytest.raises(cf.CloudflareAccessError) as exc:
        cf.extract_and_verify_assertion(
            headers,
            team_domain=TEAM,
            audience=AUD,
            jwks_client=_jwks_client(rsa_material),
        )
    assert exc.value.code == "missing"


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


def test_middleware_disabled_is_noop(rsa_material):
    client = TestClient(_api_app(_jwks_client(rsa_material), enabled=False))
    r = client.get("/api/v1/auth/login")
    assert r.status_code == 200


def test_middleware_does_not_log_raw_token(rsa_material, caplog):
    import logging

    token = _mint(rsa_material)
    client = TestClient(_api_app(_jwks_client(rsa_material)))
    with caplog.at_level(logging.WARNING):
        client.get("/api/v1/auth/login", headers={"Cf-Access-Jwt-Assertion": "forged.token.value"})
    joined = " ".join(r.message for r in caplog.records)
    assert "forged.token.value" not in joined
    assert token not in joined
    assert "access-user@example.test" not in joined


# --- app factory / settings interaction ---


def test_create_app_default_validation_disabled():
    get_settings.cache_clear()
    app = create_app()
    assert get_settings().cf_access_jwt_validation is False
    # Middleware not installed when disabled — /api reachable without Access JWT
    # (still needs app auth for protected routes).
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200


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
    """Access JWT gate does not enable registration; register stays closed by app flag."""
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    get_settings.cache_clear()

    from fastapi import HTTPException

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
    # Missing Access JWT
    assert client.post("/api/v1/auth/register", json={}).status_code == 403
    # Valid Access JWT, registration still disabled
    r = client.post(
        "/api/v1/auth/register",
        json={},
        headers={"Cf-Access-Jwt-Assertion": _mint(rsa_material)},
    )
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()
    get_settings.cache_clear()


def test_app_jwt_still_required_after_access_ok(rsa_material):
    """Valid Access JWT does not satisfy FashionRise Bearer auth on real /auth/me."""
    from app.main import app as full_app

    # Install Access middleware outermost on the real app for this request only.
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
    # Missing app Bearer → 401 from existing auth, not Access success alone.
    assert r.status_code == 401
