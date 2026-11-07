"""Store IAP confirm stays fail-closed until Apple/Google credentials are configured."""

from tests.auth_test_helpers import register_with_invite
from tests.test_looks_api import _auth


def test_iap_confirm_fail_closed_without_credentials(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_APPLE_SHARED_SECRET", "")
    monkeypatch.setenv("IAP_GOOGLE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    tokens = register_with_invite(client, db_session, "iap.user@example.com", "iapUser")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "ios",
            "product_id": "stars_50",
            "transaction_id": "txn-test-1",
            "receipt": "fake-receipt",
        },
    )
    assert res.status_code == 503, res.text
    assert "not configured" in res.json()["detail"]["message"].lower()


def test_iap_confirm_rejects_unknown_product(client, db_session, monkeypatch):
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from app.core.config import get_settings

    get_settings.cache_clear()

    tokens = register_with_invite(client, db_session, "iap2@example.com", "iapUser2")
    res = client.post(
        "/api/v1/shop/iap/confirm",
        headers=_auth(tokens),
        json={
            "platform": "android",
            "product_id": "stars_999",
            "transaction_id": "txn-2",
            "purchase_token": "tok",
        },
    )
    assert res.status_code == 422, res.text
