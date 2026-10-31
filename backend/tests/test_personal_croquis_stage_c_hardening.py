"""Stage C P0 hardening — concurrency, crash recovery, consent binding, max exposure.

Uses independent PostgreSQL sessions (real commits) where the review requires it.
Mock provider / blocking doubles only — network tripwire armed.
"""

from __future__ import annotations

import io
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.ai_job import AIJob
from app.models.personal_croquis import (
    CROQUIS_GENERATE_JOB_TYPE,
    VERSION_STATUS_AWAITING_REVIEW,
    VERSION_STATUS_RECONCILIATION,
    VERSION_STATUS_REJECTED,
    PersonalCroquis,
    PersonalCroquisVersion,
)
from app.models.personal_croquis_ai_consent import PersonalCroquisAiConsentBinding
from app.models.personal_croquis_spend import (
    RESERVATION_OPEN,
    RESERVATION_RECONCILIATION,
    RESERVATION_SETTLED,
    PersonalCroquisSpendReservation,
)
from app.models.private_media_asset import (
    KIND_CROQUIS_GENERATED,
    KIND_CROQUIS_SOURCE,
    PrivateMediaAsset,
)
from app.models.user import User
from app.models.user_consent_event import (
    PURPOSE_CROQUIS_AI_PROVIDER,
    PURPOSE_CROQUIS_STORAGE,
    UserConsentEvent,
)
from app.services import personal_croquis_generate as pcg
from app.services.personal_croquis_provider import (
    BlockingCroquisProvider,
    MockCroquisProvider,
    OpenAICroquisImagesEditAdapter,
    arm_provider_network_tripwire,
    disarm_provider_network_tripwire,
    provider_network_tripwire_hits,
    set_croquis_provider_override,
)
from app.services.personal_croquis_worker import (
    recover_stale_croquis_claims,
    run_croquis_worker_tick,
    validate_and_normalize_provider_png,
)
from tests.auth_test_helpers import register_with_invite
from tests.croquis_test_fixtures import (
    adults_body,
    ai_body,
    enable_synthetic_croquis_notices,
    storage_body,
)

BASE = "/api/v1/personal-croquis"


def _auth(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _png_bytes(w: int = 64, h: int = 96, color=(40, 80, 160)) -> bytes:
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _enable_upload(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_UPLOAD_ENABLED", "true")
    get_settings.cache_clear()


def _enable_ai_spend(
    monkeypatch,
    *,
    ceiling_usd: str = "5",
    max_run: str = "1",
    max_day: str = "5",
    max_exposure_cents: str = "5",
):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", ceiling_usd)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", max_run)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", max_day)
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_GENERATIONS_PER_USER_DAY", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "3")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", max_exposure_cents)
    get_settings.cache_clear()


