"""PostgreSQL: prove inverted notification/advisory lock order deadlocks; fixed order does not."""

from __future__ import annotations

import threading
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.iap_apple_notification import IapAppleNotification
from app.models.iap_purchase import IapPurchase
from app.models.user import User
from app.services import ai_stars, apple_asn, apple_iap, iap_service
from app.services.apple_iap import VerifiedAppleNotification, VerifiedAppleTransaction

_IAP_LOCK_NS = 728401


def _enable_credit(monkeypatch) -> None:
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)


def _advisory_key(txn: str) -> int:
    return zlib.crc32(f"iap:ios:{txn}".encode()) & 0x7FFFFFFF


def _is_deadlock(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    if getattr(orig, "pgcode", None) == "40P01":
        return True
    blob = f"{exc} {orig}".lower()
    return "deadlock" in blob


def _txn(*, txn: str, token: str | None = None) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id="stars_50",
        bundle_id="app.fashionrise.studio",
        environment="Sandbox",
        type="Consumable",
        app_account_token=token,
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=SimpleNamespace(),
    )


def _asn(
    *,
    ntype: str,
    txn: VerifiedAppleTransaction,
    uuid_s: str,
) -> VerifiedAppleNotification:
    return VerifiedAppleNotification(
        notification_uuid=uuid_s,
        notification_type=ntype,
        subtype=None,
        environment=txn.environment,
        signed_date=1_700_000_000_000,
        transaction=txn,
        raw=SimpleNamespace(),
    )


