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
        email="perielad2@gmail.com",
        username="peri2",
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
    assert user.ai_stars_unlimited is True


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