def _disable_ai(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("MY_CROQUIS_AI_ENABLED", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_SPEND_CEILING_USD", raising=False)
    monkeypatch.delenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _synthetic_notices(monkeypatch):
    enable_synthetic_croquis_notices(monkeypatch)
    set_croquis_provider_override(None)
    arm_provider_network_tripwire()
    yield
    disarm_provider_network_tripwire()
    set_croquis_provider_override(None)
    _disable_ai(monkeypatch)


def _upload_ready(client, tokens, monkeypatch):
    _enable_upload(monkeypatch)
    assert client.post(f"{BASE}/attestations/adults", headers=_auth(tokens), json=adults_body()).status_code == 200
    c = client.post(f"{BASE}/consent/storage", headers=_auth(tokens), json=storage_body())
    assert c.status_code == 200, c.text
    up = client.post(
        f"{BASE}/photos",
        headers=_auth(tokens),
        files={"file": ("photo.png", _png_bytes(), "image/png")},
        data={"storage_consent_id": c.json()["id"], "display_name": "Hardening subject"},
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


def test_max_exposure_fail_closed_when_unset(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h1@example.com", "h1")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", "1")
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_USER_DAY", "5")
    monkeypatch.setenv("MY_CROQUIS_AI_ESTIMATE_CENTS", "8")  # soft only
    monkeypatch.delenv("MY_CROQUIS_AI_MAX_EXPOSURE_CENTS", raising=False)
    # max_run set but max_exposure unset → resolve_max_exposure uses max_run (100¢)
    # Explicitly set max_exposure 0 AND max_run 0 to prove fail-closed on soft estimate.
    monkeypatch.setenv("MY_CROQUIS_AI_MAX_USD_PER_RUN", "0")
    get_settings.cache_clear()
    set_croquis_provider_override(MockCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-no-cap"},
    )
    assert r.status_code == 403
    assert "max exposure" in r.json()["detail"].lower() or "fail closed" in r.json()["detail"].lower()


def test_actual_gt_estimate_reserves_max_exposure(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h2@example.com", "h2")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    # Soft estimate 3¢; hard max exposure 12¢; provider reports 9¢ actual.
    _enable_ai_spend(monkeypatch, max_exposure_cents="12", ceiling_usd="1", max_run="1", max_day="1")
    mock = MockCroquisProvider(cost_cents=9)
    set_croquis_provider_override(mock)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-actual-gt-est"},
    )
    assert r.status_code == 201, r.text
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "h-actual-gt-est")
        .one()
    )
    assert res.max_exposure_cents == 12
    assert res.estimate_cents == 3
    assert run_croquis_worker_tick(db_session) >= 1
    db_session.expire_all()
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "h-actual-gt-est")
        .one()
    )
    assert res.status == RESERVATION_SETTLED
    assert res.actual_cost_cents == 9


def test_ai_consent_bound_to_source_not_reusable_cross_source(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h3@example.com", "h3")
    c1 = _upload_ready(client, tokens, monkeypatch)
    c2 = _upload_ready(client, tokens, monkeypatch)
    ai_c1 = _ai_consent(client, tokens, c1["id"])
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    # Consent for c1 cannot authorize generate on c2.
    denied = client.post(
        f"{BASE}/{c2['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_c1, "idempotency_key": "h-cross-src"},
    )
    assert denied.status_code == 400
    binding = (
        db_session.query(PersonalCroquisAiConsentBinding)
        .filter(PersonalCroquisAiConsentBinding.consent_id == uuid.UUID(ai_c1))
        .one()
    )
    assert str(binding.croquis_id) == c1["id"]


def test_stale_notice_hash_rejected(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h4@example.com", "h4")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    # Change approved notice text without bumping version — old hash must fail.
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_NOTICE_TEXT", "SYNTHETIC_TEST_AI_NOTICE_V1_CHANGED")
    get_settings.cache_clear()
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-stale-hash"},
    )
    assert r.status_code == 400


def test_provider_output_normalized_at_worker_boundary(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h5@example.com", "h5")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)

    class OddSizeProvider:
        calls = 0

        def generate_line_art(self, source_png: bytes):
            from app.services.personal_croquis_provider import CroquisProviderResult

            self.calls += 1
            # Deliberately wrong size / RGB — worker must normalize + validate.
            img = Image.new("RGB", (100, 200), (10, 20, 30))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return CroquisProviderResult(
                png_bytes=buf.getvalue(),
                provider_job_id="odd-1",
                actual_cost_cents=2,
                estimated_cost_cents=2,
                usage_source="provider_usage",
            )

    odd = OddSizeProvider()
    set_croquis_provider_override(odd)
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-norm"},
    )
    assert r.status_code == 201
    assert run_croquis_worker_tick(db_session) >= 1
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == VERSION_STATUS_AWAITING_REVIEW
    asset_id = poll.json()["generated_asset_id"]
    asset = db_session.get(PrivateMediaAsset, uuid.UUID(asset_id))
    assert asset is not None
    assert asset.width == 768
    assert asset.height == 1024


def test_openai_adapter_marked_incomplete(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MY_CROQUIS_AI_ENABLED", "true")
    monkeypatch.setenv("MY_CROQUIS_AI_SPEND_CEILING_USD", "5")
    get_settings.cache_clear()
    from app.services.personal_croquis_provider import (
        ProviderNetworkForbiddenError,
        ProviderNotAvailableError,
    )

    adapter = OpenAICroquisImagesEditAdapter()
    assert adapter.incomplete is True
    with pytest.raises((ProviderNetworkForbiddenError, ProviderNotAvailableError)):
        adapter.generate_line_art(_png_bytes())
    assert provider_network_tripwire_hits() >= 1


def test_crash_lease_before_provider_safe_requeue(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h6@example.com", "h6")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider(cost_cents=2))
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-lease-pre"},
    )
    assert r.status_code == 201
    job = (
        db_session.query(AIJob)
        .filter(AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE, AIJob.status == "queued")
        .one()
    )
    job.status = "running"
    job.claimed_at = datetime.now(UTC) - timedelta(seconds=600)
    job.claim_token = "stale-token"
    db_session.add(job)
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "h-lease-pre")
        .one()
    )
    assert res.provider_called is False
    db_session.commit()

    monkeypatch.setenv("MY_CROQUIS_AI_CLAIM_LEASE_SECONDS", "30")
    get_settings.cache_clear()
    assert recover_stale_croquis_claims(db_session) >= 1
    db_session.expire_all()
    job = db_session.get(AIJob, job.id)
    assert job.status == "queued"
    assert job.claim_token is None
    # Replay must not double-call provider.
    mock = MockCroquisProvider(cost_cents=2)
    set_croquis_provider_override(mock)
    assert run_croquis_worker_tick(db_session) >= 1
    assert mock.calls == 1
    poll = client.get(f"{BASE}/{croquis['id']}/versions/1", headers=_auth(tokens))
    assert poll.json()["status"] == VERSION_STATUS_AWAITING_REVIEW


