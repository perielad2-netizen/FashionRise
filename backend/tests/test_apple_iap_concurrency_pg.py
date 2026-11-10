"""PostgreSQL integration: concurrent Apple IAP confirm cannot double-credit Stars."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.security import hash_password
from app.models.iap_purchase import IapPurchase
from app.models.user import User
from app.services import ai_stars, apple_iap, iap_service
from app.services.apple_iap import VerifiedAppleTransaction


def _enable_credit(monkeypatch) -> None:
    monkeypatch.setenv("IAP_APPLE_PURCHASING_ENABLED", "false")
    monkeypatch.setenv("IAP_APPLE_CREDIT_ENABLED", "true")
    monkeypatch.setenv("IAP_ALLOW_UNVERIFIED_SANDBOX", "false")
    monkeypatch.setenv("IAP_APPLE_ONLINE_CHECKS", "false")
    monkeypatch.setenv("IAP_APPLE_BUNDLE_ID", "app.fashionrise.studio")
    monkeypatch.setenv("IAP_APPLE_APP_APPLE_ID", "6832116469")
    get_settings.cache_clear()
    apple_iap.clear_apple_iap_caches()


def _verified(*, txn: str, product: str, token: str) -> VerifiedAppleTransaction:
    return VerifiedAppleTransaction(
        transaction_id=txn,
        original_transaction_id=txn,
        product_id=product,
        bundle_id="app.fashionrise.studio",
        environment="Sandbox",
        type="Consumable",
        app_account_token=token,
        quantity=1,
        revocation_date=None,
        in_app_ownership_type="PURCHASED",
        raw=SimpleNamespace(),
    )


def test_concurrent_confirm_same_txn_no_double_credit(engine, monkeypatch):
    """Two simultaneous confirms for one verified Apple txn → one credit, one idempotent."""
    _enable_credit(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"pg-race-{uuid.uuid4().hex[:12]}"
    email = f"iap_race_{uuid.uuid4().hex[:8]}@example.com"
    username = f"iaprace_{uuid.uuid4().hex[:8]}"

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
        bootstrap.add(user)
        bootstrap.commit()
        bootstrap.refresh(user)
        user_id = user.id
        starter = int(user.ai_stars)
        token = apple_iap.app_account_token_for_user(user_id)
    finally:
        bootstrap.close()

    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn=txn_id, product="stars_50", token=token),
    )

    results: list[dict] = []
    errors: list[BaseException] = []

    def worker(_: int) -> dict:
        session = SessionLocal()
        try:
            u = session.get(User, user_id)
            assert u is not None
            return iap_service.confirm_purchase(
                session,
                u,
                platform="ios",
                product_id="stars_50",
                transaction_id=txn_id,
                jws="header.payload.sig",
            )
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker, i) for i in range(2)]
        for fut in as_completed(futs):
            try:
                results.append(fut.result(timeout=30))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    assert not errors, errors
    credited = sorted(int(r["stars_credited"]) for r in results)
    assert credited == [0, 50]

    verify = SessionLocal()
    try:
        rows = verify.scalars(
            select(IapPurchase).where(
                IapPurchase.platform == "ios",
                IapPurchase.transaction_id == txn_id,
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].user_id == user_id
        assert rows[0].stars_credited == 50
        assert rows[0].product_id == "stars_50"
        u = verify.get(User, user_id)
        assert u is not None
        assert int(u.ai_stars) == starter + 50
        total_ledger = verify.scalar(
            select(func.coalesce(func.sum(IapPurchase.stars_credited), 0)).where(
                IapPurchase.transaction_id == txn_id
            )
        )
        assert int(total_ledger or 0) == 50
    finally:
        verify.close()


def test_concurrent_cross_account_one_winner(engine, monkeypatch):
    """Same Apple txn confirmed by two accounts concurrently → one owner, other conflict/forbidden."""
    _enable_credit(monkeypatch)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    txn_id = f"pg-xacct-{uuid.uuid4().hex[:12]}"

    def make_user(suffix: str) -> tuple[uuid.UUID, str, int]:
        s = SessionLocal()
        try:
            u = User(
                email=f"iap_x_{suffix}_{uuid.uuid4().hex[:6]}@example.com",
                username=f"iapx_{suffix}_{uuid.uuid4().hex[:6]}",
                hashed_password=hash_password("StrongPass123!"),
                is_active=True,
                is_admin=False,
            )
            ai_stars.apply_new_user_stars(u)
            s.add(u)
            s.commit()
            s.refresh(u)
            return u.id, apple_iap.app_account_token_for_user(u.id), int(u.ai_stars)
        finally:
            s.close()

    user_a, token_a, starter_a = make_user("a")
    user_b, _token_b, starter_b = make_user("b")

    # Apple JWS is bound to account A only.
    monkeypatch.setattr(
        apple_iap,
        "verify_signed_transaction_jws",
        lambda jws: _verified(txn=txn_id, product="stars_50", token=token_a),
    )

    outcomes: list[str] = []

    def worker(uid: uuid.UUID) -> str:
        session = SessionLocal()
        try:
            u = session.get(User, uid)
            assert u is not None
            try:
                out = iap_service.confirm_purchase(
                    session,
                    u,
                    platform="ios",
                    product_id="stars_50",
                    transaction_id=txn_id,
                    jws="header.payload.sig",
                )
                if out.get("already_processed"):
                    return "idempotent"
                return f"credited:{out['stars_credited']}"
            except ConflictError:
                return "conflict"
            except Exception as exc:  # noqa: BLE001
                # Ownership mismatch → ForbiddenError
                name = type(exc).__name__
                return f"err:{name}"
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(worker, user_a), pool.submit(worker, user_b)]
        for fut in as_completed(futs):
            outcomes.append(fut.result(timeout=30))

    assert any(o.startswith("credited:50") for o in outcomes)
    # B must not credit: forbidden (token) and/or conflict if race ordered oddly.
    assert not any(o == "credited:50" and outcomes.count("credited:50") > 1 for o in outcomes)
    assert outcomes.count("credited:50") == 1
    assert any(o in ("conflict", "err:ForbiddenError") or o.startswith("err:") for o in outcomes)

    s = SessionLocal()
    try:
        rows = s.scalars(select(IapPurchase).where(IapPurchase.transaction_id == txn_id)).all()
        assert len(rows) == 1
        assert rows[0].user_id == user_a
        assert rows[0].stars_credited == 50
        a = s.get(User, user_a)
        b = s.get(User, user_b)
        assert a is not None and b is not None
        assert int(a.ai_stars) == starter_a + 50
        assert int(b.ai_stars) == starter_b
    finally:
        s.close()
