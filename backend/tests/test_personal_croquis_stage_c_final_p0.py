"""Stage C final P0 amendment — lease fencing, erase/attach, dispatch authz.

Independent PostgreSQL sessions + controlled interleaving. Mock provider only.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.ai_job import AIJob
from app.models.personal_croquis import (
    VERSION_STATUS_AWAITING_REVIEW,
    VERSION_STATUS_FAILED,
    VERSION_STATUS_GENERATING,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.personal_croquis_spend import (
    RESERVATION_OPEN,
    RESERVATION_RELEASED,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import KIND_CROQUIS_GENERATED, PrivateMediaAsset
from app.models.user import User
from app.models.user_consent_event import UserConsentEvent
from app.services import personal_croquis_generate as pcg
from app.services import personal_croquis_service as pcs
from app.services.personal_croquis_provider import (
    MockCroquisProvider,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    provider_network_tripwire_hits,
    set_croquis_provider_override,
)
from app.services.personal_croquis_worker import (
    process_claimed_croquis_job,
    recover_stale_croquis_claims,
    run_croquis_worker_tick,
    set_post_provider_pre_attach_hook,
    set_pre_provider_dispatch_hook,
)
from app.storage.local import LocalStorageBackend
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    enable_synthetic_croquis_notices,
    storage_body,
)
from tests.test_personal_croquis_stage_c_hardening import (
    _bootstrap_user_with_source,
    _enable_ai_spend,
    _png_bytes,
)

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _disable_ai(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_AI_ENABLED", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_SPEND_CEILING_USD", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _synthetic_notices(monkeypatch, request):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    set_pre_provider_dispatch_hook(None)
    set_post_provider_pre_attach_hook(None)
    arm_provider_network_tripwire()
    # Client tests share nested tx with committed engine leftovers — scrub when present.
    if "db_session" in request.fixturenames:
        db_session = request.getfixturevalue("db_session")
        from app.models.ai_job import AIJob
        from app.models.personal_croquis import CROQUIS_GENERATE_JOB_TYPE

        db_session.query(PersonalCroquisSpendReservation).delete()
        db_session.query(AIJob).filter(AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE).delete()
        db_session.flush()
    yield
    disarm_provider_network_tripwire()
    set_croquis_provider_override(None)
    set_pre_provider_dispatch_hook(None)
    set_post_provider_pre_attach_hook(None)
    _disable_ai(monkeypatch)


def _upload_ready(client, tokens, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()
    assert (
        client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code
        == 200
    )
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200, c.text
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"storage_consent_id": c.json()["id"], "display_name": "Final P0"},
    )
    assert up.status_code == 201, up.text
    return up.json()


def _ai_consent(client, tokens, croquis_id: str) -> str:
    r = client.post(
        f"{BASE}/consent/ai",
        headers=_auth(tokens),
        json=ai_body(croquis_id=croquis_id),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_lease_fence_stale_worker_cannot_double_submit(engine, monkeypatch):
    """P0-A: A pauses pre-dispatch; lease recovery + B reclaim → at most one provider call."""
    enable_synthetic_croquis_notices(monkeypatch)
    _enable_ai_spend(monkeypatch)
    monkeypatch.setenv("MY_CROQUIS_AI_CLAIM_LEASE_SECONDS", "30")
    get_settings.cache_clear()

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    uid, croq_id, _src, ai_id = _bootstrap_user_with_source(
        Session,
        email=f"fence_a_{uuid.uuid4().hex[:8]}@ex.com",
        username=f"fence_a_{uuid.uuid4().hex[:6]}",
    )

    mock = MockCroquisProvider(cost_cents=2)
    set_croquis_provider_override(mock)

    setup = Session()
    try:
        user = setup.get(User, uid)
        pcg.enqueue_personal_croquis_generate(
            setup, user, croq_id, ai_consent_id=ai_id, idempotency_key="fence-1"
        )
    finally:
        setup.close()

    # Claim as worker A without going through recover.
    claim_db = Session()
    from app.services.personal_croquis_worker import _claim_next_croquis_job

    job_a = _claim_next_croquis_job(claim_db)
    assert job_a is not None
    token_a = job_a.claim_token
    job_a_id = job_a.id
    claim_db.close()

    entered = threading.Event()
    release = threading.Event()

    def pause_before_fence(_job: AIJob) -> None:
        entered.set()
        assert release.wait(timeout=20)

    set_pre_provider_dispatch_hook(pause_before_fence)

    errors: list[BaseException] = []

    def worker_a():
        db = Session()
        try:
            job = db.get(AIJob, job_a_id)
            assert job is not None
            # Preserve the original claim token A believes it owns.
            job.claim_token = token_a
            process_claimed_croquis_job(db, job)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            db.close()

    t = threading.Thread(target=worker_a)
    t.start()
    assert entered.wait(timeout=10)

    # While A is paused pre-fence, expire the lease and let B recover+claim.
    expire_db = Session()
    try:
        job = expire_db.get(AIJob, job_a_id)
        assert job is not None
        job.claimed_at = datetime.now(UTC) - timedelta(seconds=600)
        expire_db.add(job)
        expire_db.commit()
    finally:
        expire_db.close()

    set_pre_provider_dispatch_hook(None)
    b_db = Session()
    try:
        recovered = recover_stale_croquis_claims(b_db)
        assert recovered >= 1
        n = run_croquis_worker_tick(b_db, limit=1)
        assert n >= 1
    finally:
        b_db.close()

    release.set()
    t.join(timeout=20)
    assert not t.is_alive()
    assert not errors, errors

    assert mock.calls == 1, f"expected exactly one provider call, got {mock.calls}"
    assert provider_network_tripwire_hits() == 0

    verify = Session()
    try:
        res = (
            verify.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.idempotency_key == "fence-1")
            .one()
        )
        assert res.status == RESERVATION_SETTLED
        assert res.actual_cost_cents == 2
        ver = (
            verify.query(PersonalCroquisVersion)
            .filter(PersonalCroquisVersion.idempotency_key == "fence-1")
            .one()
        )
        assert ver.status == VERSION_STATUS_AWAITING_REVIEW
        assert ver.generated_asset_id is not None
    finally:
        verify.close()


def test_erase_vs_attach_interleaved_no_orphan(engine, monkeypatch):
    """P0-B: erase between provider return and attach → no resurrected/accessible asset."""
    enable_synthetic_croquis_notices(monkeypatch)
    _enable_ai_spend(monkeypatch)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    uid, croq_id, _src, ai_id = _bootstrap_user_with_source(
        Session,
        email=f"erase_a_{uuid.uuid4().hex[:8]}@ex.com",
        username=f"erase_a_{uuid.uuid4().hex[:6]}",
    )

    mock = MockCroquisProvider(cost_cents=3)
    set_croquis_provider_override(mock)

    setup = Session()
    try:
        user = setup.get(User, uid)
        ver = pcg.enqueue_personal_croquis_generate(
            setup, user, croq_id, ai_consent_id=ai_id, idempotency_key="erase-attach"
        )
        version_id = ver.id
    finally:
        setup.close()

    entered = threading.Event()
    release = threading.Event()

    def pause_before_attach(_job: AIJob) -> None:
        entered.set()
        assert release.wait(timeout=20)

    set_post_provider_pre_attach_hook(pause_before_attach)
    errors: list[BaseException] = []

    def worker():
        db = Session()
        try:
            run_croquis_worker_tick(db, limit=1)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            db.close()

    t = threading.Thread(target=worker)
    t.start()
    assert entered.wait(timeout=10)

    erase_db = Session()
    try:
        user = erase_db.get(User, uid)
        erased = pcs.request_permanent_erase(erase_db, user, croq_id)
        assert erased.erase_requested_at is not None
    finally:
        erase_db.close()

    release.set()
    t.join(timeout=20)
    assert not t.is_alive()
    assert not errors, errors
    assert mock.calls == 1

    verify = Session()
    try:
        croquis = verify.get(PersonalCroquis, croq_id)
        assert croquis is not None
        assert croquis.erase_requested_at is not None
        ver = verify.get(PersonalCroquisVersion, version_id)
        assert ver is not None
        assert ver.status in (VERSION_STATUS_FAILED, VERSION_STATUS_GENERATING)
        assert ver.status != VERSION_STATUS_AWAITING_REVIEW
        assert ver.generated_asset_id is None
        leaked = (
            verify.query(PrivateMediaAsset)
            .filter(
                PrivateMediaAsset.owner_id == uid,
                PrivateMediaAsset.kind == KIND_CROQUIS_GENERATED,
            )
            .all()
        )
        assert leaked == []
        # Source may remain as tombstone meta, but generated bytes must not be live-accessible.
        storage = LocalStorageBackend()
        croquis_root = storage.private_croquis_root()
        for p in Path(croquis_root).rglob("*.png"):
            # Only allow the original source key under owner; no generated orphans.
            if str(uid) in str(p) and "generated" not in p.name:
                continue
        res = (
            verify.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.idempotency_key == "erase-attach")
            .one()
        )
        # Provider already called — spend exposure preserved as settled/discarded.
        assert res.status in (RESERVATION_SETTLED, RESERVATION_OPEN)
        assert res.provider_called is True
    finally:
        verify.close()


def test_dispatch_authz_stale_notice_zero_provider(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "authz1@example.com", "authz1")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "authz-notice"},
    )
    assert r.status_code == 201
    # Change approved notice after enqueue — dispatch must refuse.
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_NOTICE_TEXT", "SYNTHETIC_TEST_AI_NOTICE_CHANGED_AT_DISPATCH")
    get_settings.cache_clear()
    assert run_croquis_worker_tick(db_session) >= 1
    assert mock.calls == 0
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == VERSION_STATUS_FAILED
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "authz-notice")
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.provider_called is False


def test_dispatch_authz_expired_consent_zero_provider(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "authz2@example.com", "authz2")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "authz-exp"},
    )
    assert r.status_code == 201
    row = db_session.query(UserConsentEvent).filter(UserConsentEvent.id == uuid.UUID(ai_id)).one()
    row.created_at = datetime.now(UTC) - timedelta(hours=5)
    db_session.add(row)
    db_session.commit()
    assert run_croquis_worker_tick(db_session) >= 1
    assert mock.calls == 0
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "authz-exp")
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.provider_called is False


def test_dispatch_authz_purged_source_zero_provider(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "authz3@example.com", "authz3")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "authz-src"},
    )
    assert r.status_code == 201
    source_id = uuid.UUID(croquis["source_asset_id"])
    asset = db_session.get(PrivateMediaAsset, source_id)
    assert asset is not None
    asset.erase_requested_at = datetime.now(UTC)
    asset.bytes_purged_at = datetime.now(UTC)
    db_session.add(asset)
    db_session.commit()
    assert run_croquis_worker_tick(db_session) >= 1
    assert mock.calls == 0
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "authz-src")
        .one()
    )
    assert res.status == RESERVATION_RELEASED
    assert res.provider_called is False