def test_crash_lease_after_provider_called_requires_recon(client, monkeypatch, db_session):
    tokens = register_with_invite(client, db_session, "h7@example.com", "h7")
    croquis = _upload_ready(client, tokens, monkeypatch)
    ai_id = _ai_consent(client, tokens, croquis["id"])
    _enable_ai_spend(monkeypatch)
    set_croquis_provider_override(MockCroquisProvider())
    r = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-lease-post"},
    )
    assert r.status_code == 201
    job = (
        db_session.query(AIJob)
        .filter(AIJob.job_type == CROQUIS_GENERATE_JOB_TYPE, AIJob.status == "queued")
        .one()
    )
    job.status = "running"
    job.claimed_at = datetime.now(UTC) - timedelta(seconds=600)
    job.claim_token = "stale-post"
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "h-lease-post")
        .one()
    )
    res.provider_called = True
    db_session.add(job)
    db_session.add(res)
    db_session.commit()

    monkeypatch.setenv("MY_CROQUIS_AI_CLAIM_LEASE_SECONDS", "30")
    get_settings.cache_clear()
    assert recover_stale_croquis_claims(db_session) >= 1
    db_session.expire_all()
    ver = (
        db_session.query(PersonalCroquisVersion)
        .filter(PersonalCroquisVersion.idempotency_key == "h-lease-post")
        .one()
    )
    assert ver.status == VERSION_STATUS_RECONCILIATION
    res = (
        db_session.query(PersonalCroquisSpendReservation)
        .filter(PersonalCroquisSpendReservation.idempotency_key == "h-lease-post")
        .one()
    )
    assert res.status == RESERVATION_RECONCILIATION
    # No auto paid retry on new key
    mock = MockCroquisProvider()
    set_croquis_provider_override(mock)
    denied = client.post(
        f"{BASE}/{croquis['id']}/versions/generate",
        headers=_auth(tokens),
        json={"ai_consent_id": ai_id, "idempotency_key": "h-lease-post-retry"},
    )
    assert denied.status_code == 409
    assert mock.calls == 0



