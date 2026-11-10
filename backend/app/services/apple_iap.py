"""Apple StoreKit 2 / App Store Server API v2 transaction + ASN V2 verification.

Uses Apple's official ``app-store-server-library`` ``SignedDataVerifier`` to
cryptographically verify device ``jwsRepresentation`` payloads and App Store
Server Notification V2 ``signedPayload`` envelopes. Stars amounts are never taken
from the client — only from a verified ``productId``.

Public purchasing stays behind ``IAP_APPLE_PURCHASING_ENABLED`` (default off).
Credit/recovery stays behind ``IAP_APPLE_CREDIT_ENABLED`` (default off).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import jwt
from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.InAppOwnershipType import InAppOwnershipType
from appstoreserverlibrary.models.Type import Type
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
    VerificationException,
    VerificationStatus,
)

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, ValidationAppError

_log = logging.getLogger(__name__)

# Stable DNS namespace for opaque per-account StoreKit appAccountToken UUIDs.
_APP_ACCOUNT_TOKEN_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID DNS namespace
_APP_ACCOUNT_TOKEN_PREFIX = "fashionrise.iap.v1:"

IOS_BUNDLE_ID_DEFAULT = "app.fashionrise.studio"
# App Store Connect Apple ID for FashionRise (public metadata — not a secret).
IOS_APP_APPLE_ID_DEFAULT = 6832116469

_CERTS_DIR = Path(__file__).resolve().parents[1] / "certs" / "apple"


@dataclass(frozen=True)
class VerifiedAppleTransaction:
    """Fields we trust after SignedDataVerifier succeeds."""

    transaction_id: str
    original_transaction_id: str
    product_id: str
    bundle_id: str
    environment: str  # Production | Sandbox
    type: str
    app_account_token: str | None
    quantity: int
    revocation_date: int | None
    in_app_ownership_type: str | None
    raw: Any


@dataclass(frozen=True)
class VerifiedAppleNotification:
    """Fields we trust after ASN V2 signedPayload verification."""

    notification_uuid: str
    notification_type: str
    subtype: str | None
    environment: str
    signed_date: int | None
    transaction: VerifiedAppleTransaction | None
    raw: Any


def app_account_token_for_user(user_id: uuid.UUID) -> str:
    """Opaque, stable UUID string for StoreKit ``appAccountToken`` (never raw numeric ids)."""
    return str(uuid.uuid5(_APP_ACCOUNT_TOKEN_NS, f"{_APP_ACCOUNT_TOKEN_PREFIX}{user_id}"))


def apple_iap_configured() -> bool:
    """True when root certs + bundle id (+ app Apple id for prod verifier) can load."""
    try:
        load_apple_root_certificates()
    except Exception:
        return False
    s = get_settings()
    if not (s.iap_apple_bundle_id or "").strip():
        return False
    if s.iap_apple_app_apple_id <= 0:
        return False
    return True


def apple_purchasing_enabled() -> bool:
    """Allow initiating *new* StoreKit purchases (native shop). Default OFF.

    Distinct from :func:`apple_credit_enabled`. Phase B turns this on only after
    refund/ASN + shop UI are ready — never a credit bypass.
    """
    return bool(get_settings().iap_apple_purchasing_enabled)


def apple_credit_enabled() -> bool:
    """Allow server confirm/reconcile of completed Apple transactions. Default OFF.

    Covers first-time confirm after StoreKit success and unfinished-txn recovery.
    Phase A keeps this false in production; tests may enable it locally.
    """
    return bool(get_settings().iap_apple_credit_enabled)


@lru_cache(maxsize=1)
def load_apple_root_certificates() -> tuple[bytes, ...]:
    if not _CERTS_DIR.is_dir():
        raise FileNotFoundError(f"Apple root cert directory missing: {_CERTS_DIR}")
    certs = sorted(_CERTS_DIR.glob("*.cer"))
    if not certs:
        raise FileNotFoundError(f"No Apple root .cer files in {_CERTS_DIR}")
    return tuple(p.read_bytes() for p in certs)


def _environment_from_unverified_jws(jws: str) -> Environment:
    """Peek only to select Production vs Sandbox verifier — never trust for credit."""
    try:
        payload = jwt.decode(
            jws,
            options={"verify_signature": False, "verify_aud": False, "verify_exp": False},
            algorithms=["ES256"],
        )
    except Exception as exc:  # noqa: BLE001 — treat as invalid client payload
        raise ValidationAppError("Apple transaction JWS could not be parsed") from exc
    raw = str(payload.get("environment") or "").strip()
    if raw.lower() == "sandbox":
        return Environment.SANDBOX
    if raw.lower() == "production":
        return Environment.PRODUCTION
    raise ValidationAppError("Apple transaction JWS missing environment")


def _build_verifier(environment: Environment) -> SignedDataVerifier:
    settings = get_settings()
    bundle_id = (settings.iap_apple_bundle_id or IOS_BUNDLE_ID_DEFAULT).strip()
    app_apple_id = int(settings.iap_apple_app_apple_id or IOS_APP_APPLE_ID_DEFAULT)
    # Online OCSP optional; tests disable. Never use Xcode/LocalTesting (unsigned).
    online = bool(settings.iap_apple_online_checks)
    roots = list(load_apple_root_certificates())
    if environment == Environment.PRODUCTION:
        return SignedDataVerifier(roots, online, environment, bundle_id, app_apple_id)
    return SignedDataVerifier(roots, online, environment, bundle_id, None)


def verify_signed_transaction_jws(jws: str) -> VerifiedAppleTransaction:
    """Cryptographically verify Apple-signed transaction JWS and return trusted fields."""
    token = (jws or "").strip()
    if not token or token.count(".") != 2:
        raise ValidationAppError("Apple transaction JWS is required")

    if not apple_iap_configured():
        raise ServiceUnavailableError("Apple IAP verification is not configured")

    env = _environment_from_unverified_jws(token)
    # Never accept Library environments that skip signature checks.
    if env not in (Environment.PRODUCTION, Environment.SANDBOX):
        raise ForbiddenError("Unsupported Apple IAP environment")

    verifier = _build_verifier(env)
    try:
        decoded = verifier.verify_and_decode_signed_transaction(token)
    except VerificationException as exc:
        status = getattr(exc, "status", None)
        _log.warning("apple_jws_verify_failed status=%s", status)
        if status == VerificationStatus.INVALID_APP_IDENTIFIER:
            raise ForbiddenError("Apple transaction bundle id mismatch") from exc
        if status == VerificationStatus.INVALID_ENVIRONMENT:
            raise ForbiddenError("Apple transaction environment mismatch") from exc
        raise ForbiddenError("Apple transaction signature verification failed") from exc
    except Exception as exc:  # noqa: BLE001
        _log.exception("apple_jws_verify_unexpected")
        raise ForbiddenError("Apple transaction verification failed") from exc

    return _validated_payload(decoded, expected_env=env)


def _validated_payload(decoded: Any, *, expected_env: Environment) -> VerifiedAppleTransaction:
    bundle_id = (getattr(decoded, "bundleId", None) or "").strip()
    settings = get_settings()
    expected_bundle = (settings.iap_apple_bundle_id or IOS_BUNDLE_ID_DEFAULT).strip()
    if bundle_id != expected_bundle:
        raise ForbiddenError("Apple transaction bundle id mismatch")

    env_obj = getattr(decoded, "environment", None)
    env_name = getattr(env_obj, "value", None) or str(env_obj or "")
    if expected_env == Environment.PRODUCTION and env_name != Environment.PRODUCTION.value:
        raise ForbiddenError("Apple transaction environment mismatch")
    if expected_env == Environment.SANDBOX and env_name != Environment.SANDBOX.value:
        raise ForbiddenError("Apple transaction environment mismatch")

    txn_id = str(getattr(decoded, "transactionId", None) or "").strip()
    original_txn = str(getattr(decoded, "originalTransactionId", None) or txn_id).strip()
    product_id = str(getattr(decoded, "productId", None) or "").strip()
    if not txn_id or not product_id:
        raise ForbiddenError("Apple transaction missing id or product")

    type_obj = getattr(decoded, "type", None)
    type_name = getattr(type_obj, "value", None) or str(type_obj or "")
    if type_obj != Type.CONSUMABLE and type_name != Type.CONSUMABLE.value:
        raise ForbiddenError("Only consumable Stars purchases are accepted")

    ownership = getattr(decoded, "inAppOwnershipType", None)
    ownership_name = getattr(ownership, "value", None) or (str(ownership) if ownership else None)
    if ownership is not None and ownership != InAppOwnershipType.PURCHASED:
        if ownership_name and ownership_name != InAppOwnershipType.PURCHASED.value:
            raise ForbiddenError("Apple transaction ownership is not purchasable")

    revocation_date = getattr(decoded, "revocationDate", None)
    if revocation_date is not None:
        raise ForbiddenError("Apple transaction was revoked or refunded")

    qty = int(getattr(decoded, "quantity", None) or 1)
    if qty < 1:
        raise ForbiddenError("Apple transaction quantity invalid")

    app_token = getattr(decoded, "appAccountToken", None)
    app_token_s = str(app_token).strip() if app_token else None

    return VerifiedAppleTransaction(
        transaction_id=txn_id,
        original_transaction_id=original_txn,
        product_id=product_id,
        bundle_id=bundle_id,
        environment=env_name,
        type=type_name,
        app_account_token=app_token_s,
        quantity=qty,
        revocation_date=int(revocation_date) if revocation_date is not None else None,
        in_app_ownership_type=ownership_name,
        raw=decoded,
    )


def verify_signed_notification_payload(signed_payload: str) -> VerifiedAppleNotification:
    """Cryptographically verify App Store Server Notification V2 signedPayload.

    Nested ``signedTransactionInfo`` (when present) is verified with the same
    root-trust path. Notification type is taken only from the verified payload.
    """
    token = (signed_payload or "").strip()
    if not token or token.count(".") != 2:
        raise ValidationAppError("Apple notification signedPayload is required")

    if not apple_iap_configured():
        raise ServiceUnavailableError("Apple IAP verification is not configured")

    # Outer ASN envelope uses the same environment peek as transactions.
    env = _environment_from_unverified_jws(token)
    if env not in (Environment.PRODUCTION, Environment.SANDBOX):
        raise ForbiddenError("Unsupported Apple notification environment")

    verifier = _build_verifier(env)
    try:
        decoded = verifier.verify_and_decode_notification(token)
    except VerificationException as exc:
        status = getattr(exc, "status", None)
        _log.warning("apple_asn_verify_failed status=%s", status)
        if status == VerificationStatus.INVALID_APP_IDENTIFIER:
            raise ForbiddenError("Apple notification app identifier mismatch") from exc
        if status == VerificationStatus.INVALID_ENVIRONMENT:
            raise ForbiddenError("Apple notification environment mismatch") from exc
        raise ForbiddenError("Apple notification signature verification failed") from exc
    except Exception as exc:  # noqa: BLE001
        _log.exception("apple_asn_verify_unexpected")
        raise ForbiddenError("Apple notification verification failed") from exc

    n_uuid = str(getattr(decoded, "notificationUUID", None) or "").strip()
    if not n_uuid:
        raise ForbiddenError("Apple notification missing notificationUUID")

    type_obj = getattr(decoded, "notificationType", None)
    type_name = getattr(type_obj, "value", None) or str(
        getattr(decoded, "rawNotificationType", None) or type_obj or ""
    ).strip()
    if not type_name:
        raise ForbiddenError("Apple notification missing notificationType")

    subtype_obj = getattr(decoded, "subtype", None)
    subtype_name = None
    if subtype_obj is not None:
        subtype_name = getattr(subtype_obj, "value", None) or str(
            getattr(decoded, "rawSubtype", None) or subtype_obj or ""
        ).strip() or None

    data = getattr(decoded, "data", None)
    env_name = env.value
    if data is not None:
        data_env = getattr(data, "environment", None)
        if data_env is not None:
            env_name = getattr(data_env, "value", None) or str(data_env)

    nested_txn: VerifiedAppleTransaction | None = None
    signed_txn = getattr(data, "signedTransactionInfo", None) if data is not None else None
    if signed_txn:
        # Nested JWS must also pass full transaction verification (bundle/env/type).
        # For refund notifications the nested payload may include revocationDate —
        # allow that path via dedicated helper used only for ASN context.
        nested_txn = verify_signed_transaction_jws_for_notification(str(signed_txn))

    return VerifiedAppleNotification(
        notification_uuid=n_uuid,
        notification_type=type_name,
        subtype=subtype_name,
        environment=str(env_name),
        signed_date=getattr(decoded, "signedDate", None),
        transaction=nested_txn,
        raw=decoded,
    )


def verify_signed_transaction_jws_for_notification(jws: str) -> VerifiedAppleTransaction:
    """Verify nested ASN transaction JWS; revocationDate is allowed (unlike confirm)."""
    token = (jws or "").strip()
    if not token or token.count(".") != 2:
        raise ValidationAppError("Apple nested transaction JWS is required")

    env = _environment_from_unverified_jws(token)
    if env not in (Environment.PRODUCTION, Environment.SANDBOX):
        raise ForbiddenError("Unsupported Apple IAP environment")

    verifier = _build_verifier(env)
    try:
        decoded = verifier.verify_and_decode_signed_transaction(token)
    except VerificationException as exc:
        status = getattr(exc, "status", None)
        _log.warning("apple_asn_nested_jws_verify_failed status=%s", status)
        raise ForbiddenError("Apple nested transaction signature verification failed") from exc
    except Exception as exc:  # noqa: BLE001
        _log.exception("apple_asn_nested_jws_unexpected")
        raise ForbiddenError("Apple nested transaction verification failed") from exc

    # Reuse field extraction but skip the revocationDate hard-fail used on confirm.
    bundle_id = (getattr(decoded, "bundleId", None) or "").strip()
    settings = get_settings()
    expected_bundle = (settings.iap_apple_bundle_id or IOS_BUNDLE_ID_DEFAULT).strip()
    if bundle_id != expected_bundle:
        raise ForbiddenError("Apple transaction bundle id mismatch")

    env_obj = getattr(decoded, "environment", None)
    env_name = getattr(env_obj, "value", None) or str(env_obj or "")
    if expected_env_mismatch(env, env_name):
        raise ForbiddenError("Apple transaction environment mismatch")

    txn_id = str(getattr(decoded, "transactionId", None) or "").strip()
    original_txn = str(getattr(decoded, "originalTransactionId", None) or txn_id).strip()
    product_id = str(getattr(decoded, "productId", None) or "").strip()
    if not txn_id or not product_id:
        raise ForbiddenError("Apple transaction missing id or product")

    type_obj = getattr(decoded, "type", None)
    type_name = getattr(type_obj, "value", None) or str(type_obj or "")
    # Consumables + one-time charges are expected for Stars; ignore subscription types
    # at the ASN handler layer rather than failing verification of nested data.
    ownership = getattr(decoded, "inAppOwnershipType", None)
    ownership_name = getattr(ownership, "value", None) or (str(ownership) if ownership else None)
    revocation_date = getattr(decoded, "revocationDate", None)
    qty = int(getattr(decoded, "quantity", None) or 1)
    app_token = getattr(decoded, "appAccountToken", None)
    app_token_s = str(app_token).strip() if app_token else None

    return VerifiedAppleTransaction(
        transaction_id=txn_id,
        original_transaction_id=original_txn,
        product_id=product_id,
        bundle_id=bundle_id,
        environment=env_name,
        type=type_name,
        app_account_token=app_token_s,
        quantity=max(1, qty),
        revocation_date=int(revocation_date) if revocation_date is not None else None,
        in_app_ownership_type=ownership_name,
        raw=decoded,
    )


def expected_env_mismatch(expected: Environment, env_name: str) -> bool:
    if expected == Environment.PRODUCTION and env_name != Environment.PRODUCTION.value:
        return True
    if expected == Environment.SANDBOX and env_name != Environment.SANDBOX.value:
        return True
    return False


def clear_apple_iap_caches() -> None:
    load_apple_root_certificates.cache_clear()


def apple_asc_api_configured() -> bool:
    """True when ASC In-App Purchase API key material is present for outbound calls."""
    s = get_settings()
    issuer = (s.iap_apple_asc_issuer_id or "").strip()
    key_id = (s.iap_apple_asc_key_id or "").strip()
    path = (s.iap_apple_asc_private_key_path or "").strip()
    if not issuer or not key_id or not path:
        return False
    try:
        p = Path(path)
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False


def load_apple_asc_signing_key() -> bytes:
    """Read the ASC ``.p8`` signing key from the configured filesystem path."""
    path = (get_settings().iap_apple_asc_private_key_path or "").strip()
    if not path:
        raise ServiceUnavailableError("Apple ASC private key path is not configured")
    p = Path(path)
    if not p.is_file():
        raise ServiceUnavailableError("Apple ASC private key file is missing")
    raw = p.read_bytes()
    if b"BEGIN PRIVATE KEY" not in raw and b"BEGIN EC PRIVATE KEY" not in raw:
        raise ServiceUnavailableError("Apple ASC private key file is not a PEM .p8")
    return raw


def build_app_store_server_api_client(*, environment: Environment) -> AppStoreServerAPIClient:
    """Official App Store Server API client (Sandbox or Production).

    Requires ``IAP_APPLE_ASC_ISSUER_ID``, ``IAP_APPLE_ASC_KEY_ID``, and
    ``IAP_APPLE_ASC_PRIVATE_KEY_PATH``. Does not enable purchasing or credit gates.
    """
    if environment not in (Environment.PRODUCTION, Environment.SANDBOX):
        raise ForbiddenError("Unsupported App Store Server API environment")
    if not apple_asc_api_configured():
        raise ServiceUnavailableError("Apple App Store Server API is not configured")

    settings = get_settings()
    bundle_id = (settings.iap_apple_bundle_id or IOS_BUNDLE_ID_DEFAULT).strip()
    return AppStoreServerAPIClient(
        signing_key=load_apple_asc_signing_key(),
        key_id=(settings.iap_apple_asc_key_id or "").strip(),
        issuer_id=(settings.iap_apple_asc_issuer_id or "").strip(),
        bundle_id=bundle_id,
        environment=environment,
    )


def request_sandbox_test_notification() -> str:
    """Ask Apple to send one ASN V2 TEST notification to the configured Sandbox URL.

    Returns the ``testNotificationToken`` (caller must not log the full value).
    """
    client = build_app_store_server_api_client(environment=Environment.SANDBOX)
    try:
        resp = client.request_test_notification()
    except Exception as exc:  # noqa: BLE001
        _log.exception("apple_asc_request_test_notification_failed")
        raise ServiceUnavailableError(
            "Apple Request Test Notification failed"
        ) from exc
    token = (getattr(resp, "testNotificationToken", None) or "").strip()
    if not token:
        raise ServiceUnavailableError("Apple TEST notification token missing")
    return token


def get_sandbox_test_notification_status(test_notification_token: str) -> dict[str, Any]:
    """Fetch Apple's delivery attempts for a prior sandbox TEST token (redacted)."""
    token = (test_notification_token or "").strip()
    if not token:
        raise ValidationAppError("testNotificationToken is required")
    client = build_app_store_server_api_client(environment=Environment.SANDBOX)
    try:
        resp = client.get_test_notification_status(token)
    except Exception as exc:  # noqa: BLE001
        _log.exception("apple_asc_get_test_notification_status_failed")
        raise ServiceUnavailableError(
            "Apple Get Test Notification Status failed"
        ) from exc

    attempts: list[dict[str, Any]] = []
    for item in getattr(resp, "sendAttempts", None) or []:
        result = getattr(item, "sendAttemptResult", None)
        raw = getattr(item, "rawSendAttemptResult", None)
        attempts.append(
            {
                "attempt_date_ms": getattr(item, "attemptDate", None),
                "result": getattr(result, "value", None) or raw or str(result or ""),
            }
        )
    signed = getattr(resp, "signedPayload", None)
    return {
        "attempt_count": len(attempts),
        "attempts": attempts,
        "has_signed_payload": bool(signed),
        "signed_payload_len": len(signed) if isinstance(signed, str) else 0,
    }
