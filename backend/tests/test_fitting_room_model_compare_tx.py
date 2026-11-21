"""PostgreSQL transaction durability for model-compare paid budget.

Uses genuinely independent sessions (engine-bound) so COMMIT is visible across
connections — the shared TestClient fixture cannot detect production rollback.
"""

from __future__ import annotations

import base64
import io
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.fitting_room_model_compare import (
    MODEL_COMPARE_GLOBAL_LOCK_KEY,
    OP_STATUS_COMPLETED,
    OP_STATUS_RECONCILIATION,
    OP_STATUS_RUNNING,
    FittingRoomModelCompareOperation,
)
from app.models.user import User
from app.services import fitting_room_model_compare as cmp
from app.storage.local import LocalStorageBackend
from tests.look_test_images import floral_blue_look_plate_png, wings_outdoor_person_png

CONSENT = "fitting-room-model-compare-v1"


def _b64(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _png(color=(10, 20, 30)) -> bytes:
    im = Image.new("RGB", (32, 48), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def SessionFactory(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def clean_ops(engine, SessionFactory):
    s = SessionFactory()
    try:
        s.query(FittingRoomModelCompareOperation).delete()
        s.commit()
    finally:
        s.close()
    yield
    s = SessionFactory()
    try:
        s.query(FittingRoomModelCompareOperation).delete()
        s.commit()
    finally:
        s.close()


@pytest.fixture()
def owner_user(SessionFactory, clean_ops):
    s = SessionFactory()
    try:
        user = User(
            id=uuid.uuid4(),
            email=f"cmp_tx_{uuid.uuid4().hex[:8]}@example.com",
            username=f"cmp_tx_{uuid.uuid4().hex[:8]}",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        uid = user.id
        username = user.username
    finally:
        s.close()
    return {"id": uid, "username": username}


def _arm_compare(monkeypatch, tmp_path, username: str):
    get_settings.cache_clear()
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_ENABLED", "true")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_LIVE_HTTP", "true")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_OWNER_ALLOWLIST", username)
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_MAX_PAID_OPS", "1")
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_MAX_PROVIDER_CALLS", "3")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()


def test_claim_is_visible_to_independent_session(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    s1 = SessionFactory()
    s2 = SessionFactory()
    try:
        user = s1.get(User, owner_user["id"])
        assert user is not None

        def _boom(**_k):
            raise AssertionError("must not call provider during claim-only probe")

        cmp.set_model_compare_runners_for_tests(openai_runner=_boom, fashn_runner=_boom)

        # Claim via partial path: run with authorize but runner fails after dispatch.
        # First verify claim+commit alone by calling _claim_paid_operation.
        person = wings_outdoor_person_png()
        design = floral_blue_look_plate_png()
        person_fp = cmp._fingerprint(person)
        design_fp = cmp._fingerprint(design)
        op, replay = cmp._claim_paid_operation(
            s1,
            user=user,
            idempotency_key="tx-claim-visible-01",
            consent_version=CONSENT,
            arms=["A"],
            person_fp=person_fp,
            design_fp=design_fp,
        )
        assert replay is False
        assert op.status == OP_STATUS_RUNNING

        # Independent session must see the committed claim.
        seen = (
            s2.query(FittingRoomModelCompareOperation)
            .filter(FittingRoomModelCompareOperation.id == op.id)
            .one()
        )
        assert seen.status == OP_STATUS_RUNNING
        assert seen.dispatched_requests == 0
    finally:
        cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
        s1.close()
        s2.close()
        get_settings.cache_clear()


def test_concurrent_claims_only_one_succeeds(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    results: list[str] = []
    barrier = threading.Barrier(2)

    def worker(key: str):
        s = SessionFactory()
        try:
            user = s.get(User, owner_user["id"])
            person_fp = "aaaaaaaaaaaaaaaa"
            design_fp = "bbbbbbbbbbbbbbbb"
            barrier.wait(timeout=5)
            try:
                op, replay = cmp._claim_paid_operation(
                    s,
                    user=user,
                    idempotency_key=key,
                    consent_version=CONSENT,
                    arms=["A"],
                    person_fp=person_fp,
                    design_fp=design_fp,
                )
                results.append("ok" if not replay else "replay")
            except Exception as exc:  # noqa: BLE001
                results.append(type(exc).__name__)
        finally:
            s.close()

    t1 = threading.Thread(target=worker, args=("tx-conc-key-a",))
    t2 = threading.Thread(target=worker, args=("tx-conc-key-b",))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert results.count("ok") == 1
    assert any(r in {"HTTPException", "ok"} for r in results)
    # Exactly one durable row.
    s = SessionFactory()
    try:
        n = s.query(FittingRoomModelCompareOperation).count()
        assert n == 1
    finally:
        s.close()
        get_settings.cache_clear()


def test_dispatch_commit_before_provider_and_crash_retains_budget(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    s1 = SessionFactory()
    s2 = SessionFactory()
    try:
        user = s1.get(User, owner_user["id"])
        person = wings_outdoor_person_png()
        design = floral_blue_look_plate_png()
        person_fp = cmp._fingerprint(person)
        design_fp = cmp._fingerprint(design)

        op, _ = cmp._claim_paid_operation(
            s1,
            user=user,
            idempotency_key="tx-crash-after-dispatch",
            consent_version=CONSENT,
            arms=["A"],
            person_fp=person_fp,
            design_fp=design_fp,
        )
        cmp._commit_arm_dispatch(
            s1,
            op,
            arm="A",
            spec={
                "arm": "A",
                "provider": "openai",
                "model": "chatgpt-image-latest",
                "path": "openai_images_edit_person_garment",
            },
        )
        # Simulate crash: abandon s1 without finishing the arm.
        s1.close()
        s1 = SessionFactory()

        # Independent observer: dispatch consumed.
        observed = s2.get(FittingRoomModelCompareOperation, op.id)
        assert observed is not None
        assert observed.dispatched_requests == 1
        assert observed.status == OP_STATUS_RUNNING
        ledger = (observed.report or {}).get("arm_ledger") or {}
        assert ledger["A"]["status"] == "dispatched"

        # Replay must NOT re-dispatch; marks reconciliation/unknown.
        user2 = s2.get(User, owner_user["id"])
        report = cmp._finalize_replay_without_dispatch(s2, observed)
        assert report["replay"] is True
        refreshed = s2.get(FittingRoomModelCompareOperation, op.id)
        assert refreshed.status == OP_STATUS_RECONCILIATION
        assert refreshed.dispatched_requests == 1
        assert (refreshed.report or {}).get("arm_ledger", {}).get("A", {}).get("status") == "unknown"

        # Second claim with new key is exhausted.
        with pytest.raises(Exception) as ei:
            cmp._claim_paid_operation(
                s2,
                user=user2,
                idempotency_key="tx-crash-second-key",
                consent_version=CONSENT,
                arms=["A"],
                person_fp=person_fp,
                design_fp=design_fp,
            )
        assert "exhausted" in str(ei.value.detail).lower()
    finally:
        s1.close()
        s2.close()
        get_settings.cache_clear()


def test_successful_run_commits_outcomes(SessionFactory, owner_user, monkeypatch, tmp_path):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])

    def _ok(**_k):
        return _png((40, 80, 120)), {
            "provider": "openai",
            "model": "chatgpt-image-latest",
            "openai_calls": 1,
            "duration_ms": 1,
            "estimate_cents": 6,
            "preprocessing": "none",
            "postprocessing": "none",
        }

    cmp.set_model_compare_runners_for_tests(openai_runner=_ok, fashn_runner=_ok)
    s1 = SessionFactory()
    s2 = SessionFactory()
    try:
        user = s1.get(User, owner_user["id"])
        report = cmp.run_model_compare(
            db=s1,
            user=user,
            person_image_base64=_b64(wings_outdoor_person_png()),
            design_image_base64=_b64(floral_blue_look_plate_png()),
            authorize_paid=True,
            arms=["A"],
            consent_acknowledged=True,
            consent_version=CONSENT,
            idempotency_key="tx-success-commit-01",
        )
        assert report["status"] == OP_STATUS_COMPLETED
        assert report["dispatched_requests"] == 1
        assert report["successful_outputs"] == 1
        op_id = uuid.UUID(report["operation_id"])

        other = s2.get(FittingRoomModelCompareOperation, op_id)
        assert other is not None
        assert other.status == OP_STATUS_COMPLETED
        assert other.dispatched_requests == 1
        assert other.successful_outputs == 1
        key = (other.report or {}).get("arms", [{}])[0].get("storage_key")
        assert key
        path = LocalStorageBackend().resolve_private_fitting_compare_file(key=key)
        assert path is not None and path.is_file()
    finally:
        cmp.set_model_compare_runners_for_tests(openai_runner=None, fashn_runner=None)
        s1.close()
        s2.close()
        get_settings.cache_clear()


def test_idempotency_rejects_different_fingerprints(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    s = SessionFactory()
    try:
        user = s.get(User, owner_user["id"])
        op, _ = cmp._claim_paid_operation(
            s,
            user=user,
            idempotency_key="tx-identity-mismatch",
            consent_version=CONSENT,
            arms=["A"],
            person_fp="1111111111111111",
            design_fp="2222222222222222",
        )
        assert op is not None
        with pytest.raises(Exception) as ei:
            cmp._claim_paid_operation(
                s,
                user=user,
                idempotency_key="tx-identity-mismatch",
                consent_version=CONSENT,
                arms=["A"],
                person_fp="3333333333333333",
                design_fp="2222222222222222",
            )
        assert ei.value.status_code == 409
    finally:
        s.close()
        get_settings.cache_clear()


def test_retention_sweep_deletes_expired_files(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    monkeypatch.setenv("FITTING_ROOM_MODEL_COMPARE_RETENTION_HOURS", "72")
    get_settings.cache_clear()

    s = SessionFactory()
    try:
        user = s.get(User, owner_user["id"])
        op_id = uuid.uuid4()
        storage = LocalStorageBackend()
        key = storage.fitting_compare_storage_key(
            owner_id=user.id, operation_id=op_id, arm="A"
        )
        storage.save_private_fitting_compare_file(
            key=key, data=io.BytesIO(_png()), content_type="image/png"
        )
        assert storage.resolve_private_fitting_compare_file(key=key) is not None

        op = FittingRoomModelCompareOperation(
            id=op_id,
            owner_id=user.id,
            idempotency_key="tx-retention-sweep-01",
            status=OP_STATUS_COMPLETED,
            consent_version=CONSENT,
            arms_requested=["A"],
            dispatched_requests=1,
            successful_outputs=1,
            max_provider_calls=3,
            person_fingerprint="abc",
            design_fingerprint="def",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            report={
                "arms": [{"arm": "A", "status": "ok", "storage_key": key}],
                "arm_ledger": {"A": {"status": "ok", "storage_key": key}},
            },
        )
        s.add(op)
        s.commit()

        result = cmp.run_model_compare_retention_sweep(s, dry_run=False, commit=True)
        assert result["files_removed"] >= 1
        assert storage.resolve_private_fitting_compare_file(key=key) is None
    finally:
        s.close()
        get_settings.cache_clear()


def test_rollback_before_commit_does_not_consume_budget(
    SessionFactory, owner_user, monkeypatch, tmp_path
):
    """If the claim transaction rolls back before commit, budget stays free."""
    _arm_compare(monkeypatch, tmp_path, owner_user["username"])
    s1 = SessionFactory()
    s2 = SessionFactory()
    try:
        user = s1.get(User, owner_user["id"])
        from sqlalchemy import text

        s1.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": MODEL_COMPARE_GLOBAL_LOCK_KEY},
        )
        op = FittingRoomModelCompareOperation(
            id=uuid.uuid4(),
            owner_id=user.id,
            idempotency_key="tx-rollback-no-consume",
            status=OP_STATUS_RUNNING,
            consent_version=CONSENT,
            arms_requested=["A"],
            dispatched_requests=0,
            successful_outputs=0,
            max_provider_calls=3,
            person_fingerprint="aaaaaaaaaaaaaaaa",
            design_fingerprint="bbbbbbbbbbbbbbbb",
        )
        s1.add(op)
        s1.flush()
        # Abort without commit.
        s1.rollback()

        assert s2.query(FittingRoomModelCompareOperation).count() == 0
        # Fresh claim must succeed.
        user2 = s2.get(User, owner_user["id"])
        claimed, replay = cmp._claim_paid_operation(
            s2,
            user=user2,
            idempotency_key="tx-rollback-no-consume",
            consent_version=CONSENT,
            arms=["A"],
            person_fp="aaaaaaaaaaaaaaaa",
            design_fp="bbbbbbbbbbbbbbbb",
        )
        assert replay is False
        assert claimed.status == OP_STATUS_RUNNING
    finally:
        s1.close()
        s2.close()
        get_settings.cache_clear()
