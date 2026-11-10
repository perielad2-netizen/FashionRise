"""AI Stars wallet — starting balance, Magic debit, owner unlimited."""

from __future__ import annotations

import base64
import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.errors import ForbiddenError
from app.models.ai_job import AIJob
from app.models.user import User
from app.schemas.ai import AIJobCreate
from app.services import ai_stars, ai_service
from app.services.ai_worker import run_magic_worker_tick
from tests.auth_test_helpers import register_with_invite

_TINY_PNG = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z2hQAAAAASUVORK5CYII="
    )
).decode("ascii")
_DATA_URL = f"data:image/png;base64,{_TINY_PNG}"


@pytest.fixture()
def stars_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_STARS_STARTING_BALANCE", "10")
    monkeypatch.setenv("AI_STARS_MAGIC_COST", "10")
    monkeypatch.setenv(
        "AI_STARS_UNLIMITED_EMAILS",
        "perielad@gmail.com,perielad2@gmail.com",
    )
    # Default release polish: force finite wallet for purchase testing.
    monkeypatch.setenv("AI_STARS_FINITE_OVERRIDE_EMAILS", "perielad2@gmail.com")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_new_user_starts_with_ten_stars(client, db_session, stars_env):
    tokens = register_with_invite(
        client, db_session, email="newbie@example.com", username="newbie_stars"
    )
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["ai_stars"] == 10
    assert body["ai_stars_unlimited"] is False


def test_owner_emails_unlimited(client, db_session, stars_env):
    tokens = register_with_invite(
        client, db_session, email="perielad@gmail.com", username="peri_owner"
    )
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["ai_stars_unlimited"] is True


