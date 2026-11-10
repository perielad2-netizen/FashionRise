"""ASN V2 environment peek reads data.environment (not only top-level)."""

from __future__ import annotations

import base64
import json

import pytest
from appstoreserverlibrary.models.Environment import Environment

from app.core.errors import ValidationAppError
from app.services import apple_iap


def _unsigned_es256_jws(payload: dict) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "ES256", "typ": "JWT"}).encode()
    ).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.sig"


def test_environment_peek_asn_data_environment_sandbox():
    jws = _unsigned_es256_jws(
        {
            "notificationType": "TEST",
            "data": {"environment": "Sandbox", "bundleId": "app.fashionrise.studio"},
        }
    )
    assert apple_iap._environment_from_unverified_jws(jws) == Environment.SANDBOX


def test_environment_peek_transaction_top_level_still_works():
    jws = _unsigned_es256_jws({"environment": "Production", "productId": "stars_50"})
    assert apple_iap._environment_from_unverified_jws(jws) == Environment.PRODUCTION


def test_environment_peek_missing_raises():
    jws = _unsigned_es256_jws({"notificationType": "TEST", "data": {"bundleId": "x"}})
    with pytest.raises(ValidationAppError, match="missing environment"):
        apple_iap._environment_from_unverified_jws(jws)
