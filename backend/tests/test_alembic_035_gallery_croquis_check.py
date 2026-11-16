"""Alembic-path regression for 035 croquis gallery check (not create_all)."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote, urlparse

import pytest
from sqlalchemy import create_engine, text

from app.core.test_db_guard import assert_safe_test_database_url, database_name_from_url


BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC = str(BACKEND / ".venv/bin/alembic")
# Dedicated disposable DB — never fashionrise_beta / production.
DISP_DB = "fashionrise_disp_035_qa"


def _tcp_url_for_db(db_name: str) -> str:
    """Build a TCP URL from ambient DATABASE_URL credentials (local only)."""
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        pytest.skip("DATABASE_URL required to derive local disposable credentials")
    parsed = urlparse(raw.replace("postgresql+psycopg2", "postgresql"))
    if (parsed.hostname or "").lower() not in {"localhost", "127.0.0.1"}:
        pytest.skip("Refusing Alembic path test against non-localhost DATABASE_URL host")
    user = parsed.username or "postgres"
    password = parsed.password or ""
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    enc = quote(password, safe="")
    return f"postgresql+psycopg2://{user}:{enc}@{host}:{port}/{db_name}"


@pytest.fixture(scope="module")
def alembic_url() -> str:
    # Ambient DATABASE_URL may be polluted by prior manual alembic runs; prefer
    # an explicit non-disposable snapshot for the equality guard.
    app_snapshot = (
        os.environ.get("DATABASE_URL_APP_SNAPSHOT")
        or os.environ.get("DATABASE_URL_TEST")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()
    # Credentials come from a localhost URL (app snapshot or DATABASE_URL).
    cred_src = app_snapshot or (os.environ.get("DATABASE_URL") or "")
    if not cred_src:
        pytest.skip("Need localhost DATABASE_URL / DATABASE_URL_TEST for credentials")
    # Temporarily use cred_src as DATABASE_URL for _tcp_url_for_db parsing.
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = cred_src
    try:
        url = _tcp_url_for_db(DISP_DB)
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev
    # Guard against mistaking the disposable target for the app/test harness DB.
    assert_safe_test_database_url(url, app_database_url=app_snapshot or prev)
    assert database_name_from_url(url) == DISP_DB
    assert database_name_from_url(app_snapshot or prev or "") != DISP_DB
    return url


def _alembic_env(url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": url,
            "ALEMBIC_SMOKE_BOUND_URL": url,
            "DATABASE_URL_APP_SNAPSHOT": os.environ.get("DATABASE_URL", ""),
            "ENVIRONMENT": "staging",
            "TESTING": "true",
            "SECRET_KEY": "disp-035-alembic-secret-key-32chars!!",
            "AI_WORKER_ENABLED": "false",
            "OPENAI_API_KEY": "",
            "FASHN_API_KEY": "",
            "FASHIONRISE_WEEKLY_REWARDS_ENABLED": "false",
            "FASHIONRISE_STREAK_REWARDS_ENABLED": "false",
            "FASHIONRISE_WEEKLY_REWARDS_LAUNCH_WEEK_START": "",
            "FASHIONRISE_STREAK_REWARDS_START_DATE": "",
            "LOCAL_STORAGE_ROOT": "/tmp/fr035-alembic-storage",
            "CORS_ORIGINS": "http://127.0.0.1:5177",
            "PUBLIC_APP_URL": "http://127.0.0.1:5177",
        }
    )
    Path(env["LOCAL_STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
    return env


def _run_alembic(url: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [ALEMBIC, *args],
        cwd=str(BACKEND),
        env=_alembic_env(url),
        check=check,
        text=True,
        capture_output=True,
    )


def _reset_db(url: str) -> None:
    """Drop/recreate disposable DB via postgres maintenance connection."""
    admin = _tcp_url_for_db("postgres")
    eng = create_engine(admin, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :d AND pid <> pg_backend_pid()"
            ),
            {"d": DISP_DB},
        )
        c.execute(text(f'DROP DATABASE IF EXISTS "{DISP_DB}"'))
        c.execute(text(f'CREATE DATABASE "{DISP_DB}" TEMPLATE template0'))
    eng.dispose()


def _version(url: str) -> str:
    eng = create_engine(url)
    with eng.connect() as c:
        return str(c.execute(text("select version_num from alembic_version")).scalar())


def _constraint_def(url: str) -> str | None:
    eng = create_engine(url)
    with eng.connect() as c:
        rows = c.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'gallery_items'::regclass
                  AND contype = 'c'
                ORDER BY 1
                """
            )
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def _seed_user_and_croquis(url: str) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    croquis_id = str(uuid.uuid4())
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(
            text(
                """
                INSERT INTO users (
                  id, email, username, hashed_password, is_active, is_admin
                ) VALUES (
                  :id, :email, :username, 'x', true, false
                )
                """
            ),
            {
                "id": user_id,
                "email": f"u{user_id[:8]}@disp035.qa",
                "username": f"u{user_id[:8]}",
            },
        )
        c.execute(
            text(
                """
                INSERT INTO personal_croquis (
                  id, owner_id, display_name, status, created_at, updated_at
                ) VALUES (
                  :id, :owner, 'Disp Model', 'uploaded', now(), now()
                )
                """
            ),
            {"id": croquis_id, "owner": user_id},
        )
    return user_id, croquis_id


