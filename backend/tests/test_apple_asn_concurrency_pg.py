"""PostgreSQL: concurrent ASN refund workers cannot double-claw Stars."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.iap_purchase import STATUS_ACTIVE, IapPurchase
from app.models.iap_stars_adjustment import IapStarsAdjustment
from app.models.user import User
from app.services import ai_stars, apple_asn, apple_iap
from app.services.apple_iap import VerifiedAppleNotification, VerifiedAppleTransaction


def _enable(monkeypatch) -> None:
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()


def test_concurrent_refund_workers_single_clawback(engine, monkeypatch):
    _enable(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"pg-asn-{uuid.uuid4().hex[:12]}"
    email = f"asn_race_{uuid.uuid4().hex[:8]}@example.com"
    username = f"asnrace_{uuid.uuid4().hex[:8]}"

    bootstrap = SessionLocal()
    try:
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            is_admin=False,
        )
        ai_stars.apply_new_user_stars(user)
        user.ai_stars = 60
        user.ai_stars_iap_debt = 0
        bootstrap.add(user)
        bootstrap.flush()
        token = apple_iap.app_account_token_for_user(user.id)
        bootstrap.add(
            IapPurchase(
                user_id=user.id,
                platform="ios",
                product_id="stars_50",
                transaction_id=txn_id,
                original_transaction_id=txn_id,
                environment="Sandbox",
                status=STATUS_ACTIVE,
                stars_credited=50,
            )
        )
        bootstrap.commit()
        user_id = user.id
    finally:
        bootstrap.close()

    def _asn(uuid_s: str) -> VerifiedAppleNotification:
        return VerifiedAppleNotification(
            notification_uuid=uuid_s,
            notification_type="REFUND",
            subtype=None,
            environment="Sandbox",
            signed_date=1,
            transaction=VerifiedAppleTransaction(
                transaction_id=txn_id,
                original_transaction_id=txn_id,
                product_id="stars_50",
                bundle_id="app.fashionrise.studio",
                environment="Sandbox",
                type="Consumable",
                app_account_token=token,
                quantity=1,
                revocation_date=None,
                in_app_ownership_type="PURCHASED",
                raw=SimpleNamespace(),
            ),
            raw=SimpleNamespace(),
        )

    # Distinct notification UUIDs (Apple may redeliver under new ids).
    payload_map = {
        f"signed.{i}.payload": _asn(str(uuid.uuid4())) for i in range(2)
    }
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_notification_payload",
        lambda p: payload_map[p],
    )
    monkeypatch.setattr(apple_iap, "apple_iap_configured", lambda: True)

    def worker(payload: str) -> str:
        db = SessionLocal()
        try:
            out = apple_asn.process_apple_notification(db, signed_payload=payload)
            return out["processing_state"]
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, p) for p in payload_map]
        states = [f.result() for f in as_completed(futures)]

    assert any(s in ("applied", "ignored") for s in states)

    check = SessionLocal()
    try:
        u = check.get(User, user_id)
        assert u is not None
        assert int(u.ai_stars) == 10
        assert int(u.ai_stars_iap_debt or 0) == 0
        adj_count = check.scalar(
            select(func.count())
            .select_from(IapStarsAdjustment)
            .where(IapStarsAdjustment.transaction_id == txn_id)
        )
        assert int(adj_count or 0) == 1
    finally:
        check.close()