def test_reject_during_blocking_provider_cas(engine, monkeypatch):
    """Reject while provider is in-flight must CAS-discard; never resurrect awaiting_review."""
    enable_synthetic_croquis_notices(monkeypatch)
    _enable_ai_spend(monkeypatch)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    uid, croq_id, _src, ai_id = _bootstrap_user_with_source(
        Session,
        email=f"rej_{uuid.uuid4().hex[:8]}@ex.com",
        username=f"rej_{uuid.uuid4().hex[:6]}",
    )
    release = threading.Event()
    entered = threading.Event()
    blocking = BlockingCroquisProvider(release_event=release, entered_event=entered, cost_cents=4)
    set_croquis_provider_override(blocking)

    setup = Session()
    try:
        user = setup.get(User, uid)
        ver = pcg.enqueue_personal_croquis_generate(
            setup, user, croq_id, ai_consent_id=ai_id, idempotency_key="h-reject-race"
        )
        version_num = ver.version
        version_id = ver.id
    finally:
        setup.close()

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

    rej_db = Session()
    try:
        user = rej_db.get(User, uid)
        rejected = pcg.reject_personal_croquis_version(rej_db, user, croq_id, version_num)
        assert rejected.status == VERSION_STATUS_REJECTED
    finally:
        rej_db.close()

    release.set()
    t.join(timeout=20)
    assert not t.is_alive()
    assert not errors, errors

    verify = Session()
    try:
        ver = verify.get(PersonalCroquisVersion, version_id)
        assert ver is not None
        assert ver.status == VERSION_STATUS_REJECTED
        assert ver.generated_asset_id is None
        res = (
            verify.query(PersonalCroquisSpendReservation)
            .filter(PersonalCroquisSpendReservation.idempotency_key == "h-reject-race")
            .one()
        )
        assert res.status == RESERVATION_SETTLED
        assert (res.actual_cost_cents or 0) >= 1
        # No awaiting_review resurrection / leaked generated asset rows for this version
        leaked = (
            verify.query(PrivateMediaAsset)
            .filter(
                PrivateMediaAsset.owner_id == uid,
                PrivateMediaAsset.kind == KIND_CROQUIS_GENERATED,
            )
            .count()
        )
        assert leaked == 0
    finally:
        verify.close()


def test_validate_normalize_helper_strips_odd_input():
    raw = _png_bytes(50, 80)
    out = validate_and_normalize_provider_png(raw)
    with Image.open(io.BytesIO(out)) as img:
        assert img.size == (768, 1024)
        assert img.mode == "RGBA"



