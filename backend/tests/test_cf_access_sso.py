"""Cloudflare Access seamless login — verified JWT → existing User only."""

from __future__ import annotations

import base64
import time
from typing import Any
import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core import cloudflare_access as cf
from app.core.config import get_settings
from app.services import cf_access_sso
from tests.auth_test_helpers import register_with_invite

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
    return {"priv_pem": priv_pem, "jwk": jwk_dict}


def _mint(rsa_material: dict[str, Any], *, email: str = "sso-owner@example.com") -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": "cf-sub-1",
            "email": email,
            "iss": TEAM,
            "aud": AUD,
            "exp": now + 3600,
            "iat": now - 5,
        },
        rsa_material["priv_pem"],
        algorithm="RS256",
        headers={"kid": "kid-primary", "alg": "RS256"},
    )


def _install_jwks(monkeypatch, rsa_material):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [rsa_material["jwk"]]})

    transport = httpx.MockTransport(handler)
    client = cf.JwksClient(jwks_url=f"{TEAM}/cdn-cgi/access/certs", transport=transport)
    monkeypatch.setattr(cf_access_sso, "_jwks", client)
    return client


def test_cf_access_status_disabled_by_default(client):
    get_settings.cache_clear()
    res = client.get("/api/v1/auth/cf-access/status")
    assert res.status_code == 200
    assert res.json()["sso_enabled"] is False


def test_cf_access_login_maps_verified_email_to_existing_user(
    client, db_session, monkeypatch, rsa_material
):
    monkeypatch.setenv("CF_ACCESS_SSO_LOGIN", "true")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    get_settings.cache_clear()
    cf_access_sso._jwks = None
    _install_jwks(monkeypatch, rsa_material)

    tokens = register_with_invite(client, db_session, "sso-owner@example.com", "sso_owner")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    owner_id = me.json()["id"]

    assertion = _mint(rsa_material, email="sso-owner@example.com")
    login = client.post(
        "/api/v1/auth/cf-access/login",
        headers={"Cf-Access-Jwt-Assertion": assertion},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["access_token"]
    assert body["refresh_token"]
    me2 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me2.status_code == 200
    assert me2.json()["id"] == owner_id
    assert me2.json()["email"].lower() == "sso-owner@example.com"
    get_settings.cache_clear()
    cf_access_sso._jwks = None


def test_cf_access_login_rejects_unknown_email(client, db_session, monkeypatch, rsa_material):
    monkeypatch.setenv("CF_ACCESS_SSO_LOGIN", "true")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    get_settings.cache_clear()
    cf_access_sso._jwks = None
    _install_jwks(monkeypatch, rsa_material)
    assertion = _mint(rsa_material, email="stranger@example.com")
    login = client.post(
        "/api/v1/auth/cf-access/login",
        headers={"Cf-Access-Jwt-Assertion": assertion},
    )
    assert login.status_code == 403
    get_settings.cache_clear()
    cf_access_sso._jwks = None


def test_cf_access_login_rejects_unverified_assertion(client, monkeypatch, rsa_material):
    monkeypatch.setenv("CF_ACCESS_SSO_LOGIN", "true")
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    get_settings.cache_clear()
    cf_access_sso._jwks = None
    _install_jwks(monkeypatch, rsa_material)
    # Wrong audience
    now = int(time.time())
    bad = jwt.encode(
        {
            "sub": "x",
            "email": "sso-owner@example.com",
            "iss": TEAM,
            "aud": "wrong-aud",
            "exp": now + 3600,
            "iat": now - 5,
        },
        rsa_material["priv_pem"],
        algorithm="RS256",
        headers={"kid": "kid-primary", "alg": "RS256"},
    )
    login = client.post(
        "/api/v1/auth/cf-access/login",
        headers={"Cf-Access-Jwt-Assertion": bad},
    )
    assert login.status_code == 401
    get_settings.cache_clear()
    cf_access_sso._jwks = None


def test_cf_access_login_disabled_without_config(client, monkeypatch):
    monkeypatch.setenv("CF_ACCESS_SSO_LOGIN", "false")
    get_settings.cache_clear()
    login = client.post("/api/v1/auth/cf-access/login")
    assert login.status_code in (400, 422, 403)
    get_settings.cache_clear()
