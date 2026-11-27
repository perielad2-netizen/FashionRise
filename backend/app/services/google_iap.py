"""Google Play Billing verification (Androidpublisher purchases.products.get).

Fail-closed until ``IAP_GOOGLE_SERVICE_ACCOUNT_JSON`` is configured.
Stars amounts are never taken from the client — only from verified productId
mapped through ``STARS_PRODUCTS``.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError

_log = logging.getLogger(__name__)

# Reuse the same opaque account UUID namespace as Apple appAccountToken so one
# server helper covers both stores (Play obfuscatedAccountId ≤ 64 chars).
from app.services.apple_iap import app_account_token_for_user  # noqa: E402

PACKAGE_NAME_DEFAULT = "app.fashionrise.studio"

# Google purchaseState
_STATE_PURCHASED = 0
_STATE_CANCELED = 1
_STATE_PENDING = 2

# Google purchaseType (only set for non-standard flows)
_TYPE_TEST = 0


@dataclass(frozen=True)
class VerifiedGooglePurchase:
    product_id: str
    purchase_token: str
    order_id: str
    package_name: str
    purchase_state: int
    consumption_state: int | None
    acknowledgement_state: int | None
    obfuscated_external_account_id: str | None
    environment: str  # Production | Sandbox
    quantity: int
    raw: dict[str, Any]


def google_package_name() -> str:
    s = get_settings()
    return (getattr(s, "iap_google_package_name", None) or PACKAGE_NAME_DEFAULT).strip()


def google_iap_configured() -> bool:
    path_or_json = (get_settings().iap_google_service_account_json or "").strip()
    if not path_or_json:
        return False
    try:
        _load_service_account_info(path_or_json)
    except Exception:
        return False
    return True


def google_purchasing_enabled() -> bool:
    return bool(getattr(get_settings(), "iap_google_purchasing_enabled", False))


def google_credit_enabled() -> bool:
    return bool(getattr(get_settings(), "iap_google_credit_enabled", False))


def _license_tester_emails() -> set[str]:
    raw = (getattr(get_settings(), "iap_google_license_tester_emails", "") or "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def email_is_google_license_tester(email: str | None) -> bool:
    return (email or "").strip().lower() in _license_tester_emails()


def google_purchasing_enabled_for(user: Any | None = None) -> bool:
    if google_purchasing_enabled():
        return True
    if user is None:
        return False
    return email_is_google_license_tester(getattr(user, "email", None))


def google_credit_enabled_for(user: Any | None = None) -> bool:
    """Public credit gate OR designated license-tester email.

    When the global credit gate is OFF, only verified Play **Sandbox/test**
    purchases may credit for allowlisted emails (checked after API verify).
    """
    if google_credit_enabled():
        return True
    if user is None:
        return False
    return email_is_google_license_tester(getattr(user, "email", None))


def _load_service_account_info(path_or_json: str) -> dict[str, Any]:
    raw = path_or_json.strip()
    if raw.startswith("{"):
        data = json.loads(raw)
    else:
        data = json.loads(Path(raw).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "client_email" not in data:
        raise ValueError("invalid Google service account JSON")
    return data


@lru_cache(maxsize=4)
def _cached_sa_info(path_or_json: str) -> dict[str, Any]:
    return _load_service_account_info(path_or_json)


def _access_token() -> str:
    settings = get_settings()
    path_or_json = (settings.iap_google_service_account_json or "").strip()
    if not path_or_json:
        raise ServiceUnavailableError("Google Play service account not configured")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise ServiceUnavailableError("google-auth is not installed") from exc

    info = _cached_sa_info(path_or_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    creds.refresh(Request())
    if not creds.token:
        raise ServiceUnavailableError("Google Play access token unavailable")
    return str(creds.token)


def verify_product_purchase(
    *,
    product_id: str,
    purchase_token: str,
    package_name: str | None = None,
) -> VerifiedGooglePurchase:
    """Call purchases.products.get — authoritative purchase state."""
    pid = (product_id or "").strip()
    token = (purchase_token or "").strip()
    if not pid or not token:
        raise ValidationAppError("product_id and purchase_token are required")
    pkg = (package_name or google_package_name()).strip()
    if pkg != google_package_name():
        raise ForbiddenError("Google package name mismatch")

    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{pkg}/purchases/products/{pid}/tokens/{token}"
    )
    try:
        bearer = _access_token()
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {bearer}"})
    except httpx.HTTPError as exc:
        _log.warning("google_iap_transport err=%s", type(exc).__name__)
        raise ServiceUnavailableError("Google Play verification temporarily unavailable") from exc

    if resp.status_code in (401, 403):
        raise ServiceUnavailableError("Google Play Developer API authorization failed")
    if resp.status_code == 404:
        raise ForbiddenError("Google Play purchase not found")
    if resp.status_code >= 400:
        raise ServiceUnavailableError(f"Google Play verification HTTP {resp.status_code}")

    try:
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise ServiceUnavailableError("Google Play verification returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ServiceUnavailableError("Google Play verification malformed")

    purchase_state = int(payload.get("purchaseState", -1))
    consumption_state = payload.get("consumptionState")
    acknowledgement_state = payload.get("acknowledgementState")
    order_id = str(payload.get("orderId") or "").strip() or token
    qty = int(payload.get("quantity") or 1)
    if qty < 1:
        qty = 1
    obfuscated = payload.get("obfuscatedExternalAccountId")
    obfuscated_s = str(obfuscated).strip()[:64] if obfuscated else None

    purchase_type = payload.get("purchaseType")
    if purchase_type is not None and int(purchase_type) == _TYPE_TEST:
        environment = "Sandbox"
    else:
        environment = "Production"

    return VerifiedGooglePurchase(
        product_id=pid,
        purchase_token=token,
        order_id=order_id,
        package_name=pkg,
        purchase_state=purchase_state,
        consumption_state=int(consumption_state) if consumption_state is not None else None,
        acknowledgement_state=int(acknowledgement_state)
        if acknowledgement_state is not None
        else None,
        obfuscated_external_account_id=obfuscated_s,
        environment=environment,
        quantity=qty,
        raw=payload,
    )


def assert_account_owns_purchase(user_id: uuid.UUID, verified: VerifiedGooglePurchase) -> None:
    expected = app_account_token_for_user(user_id)
    got = (verified.obfuscated_external_account_id or "").strip()
    if not got:
        raise ForbiddenError(
            "Google obfuscatedExternalAccountId is required and must match this account"
        )
    if got.lower() != expected.lower():
        raise ForbiddenError("Google obfuscatedExternalAccountId does not match this account")


def is_purchased(verified: VerifiedGooglePurchase) -> bool:
    return verified.purchase_state == _STATE_PURCHASED


def is_pending(verified: VerifiedGooglePurchase) -> bool:
    return verified.purchase_state == _STATE_PENDING


def is_canceled(verified: VerifiedGooglePurchase) -> bool:
    return verified.purchase_state == _STATE_CANCELED


def purchase_token_lock_key(purchase_token: str) -> int:
    """Stable pg_advisory_xact_lock key shared by confirm + RTDN/voided clawbacks."""
    import hashlib

    return int.from_bytes(
        hashlib.sha256(f"fr.google.iap:{purchase_token}".encode()).digest()[:8],
        "big",
        signed=True,
    )


@dataclass(frozen=True)
class VoidedGooglePurchase:
    purchase_token: str
    order_id: str | None
    voided_time_millis: int | None
    raw: dict[str, Any]


def list_voided_purchases(
    *,
    start_time_ms: int,
    end_time_ms: int,
    max_pages: int = 10,
) -> list[VoidedGooglePurchase]:
    """Bounded ``purchases.voidedpurchases.list`` (in-app products only, type=0).

    Google retains at most ~30 days of voided records; callers must keep the
    window inside that limit.
    """
    if not google_iap_configured():
        raise ServiceUnavailableError("Google Play service account not configured")
    if end_time_ms < start_time_ms:
        raise ValidationAppError("voided purchases endTime must be >= startTime")
    pkg = google_package_name()
    bearer = _access_token()
    out: list[VoidedGooglePurchase] = []
    token_page: str | None = None
    pages = 0
    with httpx.Client(timeout=30.0) as client:
        while pages < max_pages:
            pages += 1
            params: dict[str, Any] = {
                "startTime": str(start_time_ms),
                "endTime": str(end_time_ms),
                "type": 0,
                "maxResults": 1000,
            }
            if token_page:
                params["token"] = token_page
            url = (
                "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
                f"{pkg}/purchases/voidedpurchases"
            )
            try:
                resp = client.get(
                    url, headers={"Authorization": f"Bearer {bearer}"}, params=params
                )
            except httpx.HTTPError as exc:
                _log.warning("google_voided_list_transport err=%s", type(exc).__name__)
                raise ServiceUnavailableError(
                    "Google Play voided purchases temporarily unavailable"
                ) from exc
            if resp.status_code in (401, 403):
                raise ServiceUnavailableError(
                    "Google Play Developer API authorization failed (voidedpurchases)"
                )
            if resp.status_code >= 400:
                raise ServiceUnavailableError(
                    f"Google Play voidedpurchases HTTP {resp.status_code}"
                )
            try:
                payload = resp.json()
            except Exception as exc:  # noqa: BLE001
                raise ServiceUnavailableError(
                    "Google Play voidedpurchases returned invalid JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise ServiceUnavailableError("Google Play voidedpurchases malformed")
            for item in payload.get("voidedPurchases") or []:
                if not isinstance(item, dict):
                    continue
                pt = str(item.get("purchaseToken") or "").strip()
                if not pt:
                    continue
                oid = str(item.get("orderId") or "").strip() or None
                vt_raw = item.get("voidedTimeMillis")
                try:
                    vt = int(vt_raw) if vt_raw is not None else None
                except (TypeError, ValueError):
                    vt = None
                out.append(
                    VoidedGooglePurchase(
                        purchase_token=pt,
                        order_id=oid,
                        voided_time_millis=vt,
                        raw=item,
                    )
                )
            next_token = (payload.get("tokenPagination") or {}).get("nextPageToken")
            if not next_token:
                break
            token_page = str(next_token)
    return out