def test_debit_magic_once_then_block(db_session, stars_env):
    user = User(
        email="spender@example.com",
        username="spender",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    remaining = ai_stars.debit_magic_stars(db_session, user)
    db_session.commit()
    assert remaining == 0

    with pytest.raises(ForbiddenError, match="Not enough Stars"):
        ai_stars.debit_magic_stars(db_session, user)


def test_unlimited_never_debits(db_session, stars_env):
    user = User(
        email="perielad@gmail.com",
        username="peri_owner_debit",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    before = user.ai_stars
    remaining = ai_stars.debit_magic_stars(db_session, user)
    db_session.commit()
    assert remaining == before
    assert ai_stars.user_has_unlimited_stars(user) is True


def test_finite_override_disables_unlimited_for_purchase_tester(db_session, stars_env, client):
    """perielad2 stays on a real wallet while other owners keep unlimited; admin untouched."""
    from sqlalchemy import select

    tokens = register_with_invite(
        client, db_session, email="perielad2@gmail.com", username="peri2_finite"
    )
    user = db_session.scalar(select(User).where(User.email == "perielad2@gmail.com"))
    assert user is not None
    user.ai_stars_unlimited = True  # stale DB flag must not win over finite override
    user.is_admin = True
    user.ai_stars = 40
    db_session.commit()
    db_session.refresh(user)

    assert user.is_admin is True
    assert ai_stars.user_has_unlimited_stars(user) is False
    assert ai_stars.public_balance(user)["ai_stars_unlimited"] is False
    assert ai_stars.public_balance(user)["ai_stars"] == 40

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["ai_stars_unlimited"] is False
    assert body["ai_stars"] == 40
    assert body["is_admin"] is True

    remaining = ai_stars.debit_stars(db_session, user, "magic")
    db_session.commit()
    assert remaining == 30
    db_session.refresh(user)
    assert user.ai_stars == 30
    assert user.is_admin is True

    credited = ai_stars.credit_stars(db_session, user, 50, reason="iap_test")
    db_session.commit()
    assert credited == 80
    db_session.refresh(user)
    assert user.ai_stars == 80

    other = User(
        email="perielad@gmail.com",
        username="peri_still_unlimited",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(other)
    db_session.add(other)
    db_session.commit()
    assert ai_stars.user_has_unlimited_stars(other) is True


def test_clearing_finite_override_restores_unlimited(db_session, stars_env, monkeypatch):
    user = User(
        email="perielad2@gmail.com",
        username="peri2_restore",
        hashed_password="x",
        is_admin=True,
        is_active=True,
        ai_stars_unlimited=True,
        ai_stars=100,
    )
    db_session.add(user)
    db_session.commit()
    assert ai_stars.user_has_unlimited_stars(user) is False

    monkeypatch.setenv("AI_STARS_FINITE_OVERRIDE_EMAILS", "")
    get_settings.cache_clear()
    assert ai_stars.user_has_unlimited_stars(user) is True
    assert user.is_admin is True


def test_magic_failure_does_not_reduce_stars(db_session, stars_env, monkeypatch):
    """Failed Magic must not charge Stars — only successful completion debits."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stars-fail")
    get_settings.cache_clear()

    user = User(
        email="magic_fail@example.com",
        username="magic_fail",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.ai_stars == 10

    job = ai_service.enqueue_job(
        db_session,
        user,
        AIJobCreate(
            job_type="sketch_polish",
            input_data={
                "image_base64": _DATA_URL,
                "magic_operation_id": str(uuid.uuid4()),
                "reference_model_id": "female",
            },
        ),
    )
    db_session.refresh(user)
    assert user.ai_stars == 10
    assert job.status == "queued"

    with patch(
        "app.services.sketch_openai.complete_sketch_job",
        side_effect=RuntimeError("provider exploded"),
    ):
        run_magic_worker_tick(db_session, limit=2)

    db_session.refresh(job)
    db_session.refresh(user)
    assert job.status == "failed"
    assert user.ai_stars == 10


def test_magic_success_debits_stars_once(db_session, stars_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stars-ok")
    get_settings.cache_clear()

    user = User(
        email="magic_ok@example.com",
        username="magic_ok",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    op = str(uuid.uuid4())
    job = ai_service.enqueue_job(
        db_session,
        user,
        AIJobCreate(
            job_type="sketch_polish",
            input_data={
                "image_base64": _DATA_URL,
                "magic_operation_id": op,
                "reference_model_id": "female",
            },
        ),
    )
    db_session.refresh(user)
    assert user.ai_stars == 10

    with patch(
        "app.services.sketch_openai.complete_sketch_job",
        return_value={"summary": "look ready", "image_base64": _DATA_URL},
    ):
        run_magic_worker_tick(db_session, limit=2)

    db_session.refresh(job)
    db_session.refresh(user)
    assert job.status == "completed"
    assert user.ai_stars == 0
    assert (job.result_data or {}).get("stars_debited") is True

    # Manual second debit attempt for same completed job is a no-op.
    ai_service.debit_magic_stars_on_success(db_session, job)
    db_session.commit()
    db_session.refresh(user)
    assert user.ai_stars == 0


def test_dual_magic_waits_for_both_sides_before_debit(db_session, stars_env, monkeypatch):
    """Front-only success must not bill; Stars drop once Front+Back both complete."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-stars-dual")
    get_settings.cache_clear()

    user = User(
        email="magic_dual@example.com",
        username="magic_dual",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    op = str(uuid.uuid4())
    front = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="sketch_polish",
        status="queued",
        input_data={
            "image_base64": _DATA_URL,
            "magic_operation_id": op,
            "studio_side": "front",
            "linked_dual_attempt": True,
            "reference_model_id": "female",
        },
    )
    back = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="sketch_polish",
        status="queued",
        input_data={
            "image_base64": _DATA_URL,
            "magic_operation_id": op,
            "studio_side": "back",
            "linked_dual_attempt": True,
            "reference_model_id": "female",
        },
    )
    db_session.add_all([front, back])
    db_session.commit()

    with patch(
        "app.services.sketch_openai.complete_sketch_job",
        return_value={"summary": "look ready", "image_base64": _DATA_URL},
    ):
        # Process only the front job first.
        front.status = "completed"
        front.result_data = {"summary": "front ready"}
        db_session.commit()
        ai_service.debit_magic_stars_on_success(db_session, front)
        db_session.commit()
        db_session.refresh(user)
        assert user.ai_stars == 10

        back.status = "completed"
        back.result_data = {"summary": "back ready"}
        db_session.commit()
        ai_service.debit_magic_stars_on_success(db_session, back)
        db_session.commit()

    db_session.refresh(user)
    db_session.refresh(front)
    db_session.refresh(back)
    assert user.ai_stars == 0
    assert (front.result_data or {}).get("stars_debited") is True
    assert (back.result_data or {}).get("stars_debited") is True


def test_try_on_success_debits_magic_stars_once(db_session, stars_env):
    """Final Try On / FASHN look success bills Magic Stars; realism must not."""
    user = User(
        email="tryon_stars@example.com",
        username="tryon_stars",
        hashed_password="x",
        is_admin=False,
        is_active=True,
    )
    ai_stars.apply_new_user_stars(user)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    smart_op = str(uuid.uuid4())
    realism = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_garment_realism",
        status="completed",
        input_data={"mode": "garment_realism"},
        result_data={"summary": "plate ready"},
    )
    try_on = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_try_on",
        status="completed",
        input_data={
            "provider": "fashn",
            "mode": "try_on_person",
            "smart_pipeline": {
                "smart_operation_id": smart_op,
                "path": "openai->fashn_max",
                "user_visible_charge_units": 1,
            },
        },
        result_data={"summary": "try-on ready", "image_base64": _DATA_URL},
    )
    db_session.add_all([realism, try_on])
    db_session.commit()

    ai_service.debit_magic_stars_on_success(db_session, realism)
    db_session.commit()
    db_session.refresh(user)
    assert user.ai_stars == 10
    assert (realism.result_data or {}).get("stars_debited") is not True

    ai_service.debit_magic_stars_on_success(db_session, try_on)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(try_on)
    assert user.ai_stars == 0
    assert (try_on.result_data or {}).get("stars_debited") is True

    # Max sibling under the same smart op must not bill again.
    max_job = AIJob(
        id=uuid.uuid4(),
        user_id=user.id,
        job_type="personal_try_on",
        status="completed",
        input_data={
            "provider": "fashn_max",
            "smart_pipeline": {"smart_operation_id": smart_op, "path": "openai->fashn_max"},
        },
        result_data={"summary": "max ready"},
    )
    db_session.add(max_job)
    db_session.commit()
    # Restore balance to prove second debit is skipped even if Stars remain.
    user.ai_stars = 10
    db_session.commit()
    ai_service.debit_magic_stars_on_success(db_session, max_job)
    db_session.commit()
    db_session.refresh(user)
    assert user.ai_stars == 10