def test_alembic_035_upgrade_inserts_and_non_destructive_downgrade(alembic_url: str):
    _reset_db(alembic_url)

    # 034 baseline (real Alembic path, not create_all).
    up034 = _run_alembic(alembic_url, "upgrade", "034")
    assert up034.returncode == 0, up034.stderr + up034.stdout
    assert _version(alembic_url) == "034"
    cons034 = _constraint_def(alembic_url)
    assert "ck_gallery_items_design_or_look" in cons034
    assert "croquis_id" not in cons034["ck_gallery_items_design_or_look"]

    # Upgrade preserves design/look check replacement.
    up035 = _run_alembic(alembic_url, "upgrade", "035")
    assert up035.returncode == 0, up035.stderr + up035.stdout
    assert _version(alembic_url) == "035"
    cons035 = _constraint_def(alembic_url)
    assert "ck_gallery_items_design_look_or_croquis" in cons035
    assert "croquis_id" in cons035["ck_gallery_items_design_look_or_croquis"]
    assert "ck_gallery_items_design_or_look" not in cons035

    user_id, croquis_id = _seed_user_and_croquis(alembic_url)
    look_id = str(uuid.uuid4())
    croquis_gallery_id = str(uuid.uuid4())
    look_gallery_id = str(uuid.uuid4())

    eng = create_engine(alembic_url)
    with eng.begin() as c:
        # Croquis-only (My Models) — must succeed at 035.
        c.execute(
            text(
                """
                INSERT INTO gallery_items (
                  id, user_id, title, image_url, visibility, moderation_status,
                  croquis_id, created_at, updated_at
                ) VALUES (
                  :id, :user_id, 'My Model', 'http://127.0.0.1/m.png', 'public', 'ok',
                  :croquis_id, now(), now()
                )
                """
            ),
            {
                "id": croquis_gallery_id,
                "user_id": user_id,
                "croquis_id": croquis_id,
            },
        )
        # Classic look-only row remains valid.
        c.execute(
            text(
                """
                INSERT INTO gallery_items (
                  id, user_id, title, image_url, visibility, moderation_status,
                  look_id, created_at, updated_at
                ) VALUES (
                  :id, :user_id, 'Look', 'http://127.0.0.1/l.png', 'public', 'ok',
                  :look_id, now(), now()
                )
                """
            ),
            {"id": look_gallery_id, "user_id": user_id, "look_id": look_id},
        )
        # Engagement that must survive a refused downgrade.
        c.execute(
            text(
                """
                INSERT INTO gallery_likes (id, user_id, gallery_item_id, created_at)
                VALUES (:id, :user_id, :gid, now())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "gid": croquis_gallery_id,
            },
        )

    # Downgrade must refuse while croquis-only rows exist.
    down = _run_alembic(alembic_url, "downgrade", "034", check=False)
    assert down.returncode != 0, down.stdout + down.stderr
    combined = (down.stdout or "") + (down.stderr or "")
    assert "Refusing Alembic downgrade 035 → 034" in combined
    assert "croquis_id" in combined

    # Schema + content preserved at 035.
    assert _version(alembic_url) == "035"
    with eng.connect() as c:
        n_gallery = c.execute(text("select count(*) from gallery_items")).scalar()
        n_likes = c.execute(text("select count(*) from gallery_likes")).scalar()
        croquis_row = c.execute(
            text(
                "select count(*) from gallery_items "
                "where id = :id and croquis_id is not null and design_id is null and look_id is null"
            ),
            {"id": croquis_gallery_id},
        ).scalar()
        look_row = c.execute(
            text(
                "select count(*) from gallery_items "
                "where id = :id and look_id is not null"
            ),
            {"id": look_gallery_id},
        ).scalar()
    assert int(n_gallery or 0) == 2
    assert int(n_likes or 0) == 1
    assert int(croquis_row or 0) == 1
    assert int(look_row or 0) == 1
    cons_still = _constraint_def(alembic_url)
    assert "ck_gallery_items_design_look_or_croquis" in cons_still

    # Remove incompatible rows (authorized test cleanup only) → downgrade OK.
    with eng.begin() as c:
        c.execute(text("DELETE FROM gallery_likes WHERE gallery_item_id = :id"), {"id": croquis_gallery_id})
        c.execute(text("DELETE FROM gallery_items WHERE id = :id"), {"id": croquis_gallery_id})

    down_ok = _run_alembic(alembic_url, "downgrade", "034")
    assert down_ok.returncode == 0, down_ok.stderr + down_ok.stdout
    assert _version(alembic_url) == "034"
    cons_back = _constraint_def(alembic_url)
    assert "ck_gallery_items_design_or_look" in cons_back
    assert "ck_gallery_items_design_look_or_croquis" not in cons_back
    with eng.connect() as c:
        remaining = c.execute(
            text("select count(*) from gallery_items where id = :id"),
            {"id": look_gallery_id},
        ).scalar()
    assert int(remaining or 0) == 1
    eng.dispose()