def test_inverted_notification_then_advisory_deadlocks(engine):
    """Opposite lock order (notification FOR UPDATE → advisory) vs (advisory → notification)
    produces a PostgreSQL deadlock. Documents why ASN must take advisory first.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"lockord-{uuid.uuid4().hex[:12]}"
    n_uuid = str(uuid.uuid4())

    boot = SessionLocal()
    try:
        row = IapAppleNotification(
            id=uuid.uuid4(),
            notification_uuid=n_uuid,
            notification_type="REFUND",
            environment="Sandbox",
            transaction_id=txn_id,
            processing_state="unmatched",
            processing_attempts=1,
        )
        boot.add(row)
        boot.commit()
        note_id = row.id
    finally:
        boot.close()

    # Coordinated steps so both sides hold the first lock before taking the second.
    a_holds_notification = threading.Event()
    b_holds_advisory = threading.Event()
    errors: list[BaseException] = []
    outcomes: list[str] = []

    def worker_a_inverted() -> None:
        """Old ASN order: notification row first, then advisory."""
        db = SessionLocal()
        try:
            db.execute(text("SET LOCAL deadlock_timeout = '200ms'"))
            locked = db.scalar(
                select(IapAppleNotification)
                .where(IapAppleNotification.id == note_id)
                .with_for_update()
            )
            assert locked is not None
            a_holds_notification.set()
            assert b_holds_advisory.wait(timeout=5)
            # Wait for B's notification lock → cycle with our advisory wait.
            db.execute(
                text("SELECT pg_advisory_xact_lock(:ns, :k)"),
                {"ns": _IAP_LOCK_NS, "k": _advisory_key(txn_id)},
            )
            outcomes.append("a_ok")
            db.rollback()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            outcomes.append(f"a_err:{type(exc).__name__}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001, S110
                pass
        finally:
            db.close()

    def worker_b_confirm_order() -> None:
        """Confirm-like order: advisory first, then notification row."""
        db = SessionLocal()
        try:
            db.execute(text("SET LOCAL deadlock_timeout = '200ms'"))
            assert a_holds_notification.wait(timeout=5)
            db.execute(
                text("SELECT pg_advisory_xact_lock(:ns, :k)"),
                {"ns": _IAP_LOCK_NS, "k": _advisory_key(txn_id)},
            )
            b_holds_advisory.set()
            locked = db.scalar(
                select(IapAppleNotification)
                .where(IapAppleNotification.id == note_id)
                .with_for_update()
            )
            assert locked is not None
            outcomes.append("b_ok")
            db.rollback()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            outcomes.append(f"b_err:{type(exc).__name__}")
            try:
                db.rollback()
            except Exception:  # noqa: BLE001, S110
                pass
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker_a_inverted), pool.submit(worker_b_confirm_order)]
        for f in as_completed(futs):
            f.result(timeout=15)

    assert errors, f"expected deadlock, outcomes={outcomes}"
    assert any(_is_deadlock(e) for e in errors), (
        f"expected 40P01 deadlock, errors={errors!r} outcomes={outcomes}"
    )
    assert any(
        isinstance(e, (OperationalError, DBAPIError)) or _is_deadlock(e) for e in errors
    )


def test_fixed_asn_then_confirm_attach_no_deadlock(engine, monkeypatch):
    """Production paths: ASN (advisory→notification) ∥ confirm (advisory→attach notification)."""
    _enable_credit(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"fixord-{uuid.uuid4().hex[:12]}"

    boot = SessionLocal()
    try:
        user = User(
            email=f"lo_{uuid.uuid4().hex[:8]}@example.com",
            username=f"lo_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
        )
        ai_stars.apply_new_user_stars(user)
        starter = int(user.ai_stars)
        boot.add(user)
        boot.commit()
        boot.refresh(user)
        user_id = user.id
        token = apple_iap.app_account_token_for_user(user_id)
    finally:
        boot.close()

    # Pre-park unmatched REFUND so confirm's attach path updates the notification row
    # while ASN apply may also lock it — under fixed advisory-first order.
    n_uuid = str(uuid.uuid4())
    park = SessionLocal()
    try:
        park.add(
            IapAppleNotification(
                id=uuid.uuid4(),
                notification_uuid=n_uuid,
                notification_type="REFUND",
                environment="Sandbox",
                transaction_id=txn_id,
                product_id="stars_50",
                app_account_token=token,
                processing_state="unmatched",
                processing_attempts=1,
            )
        )
        park.commit()
    finally:
        park.close()

    barrier = threading.Barrier(2, timeout=10)
    errors: list[BaseException] = []
    verified_txn = _txn(txn=txn_id, token=token)
    verified_asn = _asn(ntype="REFUND", txn=verified_txn, uuid_s=n_uuid)
    monkeypatch.setattr(
        apple_iap, "verify_signed_transaction_jws", lambda jws: verified_txn
    )
    monkeypatch.setattr(
        apple_iap, "verify_signed_notification_payload", lambda p: verified_asn
    )

    def do_confirm() -> str:
        db = SessionLocal()
        try:
            u = db.get(User, user_id)
            assert u is not None
            barrier.wait()
            out = iap_service.confirm_purchase(
                db,
                u,
                platform="ios",
                product_id="stars_50",
                transaction_id=txn_id,
                jws="a.b.c",
            )
            return f"confirm:{out.get('blocked')}:{out.get('stars_credited')}"
        except Exception as exc:
            errors.append(exc)
            raise
        finally:
            db.close()

    def do_asn_retry() -> str:
        db = SessionLocal()
        try:
            barrier.wait()
            out = apple_asn.process_apple_notification(db, signed_payload="a.b.c")
            return f"asn:{out['processing_state']}"
        except Exception as exc:
            errors.append(exc)
            raise
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(do_confirm), pool.submit(do_asn_retry)]
        results = [f.result(timeout=30) for f in as_completed(futs)]

    assert not errors, f"unexpected errors {errors!r} results={results}"
    assert not any(_is_deadlock(e) for e in errors)
    assert any(r.startswith("confirm:") for r in results)
    assert any(r.startswith("asn:") for r in results)

    check = SessionLocal()
    try:
        purchase = check.scalar(
            select(IapPurchase).where(IapPurchase.transaction_id == txn_id)
        )
        u = check.get(User, user_id)
        note = check.scalar(
            select(IapAppleNotification).where(
                IapAppleNotification.notification_uuid == n_uuid
            )
        )
        assert purchase is not None
        assert u is not None
        assert note is not None
        # Refund intent existed before/with credit → never keep an active credited grant.
        assert not (
            purchase.status == "active" and int(purchase.stars_credited or 0) > 0
        )
        if purchase.status == "blocked":
            assert int(purchase.stars_credited) == 0
            assert int(u.ai_stars) == starter
        assert note.processing_state in (
            "applied",
            "unmatched",
            "ignored",
            "needs_reconciliation",
        )
        assert int(getattr(u, "ai_stars_iap_debt", 0) or 0) >= 0
    finally:
        check.close()
