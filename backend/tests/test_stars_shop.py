"""Stars shop catalog + cart infrastructure (checkout disabled)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services import ai_stars
from tests.auth_test_helpers import register_with_invite


@pytest.fixture()
def stars_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STARS_STARTING_BALANCE", "10")
    monkeypatch.setenv("AI_STARS_MAGIC_COST", "10")
    monkeypatch.setenv("AI_STARS_CROQUIS_COST", "10")
    monkeypatch.setenv("AI_STARS_PDF_COST", "50")
    monkeypatch.setenv("AI_STARS_FABRIC_COST", "5")
    monkeypatch.setenv("STARS_SHOP_CHECKOUT_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _auth(client, db_session):
    tokens = register_with_invite(
        client, db_session, email="shopper@example.com", username="shopper1"
    )
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_packages_list_public(client, stars_env):
    res = client.get("/api/v1/shop/packages")
    assert res.status_code == 200
    pkgs = res.json()["packages"]
    assert len(pkgs) >= 3
    assert all(p["available"] is False for p in pkgs)


def test_cart_add_and_checkout_blocked(client, db_session, stars_env):
    headers = _auth(client, db_session)
    cart = client.get("/api/v1/shop/cart", headers=headers)
    assert cart.status_code == 200
    assert cart.json()["items"] == []

    put = client.put(
        "/api/v1/shop/cart/items",
        headers=headers,
        json={"package_sku": "stars_50", "quantity": 2},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["stars_total"] == 100
    assert body["checkout_enabled"] is False

    checkout = client.post("/api/v1/shop/cart/checkout", headers=headers)
    assert checkout.status_code == 403


def test_feature_costs(stars_env):
    assert ai_stars.feature_cost("croquis") == 10
    assert ai_stars.feature_cost("pdf") == 50
    assert ai_stars.feature_cost("fabric") == 5
    assert ai_stars.feature_cost("magic") == 10


def test_stars_wallet_endpoint(client, db_session, stars_env):
    headers = _auth(client, db_session)
    res = client.get("/api/v1/auth/stars", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ai_stars"] == 10
    assert body["ai_stars_costs"]["pdf"] == 50