def _bootstrap_user_with_source(Session, *, email: str, username: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create committed user + croquis + source + adults/AI consent binding for concurrency tests."""
    import hashlib

    from app.models.user_consent_event import PURPOSE_ADULTS_BETA
    from app.storage.local import LocalStorageBackend
    from tests.croquis_test_fixtures import (
        SYNTHETIC_ADULTS_NOTICE,
        SYNTHETIC_AI_NOTICE,
        SYNTHETIC_STORAGE_NOTICE,
    )

    def sha(t: str) -> str:
        return hashlib.sha256(t.encode()).hexdigest()

    db = Session()
    try:
        settings = get_settings()
        user = User(
            email=email,
            username=username,
            hashed_password=hash_password("StrongPass123!"),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.flush()

        adults = UserConsentEvent(
            id=uuid.uuid4(),
            owner_id=user.id,
            purpose=PURPOSE_ADULTS_BETA,
            consent_version=settings.my_croquis_adults_attestation_version,
            adults_attested=True,
            text_hash=sha(SYNTHETIC_ADULTS_NOTICE),
        )
        db.add(adults)

        storage_consent = UserConsentEvent(
            id=uuid.uuid4(),
            owner_id=user.id,
            purpose=PURPOSE_CROQUIS_STORAGE,
            consent_version=settings.my_croquis_storage_consent_version,
            adults_attested=True,
            text_hash=sha(SYNTHETIC_STORAGE_NOTICE),
        )
        db.add(storage_consent)
        db.flush()

        source_id = uuid.uuid4()
        png = _png_bytes()
        key = f"croquis/{user.id}/{source_id}.png"
        LocalStorageBackend().save_private_croquis_file(
            key=key, data=io.BytesIO(png), content_type="image/png"
        )
        db.add(
            PrivateMediaAsset(
                id=source_id,
                owner_id=user.id,
                kind=KIND_CROQUIS_SOURCE,
                content_type="image/png",
                width=64,
                height=96,
                byte_size=len(png),
                sha256=hashlib.sha256(png).hexdigest(),
                storage_key=key,
            )
        )
        db.flush()

        croquis = PersonalCroquis(
            id=uuid.uuid4(),
            owner_id=user.id,
            display_name=username,
            status="uploaded",
            source_asset_id=source_id,
            storage_consent_id=storage_consent.id,
            adults_attestation_at=datetime.now(UTC),
        )
        db.add(croquis)
        db.flush()

        ai_consent = UserConsentEvent(
            id=uuid.uuid4(),
            owner_id=user.id,
            purpose=PURPOSE_CROQUIS_AI_PROVIDER,
            consent_version=settings.my_croquis_ai_consent_version,
            adults_attested=True,
            text_hash=sha(SYNTHETIC_AI_NOTICE),
        )
        db.add(ai_consent)
        db.flush()
        db.add(
            PersonalCroquisAiConsentBinding(
                id=uuid.uuid4(),
                owner_id=user.id,
                consent_id=ai_consent.id,
                croquis_id=croquis.id,
                source_asset_id=source_id,
                notice_version=settings.my_croquis_ai_consent_version,
                notice_text_hash=sha(SYNTHETIC_AI_NOTICE),
            )
        )
        db.commit()
        return user.id, croquis.id, source_id, ai_consent.id
    finally:
        db.close()


def test_multi_user_global_ceiling_concurrency(engine, monkeypatch):
    """P0-1: two owners racing under a 1×max_exposure ceiling — exactly one reserve."""
    enable_synthetic_croquis_notices(monkeypatch)
    _enable_ai_spend(
        monkeypatch,
        ceiling_usd="0.05",  # 5¢
        max_run="1",
        max_day="1",
        max_exposure_cents="5",
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    # Isolate from other committed hardening tests in this session (operator ceiling is global).
    scrub = Session()
    try:
        scrub.query(PersonalCroquisSpendReservation).delete()
        scrub.commit()
    finally:
        scrub.close()
    uid_a, croq_a, _src_a, ai_a = _bootstrap_user_with_source(
        Session, email=f"ceil_a_{uuid.uuid4().hex[:8]}@ex.com", username=f"ceil_a_{uuid.uuid4().hex[:6]}"
    )
    uid_b, croq_b, _src_b, ai_b = _bootstrap_user_with_source(
        Session, email=f"ceil_b_{uuid.uuid4().hex[:8]}@ex.com", username=f"ceil_b_{uuid.uuid4().hex[:6]}"
    )

    results: list[str] = []
    lock = threading.Lock()

    def attempt(user_id: uuid.UUID, croquis_id: uuid.UUID, ai_id: uuid.UUID, key: str) -> None:
        db = Session()
        try:
            user = db.get(User, user_id)
            try:
                pcg.enqueue_personal_croquis_generate(
                    db,
                    user,
                    croquis_id,
                    ai_consent_id=ai_id,
                    idempotency_key=key,
                )
                outcome = "ok"
            except Exception as exc:  # noqa: BLE001
                from fastapi import HTTPException

                if isinstance(exc, HTTPException) and exc.status_code == 403:
                    detail = str(exc.detail).lower()
                    outcome = "ceiling" if "ceiling" in detail else f"403:{exc.detail}"
                else:
                    outcome = f"err:{type(exc).__name__}:{exc}"
            with lock:
                results.append(outcome)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(attempt, uid_a, croq_a, ai_a, "ceil-a"),
            pool.submit(attempt, uid_b, croq_b, ai_b, "ceil-b"),
        ]
        for f in as_completed(futs):
            f.result()

    assert results.count("ok") == 1, results
    assert results.count("ceiling") == 1, results

    verify = Session()
    try:
        opens = (
            verify.query(PersonalCroquisSpendReservation)
            .filter(
                PersonalCroquisSpendReservation.idempotency_key.in_(["ceil-a", "ceil-b"]),
                PersonalCroquisSpendReservation.status == RESERVATION_OPEN,
            )
            .count()
        )
        assert opens == 1
    finally:
        verify.close()
