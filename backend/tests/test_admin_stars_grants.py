"""Secure ADD-ONLY admin Stars grants — positive-only, idempotent, audited."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.security import create_access_token, hash_password
from app.db.base import import_models
from app.db.session import get_db
from app.main import app
from app.models.admin_stars_grant import (
    ABSOLUTE_GRANT_CEILING,
    STARS_INT_MAX,
    AdminStarsGrant,
)
from app.models.iap_purchase import IapPurchase
from app.models.user import User
from app.services import admin_stars_grants, ai_stars


@pytest.fixture()
def client(db_session: Session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def grant_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ADMIN_STARS_GRANT_MAX_AMOUNT", "10000")
    monkeypatch.setenv("ADMIN_STARS_GRANT_HARD_CEILING", "50000")
    monkeypatch.setenv("ADMIN_STARS_GRANT_LARGE_CONFIRM_THRESHOLD", "500")
    monkeypatch.setenv("AI_STARS_UNLIMITED_EMAILS", "unlimited@example.com")
    monkeypatch.setenv("AI_STARS_FINITE_OVERRIDE_EMAILS", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _user(
    db: Session,
    *,
    username: str,
    is_admin: bool = False,
    ai_stars_balance: int = 10,
    unlimited: bool = False,
    debt: int = 0,
    is_active: bool = True,
    email: str | None = None,
    classification: str | None = None,
) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email or f"{username}@example.com",
        username=username,
        hashed_password=hash_password("Password123!"),
        is_active=is_active,
        is_admin=is_admin,
        ai_stars=ai_stars_balance,
        ai_stars_unlimited=unlimited,
        ai_stars_iap_debt=debt,
    )
    if classification is not None:
        u.account_classification = classification
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _grant_payload(**overrides):
    body = {
        "amount": 50,
        "reason": "CUSTOMER_APPRECIATION",
        "note": "thank you",
        "idempotency_key": f"idem-{uuid.uuid4()}",
        "confirm_large": False,
    }
    body.update(overrides)
    return body


def _authorize_financial(monkeypatch: pytest.MonkeyPatch, *users: User) -> None:
    ids = ",".join(str(u.id) for u in users)
    monkeypatch.setenv("ADMIN_STARS_GRANT_ACTOR_IDS", ids)
    get_settings.cache_clear()


def _admin(db: Session, *, tag: str = "a") -> User:
    return _user(db, username=f"admin_{tag}_{uuid.uuid4().hex[:8]}", is_admin=True)


def test_grant_50_on_10_results_in_60(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="g50")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="shopper", ai_stars_balance=10)
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=50),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount"] == 50
    assert body["balance_before"] == 10
    assert body["balance_after"] == 60
    assert body["source"] == "ADMIN_GRANT"
    assert body["status"] == "completed"
    db_session.refresh(recipient)
    assert recipient.ai_stars == 60


def test_grant_one_star(client: TestClient, db_session: Session, grant_env, monkeypatch):
    admin = _admin(db_session, tag="t1")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="one_star_user", ai_stars_balance=5)
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=1),
    )
    assert r.status_code == 201
    assert r.json()["balance_after"] == 6


@pytest.mark.parametrize("amount", [-1, -50, 0])
def test_reject_non_positive(
    client: TestClient, db_session: Session, grant_env, monkeypatch, amount
):
    admin = _admin(db_session, tag="t2")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username=f"neg_{amount}")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=amount),
    )
    assert r.status_code in (422, 400)
    db_session.refresh(recipient)
    assert recipient.ai_stars == 10


@pytest.mark.parametrize(
    "amount",
    [1.5, 10.0, "50", True, False, None, "NaN", "Infinity"],
)
def test_reject_invalid_numeric(
    client: TestClient, db_session: Session, grant_env, monkeypatch, amount
):
    admin = _admin(db_session, tag="t3")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username=f"bad_{uuid.uuid4().hex[:8]}")
    before = recipient.ai_stars
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=amount),
    )
    assert r.status_code == 422
    db_session.refresh(recipient)
    assert recipient.ai_stars == before


def test_reject_over_maximum(client: TestClient, db_session: Session, grant_env, monkeypatch):
    admin = _admin(db_session, tag="t4")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="max_user")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=10_001, confirm_large=True),
    )
    assert r.status_code == 422
    assert "maximum" in r.text.lower() or "exceeds" in r.text.lower()


def test_absolute_ceiling_enforced(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    """Absolute 50k ceiling is code-enforced even if env tries to raise max."""
    monkeypatch.setenv("ADMIN_STARS_GRANT_MAX_AMOUNT", "999999")
    monkeypatch.setenv("ADMIN_STARS_GRANT_HARD_CEILING", "999999")
    get_settings.cache_clear()
    admin = _admin(db_session, tag="ceil")
    _authorize_financial(monkeypatch, admin)
    assert admin_stars_grants.effective_max_grant_amount() == 10_000  # fail-safe
    assert admin_stars_grants.absolute_grant_ceiling() == ABSOLUTE_GRANT_CEILING
    recipient = _user(db_session, username="ceil_user")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=ABSOLUTE_GRANT_CEILING + 1, confirm_large=True),
    )
    assert r.status_code == 422


def test_reject_overflow(client: TestClient, db_session: Session, grant_env, monkeypatch):
    admin = _admin(db_session, tag="t5")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(
        db_session, username="overflow_user", ai_stars_balance=STARS_INT_MAX - 5
    )
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=50, confirm_large=False),
    )
    assert r.status_code == 422
    assert "overflow" in r.text.lower()
    db_session.refresh(recipient)
    assert recipient.ai_stars == STARS_INT_MAX - 5


def test_reject_unauthorized(client: TestClient, db_session: Session, grant_env):
    # Empty ADMIN_STARS_GRANT_ACTOR_IDS → fail closed even for is_admin.
    regular = _user(db_session, username="regular_shopper")
    recipient = _user(db_session, username="target_a")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(regular),
        json=_grant_payload(),
    )
    assert r.status_code == 403
    db_session.refresh(recipient)
    assert recipient.ai_stars == 10


def test_admin_without_financial_allowlist_forbidden(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="nofin")
    monkeypatch.setenv("ADMIN_STARS_GRANT_ACTOR_IDS", "")
    get_settings.cache_clear()
    recipient = _user(db_session, username="nofin_target")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(),
    )
    assert r.status_code == 403
    assert "financial" in r.text.lower()
    db_session.refresh(recipient)
    assert recipient.ai_stars == 10


def test_reject_unauthenticated(client: TestClient, db_session: Session, grant_env):
    recipient = _user(db_session, username="target_b")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        json=_grant_payload(),
    )
    assert r.status_code in (401, 403)


def test_reject_invalid_recipient(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t6")
    _authorize_financial(monkeypatch, admin)
    missing = uuid.uuid4()
    r = client.post(
        f"/api/v1/admin/users/{missing}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(),
    )
    assert r.status_code == 404


def test_reject_inactive_recipient(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t7")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="gone", is_active=False)
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(),
    )
    assert r.status_code == 422


def test_idempotent_retry_no_duplicate_credit(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t8")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="idem_user", ai_stars_balance=10)
    key = f"idem-stable-{uuid.uuid4()}"
    payload = _grant_payload(amount=50, idempotency_key=key)
    r1 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=payload,
    )
    r2 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=payload,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["grant_id"] == r2.json()["grant_id"]
    assert r2.json()["idempotent_replay"] is True
    db_session.refresh(recipient)
    assert recipient.ai_stars == 60
    count = db_session.scalar(
        select(func.count())
        .select_from(AdminStarsGrant)
        .where(AdminStarsGrant.recipient_id == recipient.id)
    )
    assert int(count or 0) == 1


def test_conflicting_idempotency_payload(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t9")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="conflict_user", ai_stars_balance=10)
    key = f"idem-conflict-{uuid.uuid4()}"
    r1 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=25, idempotency_key=key),
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=40, idempotency_key=key),
    )
    assert r2.status_code == 409
    db_session.refresh(recipient)
    assert recipient.ai_stars == 35


def test_cross_administrator_idempotency_conflict(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin_a = _admin(db_session, tag="xa")
    admin_b = _admin(db_session, tag="xb")
    _authorize_financial(monkeypatch, admin_a, admin_b)
    recipient = _user(db_session, username="cross_idem", ai_stars_balance=10)
    key = f"idem-cross-{uuid.uuid4()}"
    r1 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin_a),
        json=_grant_payload(amount=25, idempotency_key=key),
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin_b),
        json=_grant_payload(amount=25, idempotency_key=key),
    )
    assert r2.status_code == 409
    db_session.refresh(recipient)
    assert recipient.ai_stars == 35


def test_concurrent_same_key_single_credit(db_url: str, grant_env, monkeypatch):
    import_models()
    eng = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    setup = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        admin = User(
            id=uuid.uuid4(),
            email=f"admin_same_{suffix}@example.com",
            username=f"admin_same_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            is_admin=True,
            ai_stars=10,
        )
        recipient = User(
            id=uuid.uuid4(),
            email=f"same_key_{suffix}@example.com",
            username=f"same_key_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            ai_stars=10,
        )
        setup.add_all([admin, recipient])
        setup.commit()
        rid, aid = recipient.id, admin.id
        monkeypatch.setenv("ADMIN_STARS_GRANT_ACTOR_IDS", str(aid))
        get_settings.cache_clear()
    finally:
        setup.close()

    key = f"same-key-{uuid.uuid4()}"
    barrier = threading.Barrier(2)
    results: list[dict] = []
    errors: list[BaseException] = []

    def _run():
        s = SessionLocal()
        try:
            actor = s.get(User, aid)
            barrier.wait(timeout=10)
            out = admin_stars_grants.grant_stars(
                s,
                actor=actor,
                recipient_id=rid,
                amount=40,
                reason="CUSTOMER_APPRECIATION",
                note=None,
                idempotency_key=key,
            )
            s.commit()
            results.append(out)
        except BaseException as exc:  # noqa: BLE001
            s.rollback()
            errors.append(exc)
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run)
        f2 = pool.submit(_run)
        f1.result(timeout=30)
        f2.result(timeout=30)

    # One success + optional IntegrityError race resolved to replay, or both success as replay.
    assert len(results) + len(
        [e for e in errors if isinstance(e, ConflictError)]
    ) >= 1
    assert len(results) >= 1
    check = SessionLocal()
    try:
        user = check.get(User, rid)
        assert int(user.ai_stars) == 50
        n = check.scalar(
            select(func.count())
            .select_from(AdminStarsGrant)
            .where(AdminStarsGrant.recipient_id == rid)
        )
        assert int(n or 0) == 1
    finally:
        check.close()
        eng.dispose()


def test_simultaneous_grants_correct_balance(db_url: str, grant_env, monkeypatch):
    """Two different idempotency keys from two admins → both credits apply."""
    import_models()
    eng = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    setup = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        admin_a = User(
            id=uuid.uuid4(),
            email=f"admin_a_{suffix}@example.com",
            username=f"admin_a_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            is_admin=True,
            ai_stars=10,
        )
        admin_b = User(
            id=uuid.uuid4(),
            email=f"admin_b_{suffix}@example.com",
            username=f"admin_b_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            is_admin=True,
            ai_stars=10,
        )
        recipient = User(
            id=uuid.uuid4(),
            email=f"race_target_{suffix}@example.com",
            username=f"race_target_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            ai_stars=10,
        )
        setup.add_all([admin_a, admin_b, recipient])
        setup.commit()
        rid, aid, bid = recipient.id, admin_a.id, admin_b.id
        monkeypatch.setenv("ADMIN_STARS_GRANT_ACTOR_IDS", f"{aid},{bid}")
        get_settings.cache_clear()
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    results: list[dict] = []
    errors: list[BaseException] = []

    def _run(actor_id: uuid.UUID, amount: int, key: str):
        s = SessionLocal()
        try:
            actor = s.get(User, actor_id)
            barrier.wait(timeout=10)
            out = admin_stars_grants.grant_stars(
                s,
                actor=actor,
                recipient_id=rid,
                amount=amount,
                reason="CUSTOMER_APPRECIATION",
                note=None,
                idempotency_key=key,
            )
            s.commit()
            results.append(out)
        except BaseException as exc:  # noqa: BLE001
            s.rollback()
            errors.append(exc)
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_run, aid, 30, f"race-a-{uuid.uuid4()}")
        f2 = pool.submit(_run, bid, 20, f"race-b-{uuid.uuid4()}")
        f1.result(timeout=30)
        f2.result(timeout=30)

    assert not errors, errors
    assert len(results) == 2
    check = SessionLocal()
    try:
        user = check.get(User, rid)
        assert user is not None
        assert int(user.ai_stars) == 60  # 10 + 30 + 20
        n = check.scalar(
            select(func.count())
            .select_from(AdminStarsGrant)
            .where(AdminStarsGrant.recipient_id == rid)
        )
        assert int(n or 0) == 2
    finally:
        check.close()
        eng.dispose()


def test_concurrent_consume_no_lost_update(db_url: str, grant_env, monkeypatch):
    import_models()
    eng = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=eng, autocommit=False, autoflush=False)
    setup = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        admin = User(
            id=uuid.uuid4(),
            email=f"admin_c_{suffix}@example.com",
            username=f"admin_c_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            is_admin=True,
            ai_stars=10,
        )
        recipient = User(
            id=uuid.uuid4(),
            email=f"consume_race_{suffix}@example.com",
            username=f"consume_race_{suffix}",
            hashed_password=hash_password("x"),
            is_active=True,
            ai_stars=100,
        )
        setup.add_all([admin, recipient])
        setup.commit()
        rid, aid = recipient.id, admin.id
        monkeypatch.setenv("ADMIN_STARS_GRANT_ACTOR_IDS", str(aid))
        get_settings.cache_clear()
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def grant_side():
        s = SessionLocal()
        try:
            actor = s.get(User, aid)
            barrier.wait(timeout=10)
            admin_stars_grants.grant_stars(
                s,
                actor=actor,
                recipient_id=rid,
                amount=50,
                reason="TECHNICAL_COMPENSATION",
                note=None,
                idempotency_key=f"consume-grant-{uuid.uuid4()}",
            )
            s.commit()
        except BaseException as exc:  # noqa: BLE001
            s.rollback()
            errors.append(exc)
        finally:
            s.close()

    def debit_side():
        s = SessionLocal()
        try:
            user = s.get(User, rid)
            barrier.wait(timeout=10)
            ai_stars.debit_stars(s, user, "magic")
            s.commit()
        except BaseException as exc:  # noqa: BLE001
            s.rollback()
            errors.append(exc)
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_grant = pool.submit(grant_side)
        fut_debit = pool.submit(debit_side)
        fut_grant.result(timeout=30)
        fut_debit.result(timeout=30)

    assert not errors, errors
    check = SessionLocal()
    try:
        user = check.get(User, rid)
        # 100 + 50 - 10 (magic) = 140
        assert int(user.ai_stars) == 140
    finally:
        check.close()
        eng.dispose()


def test_grant_and_audit_atomic_on_db_failure(db_session: Session, grant_env):
    admin = _admin(db_session, tag="t10")
    recipient = _user(db_session, username="atomic_user", ai_stars_balance=10)
    before = recipient.ai_stars

    class Boom(Exception):
        pass

    try:
        with db_session.begin_nested():
            ai_stars.credit_stars(db_session, recipient, 50, reason="test")
            raise Boom("simulated failure")
    except Boom:
        pass

    db_session.refresh(recipient)
    assert recipient.ai_stars == before
    grants = db_session.scalars(
        select(AdminStarsGrant).where(AdminStarsGrant.recipient_id == recipient.id)
    ).all()
    assert grants == []


def test_grant_service_rollback_when_ledger_flush_fails(
    db_session: Session, grant_env, monkeypatch
):
    """Actual grant_stars path: wallet credit + ledger must roll back together."""
    admin = _admin(db_session, tag="ledgerfail")
    recipient = _user(db_session, username="ledger_fail_user", ai_stars_balance=10)
    before = int(recipient.ai_stars)
    grant_count_before = int(
        db_session.scalar(select(func.count()).select_from(AdminStarsGrant)) or 0
    )

    real_flush = db_session.flush

    def boom_flush(*args, **kwargs):
        # Fail only when persisting the ledger row (after credit_stars).
        if any(isinstance(obj, AdminStarsGrant) for obj in db_session.new):
            raise RuntimeError("simulated ledger persistence failure")
        return real_flush(*args, **kwargs)

    with patch.object(db_session, "flush", boom_flush):
        with pytest.raises(RuntimeError, match="simulated ledger"):
            admin_stars_grants.grant_stars(
                db_session,
                actor=admin,
                recipient_id=recipient.id,
                amount=75,
                reason="CUSTOMER_APPRECIATION",
                note=None,
                idempotency_key=f"ledger-fail-{uuid.uuid4()}",
            )

    db_session.expire_all()
    db_session.refresh(recipient)
    assert int(recipient.ai_stars) == before
    grant_count_after = int(
        db_session.scalar(select(func.count()).select_from(AdminStarsGrant)) or 0
    )
    assert grant_count_after == grant_count_before


def test_admin_grant_not_revenue_and_no_iap(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t11")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(
        db_session,
        username="rev_user",
        ai_stars_balance=10,
        classification="CUSTOMER",
    )
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=100),
    )
    assert r.status_code == 201
    iap_n = db_session.scalar(
        select(func.count())
        .select_from(IapPurchase)
        .where(IapPurchase.user_id == recipient.id)
    )
    assert int(iap_n or 0) == 0
    ov = client.get(
        "/api/v1/admin/overview?audience=customers", headers=_auth(admin)
    )
    assert ov.status_code == 200
    body = ov.json()
    assert body["revenue"]["purchases_counted"] == 0
    assert body["revenue"]["gross_list_price_usd"] == 0
    assert body["stars"]["admin_grants"]["total_stars_granted"] >= 100
    assert body["stars"]["admin_grants"]["counts_toward_revenue"] is False
    assert body["stars"]["admin_grants"]["creates_iap_transactions"] is False
    assert body["stars"]["admin_grants"]["excluded_from_purchased_stars"] is True


def test_grants_overview_respects_audience_and_range(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="aud")
    _authorize_financial(monkeypatch, admin)

    def _total(audience: str) -> int:
        r = client.get(
            f"/api/v1/admin/stars/grants?audience={audience}&range=all_time",
            headers=_auth(admin),
        )
        assert r.status_code == 200
        return int(r.json()["total_stars_granted"])

    before_customers = _total("customers")
    before_internal = _total("internal")
    before_all = _total("all")

    customer = _user(
        db_session, username="cust_g", classification="CUSTOMER", ai_stars_balance=10
    )
    internal = _user(
        db_session,
        username="int_g",
        classification="INTERNAL_TESTER",
        ai_stars_balance=10,
    )
    assert (
        client.post(
            f"/api/v1/admin/users/{customer.id}/stars/grants",
            headers=_auth(admin),
            json=_grant_payload(amount=30, idempotency_key=f"aud-c-{uuid.uuid4()}"),
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/admin/users/{internal.id}/stars/grants",
            headers=_auth(admin),
            json=_grant_payload(amount=40, idempotency_key=f"aud-i-{uuid.uuid4()}"),
        ).status_code
        == 201
    )
    assert _total("customers") == before_customers + 30
    assert _total("internal") == before_internal + 40
    assert _total("all") == before_all + 70


def test_unlimited_wallet_blocked(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t12")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(
        db_session,
        username="unlimited_guy",
        email="unlimited@example.com",
        unlimited=True,
        ai_stars_balance=999_999,
    )
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=50),
    )
    assert r.status_code == 403
    assert "unlimited" in r.text.lower()


def test_debt_blocks_grant(client: TestClient, db_session: Session, grant_env, monkeypatch):
    admin = _admin(db_session, tag="t13")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="debt_user", ai_stars_balance=20, debt=40)
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=50),
    )
    assert r.status_code == 403
    assert "debt" in r.text.lower()
    db_session.refresh(recipient)
    assert recipient.ai_stars == 20
    assert recipient.ai_stars_iap_debt == 40


def test_classification_admin_does_not_grant_permission(
    client: TestClient, db_session: Session, grant_env
):
    classified = _user(db_session, username="class_only", classification="ADMIN")
    recipient = _user(db_session, username="class_target")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(classified),
        json=_grant_payload(),
    )
    assert r.status_code == 403


def test_other_requires_note(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t14")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="other_user")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(reason="OTHER", note=None),
    )
    assert r.status_code == 422


def test_large_requires_confirm(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="t15")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="large_user")
    r = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=500, confirm_large=False),
    )
    assert r.status_code == 422
    r2 = client.post(
        f"/api/v1/admin/users/{recipient.id}/stars/grants",
        headers=_auth(admin),
        json=_grant_payload(amount=500, confirm_large=True),
    )
    assert r2.status_code == 201


def test_reject_target_balance_field(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    """Unexpected financial fields must be rejected with zero wallet/ledger mutation."""
    admin = _admin(db_session, tag="t16")
    _authorize_financial(monkeypatch, admin)
    recipient = _user(db_session, username="no_target_bal", ai_stars_balance=10)
    before = recipient.ai_stars
    for extra in (
        {"target_balance": 999},
        {"balance_after": 999},
        {"replacement_balance": 50},
        {"signed_delta": -5},
        {"actor_id": str(admin.id)},
    ):
        payload = _grant_payload(amount=10, idempotency_key=f"extra-{uuid.uuid4()}")
        payload.update(extra)
        r = client.post(
            f"/api/v1/admin/users/{recipient.id}/stars/grants",
            headers=_auth(admin),
            json=payload,
        )
        assert r.status_code == 422, extra
        db_session.refresh(recipient)
        assert recipient.ai_stars == before
        n = db_session.scalar(
            select(func.count())
            .select_from(AdminStarsGrant)
            .where(AdminStarsGrant.recipient_id == recipient.id)
        )
        assert int(n or 0) == 0


def test_db_balance_invariants_constraint(db_session: Session, grant_env):
    """CHECK constraints reject corrupt ledger math."""
    admin = _admin(db_session, tag="ck")
    recipient = _user(db_session, username="ck_user")
    bad = AdminStarsGrant(
        id=uuid.uuid4(),
        recipient_id=recipient.id,
        actor_id=admin.id,
        amount=10,
        balance_before=10,
        balance_after=99,  # not before + amount
        reason="CUSTOMER_APPRECIATION",
        note=None,
        idempotency_key=f"ck-bad-{uuid.uuid4()}",
    )
    db_session.add(bad)
    with pytest.raises(Exception):
        db_session.flush()
    db_session.rollback()


def test_account_deletion_sets_null_preserves_grant(
    db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="del")
    recipient = _user(db_session, username="del_user", ai_stars_balance=10)
    out = admin_stars_grants.grant_stars(
        db_session,
        actor=admin,
        recipient_id=recipient.id,
        amount=15,
        reason="CUSTOMER_APPRECIATION",
        note=None,
        idempotency_key=f"del-{uuid.uuid4()}",
    )
    db_session.commit()
    grant_id = uuid.UUID(out["grant_id"])
    rid = recipient.id
    db_session.delete(recipient)
    db_session.commit()
    grant = db_session.get(AdminStarsGrant, grant_id)
    assert grant is not None
    assert grant.recipient_id is None
    assert grant.amount == 15
    assert grant.balance_after == 25
    # Actor still present; deleting actor also nulls without dropping the row.
    db_session.delete(admin)
    db_session.commit()
    grant = db_session.get(AdminStarsGrant, grant_id)
    assert grant is not None
    assert grant.actor_id is None
    _ = rid


def test_fresh_locked_balance_used(db_session: Session, grant_env, monkeypatch):
    admin = _admin(db_session, tag="fresh")
    recipient = _user(db_session, username="fresh_user", ai_stars_balance=10)
    # Stale identity-map value: mutate in-memory without flush, then grant must
    # expire_all and read authoritative locked balance.
    recipient.ai_stars = 999
    out = admin_stars_grants.grant_stars(
        db_session,
        actor=admin,
        recipient_id=recipient.id,
        amount=5,
        reason="CUSTOMER_APPRECIATION",
        note=None,
        idempotency_key=f"fresh-{uuid.uuid4()}",
    )
    db_session.commit()
    assert out["balance_before"] == 10
    assert out["balance_after"] == 15
    db_session.refresh(recipient)
    assert recipient.ai_stars == 15


def test_grants_config_endpoint(
    client: TestClient, db_session: Session, grant_env, monkeypatch
):
    admin = _admin(db_session, tag="cfg")
    # Config is readable by any admin (not financial-only).
    r = client.get("/api/v1/admin/stars/grants/config", headers=_auth(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["max_per_transaction"] == 10_000
    assert body["absolute_ceiling"] == 50_000
    assert body["large_confirm_threshold"] == 500
